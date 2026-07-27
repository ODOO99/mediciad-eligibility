"""Celery tasks for import row processing."""
import logging
import time
from datetime import datetime
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from config.celery import app
from .models import ImportBatch, ImportRow

logger = logging.getLogger(__name__)

RETRY_STATUSES = {
    'NETWORK_TIMEOUT', 'CONNECTION_ERROR', 'HTTP_5XX', 'TEMP_OUTAGE', 'PARSER_FAILURE', 'HTTP_ERROR'
}


@app.task(bind=True, max_retries=0, name='imports.tasks.process_import_batch')
def process_import_batch(self, batch_id):
    """Coordinator task — dispatches individual row tasks."""
    try:
        batch = ImportBatch.objects.get(pk=batch_id)
    except ImportBatch.DoesNotExist:
        logger.error(f"Batch {batch_id} not found")
        return

    if batch.status not in ('PENDING', 'PROCESSING', 'VALIDATING'):
        logger.info(f"Batch {batch_id} already in status {batch.status}")
        return

    batch.status = 'PROCESSING'
    batch.started_at = timezone.now()
    batch.save(update_fields=['status', 'started_at', 'updated_at'])

    pending_rows = ImportRow.objects.filter(
        import_batch=batch, status='PENDING'
    ).values_list('id', flat=True)

    # Dispatch row tasks with controlled concurrency via Celery
    for row_id in pending_rows:
        process_import_row.delay(row_id)

    # Schedule a watcher to mark batch complete when all rows done
    watch_batch_completion.apply_async(
        args=[batch_id], countdown=10
    )


@app.task(bind=True, name='imports.tasks.watch_batch_completion')
def watch_batch_completion(self, batch_id):
    """Periodically checks if all rows are done and marks batch complete."""
    try:
        batch = ImportBatch.objects.get(pk=batch_id)
    except ImportBatch.DoesNotExist:
        return

    if batch.status in ('COMPLETED', 'PARTIALLY_COMPLETED', 'FAILED', 'CANCELLED'):
        return

    # Count rows still in non-terminal states
    active_statuses = [
        'PENDING', 'PROCESSING', 'REQUEST_GENERATED', 'REQUEST_SENT',
        'WAITING_FOR_RESPONSE', 'RESPONSE_RECEIVED', 'PARSING_RESPONSE',
        'UPDATING_PATIENT', 'SAVING_ELIGIBILITY', 'RETRY_PENDING',
    ]
    active_count = ImportRow.objects.filter(
        import_batch=batch, status__in=active_statuses
    ).count()

    if active_count > 0:
        # Still running — check again in 5 seconds
        watch_batch_completion.apply_async(args=[batch_id], countdown=5)
        return

    # All done — refresh counters and set final status
    batch.refresh_counters()
    batch.refresh_from_db()

    batch.completed_at = timezone.now()
    if batch.failed_rows > 0 or batch.rejected_rows > 0:
        batch.status = 'PARTIALLY_COMPLETED'
    else:
        batch.status = 'COMPLETED'
    batch.save(update_fields=['status', 'completed_at', 'updated_at'])
    logger.info(f"Batch {batch_id} completed with status {batch.status}")


@app.task(bind=True, name='imports.tasks.process_import_row',
          max_retries=settings.MAX_RETRY_COUNT if hasattr(settings, 'MAX_RETRY_COUNT') else 3,
          rate_limit='1/s',
          acks_late=True)
def process_import_row(self, row_id):
    """Process a single ImportRow: build 270, submit to eMedNY, parse 271, update patient."""
    from emedny.client import get_emedny_client
    from emedny.builder import EligibilityRequestBuilder
    from emedny.parser import EligibilityResponseParser
    from emedny.classifier import EligibilityClassifier
    from eligibility.models import (
        EligibilityRequest, EligibilityResponse,
        PatientEligibilitySnapshot, EligibilityIndicator,
        EligibilityFinancialDetail, EligibilityBenefit, ResponseRejection
    )
    from patients.models import Patient, PatientChangeHistory, PatientDataConflict

    # --- Lock and verify row ---
    try:
        with transaction.atomic():
            row = ImportRow.objects.select_for_update(nowait=True).get(pk=row_id)
            if row.status not in ('PENDING', 'RETRY_PENDING'):
                logger.info(f"Row {row_id} already in status {row.status}, skipping")
                return
            row.status = 'PROCESSING'
            row.started_at = timezone.now()
            row.processing_stage = 'READING_CSV_ROW'
            row.save(update_fields=['status', 'started_at', 'processing_stage', 'updated_at'])
    except Exception as exc:
        logger.warning(f"Could not lock row {row_id}: {exc}")
        return

    batch = row.import_batch

    try:
        _process_row_inner(row, batch)
    except Exception as exc:
        logger.exception(f"Unexpected error processing row {row_id}: {exc}")
        row.refresh_from_db()

        # Determine if it's a retryable error
        error_str = str(exc)
        is_retryable = any(status in error_str for status in RETRY_STATUSES) or 'Timeout' in error_str or 'Connection' in error_str

        if is_retryable:
            row.status = 'RETRY_PENDING'
            row.processing_error = f"Retrying: {error_str}"
            row.save(update_fields=['status', 'processing_error', 'updated_at'])
            batch.refresh_counters()
            try:
                # self.retry() raises celery.exceptions.Retry on success —
                # we must return immediately so we don't fall through to TECHNICAL_FAILURE.
                raise self.retry(exc=exc, countdown=10 * (self.request.retries + 1))
            except self.MaxRetriesExceededError:
                # Max retries exceeded — fall through to permanent failure below.
                pass
            else:
                # retry was raised (i.e. re-raised above), so we never reach here.
                return

        # Permanent failure (non-retryable or max retries exceeded)
        row.status = 'TECHNICAL_FAILURE'
        row.processing_error = str(exc)
        row.completed_at = timezone.now()
        row.save(update_fields=['status', 'processing_error', 'completed_at', 'updated_at'])
        batch.refresh_counters()


def _process_row_inner(row, batch):
    """Inner processing logic — separated for clarity."""
    from emedny.client import get_emedny_client
    from emedny.builder import EligibilityRequestBuilder
    from emedny.parser import EligibilityResponseParser
    from emedny.classifier import EligibilityClassifier
    from eligibility.models import (
        EligibilityRequest, EligibilityResponse,
        PatientEligibilitySnapshot, EligibilityIndicator,
        EligibilityFinancialDetail, EligibilityBenefit, ResponseRejection
    )
    from patients.models import Patient, PatientChangeHistory, PatientDataConflict
    import hashlib

    logger.info(f"Processing row {row.row_number} CIN={row.cin}")

    # Step 1: Generate 270
    row.set_stage('GENERATING_270', 'REQUEST_GENERATED')
    builder = EligibilityRequestBuilder()
    request_data = builder.build(
        cin=row.cin,
        date_of_service=batch.date_of_service,
    )

    # Step 2: Save 270
    row.set_stage('SAVING_270')
    raw_270 = request_data['x12_payload']
    req_hash = hashlib.sha256(raw_270.encode()).hexdigest()

    elig_request = EligibilityRequest.objects.create(
        import_row=row,
        cin=row.cin,
        date_of_service=batch.date_of_service,
        service_type_code=request_data.get('service_type_code', '30'),
        isa_control_number=request_data.get('isa_control_number', ''),
        gs_control_number=request_data.get('gs_control_number', ''),
        st_control_number=request_data.get('st_control_number', ''),
        payload_id=request_data.get('payload_id', ''),
        raw_270=raw_270,
        request_hash=req_hash,
        content_length=len(raw_270),
        request_status='PENDING',
    )

    # Step 3: Submit to eMedNY
    row.set_stage('SENDING_TO_EMEDNY', 'REQUEST_SENT')
    client = get_emedny_client()
    row.set_stage('WAITING_FOR_EMEDNY', 'WAITING_FOR_RESPONSE')

    response_data = client.submit(request_data)

    # Step 4: Store raw response
    row.set_stage('RECEIVING_271', 'RESPONSE_RECEIVED')
    raw_response = response_data.get('raw_response', '')
    x12_response = response_data.get('x12_response', '')

    row.set_stage('SAVING_RAW_RESPONSE')
    resp_hash = hashlib.sha256(x12_response.encode()).hexdigest()

    elig_request.request_status = 'SUBMITTED'
    elig_request.submitted_at = timezone.now()
    elig_request.save(update_fields=['request_status', 'submitted_at', 'updated_at'])

    # Step 5: Parse response
    row.set_stage('PARSING_271', 'PARSING_RESPONSE')
    parser = EligibilityResponseParser()
    parsed = parser.parse(x12_response)

    # Determine response type and status
    response_type = response_data.get('response_type', 'X12_271')
    response_status = _derive_response_status(parsed, response_data)
    member_found = parsed.get('member_found', False)

    now = timezone.now()

    # Step 6: Handle business rejections
    if response_status in ('REJECTED', 'MEMBER_NOT_FOUND', 'TECHNICAL_FAILURE') and not member_found:
        if response_status == 'TECHNICAL_FAILURE' and response_data.get('error_type') in RETRY_STATUSES:
            raise Exception(f"Retryable {response_data.get('error_type')}: {response_data.get('error')}")
            
        _save_rejection_response(
            row, elig_request, parsed, response_data,
            response_type, response_status, x12_response, resp_hash, now
        )
        batch.refresh_counters()
        return

    # Step 7: Extract patient info
    row.set_stage('EXTRACTING_PATIENT', 'UPDATING_PATIENT')
    demographics = parsed.get('demographics', {})

    # Step 8: Create or update patient
    patient, patient_action, elig_response = _create_or_update_patient(
        row, elig_request, demographics, parsed, response_data,
        response_type, response_status, x12_response, resp_hash, now
    )

    # Step 9: Classify indicators
    classifier = EligibilityClassifier()

    row.set_stage('EXTRACTING_RECERTIFICATION')
    row.set_stage('EXTRACTING_CODE_60')

    classification = classifier.classify(parsed)

    # Step 10: Save eligibility data in one atomic transaction
    row.set_stage('SAVING_ELIGIBILITY', 'SAVING_ELIGIBILITY')

    with transaction.atomic():
        # Update patient link on request
        elig_request.patient = patient
        elig_request.save(update_fields=['patient', 'updated_at'])

        # Mark previous current snapshot as not current
        PatientEligibilitySnapshot.objects.filter(
            patient=patient, is_current=True
        ).update(is_current=False)

        snap = PatientEligibilitySnapshot.objects.create(
            patient=patient,
            eligibility_response=elig_response,
            date_of_service=batch.date_of_service,
            is_medicaid_eligible=response_status in ('ELIGIBLE', 'SUCCESS'),
            has_recertification=classification.get('has_recertification', False),
            recertification_date=classification.get('recertification_date'),
            has_code_60=classification.get('has_code_60', False),
            has_s1=classification.get('has_s1', False),
            effective_from=parsed.get('coverage_start_date'),
            effective_to=parsed.get('coverage_end_date'),
            is_current=True,
        )

        # Save indicators
        for indicator in classification.get('indicators', []):
            EligibilityIndicator.objects.create(
                eligibility_response=elig_response,
                patient=patient,
                **indicator,
            )

        # Save financial details
        for fin in parsed.get('financial_details', []):
            EligibilityFinancialDetail.objects.create(
                eligibility_response=elig_response,
                patient=patient,
                **fin,
            )

        # Save benefit records
        for benefit in parsed.get('benefits', []):
            EligibilityBenefit.objects.create(
                eligibility_response=elig_response,
                **benefit,
            )

        # Mark row complete
        row.status = 'COMPLETED'
        row.patient = patient
        row.patient_action = patient_action
        row.processing_stage = 'COMPLETED'
        row.completed_at = timezone.now()
        row.save(update_fields=['status', 'patient', 'patient_action', 'processing_stage', 'completed_at', 'updated_at'])

    batch.refresh_counters()
    logger.info(f"Row {row.row_number} completed: {patient_action}")


def _derive_response_status(parsed, response_data):
    """Derive a canonical response status from parsed 271."""
    if response_data.get('error'):
        return 'TECHNICAL_FAILURE'
    if parsed.get('rejections'):
        return 'REJECTED'
    if not parsed.get('member_found', False):
        return 'MEMBER_NOT_FOUND'
    if parsed.get('is_active'):
        return 'ELIGIBLE'
    return 'INELIGIBLE'


def _save_rejection_response(row, elig_request, parsed, response_data,
                              response_type, response_status, x12_response, resp_hash, now):
    from eligibility.models import EligibilityResponse, ResponseRejection

    elig_response = EligibilityResponse.objects.create(
        eligibility_request=elig_request,
        response_type=response_type,
        response_status=response_status,
        member_found=False,
        raw_271=x12_response,
        response_hash=resp_hash,
        content_length=len(x12_response),
        received_at=now,
        parsed_at=timezone.now(),
    )

    for rej in parsed.get('rejections', []):
        ResponseRejection.objects.create(
            eligibility_response=elig_response,
            **rej,
        )

    if response_status == 'MEMBER_NOT_FOUND':
        row.status = 'REJECTED'
        row.rejection_description = 'Member not found in eMedNY.'
    elif response_status == 'REJECTED':
        row.status = 'REJECTED'
        rejs = parsed.get('rejections', [])
        row.rejection_description = '; '.join(r.get('description', '') for r in rejs)
    elif response_status == 'TECHNICAL_FAILURE':
        row.status = 'TECHNICAL_FAILURE'
        row.processing_error = response_data.get('error', 'Technical failure')

    row.patient_action = 'NOT_CREATED'
    row.processing_stage = 'COMPLETED'
    row.completed_at = timezone.now()
    row.save(update_fields=['status', 'rejection_description', 'processing_error', 'patient_action', 'processing_stage', 'completed_at', 'updated_at'])


def _create_or_update_patient(row, elig_request, demographics, parsed, response_data,
                               response_type, response_status, x12_response, resp_hash, now):
    from patients.models import Patient, PatientChangeHistory, PatientDataConflict
    from eligibility.models import EligibilityResponse

    cin = row.cin
    identity_fields = {'date_of_birth', 'first_name', 'last_name', 'gender'}
    updateable_fields = ['address_line_1', 'address_line_2', 'city', 'state', 'postal_code',
                         'first_name', 'middle_name', 'last_name', 'date_of_birth', 'gender']

    try:
        patient = Patient.objects.get(cin=cin)
        patient_action = 'UNCHANGED'
        is_new = False
    except Patient.DoesNotExist:
        patient = Patient(cin=cin)
        patient_action = 'CREATED'
        is_new = True

    elig_response = EligibilityResponse.objects.create(
        eligibility_request=elig_request,
        patient=patient if not is_new else None,
        response_type=response_type,
        response_status=response_status,
        eligibility_status=parsed.get('eligibility_status', ''),
        member_found=parsed.get('member_found', False),
        coverage_start_date=parsed.get('coverage_start_date'),
        coverage_end_date=parsed.get('coverage_end_date'),
        plan_name=parsed.get('plan_name', ''),
        plan_identifier=parsed.get('plan_identifier', ''),
        managed_care_name=parsed.get('managed_care_name', ''),
        raw_271=x12_response,
        response_hash=resp_hash,
        content_length=len(x12_response),
        received_at=now,
        parsed_at=timezone.now(),
    )

    if is_new:
        # Apply demographics from 271 — skip blank values
        for field in updateable_fields:
            value = demographics.get(field, '') or ''
            if value:
                setattr(patient, field, value)
        # Wrap patient creation + response FK update atomically so we never
        # end up with an EligibilityResponse that has patient=None permanently.
        with transaction.atomic():
            patient.save()
            # Now that the patient has a PK we can back-fill the FK on the response.
            elig_response.patient = patient
            elig_response.save(update_fields=['patient'])
            PatientChangeHistory.objects.create(
                patient=patient,
                eligibility_response=elig_response,
                field_name='patient',
                old_value='',
                new_value=f'Created from CIN {cin}',
                change_type='CREATED',
            )
    else:
        # Compare and update
        conflicts = []
        changed = False
        for field in updateable_fields:
            new_val = str(demographics.get(field, '') or '').strip()
            old_val = str(getattr(patient, field, '') or '').strip()

            if old_val == new_val:
                continue

            # Identity conflict check
            if field in identity_fields and old_val and new_val:
                PatientDataConflict.objects.create(
                    patient=patient,
                    eligibility_response=elig_response,
                    field_name=field,
                    existing_value=old_val,
                    returned_value=new_val,
                )
                PatientChangeHistory.objects.create(
                    patient=patient,
                    eligibility_response=elig_response,
                    field_name=field,
                    old_value=old_val,
                    new_value=new_val,
                    change_type='CONFLICT',
                )
                continue

            # Apply update
            setattr(patient, field, new_val)
            PatientChangeHistory.objects.create(
                patient=patient,
                eligibility_response=elig_response,
                field_name=field,
                old_value=old_val,
                new_value=new_val,
                change_type='UPDATED',
            )
            changed = True

        if changed:
            patient.save()
            patient_action = 'UPDATED'

    return patient, patient_action, elig_response

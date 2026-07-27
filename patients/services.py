"""Standalone eligibility lookup service (no batch/import row required)."""
import hashlib
import logging

from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


def run_eligibility_lookup(cin, date_of_service):
    """
    Run a single CIN eligibility check against eMedNY.
    Creates / updates Patient + PatientEligibilitySnapshot.
    Returns a result dict:
        {
          'patient': Patient | None,
          'snapshot': PatientEligibilitySnapshot | None,
          'parsed': dict,
          'classification': dict,
          'response_status': str,
          'error': str | None,
        }
    """
    from emedny.builder import EligibilityRequestBuilder
    from emedny.client import get_emedny_client
    from emedny.parser import EligibilityResponseParser
    from emedny.classifier import EligibilityClassifier
    from eligibility.models import (
        EligibilityRequest, EligibilityResponse,
        PatientEligibilitySnapshot, EligibilityIndicator,
        EligibilityFinancialDetail, EligibilityBenefit, ResponseRejection,
    )
    from patients.models import Patient, PatientChangeHistory, PatientDataConflict

    result = {
        'patient': None,
        'snapshot': None,
        'parsed': {},
        'classification': {},
        'response_status': 'UNKNOWN',
        'error': None,
    }

    # --- Build 270 ---
    builder = EligibilityRequestBuilder()
    try:
        request_data = builder.build(cin=cin, date_of_service=date_of_service)
    except Exception as exc:
        result['error'] = f'Failed to build 270 request: {exc}'
        return result

    raw_270 = request_data['x12_payload']
    req_hash = hashlib.sha256(raw_270.encode()).hexdigest()

    elig_request = EligibilityRequest.objects.create(
        import_row=None,
        cin=cin,
        date_of_service=date_of_service,
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

    # --- Submit to eMedNY ---
    client = get_emedny_client()
    try:
        response_data = client.submit(request_data)
    except Exception as exc:
        result['error'] = f'eMedNY request failed: {exc}'
        return result

    if response_data.get('error'):
        result['error'] = response_data['error']
        return result

    elig_request.request_status = 'SUBMITTED'
    elig_request.submitted_at = timezone.now()
    elig_request.save(update_fields=['request_status', 'submitted_at', 'updated_at'])

    x12_response = response_data.get('x12_response', '')
    raw_response = response_data.get('raw_response', '')
    response_type = response_data.get('response_type', 'X12_271')
    resp_hash = hashlib.sha256(x12_response.encode()).hexdigest()
    now = timezone.now()

    # --- Parse 271 ---
    parser = EligibilityResponseParser()
    parsed = parser.parse(x12_response)
    result['parsed'] = parsed

    # --- Derive status ---
    if parsed.get('rejections'):
        response_status = 'REJECTED'
    elif not parsed.get('member_found', False):
        response_status = 'MEMBER_NOT_FOUND'
    elif parsed.get('is_active'):
        response_status = 'ELIGIBLE'
    elif parsed.get('eligibility_code'):
        response_status = 'INELIGIBLE'
    else:
        response_status = 'UNKNOWN'

    result['response_status'] = response_status

    # --- Classify indicators ---
    classifier = EligibilityClassifier()
    classification = classifier.classify(parsed)
    result['classification'] = classification

    # --- Create / update patient ---
    demographics = parsed.get('demographics', {})
    updateable_fields = [
        'first_name', 'middle_name', 'last_name',
        'date_of_birth', 'gender',
        'address_line_1', 'address_line_2', 'city', 'state', 'postal_code',
    ]
    identity_fields = {'date_of_birth', 'first_name', 'last_name', 'gender'}

    try:
        patient = Patient.objects.get(cin=cin)
        is_new = False
    except Patient.DoesNotExist:
        patient = Patient(cin=cin)
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
        parsed_at=now,
    )

    # Fields that are DateField — must use None, not '' when empty
    _date_fields = {'date_of_birth'}

    if is_new:
        for field in updateable_fields:
            val = demographics.get(field)
            if field in _date_fields:
                setattr(patient, field, val or None)   # None, never ''
            else:
                setattr(patient, field, val or '')      # '' for empty strings
        patient.save()
        PatientChangeHistory.objects.create(
            patient=patient, eligibility_response=elig_response,
            field_name='patient', old_value='', new_value=f'Created via lookup CIN={cin}',
            change_type='CREATED',
        )
        elig_response.patient = patient
        elig_response.save(update_fields=['patient'])
    else:
        changed = False
        for field in updateable_fields:
            new_val = str(demographics.get(field, '') or '').strip()
            old_val = str(getattr(patient, field, '') or '').strip()
            if old_val == new_val or not new_val:
                continue
            if field in identity_fields and old_val and new_val:
                PatientDataConflict.objects.get_or_create(
                    patient=patient, field_name=field, status='OPEN',
                    defaults={'eligibility_response': elig_response,
                              'existing_value': old_val, 'returned_value': new_val},
                )
                continue
            setattr(patient, field, new_val)
            PatientChangeHistory.objects.create(
                patient=patient, eligibility_response=elig_response,
                field_name=field, old_value=old_val, new_value=new_val,
                change_type='UPDATED',
            )
            changed = True
        if changed:
            patient.save()

    result['patient'] = patient

    # Skip snapshot if member not found / rejected
    if response_status in ('MEMBER_NOT_FOUND', 'REJECTED', 'TECHNICAL_FAILURE'):
        for rej in parsed.get('rejections', []):
            ResponseRejection.objects.create(eligibility_response=elig_response, **rej)
        return result

    # --- Save snapshot + indicators atomically ---
    with transaction.atomic():
        PatientEligibilitySnapshot.objects.filter(
            patient=patient, is_current=True
        ).update(is_current=False)

        snapshot = PatientEligibilitySnapshot.objects.create(
            patient=patient,
            eligibility_response=elig_response,
            date_of_service=date_of_service,
            is_medicaid_eligible=response_status in ('ELIGIBLE', 'SUCCESS'),
            has_recertification=classification.get('has_recertification', False),
            recertification_date=classification.get('recertification_date'),
            has_nhtd=classification.get('has_nhtd', False),
            has_code_60=classification.get('has_code_60', False),
            has_surplus=classification.get('has_surplus', False),
            surplus_amount=classification.get('surplus_amount'),
            effective_from=parsed.get('coverage_start_date'),
            effective_to=parsed.get('coverage_end_date'),
            is_current=True,
        )

        for indicator in classification.get('indicators', []):
            EligibilityIndicator.objects.create(
                eligibility_response=elig_response, patient=patient, **indicator,
            )

        for fin in parsed.get('financial_details', []):
            EligibilityFinancialDetail.objects.create(
                eligibility_response=elig_response, patient=patient, **fin,
            )

        for benefit in parsed.get('benefits', []):
            EligibilityBenefit.objects.create(
                eligibility_response=elig_response, **benefit,
            )

    result['snapshot'] = snapshot
    return result

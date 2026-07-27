"""Import views: upload, progress SSE, results."""
import json
import time
import logging
from django.conf import settings
from django.http import (
    JsonResponse, HttpResponse, StreamingHttpResponse, HttpResponseBadRequest
)
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone

from .models import ImportBatch, ImportRow
from .validators import validate_and_parse_csv, compute_file_hash
from .services import get_batch_progress
from .tasks import process_import_batch
from eligibility.filters import apply_import_row_filters, apply_sorting
from eligibility.exports import export_import_rows_csv

logger = logging.getLogger(__name__)


def index(request):
    """Landing page — Import Eligibility."""
    recent_batches = ImportBatch.objects.order_by('-created_at')[:5]
    return render(request, 'imports/index.html', {'recent_batches': recent_batches})


@require_http_methods(['POST'])
def upload_import(request):
    """Handle CSV upload, validation, batch creation, and trigger background processing."""
    csv_file = request.FILES.get('csv_file')
    date_of_service = request.POST.get('date_of_service', '').strip()

    errors = []
    if not csv_file:
        errors.append('No CSV file uploaded.')
    if not date_of_service:
        errors.append('Date of Service is required.')

    if errors:
        return JsonResponse({'success': False, 'errors': errors}, status=400)

    # Read and validate
    raw_bytes = csv_file.read()
    csv_file.seek(0)

    # Parse CSV
    import io as _io
    rows, file_errors = validate_and_parse_csv(_io.BytesIO(raw_bytes))

    if file_errors:
        return JsonResponse({'success': False, 'errors': file_errors}, status=400)

    if not rows:
        return JsonResponse({'success': False, 'errors': ['CSV contains no data rows.']}, status=400)

    file_hash = compute_file_hash(raw_bytes)
    total = len(rows)
    valid = sum(1 for r in rows if not r.get('error'))
    invalid = sum(1 for r in rows if r.get('error') and not r.get('is_duplicate'))
    duplicate = sum(1 for r in rows if r.get('is_duplicate'))

    # Create batch
    batch = ImportBatch.objects.create(
        file_name=csv_file.name,
        file_hash=file_hash,
        date_of_service=date_of_service,
        total_rows=total,
        valid_rows=valid,
        invalid_rows=invalid,
        duplicate_rows=duplicate,
        status='PROCESSING',
        started_at=timezone.now(),
    )

    # Create ImportRow records
    row_objs = []
    for row_data in rows:
        if row_data.get('is_duplicate'):
            status = 'DUPLICATE'
            validation_error = row_data.get('error', '')
        elif row_data.get('error'):
            status = 'VALIDATION_FAILED'
            validation_error = row_data.get('error', '')
        else:
            status = 'PENDING'
            validation_error = ''

        row_objs.append(ImportRow(
            import_batch=batch,
            row_number=row_data['row_number'],
            cin=row_data['cin'],
            status=status,
            validation_error=validation_error,
        ))

    ImportRow.objects.bulk_create(row_objs)

    # Kick off background processing
    process_import_batch.delay(batch.id)

    return JsonResponse({'success': True, 'batch_id': batch.id})


def progress_sse(request, batch_id):
    """Server-Sent Events stream for real-time import progress."""
    def event_stream():
        prev_data = None
        timeout = 300  # 5-minute timeout
        start = time.time()
        while time.time() - start < timeout:
            data = get_batch_progress(batch_id)
            if data is None:
                yield f"data: {json.dumps({'error': 'Batch not found'})}\n\n"
                break

            if data != prev_data:
                yield f"data: {json.dumps(data)}\n\n"
                prev_data = data

            # Stop streaming when batch is done
            if data['status'] in ('COMPLETED', 'PARTIALLY_COMPLETED', 'FAILED', 'CANCELLED'):
                break

            time.sleep(1)

    response = StreamingHttpResponse(event_stream(), content_type='text/event-stream')
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    return response


def progress_poll(request, batch_id):
    """AJAX polling fallback for progress."""
    data = get_batch_progress(batch_id)
    if data is None:
        return JsonResponse({'error': 'Batch not found'}, status=404)
    return JsonResponse(data)


def results(request, batch_id):
    """Import Results page."""
    batch = get_object_or_404(ImportBatch, pk=batch_id)

    queryset = ImportRow.objects.filter(import_batch=batch).select_related(
        'patient',
    ).prefetch_related(
        'eligibility_request__response__snapshot',
    )

    # Apply filters
    queryset = apply_import_row_filters(queryset, request.GET)
    sort_by = request.GET.get('sort', 'row')
    queryset = apply_sorting(queryset, sort_by)

    # Export?
    if request.GET.get('export') == 'csv':
        return export_import_rows_csv(queryset)

    rows = list(queryset)
    extra = _build_results_context(batch, request)
    context = {
        'batch': batch,
        'rows': rows,
        'params': request.GET,
        'sort': sort_by,
        **extra,
    }
    return render(request, 'imports/results.html', context)


def cancel_batch(request, batch_id):
    """Cancel pending rows in a batch."""
    if request.method != 'POST':
        return HttpResponseBadRequest()
    batch = get_object_or_404(ImportBatch, pk=batch_id)
    if batch.status not in ('PROCESSING', 'PARTIALLY_COMPLETED'):
        return JsonResponse({'error': 'Batch cannot be cancelled in its current state.'}, status=400)

    batch.status = 'CANCELLING'
    batch.save(update_fields=['status', 'updated_at'])

    cancelled = ImportRow.objects.filter(
        import_batch=batch, status='PENDING'
    ).update(status='CANCELLED')

    batch.refresh_counters()
    batch.status = 'CANCELLED' if batch.processed_rows == 0 else 'PARTIALLY_COMPLETED'
    batch.completed_at = timezone.now()
    batch.save(update_fields=['status', 'completed_at', 'updated_at'])

    return JsonResponse({'success': True, 'cancelled_rows': cancelled})


def retry_failed_rows(request, batch_id):
    """Re-queue failed/rejected rows."""
    if request.method != 'POST':
        return HttpResponseBadRequest()
    from .tasks import process_import_row
    batch = get_object_or_404(ImportBatch, pk=batch_id)
    rows = ImportRow.objects.filter(import_batch=batch, status='TECHNICAL_FAILURE')
    count = 0
    for row in rows:
        row.status = 'RETRY_PENDING'
        row.retry_count += 1
        row.save(update_fields=['status', 'retry_count', 'updated_at'])
        process_import_row.delay(row.id)
        count += 1
    return JsonResponse({'success': True, 'retried': count})


def download_sample_csv(request):
    """Serve the sample CSV template."""
    content = "cin\nAB12345C\nCD67890D\nEF11223G\n"
    response = HttpResponse(content, content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="sample_eligibility.csv"'
    return response


def app_settings(request):
    """Settings / admin page."""
    from patients.models import Patient
    from eligibility.models import EligibilityResponse
    counts = {
        'patients': Patient.objects.count(),
        'batches': ImportBatch.objects.count(),
        'responses': EligibilityResponse.objects.count(),
        'rows': ImportRow.objects.count(),
    }
    return render(request, 'imports/settings.html', {'counts': counts})


@require_http_methods(['POST'])
def wipe_all_data(request):
    """Delete all application data. Requires confirmation token."""
    if request.POST.get('confirm') != 'WIPE':
        from django.contrib import messages
        messages.error(request, 'Confirmation text did not match. Nothing was deleted.')
        return redirect('imports:settings')

    from django.db import connection
    from patients.models import Patient, PatientChangeHistory, PatientDataConflict
    from eligibility.models import (
        EligibilityRequest, EligibilityResponse, PatientEligibilitySnapshot,
        EligibilityIndicator, EligibilityFinancialDetail, EligibilityBenefit,
        ResponseRejection,
    )

    # Delete in dependency order
    ResponseRejection.objects.all().delete()
    EligibilityBenefit.objects.all().delete()
    EligibilityFinancialDetail.objects.all().delete()
    EligibilityIndicator.objects.all().delete()
    PatientEligibilitySnapshot.objects.all().delete()
    EligibilityResponse.objects.all().delete()
    EligibilityRequest.objects.all().delete()
    PatientChangeHistory.objects.all().delete()
    PatientDataConflict.objects.all().delete()
    Patient.objects.all().delete()
    ImportRow.objects.all().delete()
    ImportBatch.objects.all().delete()

    from django.contrib import messages
    messages.success(request, 'All data has been wiped successfully.')
    return redirect('imports:settings')


# Context helper used in results view
def _build_results_context(batch, request):
    """Build the context dict for the results template."""
    return {
        'batch_stats': [
            ('Date of Service', batch.date_of_service),
            ('Total Rows', batch.total_rows),
            ('Valid', batch.valid_rows),
            ('Invalid', batch.invalid_rows),
            ('Duplicate', batch.duplicate_rows),
            ('Processed', batch.processed_rows),
            ('Created', batch.created_patients),
            ('Updated', batch.updated_patients),
            ('Unchanged', batch.unchanged_patients),
            ('Rejected', batch.rejected_rows),
            ('Failed', batch.failed_rows),
            ('Started', batch.started_at),
            ('Completed', batch.completed_at),
        ],
        'indicators_choices': [
            ('recertification', 'Recertification'),
            ('nhtd', 'NHTD'),
            ('code_60', 'Code 60'),
            ('surplus', 'Surplus'),
        ],
        'status_choices': [
            ('COMPLETED', 'Completed'),
            ('REJECTED', 'Rejected'),
            ('TECHNICAL_FAILURE', 'Failed'),
            ('VALIDATION_FAILED', 'Invalid'),
            ('DUPLICATE', 'Duplicate'),
        ],
        'selected_indicators': request.GET.getlist('indicator'),
        'selected_statuses': request.GET.getlist('status'),
    }

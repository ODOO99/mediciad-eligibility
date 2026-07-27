"""Import progress service — reads batch/row state for SSE / AJAX."""
import json
from django.utils import timezone
from .models import ImportBatch, ImportRow


def get_batch_progress(batch_id):
    """Return a dict suitable for streaming to the frontend."""
    try:
        batch = ImportBatch.objects.get(pk=batch_id)
    except ImportBatch.DoesNotExist:
        return None

    # Current processing row
    current_row = ImportRow.objects.filter(
        import_batch=batch,
        status='PROCESSING',
    ).order_by('row_number').first()

    # Recent activity (last 20 terminal rows)
    terminal_statuses = ['COMPLETED', 'REJECTED', 'TECHNICAL_FAILURE', 'MANUAL_REVIEW', 'CANCELLED']
    recent_rows = list(
        ImportRow.objects.filter(
            import_batch=batch,
            status__in=terminal_statuses,
        ).select_related('patient').order_by('-updated_at')[:20]
    )

    recent_activity = []
    for row in recent_rows:
        patient_name = row.patient.full_name if row.patient else ''
        indicator_parts = []
        if row.patient:
            snap = row.patient.eligibility_snapshots.filter(is_current=True).first()
            if snap:
                if snap.has_recertification:
                    indicator_parts.append('Recert')
                if snap.has_code_60:
                    indicator_parts.append('Code 60')
                if snap.has_s1:
                    indicator_parts.append('S1')

        recent_activity.append({
            'cin': row.cin,
            'patient_name': patient_name,
            'patient_action': row.patient_action,
            'status': row.status,
            'indicators': indicator_parts,
            'error': row.rejection_description or row.processing_error or '',
        })

    current_info = None
    if current_row:
        current_info = {
            'row_number': current_row.row_number,
            'cin': current_row.cin,
            'status': current_row.status,
            'processing_stage': current_row.processing_stage,
            'updated_at': current_row.updated_at.isoformat() if current_row.updated_at else None,
        }

    return {
        'batch_id': batch.id,
        'status': batch.status,
        'file_name': batch.file_name,
        'date_of_service': str(batch.date_of_service),
        'total_rows': batch.total_rows,
        'valid_rows': batch.valid_rows,
        'invalid_rows': batch.invalid_rows,
        'duplicate_rows': batch.duplicate_rows,
        'processed_rows': batch.processed_rows,
        'remaining_rows': batch.remaining_rows,
        'percentage': batch.percentage_complete,
        'created_patients': batch.created_patients,
        'updated_patients': batch.updated_patients,
        'unchanged_patients': batch.unchanged_patients,
        'rejected_rows': batch.rejected_rows,
        'failed_rows': batch.failed_rows,
        'cancelled_rows': batch.cancelled_rows,
        'started_at': batch.started_at.isoformat() if batch.started_at else None,
        'completed_at': batch.completed_at.isoformat() if batch.completed_at else None,
        'current_row': current_info,
        'recent_activity': recent_activity,
    }

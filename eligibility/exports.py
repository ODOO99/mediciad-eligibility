"""CSV export for filtered import results."""
import csv
import re
from django.http import StreamingHttpResponse
from django.db.models import Prefetch
from eligibility.models import PatientEligibilitySnapshot

DANGEROUS_PREFIXES = ('=', '+', '-', '@')


def sanitize_csv_value(value):
    """Protect against CSV formula injection."""
    if value is None:
        return ''
    s = str(value).strip()
    if s and s[0] in DANGEROUS_PREFIXES:
        s = "'" + s
    return s


class Echo:
    """Streaming write helper."""
    def write(self, value):
        return value


def export_import_rows_csv(queryset):
    """Stream filtered ImportRow queryset as CSV."""
    pseudo_buffer = Echo()
    writer = csv.writer(pseudo_buffer)

    def rows():
        yield writer.writerow([
            'CIN', 'Patient Name', 'Date of Birth', 'Date of Service',
            'Eligibility Status', 'Eligibility', 'Recertification', 'Recertification Date', 'Code 60', 'S1',
            'Patient Action', 'Row Status', 'Error/Rejection',
        ])
        # Prefetch current snapshots to avoid N+1 queries during CSV generation
        qs = queryset.select_related(
            'patient',
            'eligibility_request__response__snapshot',
        ).prefetch_related(
            Prefetch(
                'patient__eligibility_snapshots',
                queryset=PatientEligibilitySnapshot.objects.filter(is_current=True),
                to_attr='prefetched_current_snapshots'
            )
        )

        for row in qs:
            snap = None
            if row.patient:
                current_snaps = row.patient.prefetched_current_snapshots
                snap = current_snaps[0] if current_snaps else None
            req = getattr(row, 'eligibility_request', None)
            resp = getattr(req, 'response', None) if req else None

            dos = req.date_of_service if req else ''
            eligibility_status = resp.response_status if resp else ''
            eligibility = ''
            recert = ''
            recert_date = ''
            code_60 = ''
            s1 = ''
            if snap:
                eligibility = 'Eligible' if snap.is_medicaid_eligible else 'Not Eligible'
                recert = 'Yes' if snap.has_recertification else 'No'
                recert_date = snap.recertification_date or ''
                code_60 = 'Yes' if snap.has_code_60 else 'No'
                s1 = 'Yes' if snap.has_s1 else 'No'

            patient_name = row.patient.full_name if row.patient else ''
            dob = row.patient.date_of_birth if row.patient else ''

            yield writer.writerow([
                sanitize_csv_value(row.cin),
                sanitize_csv_value(patient_name),
                sanitize_csv_value(dob),
                sanitize_csv_value(dos),
                sanitize_csv_value(eligibility_status),
                sanitize_csv_value(eligibility),
                sanitize_csv_value(recert),
                sanitize_csv_value(recert_date),
                sanitize_csv_value(code_60),
                sanitize_csv_value(s1),
                sanitize_csv_value(row.patient_action),
                sanitize_csv_value(row.status),
                sanitize_csv_value(row.processing_error or row.rejection_description or row.validation_error),
            ])

    response = StreamingHttpResponse(rows(), content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="eligibility_export.csv"'
    return response

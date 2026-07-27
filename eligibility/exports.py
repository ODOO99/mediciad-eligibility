"""CSV export for filtered import results."""
import csv
import re
from django.http import StreamingHttpResponse


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
            'Eligibility Status', 'Recertification', 'Recertification Date',
            'NHTD', 'Code 60', 'Surplus', 'Surplus Amount',
            'Patient Action', 'Row Status', 'Error/Rejection',
        ])
        for row in queryset.select_related(
            'patient',
            'eligibility_request__response__snapshot',
        ):
            snap = None
            if row.patient:
                snap = row.patient.eligibility_snapshots.filter(is_current=True).first()
            req = getattr(row, 'eligibility_request', None)
            resp = getattr(req, 'response', None) if req else None

            dos = req.date_of_service if req else ''
            eligibility_status = resp.response_status if resp else ''
            recert = ''
            recert_date = ''
            nhtd = ''
            code_60 = ''
            surplus = ''
            surplus_amount = ''
            if snap:
                recert = 'Yes' if snap.has_recertification else 'No'
                recert_date = snap.recertification_date or ''
                nhtd = 'Yes' if snap.has_nhtd else 'No'
                code_60 = 'Yes' if snap.has_code_60 else 'No'
                surplus = 'Yes' if snap.has_surplus else 'No'
                surplus_amount = snap.surplus_amount or ''

            patient_name = row.patient.full_name if row.patient else ''
            dob = row.patient.date_of_birth if row.patient else ''

            yield writer.writerow([
                sanitize_csv_value(row.cin),
                sanitize_csv_value(patient_name),
                sanitize_csv_value(dob),
                sanitize_csv_value(dos),
                sanitize_csv_value(eligibility_status),
                sanitize_csv_value(recert),
                sanitize_csv_value(recert_date),
                sanitize_csv_value(nhtd),
                sanitize_csv_value(code_60),
                sanitize_csv_value(surplus),
                sanitize_csv_value(surplus_amount),
                sanitize_csv_value(row.patient_action),
                sanitize_csv_value(row.status),
                sanitize_csv_value(row.processing_error or row.rejection_description or row.validation_error),
            ])

    response = StreamingHttpResponse(rows(), content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="eligibility_export.csv"'
    return response

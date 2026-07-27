import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.base')
django.setup()
from imports.models import ImportBatch, ImportRow
b = ImportBatch.objects.last()
print(f"Batch {b.id}, total={b.total_rows}, processed={b.processed_rows}")
terminal = ['COMPLETED', 'REJECTED', 'TECHNICAL_FAILURE', 'MANUAL_REVIEW', 'CANCELLED']
r = ImportRow.objects.filter(import_batch=b).exclude(status__in=terminal)
print(f"Non-terminal rows: {r.count()}")
for row in r[:5]:
    print(f"Row {row.id}: {row.status} - {row.processing_stage}")
    if row.status == 'PROCESSING':
        print(f"  error: {row.processing_error}")

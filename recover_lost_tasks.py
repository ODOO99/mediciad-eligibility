import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.base')
django.setup()
from imports.models import ImportBatch, ImportRow
from imports.tasks import process_import_row

batches = ImportBatch.objects.filter(status='PROCESSING')
for b in batches:
    pending = ImportRow.objects.filter(import_batch=b, status='PENDING')
    count = pending.count()
    if count > 0:
        print(f"Re-queuing {count} PENDING rows for Batch {b.id}")
        for row in pending:
            process_import_row.delay(row.id)
    
    # Also requeue PROCESSING and RETRY_PENDING just in case
    stuck = ImportRow.objects.filter(import_batch=b, status__in=['PROCESSING', 'RETRY_PENDING'])
    stuck_count = stuck.count()
    if stuck_count > 0:
        print(f"Re-queuing {stuck_count} stuck rows for Batch {b.id}")
        for row in stuck:
            row.status = 'PENDING'
            row.save(update_fields=['status'])
            process_import_row.delay(row.id)

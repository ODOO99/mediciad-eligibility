import os, django, sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.base')
django.setup()
from imports.models import ImportBatch, ImportRow

batches = ImportBatch.objects.order_by('-created_at')[:3]
for b in batches:
    print(f"\nBatch {b.id}, file={b.file_name}, status={b.status}, total={b.total_rows}, processed={b.processed_rows}")
    terminal = ['COMPLETED', 'REJECTED', 'TECHNICAL_FAILURE', 'MANUAL_REVIEW', 'CANCELLED']
    pending = ImportRow.objects.filter(import_batch=b, status='PENDING').count()
    processing = ImportRow.objects.filter(import_batch=b, status='PROCESSING').count()
    retry = ImportRow.objects.filter(import_batch=b, status='RETRY_PENDING').count()
    failed = ImportRow.objects.filter(import_batch=b, status='TECHNICAL_FAILURE').count()
    print(f"  Pending: {pending}, Processing: {processing}, Retry: {retry}, Failed: {failed}")
    
    if processing > 0:
        for row in ImportRow.objects.filter(import_batch=b, status='PROCESSING')[:3]:
            print(f"  [PROCESSING] Row {row.id}: stage={row.processing_stage}")
    if failed > 0:
        for row in ImportRow.objects.filter(import_batch=b, status='TECHNICAL_FAILURE')[:3]:
            print(f"  [FAILED] Row {row.id}: error={row.processing_error[:100]}")
    if retry > 0:
        for row in ImportRow.objects.filter(import_batch=b, status='RETRY_PENDING')[:3]:
            print(f"  [RETRY] Row {row.id}: error={row.processing_error[:100]}")

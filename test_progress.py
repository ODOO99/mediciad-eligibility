import os, django, sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.base')
django.setup()
from imports.services import get_batch_progress
try:
    data = get_batch_progress(1)
    print("Success. Percentage:", data['percentage'])
except Exception as e:
    import traceback
    traceback.print_exc()
    sys.exit(1)

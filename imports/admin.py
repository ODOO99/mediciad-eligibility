from django.contrib import admin
from .models import ImportBatch, ImportRow


@admin.register(ImportBatch)
class ImportBatchAdmin(admin.ModelAdmin):
    list_display = ['id', 'file_name', 'date_of_service', 'status', 'total_rows', 'processed_rows', 'created_at']
    list_filter = ['status', 'date_of_service']
    search_fields = ['file_name']
    readonly_fields = ['created_at', 'updated_at', 'started_at', 'completed_at']


@admin.register(ImportRow)
class ImportRowAdmin(admin.ModelAdmin):
    list_display = ['id', 'import_batch', 'row_number', 'cin', 'status', 'patient_action']
    list_filter = ['status', 'patient_action']
    search_fields = ['cin']
    raw_id_fields = ['patient', 'import_batch']

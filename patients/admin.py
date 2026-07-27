from django.contrib import admin
from .models import Patient, PatientChangeHistory, PatientDataConflict


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ['cin', 'last_name', 'first_name', 'date_of_birth', 'status', 'created_at']
    search_fields = ['cin', 'first_name', 'last_name']
    list_filter = ['status', 'gender']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(PatientChangeHistory)
class PatientChangeHistoryAdmin(admin.ModelAdmin):
    list_display = ['patient', 'field_name', 'change_type', 'created_at']
    list_filter = ['change_type']
    search_fields = ['patient__cin']


@admin.register(PatientDataConflict)
class PatientDataConflictAdmin(admin.ModelAdmin):
    list_display = ['patient', 'field_name', 'status', 'created_at']
    list_filter = ['status']
    search_fields = ['patient__cin']

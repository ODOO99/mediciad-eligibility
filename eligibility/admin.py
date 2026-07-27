from django.contrib import admin
from .models import (
    EligibilityRequest, EligibilityResponse, PatientEligibilitySnapshot,
    EligibilityIndicator, EligibilityFinancialDetail, EligibilityBenefit, ResponseRejection
)

@admin.register(EligibilityRequest)
class EligibilityRequestAdmin(admin.ModelAdmin):
    list_display = ['cin', 'date_of_service', 'request_status', 'submitted_at']
    search_fields = ['cin', 'payload_id']
    list_filter = ['request_status', 'date_of_service']

@admin.register(EligibilityResponse)
class EligibilityResponseAdmin(admin.ModelAdmin):
    list_display = ['eligibility_request', 'response_type', 'response_status', 'member_found', 'received_at']
    list_filter = ['response_type', 'response_status', 'member_found']

@admin.register(PatientEligibilitySnapshot)
class PatientEligibilitySnapshotAdmin(admin.ModelAdmin):
    list_display = ['patient', 'date_of_service', 'is_medicaid_eligible', 'has_recertification', 'has_nhtd', 'has_code_60', 'has_surplus', 'is_current']
    list_filter = ['is_medicaid_eligible', 'has_recertification', 'has_nhtd', 'has_code_60', 'has_surplus', 'is_current']
    search_fields = ['patient__cin']

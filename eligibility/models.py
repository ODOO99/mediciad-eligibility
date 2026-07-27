"""Eligibility models."""
from django.db import models
from django.utils import timezone


class EligibilityRequest(models.Model):
    REQUEST_STATUSES = [
        ('PENDING', 'Pending'),
        ('SUBMITTED', 'Submitted'),
        ('FAILED', 'Failed'),
    ]
    import_row = models.OneToOneField(
        'imports.ImportRow', on_delete=models.CASCADE,
        related_name='eligibility_request', null=True, blank=True
    )
    patient = models.ForeignKey(
        'patients.Patient', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='eligibility_requests'
    )
    cin = models.CharField(max_length=20, db_index=True)
    date_of_service = models.DateField(db_index=True)
    service_type_code = models.CharField(max_length=10, default='30')
    request_status = models.CharField(max_length=20, choices=REQUEST_STATUSES, default='PENDING')
    request_control_number = models.CharField(max_length=50, blank=True)
    isa_control_number = models.CharField(max_length=20, blank=True)
    gs_control_number = models.CharField(max_length=20, blank=True)
    st_control_number = models.CharField(max_length=20, blank=True)
    payload_id = models.CharField(max_length=100, blank=True, db_index=True)
    raw_270 = models.TextField(blank=True)
    request_hash = models.CharField(max_length=64, blank=True)
    content_length = models.IntegerField(default=0)
    submitted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['cin']),
            models.Index(fields=['cin', 'date_of_service']),
            models.Index(fields=['payload_id']),
        ]

    def __str__(self):
        return f"270 Request {self.cin} {self.date_of_service}"


class EligibilityResponse(models.Model):
    RESPONSE_TYPES = [
        ('X12_271', 'X12 271'),
        ('TA1', 'TA1 Acknowledgement'),
        ('X12_999', 'X12 999'),
        ('CORE_ERROR', 'CORE Error'),
        ('HTTP_ERROR', 'HTTP Error'),
        ('UNKNOWN', 'Unknown'),
    ]
    RESPONSE_STATUSES = [
        ('SUCCESS', 'Success'),
        ('ELIGIBLE', 'Eligible'),
        ('INELIGIBLE', 'Ineligible'),
        ('REJECTED', 'Rejected'),
        ('MEMBER_NOT_FOUND', 'Member Not Found'),
        ('TECHNICAL_FAILURE', 'Technical Failure'),
        ('UNKNOWN', 'Unknown'),
    ]
    eligibility_request = models.OneToOneField(
        EligibilityRequest, on_delete=models.CASCADE, related_name='response'
    )
    patient = models.ForeignKey(
        'patients.Patient', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='eligibility_responses'
    )
    response_type = models.CharField(max_length=20, choices=RESPONSE_TYPES, default='UNKNOWN')
    response_status = models.CharField(max_length=30, choices=RESPONSE_STATUSES, default='UNKNOWN')
    eligibility_status = models.CharField(max_length=200, blank=True)
    member_found = models.BooleanField(default=False)
    coverage_start_date = models.DateField(null=True, blank=True)
    coverage_end_date = models.DateField(null=True, blank=True)
    plan_name = models.CharField(max_length=200, blank=True)
    plan_identifier = models.CharField(max_length=100, blank=True)
    managed_care_name = models.CharField(max_length=200, blank=True)
    response_control_number = models.CharField(max_length=50, blank=True)
    raw_271 = models.TextField(blank=True)
    response_hash = models.CharField(max_length=64, blank=True)
    content_length = models.IntegerField(default=0)
    parser_version = models.CharField(max_length=20, default='1.0')
    received_at = models.DateTimeField(null=True, blank=True)
    parsed_at = models.DateTimeField(null=True, blank=True)
    is_final_response = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['patient', 'response_status']),
            models.Index(fields=['received_at']),
        ]

    def __str__(self):
        return f"271 Response {self.eligibility_request.cin} {self.response_status}"


class PatientEligibilitySnapshot(models.Model):
    patient = models.ForeignKey(
        'patients.Patient', on_delete=models.CASCADE, related_name='eligibility_snapshots'
    )
    eligibility_response = models.OneToOneField(
        EligibilityResponse, on_delete=models.CASCADE, related_name='snapshot'
    )
    date_of_service = models.DateField(db_index=True)
    is_medicaid_eligible = models.BooleanField(default=False)
    has_recertification = models.BooleanField(default=False, db_index=True)
    recertification_date = models.DateField(null=True, blank=True, db_index=True)
    # Code 60 flag
    has_code_60 = models.BooleanField(default=False, db_index=True)
    # S1 flag
    has_s1 = models.BooleanField(default=False, db_index=True)
    effective_from = models.DateField(null=True, blank=True)
    effective_to = models.DateField(null=True, blank=True)
    is_current = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['patient', 'date_of_service']),
            models.Index(fields=['patient', 'is_current']),
            models.Index(fields=['has_recertification', 'recertification_date']),
            models.Index(fields=['has_code_60']),
            models.Index(fields=['has_s1']),
            # Partial index for current snapshots (defined via migration)
        ]
        ordering = ['-date_of_service', '-created_at']

    def __str__(self):
        return f"Snapshot {self.patient.cin} {self.date_of_service} current={self.is_current}"


class EligibilityIndicator(models.Model):
    INDICATOR_TYPES = [
        ('RECERTIFICATION', 'Recertification'),
        ('CODE_60', 'Code 60'),
        ('S1', 'S1'),
        ('OTHER', 'Other'),
    ]
    eligibility_response = models.ForeignKey(
        EligibilityResponse, on_delete=models.CASCADE, related_name='indicators'
    )
    patient = models.ForeignKey(
        'patients.Patient', on_delete=models.SET_NULL, null=True, blank=True, related_name='indicators'
    )
    indicator_type = models.CharField(max_length=30, choices=INDICATOR_TYPES, db_index=True)
    indicator_code = models.CharField(max_length=50, blank=True, db_index=True)
    indicator_value = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    source_segment = models.CharField(max_length=20, blank=True)
    source_element = models.CharField(max_length=20, blank=True)
    effective_from = models.DateField(null=True, blank=True)
    effective_to = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['indicator_type', 'is_active']),
            models.Index(fields=['indicator_code']),
        ]

    def __str__(self):
        return f"{self.indicator_type} {self.indicator_code}"


class EligibilityFinancialDetail(models.Model):
    FINANCIAL_TYPES = [
        ('SURPLUS', 'Surplus'),
        ('SPEND_DOWN', 'Spend Down'),
        ('COPAY', 'Co-pay'),
        ('DEDUCTIBLE', 'Deductible'),
        ('COINSURANCE', 'Co-insurance'),
        ('OTHER', 'Other'),
    ]
    eligibility_response = models.ForeignKey(
        EligibilityResponse, on_delete=models.CASCADE, related_name='financial_details'
    )
    patient = models.ForeignKey(
        'patients.Patient', on_delete=models.SET_NULL, null=True, blank=True, related_name='financial_details'
    )
    financial_type = models.CharField(max_length=20, choices=FINANCIAL_TYPES, db_index=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, db_index=True)
    currency = models.CharField(max_length=3, default='USD')
    period_type = models.CharField(max_length=50, blank=True)
    period_start = models.DateField(null=True, blank=True)
    period_end = models.DateField(null=True, blank=True)
    remaining_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    description = models.TextField(blank=True)
    source_segment = models.CharField(max_length=20, blank=True)
    source_element = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['financial_type', 'amount']),
        ]

    def __str__(self):
        return f"{self.financial_type} {self.amount}"


class EligibilityBenefit(models.Model):
    eligibility_response = models.ForeignKey(
        EligibilityResponse, on_delete=models.CASCADE, related_name='benefits'
    )
    service_type_code = models.CharField(max_length=10, blank=True)
    service_type_description = models.CharField(max_length=200, blank=True)
    benefit_information_code = models.CharField(max_length=10, blank=True)
    coverage_level_code = models.CharField(max_length=10, blank=True)
    insurance_type_code = models.CharField(max_length=10, blank=True)
    plan_coverage_description = models.CharField(max_length=200, blank=True)
    time_period_qualifier = models.CharField(max_length=10, blank=True)
    monetary_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    percentage = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    network_indicator = models.CharField(max_length=10, blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    message = models.TextField(blank=True)
    source_segment = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Benefit {self.service_type_code} {self.benefit_information_code}"


class ResponseRejection(models.Model):
    eligibility_response = models.ForeignKey(
        EligibilityResponse, on_delete=models.CASCADE, related_name='rejections'
    )
    reject_code = models.CharField(max_length=20, blank=True)
    follow_up_action_code = models.CharField(max_length=20, blank=True)
    entity_identifier_code = models.CharField(max_length=20, blank=True)
    description = models.TextField(blank=True)
    segment_reference = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Rejection {self.reject_code}: {self.description}"

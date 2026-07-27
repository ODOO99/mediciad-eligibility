"""Patient models."""
from django.db import models
from django.utils import timezone


class Patient(models.Model):
    GENDER_CHOICES = [('M', 'Male'), ('F', 'Female'), ('U', 'Unknown')]
    STATUS_CHOICES = [('ACTIVE', 'Active'), ('INACTIVE', 'Inactive'), ('MANUAL_REVIEW', 'Manual Review')]

    cin = models.CharField(max_length=20, unique=True, db_index=True, help_text="Medicaid Client Identification Number")
    first_name = models.CharField(max_length=100, blank=True)
    middle_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, blank=True)
    address_line_1 = models.CharField(max_length=200, blank=True)
    address_line_2 = models.CharField(max_length=200, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=50, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ACTIVE')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=['cin'])]
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.last_name}, {self.first_name} ({self.cin})"

    @property
    def full_name(self):
        parts = [p for p in [self.first_name, self.middle_name, self.last_name] if p]
        return ' '.join(parts)

    @property
    def current_eligibility(self):
        return self.eligibility_snapshots.filter(is_current=True).first()


class PatientChangeHistory(models.Model):
    CHANGE_TYPES = [
        ('CREATED', 'Created'),
        ('UPDATED', 'Updated'),
        ('CONFLICT', 'Conflict'),
        ('IGNORED', 'Ignored'),
    ]
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='change_history')
    eligibility_response = models.ForeignKey(
        'eligibility.EligibilityResponse', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='patient_changes'
    )
    field_name = models.CharField(max_length=100)
    old_value = models.TextField(blank=True)
    new_value = models.TextField(blank=True)
    change_type = models.CharField(max_length=20, choices=CHANGE_TYPES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['patient', 'field_name'])]

    def __str__(self):
        return f"{self.patient.cin} {self.field_name}: {self.old_value!r} -> {self.new_value!r}"


class PatientDataConflict(models.Model):
    STATUS_CHOICES = [('OPEN', 'Open'), ('ACCEPTED', 'Accepted'), ('REJECTED', 'Rejected')]

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='data_conflicts')
    eligibility_response = models.ForeignKey(
        'eligibility.EligibilityResponse', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='patient_conflicts'
    )
    field_name = models.CharField(max_length=100)
    existing_value = models.TextField(blank=True)
    returned_value = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='OPEN')
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Conflict {self.patient.cin} {self.field_name}"

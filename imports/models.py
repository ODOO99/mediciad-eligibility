"""Import batch and row models."""
from django.db import models
from django.utils import timezone


class ImportBatch(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('UPLOADING', 'Uploading'),
        ('VALIDATING', 'Validating'),
        ('PROCESSING', 'Processing'),
        ('COMPLETED', 'Completed'),
        ('PARTIALLY_COMPLETED', 'Partially Completed'),
        ('FAILED', 'Failed'),
        ('CANCELLING', 'Cancelling'),
        ('CANCELLED', 'Cancelled'),
    ]
    file_name = models.CharField(max_length=255)
    file_hash = models.CharField(max_length=64, blank=True)
    date_of_service = models.DateField()
    total_rows = models.IntegerField(default=0)
    valid_rows = models.IntegerField(default=0)
    invalid_rows = models.IntegerField(default=0)
    duplicate_rows = models.IntegerField(default=0)
    processed_rows = models.IntegerField(default=0)
    created_patients = models.IntegerField(default=0)
    updated_patients = models.IntegerField(default=0)
    unchanged_patients = models.IntegerField(default=0)
    rejected_rows = models.IntegerField(default=0)
    failed_rows = models.IntegerField(default=0)
    cancelled_rows = models.IntegerField(default=0)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='PENDING', db_index=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"Batch {self.id} - {self.file_name} ({self.status})"

    @property
    def remaining_rows(self):
        return max(0, self.valid_rows - self.processed_rows - self.cancelled_rows)

    @property
    def percentage_complete(self):
        if self.valid_rows == 0:
            return 0
        done = self.processed_rows + self.cancelled_rows
        return min(100, int((done / self.valid_rows) * 100))

    def refresh_counters(self):
        """Recalculate counters from ImportRow aggregates."""
        from django.db.models import Count
        rows = self.rows.values('status', 'patient_action').annotate(count=Count('id'))
        
        processed = 0
        created = 0
        updated = 0
        unchanged = 0
        rejected = 0
        failed = 0
        cancelled = 0

        terminal_statuses = {'COMPLETED', 'REJECTED', 'TECHNICAL_FAILURE', 'MANUAL_REVIEW', 'CANCELLED'}
        for row in rows:
            s = row['status']
            a = row['patient_action']
            c = row['count']
            if s in terminal_statuses:
                if s != 'CANCELLED':
                    processed += c
                if s == 'COMPLETED':
                    if a == 'CREATED':
                        created += c
                    elif a == 'UPDATED':
                        updated += c
                    elif a == 'UNCHANGED':
                        unchanged += c
                elif s in ('REJECTED', 'MANUAL_REVIEW'):
                    rejected += c
                elif s == 'TECHNICAL_FAILURE':
                    failed += c
                elif s == 'CANCELLED':
                    cancelled += c

        self.processed_rows = processed
        self.created_patients = created
        self.updated_patients = updated
        self.unchanged_patients = unchanged
        self.rejected_rows = rejected
        self.failed_rows = failed
        self.cancelled_rows = cancelled
        self.save(update_fields=[
            'processed_rows', 'created_patients', 'updated_patients',
            'unchanged_patients', 'rejected_rows', 'failed_rows', 'cancelled_rows', 'updated_at'
        ])


class ImportRow(models.Model):
    ROW_STATUSES = [
        ('PENDING', 'Pending'),
        ('DUPLICATE', 'Duplicate'),
        ('VALIDATION_FAILED', 'Validation Failed'),
        ('PROCESSING', 'Processing'),
        ('REQUEST_GENERATED', 'Request Generated'),
        ('REQUEST_SENT', 'Request Sent'),
        ('WAITING_FOR_RESPONSE', 'Waiting for Response'),
        ('RESPONSE_RECEIVED', 'Response Received'),
        ('PARSING_RESPONSE', 'Parsing Response'),
        ('UPDATING_PATIENT', 'Updating Patient'),
        ('SAVING_ELIGIBILITY', 'Saving Eligibility'),
        ('COMPLETED', 'Completed'),
        ('REJECTED', 'Rejected'),
        ('TECHNICAL_FAILURE', 'Technical Failure'),
        ('RETRY_PENDING', 'Retry Pending'),
        ('MANUAL_REVIEW', 'Manual Review'),
        ('CANCELLED', 'Cancelled'),
    ]
    PROCESSING_STAGES = [
        ('READING_CSV_ROW', 'Reading CSV Row'),
        ('GENERATING_270', 'Generating 270 Request'),
        ('SAVING_270', 'Saving 270'),
        ('SENDING_TO_EMEDNY', 'Sending to eMedNY'),
        ('WAITING_FOR_EMEDNY', 'Waiting for eMedNY'),
        ('RECEIVING_271', 'Receiving 271'),
        ('SAVING_RAW_RESPONSE', 'Saving Raw Response'),
        ('PARSING_271', 'Parsing 271'),
        ('EXTRACTING_PATIENT', 'Extracting Patient'),
        ('UPDATING_PATIENT', 'Updating Patient'),
        ('EXTRACTING_RECERTIFICATION', 'Extracting Recertification'),
        ('EXTRACTING_NHTD', 'Extracting NHTD'),
        ('EXTRACTING_CODE_60', 'Extracting Code 60'),
        ('EXTRACTING_SURPLUS', 'Extracting Surplus'),
        ('SAVING_ELIGIBILITY', 'Saving Eligibility'),
        ('COMPLETING_ROW', 'Completing Row'),
        ('COMPLETED', 'Completed'),
    ]
    PATIENT_ACTIONS = [
        ('CREATED', 'Created'),
        ('UPDATED', 'Updated'),
        ('UNCHANGED', 'Unchanged'),
        ('NOT_CREATED', 'Not Created'),
    ]

    import_batch = models.ForeignKey(ImportBatch, on_delete=models.CASCADE, related_name='rows')
    row_number = models.IntegerField()
    cin = models.CharField(max_length=20, db_index=True)
    patient = models.ForeignKey(
        'patients.Patient', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='import_rows'
    )
    status = models.CharField(max_length=30, choices=ROW_STATUSES, default='PENDING', db_index=True)
    processing_stage = models.CharField(max_length=40, choices=PROCESSING_STAGES, blank=True, db_index=True)
    patient_action = models.CharField(max_length=20, choices=PATIENT_ACTIONS, blank=True)
    validation_error = models.TextField(blank=True)
    processing_error = models.TextField(blank=True)
    rejection_description = models.TextField(blank=True)
    retry_count = models.IntegerField(default=0)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [('import_batch', 'row_number')]
        indexes = [
            models.Index(fields=['import_batch', 'status']),
            models.Index(fields=['cin']),
            models.Index(fields=['processing_stage']),
        ]
        ordering = ['row_number']

    def __str__(self):
        return f"Row {self.row_number} CIN={self.cin} ({self.status})"

    def set_stage(self, stage, status=None):
        """Update processing stage and optionally status."""
        update_fields = ['processing_stage', 'updated_at']
        self.processing_stage = stage
        if status:
            self.status = status
            update_fields.append('status')
        self.save(update_fields=update_fields)

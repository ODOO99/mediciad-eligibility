from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='ImportBatch',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('file_name', models.CharField(max_length=255)),
                ('file_hash', models.CharField(blank=True, max_length=64)),
                ('date_of_service', models.DateField()),
                ('total_rows', models.IntegerField(default=0)),
                ('valid_rows', models.IntegerField(default=0)),
                ('invalid_rows', models.IntegerField(default=0)),
                ('duplicate_rows', models.IntegerField(default=0)),
                ('processed_rows', models.IntegerField(default=0)),
                ('created_patients', models.IntegerField(default=0)),
                ('updated_patients', models.IntegerField(default=0)),
                ('unchanged_patients', models.IntegerField(default=0)),
                ('rejected_rows', models.IntegerField(default=0)),
                ('failed_rows', models.IntegerField(default=0)),
                ('cancelled_rows', models.IntegerField(default=0)),
                ('status', models.CharField(choices=[('PENDING','Pending'),('UPLOADING','Uploading'),('VALIDATING','Validating'),('PROCESSING','Processing'),('COMPLETED','Completed'),('PARTIALLY_COMPLETED','Partially Completed'),('FAILED','Failed'),('CANCELLING','Cancelling'),('CANCELLED','Cancelled')], db_index=True, default='PENDING', max_length=30)),
                ('started_at', models.DateTimeField(blank=True, null=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={'ordering': ['-created_at']},
        ),
        migrations.CreateModel(
            name='ImportRow',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('row_number', models.IntegerField()),
                ('cin', models.CharField(db_index=True, max_length=20)),
                ('status', models.CharField(choices=[('PENDING','Pending'),('DUPLICATE','Duplicate'),('VALIDATION_FAILED','Validation Failed'),('PROCESSING','Processing'),('REQUEST_GENERATED','Request Generated'),('REQUEST_SENT','Request Sent'),('WAITING_FOR_RESPONSE','Waiting for Response'),('RESPONSE_RECEIVED','Response Received'),('PARSING_RESPONSE','Parsing Response'),('UPDATING_PATIENT','Updating Patient'),('SAVING_ELIGIBILITY','Saving Eligibility'),('COMPLETED','Completed'),('REJECTED','Rejected'),('TECHNICAL_FAILURE','Technical Failure'),('RETRY_PENDING','Retry Pending'),('MANUAL_REVIEW','Manual Review'),('CANCELLED','Cancelled')], db_index=True, default='PENDING', max_length=30)),
                ('processing_stage', models.CharField(blank=True, choices=[('READING_CSV_ROW','Reading CSV Row'),('GENERATING_270','Generating 270 Request'),('SAVING_270','Saving 270'),('SENDING_TO_EMEDNY','Sending to eMedNY'),('WAITING_FOR_EMEDNY','Waiting for eMedNY'),('RECEIVING_271','Receiving 271'),('SAVING_RAW_RESPONSE','Saving Raw Response'),('PARSING_271','Parsing 271'),('EXTRACTING_PATIENT','Extracting Patient'),('UPDATING_PATIENT','Updating Patient'),('EXTRACTING_RECERTIFICATION','Extracting Recertification'),('EXTRACTING_NHTD','Extracting NHTD'),('EXTRACTING_CODE_60','Extracting Code 60'),('EXTRACTING_SURPLUS','Extracting Surplus'),('SAVING_ELIGIBILITY','Saving Eligibility'),('COMPLETING_ROW','Completing Row'),('COMPLETED','Completed')], db_index=True, max_length=40)),
                ('patient_action', models.CharField(blank=True, choices=[('CREATED','Created'),('UPDATED','Updated'),('UNCHANGED','Unchanged'),('NOT_CREATED','Not Created')], max_length=20)),
                ('validation_error', models.TextField(blank=True)),
                ('processing_error', models.TextField(blank=True)),
                ('rejection_description', models.TextField(blank=True)),
                ('retry_count', models.IntegerField(default=0)),
                ('started_at', models.DateTimeField(blank=True, null=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('import_batch', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='rows', to='imports.importbatch')),
                ('patient', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='import_rows', to='patients.patient')),
            ],
            options={'ordering': ['row_number']},
        ),
        migrations.AddIndex(
            model_name='importbatch',
            index=models.Index(fields=['status'], name='imports_batch_status_idx'),
        ),
        migrations.AddIndex(
            model_name='importbatch',
            index=models.Index(fields=['created_at'], name='imports_batch_created_idx'),
        ),
        migrations.AddIndex(
            model_name='importrow',
            index=models.Index(fields=['import_batch', 'status'], name='imports_row_batch_status_idx'),
        ),
        migrations.AddIndex(
            model_name='importrow',
            index=models.Index(fields=['cin'], name='imports_row_cin_idx'),
        ),
        migrations.AddIndex(
            model_name='importrow',
            index=models.Index(fields=['processing_stage'], name='imports_row_stage_idx'),
        ),
        migrations.AlterUniqueTogether(
            name='importrow',
            unique_together={('import_batch', 'row_number')},
        ),
    ]

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('patients', '0001_initial'),
        ('eligibility', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='PatientChangeHistory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('field_name', models.CharField(max_length=100)),
                ('old_value', models.TextField(blank=True)),
                ('new_value', models.TextField(blank=True)),
                ('change_type', models.CharField(choices=[('CREATED', 'Created'), ('UPDATED', 'Updated'), ('CONFLICT', 'Conflict'), ('IGNORED', 'Ignored')], max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('patient', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='change_history', to='patients.patient')),
                ('eligibility_response', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='patient_changes', to='eligibility.eligibilityresponse')),
            ],
            options={'ordering': ['-created_at']},
        ),
        migrations.CreateModel(
            name='PatientDataConflict',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('field_name', models.CharField(max_length=100)),
                ('existing_value', models.TextField(blank=True)),
                ('returned_value', models.TextField(blank=True)),
                ('status', models.CharField(choices=[('OPEN', 'Open'), ('ACCEPTED', 'Accepted'), ('REJECTED', 'Rejected')], default='OPEN', max_length=20)),
                ('resolved_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('patient', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='data_conflicts', to='patients.patient')),
                ('eligibility_response', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='patient_conflicts', to='eligibility.eligibilityresponse')),
            ],
            options={'ordering': ['-created_at']},
        ),
    ]

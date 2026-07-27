"""Tests for Django models."""
import pytest
from datetime import date
from django.test import TestCase


@pytest.mark.django_db
class TestPatientModel:

    def test_unique_cin(self):
        from patients.models import Patient
        Patient.objects.create(cin='TEST001')
        with pytest.raises(Exception):
            Patient.objects.create(cin='TEST001')

    def test_full_name(self):
        from patients.models import Patient
        p = Patient(first_name='John', middle_name='M', last_name='Smith')
        assert p.full_name == 'John M Smith'

    def test_full_name_without_middle(self):
        from patients.models import Patient
        p = Patient(first_name='John', last_name='Smith')
        assert p.full_name == 'John Smith'


@pytest.mark.django_db
class TestImportBatch:

    def test_remaining_rows(self):
        from imports.models import ImportBatch
        batch = ImportBatch.objects.create(
            file_name='test.csv',
            date_of_service=date(2024, 1, 1),
            total_rows=10,
            valid_rows=10,
            processed_rows=3,
        )
        assert batch.remaining_rows == 7

    def test_percentage_complete(self):
        from imports.models import ImportBatch
        batch = ImportBatch(valid_rows=100, processed_rows=42)
        assert batch.percentage_complete == 42

    def test_percentage_zero_valid(self):
        from imports.models import ImportBatch
        batch = ImportBatch(valid_rows=0, processed_rows=0)
        assert batch.percentage_complete == 0


@pytest.mark.django_db
class TestImportRowUnique:

    def test_unique_batch_row_number(self):
        from imports.models import ImportBatch, ImportRow
        batch = ImportBatch.objects.create(
            file_name='test.csv',
            date_of_service=date(2024, 1, 1),
        )
        ImportRow.objects.create(import_batch=batch, row_number=1, cin='AB12345C')
        with pytest.raises(Exception):
            ImportRow.objects.create(import_batch=batch, row_number=1, cin='CD67890D')


@pytest.mark.django_db
class TestSnapshotCurrentFlag:

    def _make_patient(self, cin='SNAP001'):
        from patients.models import Patient
        return Patient.objects.create(cin=cin)

    def _make_request(self, patient, batch):
        from imports.models import ImportRow
        from eligibility.models import EligibilityRequest
        row = ImportRow.objects.create(
            import_batch=batch, row_number=1, cin=patient.cin
        )
        return EligibilityRequest.objects.create(
            import_row=row, cin=patient.cin,
            date_of_service=date(2024, 1, 1),
        )

    def test_only_one_current_snapshot(self):
        from patients.models import Patient
        from imports.models import ImportBatch, ImportRow
        from eligibility.models import (
            EligibilityRequest, EligibilityResponse, PatientEligibilitySnapshot
        )
        patient = Patient.objects.create(cin='SNAP999')
        batch = ImportBatch.objects.create(file_name='t.csv', date_of_service=date(2024, 1, 1))
        row1 = ImportRow.objects.create(import_batch=batch, row_number=1, cin='SNAP999')
        row2 = ImportRow.objects.create(import_batch=batch, row_number=2, cin='SNAP999')
        req1 = EligibilityRequest.objects.create(import_row=row1, cin='SNAP999', date_of_service=date(2024, 1, 1))
        req2 = EligibilityRequest.objects.create(import_row=row2, cin='SNAP999', date_of_service=date(2024, 2, 1))
        resp1 = EligibilityResponse.objects.create(eligibility_request=req1, response_status='ELIGIBLE')
        resp2 = EligibilityResponse.objects.create(eligibility_request=req2, response_status='ELIGIBLE')

        snap1 = PatientEligibilitySnapshot.objects.create(
            patient=patient, eligibility_response=resp1,
            date_of_service=date(2024, 1, 1), is_current=True
        )
        # Simulate marking old as not current
        PatientEligibilitySnapshot.objects.filter(patient=patient, is_current=True).update(is_current=False)
        snap2 = PatientEligibilitySnapshot.objects.create(
            patient=patient, eligibility_response=resp2,
            date_of_service=date(2024, 2, 1), is_current=True
        )

        current = PatientEligibilitySnapshot.objects.filter(patient=patient, is_current=True)
        assert current.count() == 1
        assert current.first().id == snap2.id

        # Old snapshot must still exist
        assert PatientEligibilitySnapshot.objects.filter(patient=patient).count() == 2

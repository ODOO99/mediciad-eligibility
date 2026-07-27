"""Tests for X12 270 request builder."""
import pytest
from datetime import date
from emedny.builder import EligibilityRequestBuilder


class TestBuilder:

    def setup_method(self):
        self.builder = EligibilityRequestBuilder()

    def test_build_returns_x12_payload(self):
        result = self.builder.build(cin='AB12345C', date_of_service=date(2024, 1, 1))
        assert 'x12_payload' in result
        assert 'ST*270' in result['x12_payload']

    def test_cin_in_nm1_segment(self):
        result = self.builder.build(cin='AB12345C', date_of_service=date(2024, 1, 1))
        assert 'MI*AB12345C' in result['x12_payload']

    def test_date_of_service_in_dtp(self):
        result = self.builder.build(cin='AB12345C', date_of_service=date(2024, 6, 15))
        assert 'DTP*291*D8*20240615' in result['x12_payload']

    def test_payload_id_is_present(self):
        result = self.builder.build(cin='AB12345C', date_of_service=date(2024, 1, 1))
        assert result['payload_id']
        assert '-' in result['payload_id']  # UUID format

    def test_control_numbers_are_present(self):
        result = self.builder.build(cin='AB12345C', date_of_service=date(2024, 1, 1))
        assert result['isa_control_number']
        assert result['gs_control_number']
        assert result['st_control_number']

    def test_soap_envelope_contains_core_elements(self):
        result = self.builder.build(cin='AB12345C', date_of_service=date(2024, 1, 1))
        soap = result['soap_body']
        assert 'COREEnvelopeRealTimeRequest' in soap
        assert 'X12_270_Request_005010X279A1' in soap
        assert result['payload_id'] in soap

    def test_service_type_code_default(self):
        result = self.builder.build(cin='AB12345C', date_of_service=date(2024, 1, 1))
        assert 'EQ*30' in result['x12_payload']

    def test_custom_service_type_code(self):
        result = self.builder.build(cin='AB12345C', date_of_service=date(2024, 1, 1), service_type_code='1')
        assert 'EQ*1' in result['x12_payload']

    def test_isa_segment_structure(self):
        result = self.builder.build(cin='AB12345C', date_of_service=date(2024, 1, 1))
        payload = result['x12_payload']
        assert payload.startswith('ISA*')
        assert 'GS*HS*' in payload

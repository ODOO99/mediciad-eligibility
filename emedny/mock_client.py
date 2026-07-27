"""
Mock eMedNY client for development and testing.
Returns realistic X12 271 responses based on CIN patterns.

CIN patterns:
  Starts with 'ERR'  → Technical failure
  Starts with 'NF'   → Member not found
  Starts with 'REJ'  → Business rejection
  Starts with 'NHTD' → NHTD waiver
  Starts with 'C60'  → Code 60
  Starts with 'SURP' → Surplus
  Otherwise          → Eligible member
"""
import logging
import time
import random
from datetime import date, timedelta

logger = logging.getLogger(__name__)


class MockEmednyCoreClient:
    """Returns mock 271 responses for development and testing."""

    def submit(self, request_data):
        """Simulate eMedNY submission with a brief delay."""
        cin = request_data.get('cin', '')
        dos = request_data.get('date_of_service', '')
        isa_ctrl = request_data.get('isa_control_number', '000000001')

        # Simulate network latency
        time.sleep(random.uniform(0.1, 0.5))

        if cin.upper().startswith('ERR'):
            return self._technical_failure(cin)
        if cin.upper().startswith('NF'):
            return self._member_not_found(cin, isa_ctrl)
        if cin.upper().startswith('REJ'):
            return self._rejection(cin, isa_ctrl)

        return self._eligible_response(cin, dos, isa_ctrl)

    def _eligible_response(self, cin, dos, isa_ctrl):
        has_nhtd = cin.upper().startswith('NHTD')
        has_code_60 = cin.upper().startswith('C60')
        has_surplus = cin.upper().startswith('SURP')
        has_recert = cin.upper().startswith('REC') or not (has_nhtd or has_code_60 or has_surplus)

        today = date.today()
        recert_month = (today.month % 12) + 1
        begin_date = (today - timedelta(days=180)).strftime('%Y%m%d')
        end_date = (today + timedelta(days=180)).strftime('%Y%m%d')

        segments = [
            f'ISA*00*          *00*          *ZZ*{cin[:15]:<15}*ZZ*EMEDNYREL       *{today.strftime("%y%m%d")}*1200*|*00501*{isa_ctrl}*0*T*:',
            'GS*HB*EMEDNY*SENDER*20240101*1200*1*X*005010X279A1',
            'ST*271*0001*005010X279A1',
            f'BHT*0022*11*{today.strftime("%Y%m%d")}1200*{today.strftime("%Y%m%d")}*1200',
            'HL*1**20*1',
            'NM1*PR*2*NYSDOH*****PI*EMEDNY',
            'HL*2*1*21*1',
            'NM1*1P*2*TEST PROVIDER*****SV*TEST001',
            'HL*3*2*22*0',
            f'TRN*2*{today.strftime("%Y%m%d")}120001*9TEST00001',
            f'NM1*IL*1*DOE*JOHN*M***MI*{cin}',
            'DMG*D8*19800115*M',
            f'DTP*291*D8*{dos or today.strftime("%Y%m%d")}',
            f'EB*1**30*MC*MEDICAID FFS**27*{begin_date}*{end_date}',
            f'DTP*346*D8*{begin_date}',
            f'DTP*347*D8*{end_date}',
            'EB*1**1*MC*MEDICAID',
        ]

        if has_nhtd:
            segments.append('MSG*NHTD')

        if has_code_60:
            segments.append('EB*1**60*MC*SKILLED NURSING CARE')

        if has_surplus:
            segments.append('EB*B**30***215.00')

        if has_recert:
            segments.append(f'MSG*RECERT MONTH={recert_month}')

        segments.append('MSG*CNTY CD=01 034')
        segments.append('SE*20*0001')
        segments.append('GE*1*1')
        segments.append(f'IEA*1*{isa_ctrl}')

        x12 = '~'.join(segments) + '~'

        return {
            'raw_response': f'<MockSOAPResponse><Payload><![CDATA[{x12}]]></Payload></MockSOAPResponse>',
            'x12_response': x12,
            'response_type': 'X12_271',
            'error': None,
            'error_code': '',
            'error_message': '',
        }

    def _member_not_found(self, cin, isa_ctrl):
        today = date.today()
        x12 = (
            f'ISA*00*          *00*          *ZZ*{cin[:15]:<15}*ZZ*EMEDNYREL       *{today.strftime("%y%m%d")}*1200*|*00501*{isa_ctrl}*0*T*:~'
            'GS*HB*EMEDNY*SENDER*20240101*1200*1*X*005010X279A1~'
            'ST*271*0001*005010X279A1~'
            f'BHT*0022*11*{today.strftime("%Y%m%d")}1200*{today.strftime("%Y%m%d")}*1200~'
            'HL*1**20*1~'
            'NM1*PR*2*NYSDOH*****PI*EMEDNY~'
            'HL*2*1*21*1~'
            'NM1*1P*2*TEST PROVIDER*****SV*TEST001~'
            'HL*3*2*22*0~'
            f'TRN*2*{today.strftime("%Y%m%d")}120001*9TEST00001~'
            f'NM1*IL*1*******MI*{cin}~'
            'AAA*N**75*C~'
            'SE*12*0001~'
            'GE*1*1~'
            f'IEA*1*{isa_ctrl}~'
        )
        return {
            'raw_response': f'<MockSOAPResponse><Payload><![CDATA[{x12}]]></Payload></MockSOAPResponse>',
            'x12_response': x12,
            'response_type': 'X12_271',
            'error': None,
            'error_code': '',
            'error_message': '',
        }

    def _rejection(self, cin, isa_ctrl):
        today = date.today()
        x12 = (
            f'ISA*00*          *00*          *ZZ*{cin[:15]:<15}*ZZ*EMEDNYREL       *{today.strftime("%y%m%d")}*1200*|*00501*{isa_ctrl}*0*T*:~'
            'GS*HB*EMEDNY*SENDER*20240101*1200*1*X*005010X279A1~'
            'ST*271*0001*005010X279A1~'
            f'BHT*0022*11*{today.strftime("%Y%m%d")}1200*{today.strftime("%Y%m%d")}*1200~'
            'HL*1**20*1~'
            'NM1*PR*2*NYSDOH*****PI*EMEDNY~'
            'HL*2*1*21*1~'
            'NM1*1P*2*TEST PROVIDER*****SV*TEST001~'
            'HL*3*2*22*0~'
            f'TRN*2*{today.strftime("%Y%m%d")}120001*9TEST00001~'
            f'NM1*IL*1*******MI*{cin}~'
            'AAA*N**53*C~'
            'SE*12*0001~'
            'GE*1*1~'
            f'IEA*1*{isa_ctrl}~'
        )
        return {
            'raw_response': f'<MockSOAPResponse><Payload><![CDATA[{x12}]]></Payload></MockSOAPResponse>',
            'x12_response': x12,
            'response_type': 'X12_271',
            'error': None,
            'error_code': '',
            'error_message': '',
        }

    def _technical_failure(self, cin):
        return {
            'raw_response': '',
            'x12_response': '',
            'response_type': 'HTTP_ERROR',
            'error': f'Mock technical failure for CIN {cin}',
            'error_type': 'NETWORK_TIMEOUT',
            'error_code': '',
            'error_message': 'Simulated network timeout',
        }

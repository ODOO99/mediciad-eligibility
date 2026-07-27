"""Tests for X12 271 parser."""
import pytest
from decimal import Decimal
from emedny.parser import EligibilityResponseParser


PARSER = EligibilityResponseParser()


ELIGIBLE_271 = (
    "ISA*00*          *00*          *ZZ*TESTSENDER      *ZZ*EMEDNYREL       *240101*1200*|*00501*000000001*0*T*:~"
    "GS*HB*EMEDNY*SENDER*20240101*1200*1*X*005010X279A1~"
    "ST*271*0001*005010X279A1~"
    "BHT*0022*11*20240101120000*20240101*1200~"
    "HL*1**20*1~"
    "NM1*PR*2*NYSDOH*****PI*EMEDNY~"
    "HL*2*1*21*1~"
    "NM1*1P*2*TEST PROVIDER*****SV*TEST001~"
    "HL*3*2*22*0~"
    "TRN*2*20240101120001*9TEST00001~"
    "NM1*IL*1*SMITH*JOHN*M***MI*AB12345C~"
    "N3*123 MAIN STREET~"
    "N4*ALBANY*NY*12201~"
    "DMG*D8*19800115*M~"
    "DTP*291*D8*20240101~"
    "EB*1**30*MC*MEDICAID FFS**27*20240101*20241231~"
    "DTP*346*D8*20240101~"
    "DTP*347*D8*20241231~"
    "MSG*RECERT MONTH=6~"
    "MSG*CNTY CD=01 034~"
    "SE*20*0001~"
    "GE*1*1~"
    "IEA*1*000000001~"
)

MEMBER_NOT_FOUND_271 = (
    "ISA*00*          *00*          *ZZ*TESTSENDER      *ZZ*EMEDNYREL       *240101*1200*|*00501*000000002*0*T*:~"
    "GS*HB*EMEDNY*SENDER*20240101*1200*2*X*005010X279A1~"
    "ST*271*0001*005010X279A1~"
    "BHT*0022*11*20240101120000*20240101*1200~"
    "HL*1**20*1~"
    "NM1*PR*2*NYSDOH*****PI*EMEDNY~"
    "HL*2*1*21*1~"
    "NM1*1P*2*TEST PROVIDER*****SV*TEST001~"
    "HL*3*2*22*0~"
    "TRN*2*20240101120001*9TEST00001~"
    "NM1*IL*1*******MI*NF00001~"
    "AAA*N**75*C~"
    "SE*12*0001~"
    "GE*1*1~"
    "IEA*1*000000002~"
)

NHTD_271 = (
    ELIGIBLE_271.replace("MSG*RECERT MONTH=6~", "MSG*NHTD~MSG*RECERT MONTH=6~")
)

CODE_60_271 = (
    ELIGIBLE_271 + "EB*1**60*MC*SKILLED NURSING CARE~"
).replace("SE*20*0001~", "EB*1**60*MC*SKILLED NURSING CARE~SE*21*0001~")

SURPLUS_271 = (
    ELIGIBLE_271.replace("SE*20*0001~", "EB*B**30***215.00~SE*21*0001~")
)


class TestParser:

    def test_eligible_member(self):
        result = PARSER.parse(ELIGIBLE_271)
        assert result['member_found'] is True
        assert result['is_active'] is True
        assert result['demographics']['last_name'] == 'SMITH'
        assert result['demographics']['first_name'] == 'JOHN'
        assert result['returned_cin'] == 'AB12345C'
        assert result['overall_status'] == 'ELIGIBLE'

    def test_member_demographics(self):
        result = PARSER.parse(ELIGIBLE_271)
        assert result['demographics']['city'] == 'ALBANY'
        assert result['demographics']['state'] == 'NY'
        assert result['demographics']['postal_code'] == '12201'
        assert result['demographics']['gender'] == 'M'

    def test_coverage_dates(self):
        result = PARSER.parse(ELIGIBLE_271)
        from datetime import date
        assert result['coverage_start_date'] == date(2024, 1, 1)
        assert result['coverage_end_date'] == date(2024, 12, 31)

    def test_recertification(self):
        result = PARSER.parse(ELIGIBLE_271)
        assert result['recertification_month'] == '6'

    def test_member_not_found(self):
        result = PARSER.parse(MEMBER_NOT_FOUND_271)
        assert result['member_found'] is False
        assert len(result['rejections']) == 1
        assert result['rejections'][0]['reject_code'] == '75'

    def test_nhtd_detection(self):
        result = PARSER.parse(NHTD_271)
        assert result['nhtd_from_msg'] is True

    def test_code_60_detection(self):
        x12 = (
            "ISA*00*          *00*          *ZZ*TESTSENDER      *ZZ*EMEDNYREL       *240101*1200*|*00501*000000003*0*T*:~"
            "GS*HB*EMEDNY*SENDER*20240101*1200*3*X*005010X279A1~"
            "ST*271*0001*005010X279A1~"
            "BHT*0022*11*20240101120000*20240101*1200~"
            "HL*1**20*1~"
            "NM1*PR*2*NYSDOH*****PI*EMEDNY~"
            "HL*2*1*21*1~"
            "NM1*1P*2*TEST PROVIDER*****SV*TEST001~"
            "HL*3*2*22*0~"
            "TRN*2*20240101120001*9TEST00001~"
            "NM1*IL*1*JONES*MARY***MI*C60TESTCIN~"
            "DMG*D8*19850601*F~"
            "DTP*291*D8*20240101~"
            "EB*1**30*MC*MEDICAID~"
            "EB*1**60*MC*SKILLED NURSING~"
            "SE*15*0001~"
            "GE*1*1~"
            "IEA*1*000000003~"
        )
        result = PARSER.parse(x12)
        assert result['raw_code_60_eb'] is True

    def test_surplus_detection(self):
        x12 = (
            "ISA*00*          *00*          *ZZ*TESTSENDER      *ZZ*EMEDNYREL       *240101*1200*|*00501*000000004*0*T*:~"
            "GS*HB*EMEDNY*SENDER*20240101*1200*4*X*005010X279A1~"
            "ST*271*0001*005010X279A1~"
            "BHT*0022*11*20240101120000*20240101*1200~"
            "HL*1**20*1~"
            "NM1*PR*2*NYSDOH*****PI*EMEDNY~"
            "HL*2*1*21*1~"
            "NM1*1P*2*TEST PROVIDER*****SV*TEST001~"
            "HL*3*2*22*0~"
            "TRN*2*20240101120001*9TEST00001~"
            "NM1*IL*1*DOE*JANE***MI*SURP0001~"
            "DMG*D8*19900301*F~"
            "DTP*291*D8*20240101~"
            "EB*1**30*MC*MEDICAID~"
            "EB*B**30***215.00~"
            "SE*14*0001~"
            "GE*1*1~"
            "IEA*1*000000004~"
        )
        result = PARSER.parse(x12)
        assert result['copay_amount'] == Decimal('215.00')

    def test_empty_response(self):
        result = PARSER.parse('')
        assert result['member_found'] is False
        assert result['warnings']

    def test_missing_segments(self):
        result = PARSER.parse("ISA*test~GS*test~")
        assert result['member_found'] is False

    def test_parser_warnings_list(self):
        result = PARSER.parse(ELIGIBLE_271)
        assert isinstance(result['warnings'], list)

    def test_county_code_parsing(self):
        result = PARSER.parse(ELIGIBLE_271)
        assert result['county_code'] == '01'
        assert result['office_code'] == '034'

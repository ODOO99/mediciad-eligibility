"""Tests for EligibilityClassifier."""
import pytest
from decimal import Decimal
from emedny.classifier import EligibilityClassifier
from emedny.parser import EligibilityResponseParser


CLASSIFIER = EligibilityClassifier()
PARSER = EligibilityResponseParser()


class TestClassifier:

    def _parse(self, x12):
        return PARSER.parse(x12)

    def _classify(self, x12):
        return CLASSIFIER.classify(self._parse(x12))

    def test_recertification_from_msg(self):
        x12 = (
            "ISA*00*          *00*          *ZZ*TEST           *ZZ*EMEDNYREL       *240101*1200*|*00501*000000001*0*T*:~"
            "ST*271*0001~NM1*IL*1*SMITH*JOHN***MI*AB12345C~"
            "EB*1**30*MC*MEDICAID~MSG*RECERT MONTH=8~SE*5*0001~IEA*1*000000001~"
        )
        result = self._classify(x12)
        assert result['has_recertification'] is True
        assert len([i for i in result['indicators'] if i['indicator_type'] == 'RECERTIFICATION']) == 1

    def test_nhtd_from_msg(self):
        x12 = (
            "ISA*00*          *00*          *ZZ*TEST           *ZZ*EMEDNYREL       *240101*1200*|*00501*000000002*0*T*:~"
            "ST*271*0001~NM1*IL*1*DOE*JOHN***MI*NHTD0001~"
            "EB*1**30*MC*MEDICAID~MSG*NHTD~SE*5*0001~IEA*1*000000002~"
        )
        result = self._classify(x12)
        assert result['has_nhtd'] is True

    def test_code_60_from_eb03(self):
        x12 = (
            "ISA*00*          *00*          *ZZ*TEST           *ZZ*EMEDNYREL       *240101*1200*|*00501*000000003*0*T*:~"
            "ST*271*0001~NM1*IL*1*DOE*JANE***MI*C600001~"
            "EB*1**30*MC*MEDICAID~EB*1**60*MC*SKILLED~SE*5*0001~IEA*1*000000003~"
        )
        result = self._classify(x12)
        assert result['has_code_60'] is True
        ind = next((i for i in result['indicators'] if i['indicator_type'] == 'CODE_60'), None)
        assert ind is not None
        assert ind['source_segment'] == 'EB'
        assert ind['source_element'] == 'EB03'
        assert ind['indicator_code'] == '60'

    def test_code_60_not_from_string_search(self):
        """Code 60 must NOT be triggered by the number 60 appearing anywhere in raw text."""
        x12 = (
            "ISA*00*          *00*          *ZZ*TEST           *ZZ*EMEDNYREL       *240101*1200*|*00501*000000099*0*T*:~"
            "ST*271*0001~NM1*IL*1*SIXTY*JOHN***MI*NUM600001~"
            "EB*1**30*MC*MEDICAID PLAN 60MG~MSG*60 tablets~SE*4*0001~IEA*1*000000099~"
        )
        result = self._classify(x12)
        # Code 60 must NOT be flagged — '60' only appears in plan description and MSG text, not EB03
        assert result['has_code_60'] is False

    def test_surplus_from_eb_copay(self):
        x12 = (
            "ISA*00*          *00*          *ZZ*TEST           *ZZ*EMEDNYREL       *240101*1200*|*00501*000000004*0*T*:~"
            "ST*271*0001~NM1*IL*1*JONES*MARY***MI*SURP0002~"
            "EB*1**30*MC*MEDICAID~EB*B**30***215.00~SE*4*0001~IEA*1*000000004~"
        )
        result = self._classify(x12)
        assert result['has_surplus'] is True
        assert result['surplus_amount'] == Decimal('215.00')

    def test_no_indicators_for_plain_eligible(self):
        x12 = (
            "ISA*00*          *00*          *ZZ*TEST           *ZZ*EMEDNYREL       *240101*1200*|*00501*000000005*0*T*:~"
            "ST*271*0001~NM1*IL*1*PLAIN*JOHN***MI*PLAIN001~"
            "EB*1**30*MC*MEDICAID~SE*3*0001~IEA*1*000000005~"
        )
        result = self._classify(x12)
        assert result['has_recertification'] is False
        assert result['has_nhtd'] is False
        assert result['has_code_60'] is False
        assert result['has_surplus'] is False

    def test_indicators_have_source_fields(self):
        x12 = (
            "ISA*00*          *00*          *ZZ*TEST           *ZZ*EMEDNYREL       *240101*1200*|*00501*000000006*0*T*:~"
            "ST*271*0001~NM1*IL*1*SMITH*JOHN***MI*AB12345C~"
            "EB*1**30*MC*MEDICAID~MSG*RECERT MONTH=3~SE*4*0001~IEA*1*000000006~"
        )
        result = self._classify(x12)
        assert result['has_recertification']
        ind = result['indicators'][0]
        assert ind['source_segment']
        assert ind['source_element']

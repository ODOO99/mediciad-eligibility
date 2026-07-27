"""
EligibilityClassifier — derives has_recertification, has_nhtd, has_code_60,
has_surplus, and their associated values from a parsed 271 result dict.

Classification rules are based on documented X12 segment positions and
eMedNY-specific MSG patterns. No free-text search of the raw 271 is performed.
"""
import logging
from decimal import Decimal
from .mappings import (
    CODE_60_INDICATORS,
    NHTD_INDICATORS,
    SURPLUS_INDICATORS,
    MSG_RECERTIFICATION_PREFIX,
)

logger = logging.getLogger(__name__)


class EligibilityClassifier:
    """Classifies eligibility indicators from a parsed 271 result."""

    def classify(self, parsed):
        """
        Accepts a parsed dict from EligibilityResponseParser.parse().
        Returns a classification dict with indicators list.
        """
        result = {
            'has_recertification': False,
            'recertification_date': None,
            'has_nhtd': False,
            'has_code_60': False,
            'has_surplus': False,
            'surplus_amount': None,
            'indicators': [],
        }

        self._classify_recertification(parsed, result)
        self._classify_nhtd(parsed, result)
        self._classify_code_60(parsed, result)
        self._classify_surplus(parsed, result)

        return result

    # ------------------------------------------------------------------ #
    # Recertification
    # ------------------------------------------------------------------ #
    def _classify_recertification(self, parsed, result):
        """
        Recertification is detected from:
        1. MSG segment containing 'RECERT MONTH=' (most common eMedNY pattern)
        2. DTP segment with qualifier 309 (Recertification date)
        """
        # Source 1: MSG RECERT MONTH= pattern
        if parsed.get('recertification_month'):
            result['has_recertification'] = True
            result['recertification_date'] = parsed.get('recertification_date')
            result['indicators'].append({
                'indicator_type': 'RECERTIFICATION',
                'indicator_code': 'RECERT_MONTH',
                'indicator_value': parsed['recertification_month'],
                'description': f"Recertification month: {parsed['recertification_month']}",
                'source_segment': 'MSG',
                'source_element': 'MSG01',
                'effective_from': None,
                'effective_to': result['recertification_date'],
                'is_active': True,
            })
            return  # Trust MSG source; don't double-count

        # Source 2: DTP 309
        dtp_recert = parsed.get('recertification_date_from_dtp')
        if dtp_recert:
            result['has_recertification'] = True
            result['recertification_date'] = dtp_recert
            result['indicators'].append({
                'indicator_type': 'RECERTIFICATION',
                'indicator_code': 'DTP_309',
                'indicator_value': str(dtp_recert),
                'description': f"Recertification date from DTP 309: {dtp_recert}",
                'source_segment': 'DTP',
                'source_element': 'DTP03',
                'effective_from': None,
                'effective_to': dtp_recert,
                'is_active': True,
            })

    # ------------------------------------------------------------------ #
    # NHTD (Nursing Home Transition and Diversion)
    # ------------------------------------------------------------------ #
    def _classify_nhtd(self, parsed, result):
        """
        NHTD is detected from MSG segments containing configured patterns.
        TODO: Expand detection to EB-based indicators once eMedNY
        documents the exact service type / eligibility code combination
        used for NHTD waiver identification.
        """
        # MSG-based detection
        if parsed.get('nhtd_from_msg'):
            result['has_nhtd'] = True
            result['indicators'].append({
                'indicator_type': 'NHTD',
                'indicator_code': 'NHTD_MSG',
                'indicator_value': parsed.get('nhtd_msg_source', ''),
                'description': 'NHTD waiver indicator found in MSG segment',
                'source_segment': 'MSG',
                'source_element': 'MSG01',
                'effective_from': None,
                'effective_to': None,
                'is_active': True,
            })
            return

        # EB-based detection (configured service type codes)
        # TODO: Add confirmed NHTD EB codes when eMedNY documentation is available
        nhtd_eb_codes = NHTD_INDICATORS.get('eb_service_codes', set())
        if nhtd_eb_codes:
            for benefit in parsed.get('benefits', []):
                stc = benefit.get('service_type_code', '')
                eb01 = benefit.get('benefit_information_code', '')
                if stc in nhtd_eb_codes:
                    result['has_nhtd'] = True
                    result['indicators'].append({
                        'indicator_type': 'NHTD',
                        'indicator_code': f'EB_{stc}',
                        'indicator_value': stc,
                        'description': f'NHTD indicator from EB segment service type {stc}',
                        'source_segment': 'EB',
                        'source_element': 'EB03',
                        'effective_from': None,
                        'effective_to': None,
                        'is_active': True,
                    })
                    break

    # ------------------------------------------------------------------ #
    # Code 60
    # ------------------------------------------------------------------ #
    def _classify_code_60(self, parsed, result):
        """
        Code 60 is detected ONLY when the X12 service type code '60' appears
        in EB03 (service type code element) of an EB segment.
        It is NOT detected by searching the raw 271 for the string '60'.
        """
        if parsed.get('raw_code_60_eb'):
            result['has_code_60'] = True
            result['indicators'].append({
                'indicator_type': 'CODE_60',
                'indicator_code': '60',
                'indicator_value': '60',
                'description': 'Service type code 60 found in EB03 element',
                'source_segment': parsed.get('code_60_source_segment', 'EB'),
                'source_element': parsed.get('code_60_source_element', 'EB03'),
                'effective_from': None,
                'effective_to': None,
                'is_active': True,
            })

    # ------------------------------------------------------------------ #
    # Surplus / Spend-Down
    # ------------------------------------------------------------------ #
    def _classify_surplus(self, parsed, result):
        """
        Surplus / spend-down is detected from:
        1. EB segment EB01=B (co-payment) with EB03=30 and monetary amount
        2. MSG segment patterns for SURPLUS or SPEND DOWN
        3. Financial detail records already extracted by the parser
        """
        # Source 1: Financial details already extracted from EB co-pay
        copay = parsed.get('copay_amount')
        if copay is not None:
            result['has_surplus'] = True
            result['surplus_amount'] = copay
            result['indicators'].append({
                'indicator_type': 'SURPLUS',
                'indicator_code': 'EB_COPAY',
                'indicator_value': str(copay),
                'description': f'Surplus/co-payment amount ${copay} from EB segment',
                'source_segment': 'EB',
                'source_element': 'EB08',
                'effective_from': None,
                'effective_to': None,
                'is_active': True,
            })
            return

        # Source 2: MSG-based surplus/spend-down text
        if parsed.get('surplus_from_msg'):
            result['has_surplus'] = True
            msg_text = parsed.get('surplus_msg_source', '')
            # Try to extract amount from MSG text (e.g. "SURPLUS $215.00")
            amount = self._extract_amount_from_msg(msg_text)
            result['surplus_amount'] = amount
            result['indicators'].append({
                'indicator_type': 'SURPLUS',
                'indicator_code': 'MSG_SURPLUS',
                'indicator_value': msg_text,
                'description': f'Surplus indicator from MSG segment: {msg_text}',
                'source_segment': 'MSG',
                'source_element': 'MSG01',
                'effective_from': None,
                'effective_to': None,
                'is_active': True,
            })

    @staticmethod
    def _extract_amount_from_msg(msg_text):
        """Attempt to extract a dollar amount from a MSG text string."""
        import re
        match = re.search(r'\$?([\d,]+\.?\d*)', msg_text)
        if match:
            try:
                return Decimal(match.group(1).replace(',', ''))
            except Exception:
                pass
        return None

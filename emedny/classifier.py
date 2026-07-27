"""
EligibilityClassifier — derives indicators from a parsed 271 result dict.
"""
import logging

logger = logging.getLogger(__name__)


class EligibilityClassifier:
    """Classifies eligibility indicators from a parsed 271 result."""

    def classify(self, parsed):
        """
        Accepts a parsed dict from EligibilityResponseParser.parse().
        Returns a classification dict with indicators list.
        """
        result = {
            'has_code_60': False,
            'has_s1': False,
            'has_recertification': False,
            'recertification_date': None,
            'indicators': [],
        }

        self._classify_code_60_and_s1(parsed, result)
        self._classify_recertification(parsed, result)

        return result

    def _classify_code_60_and_s1(self, parsed, result):
        """
        Set has_code_60 independently if MSG*60 is found.
        Set has_s1 independently if MSG*S1 is found.
        """
        if parsed.get('msg_code_60', False):
            result['has_code_60'] = True
            result['indicators'].append({
                'indicator_type': 'CODE_60',
                'indicator_code': '60',
                'indicator_value': '60',
                'description': 'Code 60 found in MSG segment',
                'source_segment': 'MSG',
                'source_element': 'MSG01',
                'effective_from': None,
                'effective_to': None,
                'is_active': True,
            })
            
        if parsed.get('msg_s1', False):
            result['has_s1'] = True
            result['indicators'].append({
                'indicator_type': 'S1',
                'indicator_code': 'S1',
                'indicator_value': 'S1',
                'description': 'S1 exemption code found in MSG segment',
                'source_segment': 'MSG',
                'source_element': 'MSG01',
                'effective_from': None,
                'effective_to': None,
                'is_active': True,
            })

    def _classify_recertification(self, parsed, result):
        """Set recertification details if present."""
        recert_date = parsed.get('recertification_date')
        if recert_date:
            result['has_recertification'] = True
            result['recertification_date'] = recert_date
            result['indicators'].append({
                'indicator_type': 'RECERTIFICATION',
                'indicator_code': 'RECERT',
                'indicator_value': str(recert_date),
                'description': 'Recertification required by this date',
                'source_segment': parsed.get('recertification_msg_source') or 'DTP',
                'effective_to': recert_date,
                'is_active': True,
            })

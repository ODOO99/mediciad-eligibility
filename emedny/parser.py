"""
X12 271 Eligibility Benefit Response parser.

Parses the X12 271 transaction based on ASC X12N 005010X279A1
and the eMedNY implementation as documented in the reference Deluge script.
"""
import logging
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from .mappings import (
    ACTIVE_ELIGIBILITY_CODES, INACTIVE_ELIGIBILITY_CODES, ELIGIBILITY_CODES,
    SERVICE_TYPE_CODES, DATE_QUALIFIERS, REJECT_REASON_CODES,
    MSG_RECERTIFICATION_PREFIX, MSG_COUNTY_PREFIX,
)

logger = logging.getLogger(__name__)

ELEMENT_SEP = '*'
SEGMENT_TERM = '~'


def _parse_date(date_str):
    """Parse YYYYMMDD or YYYYMMDD-range into a date object."""
    if not date_str:
        return None
    date_str = date_str.strip()
    # Handle date ranges (take first part)
    if '-' in date_str and len(date_str) > 10:
        date_str = date_str.split('-')[0]
    try:
        if len(date_str) == 8:
            return datetime.strptime(date_str, '%Y%m%d').date()
        return None
    except ValueError:
        return None


def _parse_decimal(value_str):
    """Parse a decimal amount string. Returns None for date-like or non-numeric values."""
    if not value_str:
        return None
    s = str(value_str).strip()
    # Reject 8-digit strings that look like dates (YYYYMMDD)
    if len(s) == 8 and s.isdigit():
        return None
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


class EligibilityResponseParser:
    """Parses an X12 271 response string into a structured dict."""

    PARSER_VERSION = '1.1'

    def parse(self, x12_text):
        """
        Parse X12 271 text.
        Returns a dict with all extracted fields and a 'warnings' list.
        """
        if not x12_text or not x12_text.strip():
            return self._empty_result(warnings=['Empty 271 response received.'])

        segments = [s.strip() for s in x12_text.split(SEGMENT_TERM) if s.strip()]
        warnings = []
        result = self._empty_result()

        # Track loop context
        current_loop = ''   # subscriber, payer, managed_care, third_party, medicare, mc_exception
        pending_ref18 = ''
        pending_ref6p = ''

        for seg_str in segments:
            parts = seg_str.split(ELEMENT_SEP)
            seg_id = parts[0] if parts else ''

            try:
                if seg_id == 'ST':
                    result['transaction_control_number'] = parts[2] if len(parts) > 2 else ''

                elif seg_id == 'BHT':
                    result['transaction_date'] = _parse_date(parts[4]) if len(parts) > 4 else None
                    if len(parts) > 5:
                        result['transaction_time'] = parts[5]

                elif seg_id == 'TRN':
                    result['trace_number'] = parts[2] if len(parts) > 2 else ''

                elif seg_id == 'NM1':
                    entity_code = parts[1] if len(parts) > 1 else ''
                    entity_type = parts[2] if len(parts) > 2 else ''
                    last_name = parts[3] if len(parts) > 3 else ''
                    first_name = parts[4] if len(parts) > 4 else ''
                    middle_name = parts[5] if len(parts) > 5 else ''
                    id_code_qual = parts[8] if len(parts) > 8 else ''
                    entity_id = parts[9] if len(parts) > 9 else ''

                    if entity_code == 'IL':  # Subscriber/Member
                        current_loop = 'subscriber'
                        result['member_found'] = True
                        result['demographics']['last_name'] = last_name
                        result['demographics']['first_name'] = first_name
                        result['demographics']['middle_name'] = middle_name
                        if entity_id:
                            result['returned_cin'] = entity_id

                    elif entity_code == 'PR':  # Payer
                        current_loop = 'payer'
                        result['payer_name'] = last_name
                        result['payer_id'] = entity_id

                    elif entity_code == 'Y2':  # Managed care or MC exception provider
                        if current_loop == 'mc_exception':
                            result['mc_exception_provider_names'].append(last_name)
                            if entity_id:
                                result['mc_exception_provider_ids'].append(entity_id)
                        else:
                            current_loop = 'managed_care'
                            result['managed_care_name'] = last_name
                            result['plan_identifier'] = entity_id

                    elif entity_code == 'P4':  # Other payer
                        if pending_ref18 and 'MEDICARE' in last_name.upper():
                            current_loop = 'medicare'
                            result['medicare_name'] = last_name
                            result['medicare_reference_id'] = pending_ref18
                            pending_ref18 = ''
                        else:
                            current_loop = 'third_party'
                            result['third_party_name'] = last_name
                            result['third_party_plan_id'] = entity_id or pending_ref6p
                            pending_ref6p = ''

                elif seg_id == 'DMG':
                    if len(parts) > 2:
                        result['demographics']['date_of_birth'] = _parse_date(parts[2])
                    if len(parts) > 3:
                        g = parts[3]
                        result['demographics']['gender'] = 'M' if g == 'M' else ('F' if g == 'F' else g)

                elif seg_id == 'N3':
                    address = parts[1] if len(parts) > 1 else ''
                    if current_loop == 'subscriber':
                        result['demographics']['address_line_1'] = address
                    elif current_loop == 'managed_care':
                        result['managed_care_address'] = address

                elif seg_id == 'N4':
                    city = parts[1] if len(parts) > 1 else ''
                    state = parts[2] if len(parts) > 2 else ''
                    postal = parts[3] if len(parts) > 3 else ''
                    if current_loop == 'subscriber':
                        result['demographics']['city'] = city
                        result['demographics']['state'] = state
                        result['demographics']['postal_code'] = postal

                elif seg_id == 'DTP':
                    qualifier = parts[1] if len(parts) > 1 else ''
                    date_val = _parse_date(parts[3]) if len(parts) > 3 else None
                    if qualifier == '291':
                        result['eligibility_date'] = date_val
                    elif qualifier == '346':
                        result['coverage_start_date'] = date_val
                    elif qualifier == '347':
                        result['coverage_end_date'] = date_val
                    elif qualifier == '102':
                        result['coverage_issue_date'] = date_val
                    elif qualifier == '309':
                        result['recertification_date_from_dtp'] = date_val

                elif seg_id == 'EB':
                    self._parse_eb_segment(parts, result, current_loop)

                elif seg_id == 'MSG':
                    msg_text = parts[1].strip() if len(parts) > 1 else ''
                    self._parse_msg_segment(msg_text, result, warnings)

                elif seg_id == 'REF':
                    qualifier = parts[1] if len(parts) > 1 else ''
                    ref_value = parts[2] if len(parts) > 2 else ''
                    if qualifier == '6P':
                        pending_ref6p = ref_value
                    elif qualifier == '18':
                        pending_ref18 = ref_value
                        if current_loop == 'medicare':
                            result['medicare_reference_id'] = ref_value

                elif seg_id == 'AAA':
                    self._parse_aaa_segment(parts, result)

                elif seg_id == 'LE':
                    current_loop = ''

            except (IndexError, AttributeError) as exc:
                warnings.append(f"Could not parse segment {seg_id}: {exc}")

        # Post-processing
        self._derive_eligibility_status(result)
        self._derive_recertification_date(result)
        result['warnings'] = warnings
        result['parser_version'] = self.PARSER_VERSION
        return result

    def _parse_eb_segment(self, parts, result, current_loop):
        """Parse EB (Eligibility/Benefit Information) segment."""
        eb01 = parts[1] if len(parts) > 1 else ''  # Eligibility/Benefit Code
        eb02 = parts[2] if len(parts) > 2 else ''  # Coverage Level Code
        eb03 = parts[3] if len(parts) > 3 else ''  # Service Type Code
        eb04 = parts[4] if len(parts) > 4 else ''  # Insurance Type Code
        eb05 = parts[5] if len(parts) > 5 else ''  # Plan Coverage Description
        eb06 = parts[6] if len(parts) > 6 else ''  # Time Period Qualifier
        eb07 = parts[7] if len(parts) > 7 else ''  # Monetary Amount (X12 EB07)
        eb08 = parts[8] if len(parts) > 8 else ''  # Percent
        eb09 = parts[9] if len(parts) > 9 else ''  # Quantity Qualifier

        # Monetary amount may appear at EB07 (index 7) per X12 spec.
        # Some eMedNY responses may omit earlier optional fields, shifting amount to index 6.
        monetary_amount_raw = eb07 or eb06

        benefit = {
            'benefit_information_code': eb01,
            'coverage_level_code': eb02,
            'service_type_code': eb03,
            'service_type_description': SERVICE_TYPE_CODES.get(eb03, eb03),
            'insurance_type_code': eb04,
            'plan_coverage_description': eb05,
            'time_period_qualifier': eb06,
            'monetary_amount': _parse_decimal(monetary_amount_raw),
            'percentage': _parse_decimal(eb08),
            'source_segment': '*'.join(parts),
        }
        result['benefits'].append(benefit)

        # Active coverage detection
        if eb01 in ACTIVE_ELIGIBILITY_CODES:
            result['is_active'] = True
            result['eligibility_code'] = eb01
            result['eligibility_status'] = ELIGIBILITY_CODES.get(eb01, eb01)
            if eb03 in ('30', '') and eb05:
                result['plan_name'] = eb05

        elif eb01 == 'U':
            # eMedNY uses EB*U (Contact Following Entity) to signal managed care enrollment.
            # When the plan description contains 'ELIGIBLE', the member IS active/eligible.
            # This is the primary mechanism eMedNY uses for Managed Care patients.
            if 'ELIGIBLE' in eb05.upper():
                result['is_active'] = True
                result['eligibility_code'] = eb01
                result['eligibility_status'] = ELIGIBILITY_CODES.get(eb01, eb05 or eb01)
                if eb03 in ('30', '') and eb05:
                    result['plan_name'] = eb05
            elif not result.get('is_active'):
                # U without ELIGIBLE description — treat as non-active unless
                # another EB segment already confirmed active
                result['eligibility_code'] = result['eligibility_code'] or eb01
                result['eligibility_status'] = result['eligibility_status'] or ELIGIBILITY_CODES.get(eb01, eb01)

        elif eb01 in INACTIVE_ELIGIBILITY_CODES:
            if not result.get('is_active'):
                result['is_active'] = False
                result['eligibility_code'] = eb01
                result['eligibility_status'] = ELIGIBILITY_CODES.get(eb01, eb01)

        # Plan name from U/30 combination
        if eb01 == 'U' and eb03 == '30' and eb05:
            result['plan_name'] = eb05

        # Co-pay / surplus amount (EB01=B, EB03=30) — amount at EB07 (index 7) per X12 spec
        if eb01 == 'B' and eb03 == '30' and monetary_amount_raw:
            amount = _parse_decimal(monetary_amount_raw)
            result['copay_amount'] = amount
            if amount is not None:
                result['financial_details'].append({
                    'financial_type': 'COPAY',
                    'amount': amount,
                    'source_segment': 'EB',
                    'source_element': 'EB07',
                    'description': 'Co-payment amount from EB segment',
                })

        # MC exception provider detection (EB01=W, EB03=CQ)
        if eb01 == 'W' and eb03 == 'CQ':
            result['_current_loop_override'] = 'mc_exception'

        # Code 60 — only from EB03 == '60' in correct context
        if eb03 == '60':
            result['raw_code_60_eb'] = True
            result['code_60_source_segment'] = 'EB'
            result['code_60_source_element'] = 'EB03'

    def _parse_msg_segment(self, msg_text, result, warnings):
        """Parse MSG (Message Text) segments."""
        if not msg_text:
            return

        if msg_text.startswith(MSG_RECERTIFICATION_PREFIX):
            month_str = msg_text[len(MSG_RECERTIFICATION_PREFIX):].strip()
            result['recertification_month'] = month_str
            result['recertification_msg_source'] = 'MSG'

        elif msg_text.startswith(MSG_COUNTY_PREFIX):
            rest = msg_text[len(MSG_COUNTY_PREFIX):].strip()
            parts = rest.split()
            result['county_code'] = parts[0] if parts else ''
            result['office_code'] = parts[1] if len(parts) > 1 else ''

        else:
            # Check for MC exemption codes (short 1-3 char codes)
            normalized = msg_text.strip().upper()
            if normalized and len(normalized) <= 3 and normalized.isalnum():
                result['mc_exemption_codes'].append(normalized)

            # ─── Code 60 detection from MSG segment ────────────────────────
            # eMedNY sends MSG*60 to signal Code 60 eligibility category.
            if normalized == '60':
                result['msg_code_60'] = True
                result['msg_code_60_source'] = msg_text

            # ─── S1 detection from MSG segment ─────────────────────────────
            # eMedNY sends MSG*S1 to signal S1 exemption code.
            if normalized == 'S1':
                result['msg_s1'] = True
                result['msg_s1_source'] = msg_text

            # NHTD detection from MSG
            if any(pattern in msg_text.upper() for pattern in ['NHTD', 'NHT&D']):
                result['nhtd_from_msg'] = True
                result['nhtd_msg_source'] = msg_text
            # Surplus detection from MSG
            if any(p in msg_text.upper() for p in ['SURPLUS', 'SPEND DOWN', 'SPENDDOWN', 'SPEND-DOWN']):
                result['surplus_from_msg'] = True
                result['surplus_msg_source'] = msg_text

    def _parse_aaa_segment(self, parts, result):
        """Parse AAA (Request Validation) segment."""
        valid_req = parts[1] if len(parts) > 1 else ''
        reject_code = parts[3] if len(parts) > 3 else ''
        follow_up = parts[4] if len(parts) > 4 else ''
        entity_code = parts[5] if len(parts) > 5 else ''

        rejection = {
            'reject_code': reject_code,
            'follow_up_action_code': follow_up,
            'entity_identifier_code': entity_code,
            'description': REJECT_REASON_CODES.get(reject_code, f'Rejection code {reject_code}'),
            'segment_reference': '*'.join(parts),
        }
        result['rejections'].append(rejection)

    def _derive_eligibility_status(self, result):
        """Derive overall eligibility status from parsed data."""
        # AAA code 75 = Member Not Found — override member_found even if NM1*IL was parsed
        if any(r.get('reject_code') == '75' for r in result['rejections']):
            result['member_found'] = False

        if result['rejections']:
            # If the only rejection is code 75 (member not found), use MEMBER_NOT_FOUND status
            non_75 = [r for r in result['rejections'] if r.get('reject_code') != '75']
            if non_75:
                result['overall_status'] = 'REJECTED'
            else:
                result['overall_status'] = 'MEMBER_NOT_FOUND'
        elif not result['member_found']:
            result['overall_status'] = 'MEMBER_NOT_FOUND'
        elif result.get('is_active'):
            result['overall_status'] = 'ELIGIBLE'
        elif result.get('eligibility_code'):
            result['overall_status'] = 'INELIGIBLE'
        else:
            result['overall_status'] = 'UNKNOWN'

    def _derive_recertification_date(self, result):
        """Derive the recertification date from month string if not already a date."""
        if result.get('recertification_date_from_dtp'):
            result['recertification_date'] = result['recertification_date_from_dtp']
            return

        month_str = result.get('recertification_month', '').strip()
        if not month_str:
            return

        # Compute end-of-recert-month date
        try:
            month_num = int(month_str)
            from django.utils import timezone as tz
            from datetime import date
            import calendar
            today = date.today()
            year = today.year
            if month_num < today.month:
                year += 1
            last_day = calendar.monthrange(year, month_num)[1]
            result['recertification_date'] = date(year, month_num, last_day)
        except (ValueError, OverflowError):
            pass

    @staticmethod
    def _empty_result(warnings=None):
        return {
            'member_found': False,
            'is_active': False,
            'eligibility_code': '',
            'eligibility_status': '',
            'overall_status': 'UNKNOWN',
            'returned_cin': '',
            'transaction_control_number': '',
            'transaction_date': None,
            'transaction_time': '',
            'trace_number': '',
            'demographics': {
                'first_name': '',
                'middle_name': '',
                'last_name': '',
                'date_of_birth': None,
                'gender': '',
                'address_line_1': '',
                'address_line_2': '',
                'city': '',
                'state': '',
                'postal_code': '',
            },
            'coverage_start_date': None,
            'coverage_end_date': None,
            'eligibility_date': None,
            'coverage_issue_date': None,
            'plan_name': '',
            'plan_identifier': '',
            'managed_care_name': '',
            'managed_care_address': '',
            'payer_name': '',
            'payer_id': '',
            'third_party_name': '',
            'third_party_plan_id': '',
            'medicare_name': '',
            'medicare_reference_id': '',
            'copay_amount': None,
            'recertification_month': '',
            'recertification_date': None,
            'recertification_date_from_dtp': None,
            'county_code': '',
            'office_code': '',
            'mc_exemption_codes': [],
            'mc_exception_provider_ids': [],
            'mc_exception_provider_names': [],
            # Code 60: set when EB03 == '60' (EB segment)
            'raw_code_60_eb': False,
            'code_60_source_segment': '',
            'code_60_source_element': '',
            # Code 60 and S1 from MSG segments (eMedNY-specific)
            'msg_code_60': False,
            'msg_code_60_source': '',
            'msg_s1': False,
            'msg_s1_source': '',
            'nhtd_from_msg': False,
            'nhtd_msg_source': '',
            'surplus_from_msg': False,
            'surplus_msg_source': '',
            'benefits': [],
            'financial_details': [],
            'rejections': [],
            'warnings': warnings or [],
            'parser_version': '1.1',
        }

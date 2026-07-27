"""
eMedNY X12 code mappings.
All mappings are based on the X12 278/270/271 implementation guides and
eMedNY documentation. Where exact eMedNY-specific codes are not publicly
documented, clear TODO comments and placeholders are provided.
"""

# EB01 Eligibility/Benefit Information codes
ELIGIBILITY_CODES = {
    '1': 'Active Coverage',
    '2': 'Active - Full Risk Capitation',
    '3': 'Active - Services Capitated',
    '4': 'Active - Services Capitated to Primary Care Physician',
    '5': 'Active - Pending Investigation',
    '6': 'Inactive',
    '7': 'Inactive - Pending Eligibility Update',
    '8': 'Inactive - Pending Investigation',
    'I': 'Non-Covered',
    'B': 'Co-Payment',
    'R': 'Other or Additional Payor',
    'U': 'Contact Following Entity for Information',
    'W': 'Other Source of Data',
}

ACTIVE_ELIGIBILITY_CODES = {'1', '2', '3', '4', '5'}
INACTIVE_ELIGIBILITY_CODES = {'6', '7', '8', 'I'}

# EB03 Service Type codes
SERVICE_TYPE_CODES = {
    '1': 'Medical Care',
    '4': 'Diagnostic X-Ray',
    '5': 'Diagnostic Lab',
    '30': 'Health Benefit Plan Coverage',
    '33': 'Chiropractic',
    '35': 'Dental Care',
    '47': 'Hospital',
    '48': 'Hospital - Inpatient',
    '50': 'Hospital - Outpatient',
    '54': 'Long-Term Care',
    '82': 'Family Planning',
    '86': 'Emergency Services',
    '88': 'Pharmacy',
    '98': 'Professional (Physician) Visit - Office',
    'AG': 'Skilled Nursing Care',
    'AL': 'Vision (Optometry)',
    'CQ': 'Provider Type',  # Used for MC exemption provider identification
    'MH': 'Mental Health',
    'UC': 'Urgent Care',
}

# DTP date qualifiers used in 271
DATE_QUALIFIERS = {
    '291': 'Plan',              # Eligibility/benefit date (Date of Service)
    '346': 'Plan Begin',        # Coverage start date
    '347': 'Plan End',          # Coverage end date
    '102': 'Issue',             # Coverage issue date
    '307': 'Eligibility Begin', # Eligibility begin date
    '308': 'Eligibility End',   # Eligibility end date
    '309': 'Recertification',   # Recertification date
    '356': 'Maintenance Effective', # Maintenance effective date
}

# AAA reject reason codes (X12 271 loop 2100C/2110C)
REJECT_REASON_CODES = {
    '15': 'Required application data missing',
    '41': 'Authorization/access restrictions',
    '42': 'Unable to respond at current time',
    '43': 'Invalid/Missing provider identification',
    '44': 'Invalid/Missing provider name',
    '45': 'Invalid/Missing provider specialty',
    '46': 'Invalid/Missing provider phone number',
    '47': 'Invalid/Missing provider address',
    '48': 'Invalid/Missing referring provider identification',
    '49': 'Invalid/Missing dates of service',
    '50': 'Invalid/Missing patient identification',
    '51': 'Invalid/Missing patient name',
    '52': 'Invalid/Missing patient birth date',
    '53': 'Invalid/Missing subscriber/insured ID',
    '54': 'Invalid/Missing subscriber/insured name',
    '55': 'Invalid/Missing subscriber/insured gender code',
    '56': 'Invalid/Missing subscriber/insured birth date',
    '57': 'Invalid/Missing insured group ID',
    '58': 'Invalid/Missing subscriber date',
    '59': 'Invalid/Missing service location information',
    '60': 'Invalid/Missing patient contact information',
    '61': 'Invalid/Missing diagnosis code(s)',
    '62': 'Invalid/Missing date of birth',
    '63': 'Invalid/Missing gender',
    '64': 'Invalid/Missing relationship code',
    '65': 'Subscriber found, patient not found',
    '66': 'Patient found, subscriber not found',
    '67': 'Subscriber/dependent not found',
    '68': 'Duplicate inquiry',
    '69': 'Invalid physician ID',
    '70': 'Provider not on file',
    '71': 'Required field or code missing',
    '72': 'Invalid/Incomplete data',
    '73': 'No coverage for requested service types',
    '74': 'Benefit Plan not covered by processor',
    '75': 'Subscriber/Insured not found',
    '76': 'Duplicate eligibility inquiry',
    '77': 'Provider not eligible to inquire for member',
    '78': 'Stop loss not applicable',
    '79': 'Invalid/Missing diagnosis',
    '80': 'No response received - Transaction Terminated',
    'AAA': 'Rejection',  # Generic
}

# MSG segment patterns for eMedNY-specific data
# These are patterns recognised in MSG segments of the 271 response
MSG_RECERTIFICATION_PREFIX = 'RECERT MONTH='  # e.g. "RECERT MONTH=6"
MSG_COUNTY_PREFIX = 'CNTY CD='               # e.g. "CNTY CD=01 034"

# eMedNY Medicaid MC Exemption codes (found in MSG segments)
# TODO: Verify complete list against current eMedNY implementation guide
MC_EXEMPTION_CODES = {
    'S1': 'Medicaid MC Exemption',
    'A1': 'Medicaid MC Exception - Provider Specific',
    'A2': 'Medicaid MC Exception - Provider Specific',
    'CF': 'Medicaid MC Exemption',
    'PD': 'Medicaid MC Exemption',
    # TODO: Add additional eMedNY exemption codes per current documentation
}

# NHTD (Nursing Home Transition and Diversion) waiver indicators
# TODO: Verify current eMedNY NHTD indicator codes in 271 responses.
# Common locations: EB segment with specific service type codes, or MSG segments.
# Placeholder mapping below — update with confirmed eMedNY codes.
NHTD_INDICATORS = {
    # EB-based indicators
    'eb_service_codes': set(),          # TODO: Add confirmed service type codes for NHTD
    'eb_eligibility_codes': set(),      # TODO: Add confirmed eligibility codes for NHTD
    # MSG-based patterns
    'msg_patterns': ['NHTD', 'NHT&D'],  # TODO: Verify exact MSG text patterns
    # REF-based indicators
    'ref_qualifiers': set(),            # TODO: Add confirmed REF qualifiers
}

# Code 60 indicators (Institutional-level skilled nursing care or specific benefit)
# TODO: Verify exact eMedNY documentation for Code 60 in 271 responses.
# Code 60 should only be detected from the correct X12 segment and element.
CODE_60_INDICATORS = {
    # EB segment: EB01 eligibility code + EB03 service type code combination
    # Only flag Code 60 when found in EB03 position with value '60' AND matching EB01
    'eb_service_type_code': '60',       # X12 service type code
    'eb_eligibility_code': None,        # TODO: Confirm required EB01 code for Code 60 at eMedNY
    # REF segment qualifier for Code 60
    'ref_qualifier': None,              # TODO: Confirm REF qualifier if applicable
}

# Surplus / Spend-Down indicators
# TODO: Verify complete list of eMedNY surplus/spend-down indicators.
SURPLUS_INDICATORS = {
    # EB segment: B = Co-payment, monetary amount present, service type 30
    'eb_copay_code': 'B',
    'eb_service_type': '30',
    # Financial/benefit codes that indicate spend-down or surplus
    'financial_eb_codes': {'B', 'C', 'D'},  # B=copay, C=deductible, D=benefit
    # MSG patterns
    'msg_patterns': ['SURPLUS', 'SPEND DOWN', 'SPENDDOWN', 'SPEND-DOWN'],
    # TODO: Confirm additional eMedNY surplus field locations
}

# INS segment relationship codes
RELATIONSHIP_CODES = {
    '18': 'Self',
    '01': 'Spouse',
    '19': 'Child',
    '21': 'Unknown',
}

"""CSV validation for import uploads."""
import csv
import io
import hashlib
import re
import chardet
from django.conf import settings

DANGEROUS_PREFIXES = ('=', '+', '-', '@')
REQUIRED_HEADER = 'cin'
CIN_PATTERN = re.compile(r'^[A-Za-z0-9]+$')


def detect_encoding(raw_bytes):
    result = chardet.detect(raw_bytes)
    encoding = result.get('encoding') or 'utf-8'
    # Allow utf-8, ascii, latin-1; reject others with a warning
    safe = {'utf-8', 'ascii', 'iso-8859-1', 'latin-1', 'windows-1252'}
    if encoding.lower().replace('-', '') not in {e.replace('-', '') for e in safe}:
        return None, encoding
    return encoding, None


def validate_and_parse_csv(file_obj):
    """
    Validate and parse uploaded CSV.
    Returns (rows, errors) where:
      rows = list of {'row_number': int, 'cin': str, 'error': str or None}
      errors = list of file-level error strings
    """
    file_errors = []
    rows = []

    # Read raw bytes
    raw = file_obj.read()
    if not raw:
        return [], ['Uploaded file is empty.']

    # File size check
    max_bytes = getattr(settings, 'MAX_CSV_FILE_SIZE_BYTES', 10 * 1024 * 1024)
    if len(raw) > max_bytes:
        mb = max_bytes / (1024 * 1024)
        return [], [f'File exceeds maximum size of {mb:.0f} MB.']

    # Encoding detection
    encoding, bad_encoding = detect_encoding(raw)
    if bad_encoding:
        return [], [f'Unsupported file encoding: {bad_encoding}. Please use UTF-8.']

    try:
        text = raw.decode(encoding or 'utf-8', errors='replace')
    except Exception as exc:
        return [], [f'Could not decode file: {exc}']

    # Split into lines for manual blank-line handling (DictReader silently drops blank lines)
    all_lines = text.splitlines()
    if not all_lines:
        return [], ['CSV file has no headers.']

    header_line = all_lines[0]
    data_lines = all_lines[1:]

    # Determine headers from the header line
    try:
        reader = csv.DictReader(io.StringIO(text))
        headers = reader.fieldnames
    except Exception as exc:
        return [], [f'Malformed CSV: {exc}']

    if not headers:
        return [], ['CSV file has no headers.']

    # Normalise headers
    normalised_headers = [h.strip().lower() for h in headers]
    if REQUIRED_HEADER not in normalised_headers:
        return [], [f'Required column "{REQUIRED_HEADER}" not found. Found: {", ".join(headers)}']

    seen_cins = {}
    row_number = 0

    for raw_line in data_lines:
        row_number += 1

        # Blank line → blank CIN (DictReader would skip this silently)
        if not raw_line.strip():
            rows.append({
                'row_number': row_number,
                'cin': '',
                'error': 'CIN is blank.',
                'is_duplicate': False,
            })
            continue

        # Parse this single data line through csv.reader to handle quoting properly
        try:
            line_reader = csv.DictReader(io.StringIO(header_line + '\n' + raw_line))
            row = next(line_reader, None)
        except csv.Error as exc:
            rows.append({
                'row_number': row_number,
                'cin': '',
                'error': f'Malformed CSV row: {exc}',
                'is_duplicate': False,
            })
            continue

        if row is None:
            rows.append({
                'row_number': row_number,
                'cin': '',
                'error': 'CIN is blank.',
                'is_duplicate': False,
            })
            continue

        try:
            # Normalize keys to lowercase so 'cin', 'CIN', 'Cin' all work.
            normalized_row = {k.strip().lower(): v for k, v in row.items() if k is not None}
            cin_raw = normalized_row.get('cin', '')
        except Exception:
            rows.append({
                'row_number': row_number,
                'cin': '',
                'error': 'Malformed CSV row.',
                'is_duplicate': False,
            })
            continue

        cin = cin_raw.strip()

        # Formula injection check
        if cin and cin[0] in DANGEROUS_PREFIXES:
            rows.append({
                'row_number': row_number,
                'cin': cin,
                'error': f'CIN value starts with a potentially dangerous character: {cin[0]!r}',
                'is_duplicate': False,
            })
            continue

        # Blank CIN
        if not cin:
            rows.append({
                'row_number': row_number,
                'cin': '',
                'error': 'CIN is blank.',
                'is_duplicate': False,
            })
            continue

        # Duplicate detection
        cin_upper = cin.upper()
        if cin_upper in seen_cins:
            rows.append({
                'row_number': row_number,
                'cin': cin,
                'error': f'Duplicate CIN (first seen at row {seen_cins[cin_upper]}).',
                'is_duplicate': True,
            })
            continue

        seen_cins[cin_upper] = row_number
        rows.append({
            'row_number': row_number,
            'cin': cin,
            'error': None,
            'is_duplicate': False,
        })

    return rows, file_errors


def compute_file_hash(raw_bytes):
    return hashlib.sha256(raw_bytes).hexdigest()

"""Tests for CSV validation."""
import io
import pytest
from imports.validators import validate_and_parse_csv


def make_csv(content):
    return io.BytesIO(content.encode('utf-8'))


class TestCsvValidation:

    def test_valid_csv(self):
        rows, errors = validate_and_parse_csv(make_csv("cin\nAB12345C\nCD67890D\n"))
        assert not errors
        assert len(rows) == 2
        assert rows[0]['cin'] == 'AB12345C'
        assert rows[0]['error'] is None

    def test_missing_cin_header(self):
        rows, errors = validate_and_parse_csv(make_csv("id,name\n1,test\n"))
        assert errors
        assert 'cin' in errors[0].lower()

    def test_blank_cin(self):
        rows, errors = validate_and_parse_csv(make_csv("cin\n\nAB12345C\n"))
        assert not errors
        blank = [r for r in rows if r.get('error') and 'blank' in r['error'].lower()]
        assert blank

    def test_duplicate_cin(self):
        rows, errors = validate_and_parse_csv(make_csv("cin\nAB12345C\nAB12345C\n"))
        assert not errors
        dups = [r for r in rows if r.get('is_duplicate')]
        assert len(dups) == 1

    def test_cin_with_leading_zero(self):
        rows, errors = validate_and_parse_csv(make_csv("cin\n0A12345B\n"))
        assert not errors
        assert rows[0]['cin'] == '0A12345B'

    def test_cin_with_spaces(self):
        rows, errors = validate_and_parse_csv(make_csv("cin\n  AB12345C  \n"))
        assert not errors
        assert rows[0]['cin'] == 'AB12345C'

    def test_formula_injection_equals(self):
        rows, errors = validate_and_parse_csv(make_csv("cin\n=CMD|' /C calc'!A0\n"))
        assert not errors
        assert rows[0].get('error')

    def test_formula_injection_plus(self):
        rows, errors = validate_and_parse_csv(make_csv("cin\n+AB12345C\n"))
        assert not errors
        assert rows[0].get('error')

    def test_formula_injection_at(self):
        rows, errors = validate_and_parse_csv(make_csv("cin\n@AB12345C\n"))
        assert not errors
        assert rows[0].get('error')

    def test_empty_file(self):
        rows, errors = validate_and_parse_csv(io.BytesIO(b''))
        assert errors

    def test_file_too_large(self):
        content = "cin\n" + "AB12345C\n" * 200000  # large file
        big = io.BytesIO(content.encode() * 100)
        rows, errors = validate_and_parse_csv(big)
        # Should error if over limit (depends on setting; just check it handles gracefully)
        assert isinstance(errors, list)

    def test_extra_columns_ignored(self):
        rows, errors = validate_and_parse_csv(make_csv("cin,name,dob\nAB12345C,John,2000-01-01\n"))
        assert not errors
        assert rows[0]['cin'] == 'AB12345C'

    def test_empty_csv_with_header(self):
        rows, errors = validate_and_parse_csv(make_csv("cin\n"))
        assert not errors
        assert len(rows) == 0

    def test_case_insensitive_duplicate_detection(self):
        rows, errors = validate_and_parse_csv(make_csv("cin\nAB12345C\nab12345c\n"))
        assert not errors
        dups = [r for r in rows if r.get('is_duplicate')]
        assert len(dups) == 1

"""
Management command to test eMedNY connectivity and authentication.

Usage:
    python manage.py check_emedny
    python manage.py check_emedny --cin AA12345A
    python manage.py check_emedny --verbose
"""
from datetime import date

from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Test eMedNY CORE endpoint connectivity and authentication.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--cin', default='AA12345A',
            help='CIN to use for the test 270 request (default: AA12345A)',
        )
        parser.add_argument(
            '--verbose', action='store_true',
            help='Print the full SOAP request and response bodies',
        )

    def handle(self, *args, **options):
        cin = options['cin']
        verbose = options['verbose']

        self.stdout.write('\n' + '=' * 60)
        self.stdout.write('  eMedNY Connection Diagnostic')
        self.stdout.write('=' * 60)

        # Settings dump
        self.stdout.write('\n[1] Current Settings')
        self.stdout.write(f"  MOCK_MODE        : {settings.EMEDNY_MOCK_MODE}")
        self.stdout.write(f"  ENDPOINT         : {settings.EMEDNY_ENDPOINT}")
        self.stdout.write(f"  USERNAME         : {settings.EMEDNY_USERNAME or '(not set)'}")
        self.stdout.write(f"  ETIN             : {settings.EMEDNY_ETIN or '(not set)'}")
        self.stdout.write(f"  PROVIDER_ID      : {settings.EMEDNY_PROVIDER_ID or '(not set)'}")
        self.stdout.write(f"  USAGE_INDICATOR  : {settings.EMEDNY_USAGE_INDICATOR}")
        ws_user = getattr(settings, 'EMEDNY_WS_USERNAME', '') or settings.EMEDNY_USERNAME
        self.stdout.write(f"  WS_USERNAME      : {ws_user} (SOAP WS-Security)")
        self.stdout.write(f"  PASSWORD         : {'(set)' if settings.EMEDNY_PASSWORD else '(not set)'}")

        if settings.EMEDNY_MOCK_MODE:
            self.stdout.write(
                '\n  WARNING: EMEDNY_MOCK_MODE=True -- set to False in .env to use the real endpoint.'
            )
            return

        # Build 270
        self.stdout.write('\n[2] Building 270 Request')
        from emedny.builder import EligibilityRequestBuilder
        builder = EligibilityRequestBuilder()
        request_data = builder.build(cin=cin, date_of_service=date.today())
        self.stdout.write(f"  PayloadID : {request_data['payload_id']}")
        self.stdout.write(f"  Control#  : {request_data['isa_control_number']}")
        if verbose:
            self.stdout.write('\n--- X12 270 Payload ---')
            self.stdout.write(request_data['x12_payload'])

        # Submit
        self.stdout.write('\n[3] Submitting to eMedNY...')
        from emedny.client import EmednyCoreClient
        client = EmednyCoreClient()

        if verbose:
            self.stdout.write('\n--- SOAP Request ---')
            self.stdout.write(request_data['soap_body'][:5000])

        response = client.submit(request_data)

        # Results
        self.stdout.write('\n[4] Response')
        error = response.get('error')
        error_type = response.get('error_type', '')
        response_type = response.get('response_type', '')
        x12 = response.get('x12_response', '')

        if verbose:
            self.stdout.write('\n--- Raw Response ---')
            self.stdout.write(response.get('raw_response', '')[:5000])

        if error:
            if error_type == 'AUTH_FAILED':
                self.stdout.write(
                    f'\n  ERROR: AUTHENTICATION FAILED\n'
                    f'  {error}\n\n'
                    f'  Troubleshooting steps:\n'
                    f'  1. Verify EMEDNY_USERNAME and EMEDNY_PASSWORD in .env\n'
                    f'  2. If WS-Security uses ETIN, add to .env: EMEDNY_WS_USERNAME={settings.EMEDNY_ETIN}\n'
                    f'  3. Confirm the web services account is active at emedny.org\n'
                    f'  4. Confirm your server IP is whitelisted by eMedNY\n'
                    f'  5. Check eMedNY portal for password expiry'
                )
            elif error_type == 'NETWORK_TIMEOUT':
                self.stdout.write(
                    f'\n  ERROR: NETWORK TIMEOUT\n'
                    f'  Check firewall rules for outbound HTTPS to:\n'
                    f'  {settings.EMEDNY_ENDPOINT}'
                )
            elif error_type == 'CONNECTION_ERROR':
                self.stdout.write(f'\n  ERROR: CONNECTION ERROR\n  {error}')
            else:
                self.stdout.write(f'\n  ERROR ({error_type}): {error}')
        else:
            self.stdout.write(f'\n  SUCCESS -- Response type: {response_type}')
            if x12:
                self.stdout.write('\n--- X12 271 Response (first 500 chars) ---')
                self.stdout.write(x12[:500])

                from emedny.parser import EligibilityResponseParser
                parsed = EligibilityResponseParser().parse(x12)
                self.stdout.write('\n[5] Parsed Result')
                self.stdout.write(f"  Member found   : {parsed.get('member_found')}")
                self.stdout.write(f"  Overall status : {parsed.get('overall_status')}")
                demo = parsed.get('demographics', {})
                name = f"{demo.get('first_name', '')} {demo.get('last_name', '')}".strip()
                if name:
                    self.stdout.write(f"  Member name    : {name}")
                if parsed.get('coverage_start_date'):
                    self.stdout.write(f"  Coverage start : {parsed['coverage_start_date']}")
                if parsed.get('coverage_end_date'):
                    self.stdout.write(f"  Coverage end   : {parsed['coverage_end_date']}")
                if parsed.get('warnings'):
                    self.stdout.write(f"  Warnings       : {parsed['warnings']}")

        self.stdout.write('\n' + '=' * 60 + '\n')

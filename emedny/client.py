"""eMedNY CORE Web Services HTTP client."""
import base64
import logging
import re
import requests
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

# 500 with Authentication Failed is NOT retryable — exclude from retry set
RETRYABLE_HTTP_CODES = {502, 503, 504}


class EmednyCoreClient:
    """Real HTTP client for eMedNY CORE Web Services."""

    SOAP_ACTION = 'RealTimeTransaction'

    def __init__(self):
        self.endpoint = settings.EMEDNY_ENDPOINT
        self.timeout = settings.EMEDNY_TIMEOUT
        self.username = getattr(settings, 'EMEDNY_USERNAME', '')
        self.password = getattr(settings, 'EMEDNY_PASSWORD', '')

    def _build_headers(self):
        """Build HTTP headers including Basic Auth for the CAQH EDIGateway."""
        headers = {
            'Content-Type': f'application/soap+xml; action="{self.SOAP_ACTION}"',
        }
        if self.username and self.password:
            creds = base64.b64encode(
                f'{self.username}:{self.password}'.encode('utf-8')
            ).decode('ascii')
            headers['Authorization'] = f'Basic {creds}'
        return headers

    def submit(self, request_data):
        """
        Submit a 270 request and return parsed response dict.
        Never raises — returns error information in the dict.
        """
        soap_body = request_data['soap_body']
        payload_id = request_data.get('payload_id', '')

        headers = self._build_headers()

        logger.info("Submitting 270 to eMedNY (PayloadID=%s)", payload_id)
        logger.debug("SOAP body:\n%s", soap_body[:3000])

        try:
            http_resp = requests.post(
                self.endpoint,
                data=soap_body.encode('utf-8'),
                headers=headers,
                timeout=(5, 25),
            )
        except requests.exceptions.Timeout:
            return self._error_result('NETWORK_TIMEOUT', 'Request to eMedNY timed out.')
        except requests.exceptions.ConnectionError as exc:
            return self._error_result('CONNECTION_ERROR', f'Connection error: {exc}')
        except Exception as exc:
            return self._error_result('UNKNOWN', f'Unexpected HTTP error: {exc}')

        raw_response = http_resp.text or ''

        if http_resp.status_code in RETRYABLE_HTTP_CODES:
            # Log and surface the body — it often contains eMedNY's error detail
            body_preview = raw_response[:2000] if raw_response else '(empty body)'
            logger.error("eMedNY HTTP %s body: %s", http_resp.status_code, body_preview)
            return self._error_result(
                'HTTP_5XX',
                f'eMedNY returned HTTP {http_resp.status_code}: {body_preview}',
                raw_response=raw_response,
            )

        if http_resp.status_code != 200:
            # Try to extract a human-readable message from SOAP Fault first
            fault_msg = self._extract_soap_fault(raw_response)
            body_preview = fault_msg or (raw_response[:2000] if raw_response else '(empty body)')
            error_type = 'AUTH_FAILED' if 'Authentication Failed' in body_preview else 'HTTP_ERROR'
            logger.error(
                "eMedNY HTTP %s (%s): %s",
                http_resp.status_code, error_type, body_preview
            )
            return self._error_result(
                error_type,
                f'eMedNY error: {body_preview}',
                raw_response=raw_response,
            )

        return self._parse_soap_response(raw_response)

    def _parse_soap_response(self, raw_response):
        """Extract payload and metadata from SOAP response."""
        # Extract error code
        error_code = self._extract_between(raw_response, '<ns3:ErrorCode>', '</ns3:ErrorCode>') or \
                     self._extract_between(raw_response, '<ErrorCode>', '</ErrorCode>')

        error_message = self._extract_between(raw_response, '<ns3:ErrorMessage>', '</ns3:ErrorMessage>') or \
                        self._extract_between(raw_response, '<ErrorMessage>', '</ErrorMessage>')

        # Extract response payload type
        response_payload_type = (
            self._extract_between(raw_response, '<ns3:PayloadType>', '</ns3:PayloadType>') or
            self._extract_between(raw_response, '<PayloadType>', '</PayloadType>') or ''
        )

        # Extract X12 payload
        x12_response = ''
        for start_tag, end_tag in [
            ('<ns3:Payload><![CDATA[', ']]></ns3:Payload>'),
            ('<Payload><![CDATA[', ']]></Payload>'),
            ('<ns3:Payload>', '</ns3:Payload>'),
            ('<Payload>', '</Payload>'),
        ]:
            x12_response = self._extract_between(raw_response, start_tag, end_tag)
            if x12_response:
                x12_response = x12_response.strip()
                # Strip stray CDATA brackets
                if x12_response.startswith('['):
                    x12_response = x12_response[1:]
                if x12_response.endswith(']'):
                    x12_response = x12_response[:-1]
                break

        if not x12_response:
            return self._error_result(
                'NO_PAYLOAD',
                f'No X12 payload in eMedNY response. ErrorCode={error_code} ErrorMessage={error_message}',
                raw_response=raw_response,
            )

        # Detect response type
        if 'ST*999' in x12_response or response_payload_type.find('999') >= 0:
            response_type = 'X12_999'
        elif 'TA1*' in x12_response or response_payload_type.find('TA1') >= 0:
            response_type = 'TA1'
        elif 'ST*271' in x12_response:
            response_type = 'X12_271'
        else:
            response_type = 'UNKNOWN'

        return {
            'raw_response': raw_response,
            'x12_response': x12_response,
            'response_type': response_type,
            'response_payload_type': response_payload_type,
            'error_code': error_code or '',
            'error_message': error_message or '',
            'error': None,
        }

    @staticmethod
    def _extract_between(text, start, end):
        s = text.find(start)
        if s < 0:
            return ''
        s += len(start)
        e = text.find(end, s)
        if e < 0:
            return ''
        return text[s:e]

    @staticmethod
    def _extract_soap_fault(raw_response):
        """
        Extract a readable message from a SOAP Fault body.
        Handles both SOAP 1.1 and SOAP 1.2 fault formats.
        Returns a short string or empty string if not a fault.
        """
        if not raw_response or 'Fault' not in raw_response:
            return ''
        # SOAP 1.2: <soap:Reason><soap:Text>...</soap:Text></soap:Reason>
        # SOAP 1.1: <faultstring>...</faultstring>
        # eMedNY detail: <wfe:invokeFault>...</wfe:invokeFault>
        parts = []
        for start, end in [
            ('<wfe:invokeFault', '</wfe:invokeFault>'),
            ('<faultstring>', '</faultstring>'),
            ('<soap:Text', '</soap:Text>'),
        ]:
            s = raw_response.find(start)
            if s >= 0:
                s_end = raw_response.find('>', s) + 1
                e = raw_response.find(end, s_end)
                if e >= 0:
                    text = raw_response[s_end:e].strip()
                    if text:
                        parts.append(text)
        return ' | '.join(parts) if parts else ''

    @staticmethod
    def _error_result(error_type, message, raw_response=''):
        return {
            'raw_response': raw_response,
            'x12_response': '',
            'response_type': 'HTTP_ERROR',
            'error': message,
            'error_type': error_type,
            'error_code': '',
            'error_message': message,
        }


def get_emedny_client():
    """Factory — returns mock or real client based on settings."""
    if getattr(settings, 'EMEDNY_MOCK_MODE', True):
        from .mock_client import MockEmednyCoreClient
        return MockEmednyCoreClient()
    return EmednyCoreClient()

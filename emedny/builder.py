"""X12 270 Eligibility Benefit Inquiry builder.

Based on ASC X12N 270/271 Health Care Eligibility Benefit Inquiry and
Response version 005010X279A1, and the Zoho Deluge reference implementation
provided by the client.
"""
import uuid
import time
import hashlib
from datetime import datetime
from django.conf import settings
from django.utils import timezone


class EligibilityRequestBuilder:
    """Builds an X12 270 request payload wrapped in a SOAP/CORE envelope."""

    ELEMENT_SEP = '*'
    SEGMENT_TERM = '~'
    SUB_SEP = ':'
    COMP_SEP = '|'

    def build(self, cin, date_of_service, service_type_code=None):
        """
        Build a complete 270 request.
        Returns a dict with x12_payload, soap_body, and control numbers.
        """
        etin = settings.EMEDNY_ETIN
        provider_id = settings.EMEDNY_PROVIDER_ID
        organization_name = settings.EMEDNY_ORGANIZATION_NAME
        usage_indicator = settings.EMEDNY_USAGE_INDICATOR
        taxonomy_code = settings.EMEDNY_TAXONOMY_CODE
        svc_type = service_type_code or settings.EMEDNY_SERVICE_TYPE

        now = timezone.now()
        date_yymmdd = now.strftime('%y%m%d')
        date_yyyymmdd = now.strftime('%Y%m%d')
        time_hhmm = now.strftime('%H%M')
        timestamp_utc = now.strftime('%Y-%m-%dT%H:%M:%SZ')

        millis = str(int(time.time() * 1000))[-9:]
        control_number = ('000000000' + millis)[-9:]
        group_control_number = ('000000' + millis)[-6:]
        st_control_number = ('0000' + millis)[-4:]

        bht_ref = date_yyyymmdd + time_hhmm + '000001'
        trace_number = date_yyyymmdd + time_hhmm + '000001'
        trn03 = ('0000000000' + etin)[-10:]

        # Generate UUID-style payload ID
        payload_id = str(uuid.uuid4())

        # ISA padding: sender/receiver must be exactly 15 chars
        receiver_id_raw = getattr(settings, 'EMEDNY_RECEIVER_ID', 'EMEDNY')
        sender_id = (etin + ' ' * 15)[:15]
        receiver_id = (receiver_id_raw + ' ' * 15)[:15]

        # Format date of service
        if hasattr(date_of_service, 'strftime'):
            service_date = date_of_service.strftime('%Y%m%d')
        else:
            service_date = str(date_of_service).replace('-', '')

        segments = []

        # ISA — Interchange Control Header
        segments.append(
            f"ISA{self.ELEMENT_SEP}00{self.ELEMENT_SEP}          "
            f"{self.ELEMENT_SEP}00{self.ELEMENT_SEP}          "
            f"{self.ELEMENT_SEP}ZZ{self.ELEMENT_SEP}{sender_id}"
            f"{self.ELEMENT_SEP}ZZ{self.ELEMENT_SEP}{receiver_id}"
            f"{self.ELEMENT_SEP}{date_yymmdd}{self.ELEMENT_SEP}{time_hhmm}"
            f"{self.ELEMENT_SEP}{self.COMP_SEP}"
            f"{self.ELEMENT_SEP}00501"
            f"{self.ELEMENT_SEP}{control_number}"
            f"{self.ELEMENT_SEP}1"
            f"{self.ELEMENT_SEP}{usage_indicator}"
            f"{self.ELEMENT_SEP}{self.SUB_SEP}"
        )

        # GS — Functional Group Header
        segments.append(
            f"GS{self.ELEMENT_SEP}HS"
            f"{self.ELEMENT_SEP}{etin}"
            f"{self.ELEMENT_SEP}{receiver_id_raw}"
            f"{self.ELEMENT_SEP}{date_yyyymmdd}"
            f"{self.ELEMENT_SEP}{time_hhmm}"
            f"{self.ELEMENT_SEP}{group_control_number}"
            f"{self.ELEMENT_SEP}X"
            f"{self.ELEMENT_SEP}005010X279A1"
        )

        # ST — Transaction Set Header
        segments.append(
            f"ST{self.ELEMENT_SEP}270{self.ELEMENT_SEP}{st_control_number}"
            f"{self.ELEMENT_SEP}005010X279A1"
        )

        # BHT — Beginning of Hierarchical Transaction
        segments.append(
            f"BHT{self.ELEMENT_SEP}0022{self.ELEMENT_SEP}13"
            f"{self.ELEMENT_SEP}{bht_ref}"
            f"{self.ELEMENT_SEP}{date_yyyymmdd}"
            f"{self.ELEMENT_SEP}{time_hhmm}"
        )

        # 2000A — Information Source (HL)
        segments.append(f"HL{self.ELEMENT_SEP}1{self.ELEMENT_SEP}{self.ELEMENT_SEP}20{self.ELEMENT_SEP}1")
        # NM1 — Payer Name
        segments.append(f"NM1{self.ELEMENT_SEP}PR{self.ELEMENT_SEP}2{self.ELEMENT_SEP}NYSDOH"
                        f"{self.ELEMENT_SEP}{self.ELEMENT_SEP}{self.ELEMENT_SEP}{self.ELEMENT_SEP}"
                        f"{self.ELEMENT_SEP}PI{self.ELEMENT_SEP}EMEDNY")

        # 2000B — Information Receiver (HL)
        segments.append(f"HL{self.ELEMENT_SEP}2{self.ELEMENT_SEP}1{self.ELEMENT_SEP}21{self.ELEMENT_SEP}1")
        # NM1 — Provider
        segments.append(
            f"NM1{self.ELEMENT_SEP}1P{self.ELEMENT_SEP}2"
            f"{self.ELEMENT_SEP}{organization_name}"
            f"{self.ELEMENT_SEP}{self.ELEMENT_SEP}{self.ELEMENT_SEP}{self.ELEMENT_SEP}"
            f"{self.ELEMENT_SEP}SV{self.ELEMENT_SEP}{provider_id}"
        )
        if taxonomy_code:
            segments.append(f"PRV{self.ELEMENT_SEP}PE{self.ELEMENT_SEP}PXC{self.ELEMENT_SEP}{taxonomy_code}")

        # 2000C — Subscriber (HL)
        segments.append(f"HL{self.ELEMENT_SEP}3{self.ELEMENT_SEP}2{self.ELEMENT_SEP}22{self.ELEMENT_SEP}0")
        # TRN — Trace Number
        segments.append(
            f"TRN{self.ELEMENT_SEP}1{self.ELEMENT_SEP}{trace_number}"
            f"{self.ELEMENT_SEP}{trn03}"
        )
        # NM1 — Subscriber (CIN lookup)
        segments.append(
            f"NM1{self.ELEMENT_SEP}IL{self.ELEMENT_SEP}1"
            f"{self.ELEMENT_SEP}{self.ELEMENT_SEP}{self.ELEMENT_SEP}{self.ELEMENT_SEP}"
            f"{self.ELEMENT_SEP}{self.ELEMENT_SEP}MI{self.ELEMENT_SEP}{cin}"
        )
        # EQ — Eligibility Inquiry
        segments.append(f"EQ{self.ELEMENT_SEP}{svc_type}")
        # DTP — Date of Service
        segments.append(f"DTP{self.ELEMENT_SEP}291{self.ELEMENT_SEP}D8{self.ELEMENT_SEP}{service_date}")

        # SE — Transaction Set Trailer
        # SE01 counts segments from ST to SE *inclusive* (exclude ISA and GS, add 1 for SE itself)
        segment_count = len(segments) - 2 + 1
        segments.append(
            f"SE{self.ELEMENT_SEP}{segment_count}{self.ELEMENT_SEP}{st_control_number}"
        )

        # GE — Functional Group Trailer
        segments.append(f"GE{self.ELEMENT_SEP}1{self.ELEMENT_SEP}{group_control_number}")

        # IEA — Interchange Control Trailer
        segments.append(f"IEA{self.ELEMENT_SEP}1{self.ELEMENT_SEP}{control_number}")

        x12_payload = self.SEGMENT_TERM.join(segments) + self.SEGMENT_TERM

        # Build SOAP envelope
        soap_body = self._build_soap_envelope(
            x12_payload=x12_payload,
            payload_id=payload_id,
            timestamp_utc=timestamp_utc,
            etin=etin,
            username=(
                getattr(settings, 'EMEDNY_WS_USERNAME', None)
                or settings.EMEDNY_USERNAME
            ),
            password=(
                getattr(settings, 'EMEDNY_WS_PASSWORD', None)
                or settings.EMEDNY_PASSWORD
            ),
            receiver_id=receiver_id_raw,
        )

        return {
            'x12_payload': x12_payload,
            'soap_body': soap_body,
            'isa_control_number': control_number,
            'gs_control_number': group_control_number,
            'st_control_number': st_control_number,
            'payload_id': payload_id,
            'service_type_code': svc_type,
            'cin': cin,
            'date_of_service': service_date,
        }

    def _build_soap_envelope(self, x12_payload, payload_id, timestamp_utc, etin, username, password, receiver_id='EMEDNY'):
        return (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope">'
            '<soap:Header>'
            '<wsse:Security xmlns:wsse="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd" soap:mustUnderstand="true">'
            '<wsse:UsernameToken xmlns:wsu="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd">'
            f'<wsse:Username>{username}</wsse:Username>'
            '<wsse:Password Type="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-username-token-profile-1.0#PasswordText">'
            f'{password}</wsse:Password>'
            '</wsse:UsernameToken>'
            '</wsse:Security>'
            '</soap:Header>'
            '<soap:Body>'
            '<cor:COREEnvelopeRealTimeRequest xmlns:cor="http://emedny.org/CORERule.xsd">'
            '<cor:PayloadType>X12_270_Request_005010X279A1</cor:PayloadType>'
            '<cor:ProcessingMode>RealTime</cor:ProcessingMode>'
            f'<cor:PayloadID>{payload_id}</cor:PayloadID>'
            f'<cor:TimeStamp>{timestamp_utc}</cor:TimeStamp>'
            f'<cor:SenderID>{etin}</cor:SenderID>'
            f'<cor:ReceiverID>{receiver_id}</cor:ReceiverID>'
            '<cor:CORERuleVersion>2.2.0</cor:CORERuleVersion>'
            f'<cor:Payload><![CDATA[{x12_payload}]]></cor:Payload>'
            '</cor:COREEnvelopeRealTimeRequest>'
            '</soap:Body>'
            '</soap:Envelope>'
        )

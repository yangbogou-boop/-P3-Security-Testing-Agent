"""Finite GET construction, bounded parsing and pure simulated verdicts. No I/O."""
from dataclasses import dataclass, field
import re

from ..models import InvalidInput
from .contract import IDENTITIES, strict_json


@dataclass(frozen=True)
class PreparedRequest:
    action_id: str
    snapshot_id: str
    check_id: str
    target: str
    wire: bytes = field(repr=False)


def build_request(config, snapshot, check, action_id, credential=None):
    from ..models import identifier
    identifier(action_id)
    if (snapshot.scope_digest != config.scope_digest or check not in config.candidates
            or snapshot.authorization_id != config.authorization_id
            or snapshot.authorization_version != config.authorization_version):
        raise InvalidInput('REQUEST_NOT_APPROVED')
    paths = {'profile_read': '/v1/profile', 'object_read': '/v1/objects/obj-b',
             'admin_report': '/v1/admin/report?period=demo'}
    target = paths[check.endpoint_id]  # Only the six exact, versioned candidates.
    headers = ['GET ' + target + ' HTTP/1.1', 'Host: 127.0.0.1:' + str(config.port),
               'Accept: application/json', 'Connection: close', 'User-Agent: P3-contract-v1',
               'X-P3-Action-Id: ' + action_id]
    if check.identity_ref != 'anonymous':
        if type(credential) is not str or not re.fullmatch(r'[A-Za-z0-9._~-]{1,256}', credential):
            raise InvalidInput('INVALID_CREDENTIAL')
        headers.append('Authorization: Bearer ' + credential)
    elif credential is not None:
        raise InvalidInput('ANONYMOUS_CREDENTIAL_FORBIDDEN')
    return PreparedRequest(action_id, snapshot.snapshot_id, check.check_id, target,
                           ('\r\n'.join(headers) + '\r\n\r\n').encode('ascii'))


@dataclass(frozen=True)
class Observation:
    valid: bool
    status: object
    body: object = field(repr=False)
    reason: object = None
    diagnostic: object = None
    headers_received: bool = False


class ResponseParser:
    """Incremental bounded byte buffer; errors never retain the raw body."""
    def __init__(self, limits):
        self.limits = limits
        self._buffer = bytearray()
        self._closed = False
        self._failure = None

    def _fail(self, code):
        self._buffer.clear()
        self._failure = code

    def feed(self, chunk):
        if self._closed:
            raise InvalidInput('PARSER_CLOSED')
        if self._failure:
            return
        if type(chunk) is not bytes:
            self._fail('INVALID_CHUNK'); return
        if len(chunk) + len(self._buffer) > self.limits.response_bytes:
            self._fail('RESPONSE_TOO_LARGE'); return
        self._buffer.extend(chunk)
        split = self._buffer.find(b'\r\n\r\n')
        if (split < 0 and len(self._buffer) > self.limits.header_bytes
                or split >= 0 and split + 4 > self.limits.header_bytes):
            self._fail('HEADERS_TOO_LARGE')
        elif split >= 0 and len(self._buffer) - split - 4 > self.limits.body_bytes:
            self._fail('BODY_TOO_LARGE')

    def finish(self):
        if self._closed: raise InvalidInput('PARSER_CLOSED')
        self._closed = True
        data = bytes(self._buffer); self._buffer.clear()
        status = None
        headers_received = False
        try:
            if self._failure: raise InvalidInput(self._failure)
            if b'\r\n\r\n' not in data: raise InvalidInput('TRUNCATED_HEADERS')
            head, body = data.split(b'\r\n\r\n', 1)
            lines = head.split(b'\r\n')
            if not re.fullmatch(rb'HTTP/1\.1 [1-5][0-9]{2} [\x20-\x7e]*', lines[0]):
                raise InvalidInput('INVALID_STATUS_LINE')
            status = int(lines[0][9:12])
            headers = {}
            for line in lines[1:]:
                if b':' not in line: raise InvalidInput('INVALID_HEADER')
                key, value = line.split(b':', 1)
                if not re.fullmatch(rb'[A-Za-z0-9-]+', key) or not re.fullmatch(rb'[\x20-\x7e]*', value):
                    raise InvalidInput('INVALID_HEADER')
                key = key.lower()
                if key in headers: raise InvalidInput('DUPLICATE_HEADER')
                headers[key] = value.strip()
            headers_received = True
            if b'transfer-encoding' in headers or b'content-encoding' in headers:
                raise InvalidInput('UNSUPPORTED_ENCODING')
            length = headers.get(b'content-length', b'')
            if not re.fullmatch(rb'[0-9]{1,10}', length): raise InvalidInput('INVALID_LENGTH')
            length = int(length)
            if length > self.limits.body_bytes: raise InvalidInput('BODY_TOO_LARGE')
            if length != len(body): raise InvalidInput('LENGTH_MISMATCH')
            if headers.get(b'content-type', b'').lower() not in (b'application/json', b'application/json; charset=utf-8'):
                raise InvalidInput('INVALID_CONTENT_TYPE')
            parsed = strict_json(body.decode('utf-8', errors='strict'))
            if type(parsed) is not dict: raise InvalidInput('INVALID_JSON_OBJECT')
            return Observation(True, status, parsed, headers_received=True)
        except (InvalidInput, UnicodeError, ValueError, RecursionError) as error:
            # Only locally chosen codes; never interpolate unexpected exception text.
            code = str(error) if type(error) is InvalidInput else 'INVALID_RESPONSE'
            return Observation(False, status, None, 'RESPONSE_ERROR', code, headers_received)


@dataclass(frozen=True)
class Verdict:
    simulated_conclusion: str
    reason: object
    assertion: str
    # Normal report fields MUST NOT imply a real HTTP execution/security result.
    execution: str = 'NOT_EXECUTED'
    conclusion: str = 'INCONCLUSIVE'
    provenance: str = 'NO_NETWORK_SIMULATION'


def evaluate(config, check, action_id, observation, *, control_pass=False, identity_verified=True):
    inconclusive = lambda why, code: Verdict('INCONCLUSIVE', why, code)
    if check not in config.candidates or not observation.valid:
        return inconclusive(observation.reason or 'RESPONSE_ERROR', 'INVALID_RESPONSE')
    b, status = observation.body, observation.status
    if (b.get('fixture_instance_id') != config.fixture_instance_id
            or b.get('contract_version') != config.contract_version or b.get('request_id') != action_id):
        return inconclusive('RESPONSE_ERROR', 'CORRELATION_MISMATCH')
    common = {'fixture_instance_id', 'contract_version', 'request_id'}
    denial = False
    content = False
    if set(b) == common | {'error'}:
        error = b['error']
        denial = (type(error) is dict and set(error) == {'code'}
                  and ((status == 401 and error['code'] == 'AUTHENTICATION_REQUIRED')
                       or (status == 403 and error['code'] == 'ACCESS_DENIED')))
        if not denial:
            return inconclusive('RESPONSE_ERROR', 'INVALID_ERROR_SCHEMA')
    elif set(b) == common | {'data'}:
        data = b['data']
        if check.endpoint_id == 'object_read':
            expected = dict(object_id='obj-b', owner_id='bob', protected_marker='OBJECT_B_CANARY')
        elif check.endpoint_id == 'admin_report':
            expected = dict(period='demo', audience='admin', report_marker='ADMIN_REPORT_CANARY')
        else:
            identity = 'user_alice' if check.identity_ref == 'anonymous' else check.identity_ref
            entry = next(i for i in IDENTITIES if i[0] == identity)
            expected = dict(user_id=entry[1], role=entry[2], profile_marker=entry[1].upper() + '_PROFILE_CANARY')
        content = type(data) is dict and data == expected
        if not content:
            return inconclusive('RESPONSE_ERROR', 'INVALID_DATA_SCHEMA')
    else:
        return inconclusive('RESPONSE_ERROR', 'EXTRA_OR_MISSING_FIELDS')
    if not identity_verified:
        return inconclusive(None, 'UNVERIFIED_FIXTURE_IDENTITY')
    if status >= 500:
        return Verdict('FAIL', 'RESPONSE_ERROR', 'CONFIRMED_DISCLOSURE') if content and check.expected == 'DENY' else inconclusive('RESPONSE_ERROR', 'SERVER_ERROR')
    if status == 404 or status not in (200, 401, 403):
        return inconclusive('RESPONSE_ERROR', 'UNEXPECTED_STATUS')
    if check.expected == 'ALLOW':
        if denial: return Verdict('FAIL', None, 'CONFIRMED_OVERDENIAL')
        if status == 200 and content: return Verdict('PASS', None, 'AUTHORIZED_CONTENT')
    else:
        if content and status == 200: return Verdict('FAIL', None, 'CONFIRMED_DISCLOSURE')
        wanted = 401 if check.identity_ref == 'anonymous' else 403
        if denial and status == wanted:
            return Verdict('PASS', None, 'REFUSAL_WITH_CONTROL') if control_pass else inconclusive(None, 'MISSING_CONTROL')
    return inconclusive('RESPONSE_ERROR', 'UNEXPECTED_RESPONSE')

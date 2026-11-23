"""Contract-driven V2 request construction, correlation and verdicts (pure functions).

The module reuses only the business-agnostic parsing primitives from
``protocol.py`` (``ResponseParser``/``Observation``/``Verdict``/``PreparedRequest``).
It never imports ``evaluate``, ``build_request`` or ``IDENTITIES``: V1's fixed
paths, identities and canaries are not part of this protocol.
"""
import re

from ..models import InvalidInput, identifier
from .protocol import Observation, PreparedRequest, ResponseParser, Verdict

ENVELOPE_KEYS = {'request_id', 'fixture_instance_id', 'contract_version', 'fields'}
APPROVED_ASSERTIONS = {'AUTHORIZED_CONTENT', 'REFUSAL_WITH_CONTROL', 'MISSING_CONTROL',
                       'CONFIRMED_DISCLOSURE', 'CONFIRMED_OVERDENIAL'}
_PLACEHOLDER = re.compile(r'\{([A-Za-z0-9_-]{1,64})\}')


def _domain_values(domain, name):
    for key, values in domain:
        if key == name:
            return values
    return None


def build_request_v2(snapshot, spec, action_id, credential):
    """Build one bounded GET request from reviewed contract data only."""
    identifier(action_id)
    endpoint = snapshot.endpoint(spec.endpoint_id)
    if endpoint is None:
        raise InvalidInput('UNKNOWN_REVIEWED_ENDPOINT')
    placeholders = _PLACEHOLDER.findall(endpoint.path_template)
    if len(placeholders) != len(set(placeholders)):
        raise InvalidInput('INVALID_PATH_TEMPLATE')
    params = dict(spec.path_params)
    if set(params) != set(placeholders):
        raise InvalidInput('PATH_PARAMETER_MISMATCH')
    path = endpoint.path_template
    for name in placeholders:
        allowed = _domain_values(endpoint.path_domain, name)
        if allowed is None or params[name] not in allowed:
            raise InvalidInput('UNREGISTERED_PARAMETERS')
        path = path.replace('{' + name + '}', params[name])
    if spec.query:
        parts = []
        for name, value in spec.query:
            allowed = _domain_values(endpoint.query_domain, name)
            if allowed is None or value not in allowed:
                raise InvalidInput('UNREGISTERED_PARAMETERS')
            parts.append(name + '=' + value)
        path = path + '?' + '&'.join(parts)
    headers = ['GET ' + path + ' HTTP/1.1',
               'Host: 127.0.0.1:' + str(snapshot.port),
               'Accept: application/json',
               'Connection: close',
               'User-Agent: P3-reviewed-v2',
               'X-P3-Action-Id: ' + action_id]
    identity = snapshot.identity(spec.identity_ref)
    if identity is None:
        raise InvalidInput('UNKNOWN_REVIEWED_IDENTITY')
    if identity.credential_ref is None:
        if credential is not None:
            raise InvalidInput('ANONYMOUS_CREDENTIAL_FORBIDDEN')
    else:
        if type(credential) is not str or not re.fullmatch(r'[A-Za-z0-9._~-]{1,256}', credential):
            raise InvalidInput('INVALID_CREDENTIAL')
        headers.append('Authorization: Bearer ' + credential)
    wire = ('\r\n'.join(headers) + '\r\n\r\n').encode('ascii')
    return PreparedRequest(action_id, snapshot.snapshot_id, spec.check_id, path, wire)


def parse_response_v2(payload, snapshot):
    """Feed one bounded response payload through the shared strict parser."""
    parser = ResponseParser(snapshot.limits)
    if type(payload) is not bytes:
        raise InvalidInput('INVALID_FIXTURE_PAYLOAD')
    parser.feed(payload)
    return parser.finish()


def correlate_v2(body, action_id, snapshot):
    """Return the closed ``fields`` pairs or raise a locally chosen code."""
    if type(body) is not dict or set(body) != ENVELOPE_KEYS:
        raise InvalidInput('EXTRA_OR_MISSING_FIELDS')
    for name in ('request_id', 'fixture_instance_id', 'contract_version'):
        if type(body[name]) is not str:
            raise InvalidInput('INVALID_CORRELATION_TYPE')
    if body['request_id'] != action_id:
        raise InvalidInput('CORRELATION_MISMATCH')
    if body['fixture_instance_id'] != snapshot.fixture_instance_id:
        raise InvalidInput('CORRELATION_MISMATCH')
    if body['contract_version'] != snapshot.contract_version:
        raise InvalidInput('CORRELATION_MISMATCH')
    fields = body['fields']
    if type(fields) is not dict:
        raise InvalidInput('INVALID_FIELD_ENVELOPE')
    for key, value in fields.items():
        # No str() coercion: a non-string value must not become a matching string.
        if type(key) is not str or type(value) is not str:
            raise InvalidInput('INVALID_FIELD_TYPE')
    return tuple(sorted(fields.items()))


def _rule_expectation(snapshot, spec):
    rule = snapshot.rule(spec.response_rule)
    if rule is None:
        raise InvalidInput('MISSING_RESPONSE_RULE')
    return rule


def evaluate_v2(snapshot, spec, observation, action_id, *, control_pass=False, identity_verified=True):
    """Contract-driven verdict; insufficient evidence never becomes PASS."""
    rule = _rule_expectation(snapshot, spec)
    inconclusive = lambda why, code: Verdict('INCONCLUSIVE', why, code)
    if not observation.valid:
        return inconclusive(observation.reason or 'RESPONSE_ERROR', 'INVALID_RESPONSE')
    try:
        fields = correlate_v2(observation.body, action_id, snapshot)
    except InvalidInput as error:
        return inconclusive('RESPONSE_ERROR', str(error))
    status = observation.status
    matches = fields == rule.expected_fields
    if status >= 500:
        if matches and spec.expected == 'DENY':
            return Verdict('FAIL', 'RESPONSE_ERROR', 'CONFIRMED_DISCLOSURE')
        return inconclusive('RESPONSE_ERROR', 'SERVER_ERROR')
    if status not in (200, 401, 403):
        return inconclusive('RESPONSE_ERROR', 'UNEXPECTED_STATUS')
    if spec.expected == 'ALLOW':
        if status == rule.status and matches:
            return Verdict('PASS', None, 'AUTHORIZED_CONTENT')
        if status in (401, 403):
            if not identity_verified:
                return inconclusive(None, 'UNVERIFIED_FIXTURE_IDENTITY')
            return Verdict('FAIL', None, 'CONFIRMED_OVERDENIAL')
        return inconclusive('RESPONSE_ERROR', 'UNEXPECTED_RESPONSE')
    if status == 200 and matches:
        return Verdict('FAIL', None, 'CONFIRMED_DISCLOSURE')
    if status in (401, 403):
        # The reviewed contract binds identity to an exact status; a different
        # denial status is a mismatch, not a pass and not a confirmed defect.
        if status != rule.status:
            return inconclusive('RESPONSE_ERROR', 'STATUS_MISMATCH')
        if matches:
            if control_pass:
                return Verdict('PASS', None, 'REFUSAL_WITH_CONTROL')
            return inconclusive(None, 'MISSING_CONTROL')
    return inconclusive('RESPONSE_ERROR', 'UNEXPECTED_RESPONSE')


def projection_v2(snapshot, spec, observation, verdict, action_id):
    """Persist only reviewed ``evidence_fields``; never raw bytes or exception text."""
    rule = _rule_expectation(snapshot, spec)
    safe = None
    if observation.valid and verdict.assertion in APPROVED_ASSERTIONS:
        try:
            fields = correlate_v2(observation.body, action_id, snapshot)
        except InvalidInput:
            fields = None
        if fields is not None and fields == rule.expected_fields:
            allowed = set(rule.evidence_fields)
            safe = {key: value for key, value in fields if key in allowed}
    return dict(status=observation.status, response_valid=observation.valid,
                assertions_complete=safe is not None, response_fields=safe,
                diagnostic=observation.diagnostic, assertion=verdict.assertion)

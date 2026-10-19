"""Versioned, finite HTTP contract; independent of offline authorization."""
from dataclasses import dataclass
import hashlib
import json
import re

from ..models import Budget, InvalidInput, fields, identifier, number


def strict_json(data):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise InvalidInput('DUPLICATE_JSON_KEY')
            result[key] = value
        return result
    def constant(_):
        raise InvalidInput('INVALID_JSON_NUMBER')
    try:
        return json.loads(data, object_pairs_hook=pairs, parse_constant=constant)
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise InvalidInput('INVALID_JSON') from None


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    allow_nan=False).encode()).hexdigest()


@dataclass(frozen=True)
class HttpCheck:
    check_id: str
    endpoint_id: str
    method: str
    identity_ref: str
    path_params: tuple
    query: tuple
    expected: str
    control_id: object

    @classmethod
    def parse(cls, raw):
        fields(raw, 'check_id endpoint_id method identity_ref path_params query expected control_id')
        for key in ('check_id', 'endpoint_id', 'identity_ref'):
            identifier(raw[key])
        if raw['method'] != 'GET' or raw['expected'] not in ('ALLOW', 'DENY'):
            raise InvalidInput('INVALID_CHECK')
        if raw['control_id'] is not None:
            identifier(raw['control_id'])
        parsed = {}
        for key in ('path_params', 'query'):
            if type(raw[key]) is not dict:
                raise InvalidInput('INVALID_PARAMETERS')
            for k, v in raw[key].items():
                identifier(k)
                if type(v) is not str or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', v):
                    raise InvalidInput('INVALID_PARAMETERS')
            parsed[key] = tuple(sorted(raw[key].items()))
        return cls(**{**raw, **parsed})

    def to_dict(self):
        return dict(check_id=self.check_id, endpoint_id=self.endpoint_id, method=self.method,
                    identity_ref=self.identity_ref, path_params=dict(self.path_params),
                    query=dict(self.query), expected=self.expected, control_id=self.control_id)


IDENTITIES = (('anonymous', None, 'anonymous', None),
              ('user_alice', 'alice', 'member', 'fixture/alice'),
              ('user_bob', 'bob', 'member', 'fixture/bob'),
              ('admin_carol', 'carol', 'admin', 'fixture/carol'))
ENDPOINTS = (('profile_read', '/v1/profile'), ('object_read', '/v1/objects/{object_id}'),
             ('admin_report', '/v1/admin/report'))


def matrix_expectation(endpoint, identity, path_params=(), query=()):
    if identity not in dict((i[0], i) for i in IDENTITIES) or endpoint not in dict(ENDPOINTS):
        raise InvalidInput('UNREGISTERED_COMBINATION')
    if endpoint == 'object_read':
        if path_params not in ((('object_id', 'obj-a'),), (('object_id', 'obj-b'),)) or query:
            raise InvalidInput('UNREGISTERED_PARAMETERS')
    elif endpoint == 'admin_report':
        if path_params or query != (('period', 'demo'),):
            raise InvalidInput('UNREGISTERED_PARAMETERS')
    elif path_params or query:
        raise InvalidInput('UNREGISTERED_PARAMETERS')
    if identity == 'anonymous':
        return 'DENY'
    if endpoint == 'profile_read':
        return 'ALLOW'
    if endpoint == 'admin_report':
        return 'ALLOW' if identity == 'admin_carol' else 'DENY'
    owner = {'obj-a': 'user_alice', 'obj-b': 'user_bob'}[dict(path_params)['object_id']]
    return 'ALLOW' if identity == owner else 'DENY'


def base_checks():
    return tuple(HttpCheck(*row) for row in (
        ('HTTP-C-AUTH', 'profile_read', 'GET', 'user_alice', (), (), 'ALLOW', None),
        ('HTTP-N-AUTH', 'profile_read', 'GET', 'anonymous', (), (), 'DENY', 'HTTP-C-AUTH'),
        ('HTTP-C-BOLA', 'object_read', 'GET', 'user_bob', (('object_id', 'obj-b'),), (), 'ALLOW', None),
        ('HTTP-N-BOLA', 'object_read', 'GET', 'user_alice', (('object_id', 'obj-b'),), (), 'DENY', 'HTTP-C-BOLA'),
        ('HTTP-C-RBAC', 'admin_report', 'GET', 'admin_carol', (), (('period', 'demo'),), 'ALLOW', None),
        ('HTTP-N-RBAC', 'admin_report', 'GET', 'user_alice', (), (('period', 'demo'),), 'DENY', 'HTTP-C-RBAC')))


@dataclass(frozen=True)
class Limits:
    header_bytes: int
    body_bytes: int
    response_bytes: int


@dataclass(frozen=True)
class HttpConfig:
    port: int
    budget: Budget
    limits: Limits
    authorization_id: str
    authorization_version: str
    registry_ref: str
    fixture_instance_id: str
    contract_version: str
    matrix_version: str
    candidate_version: str
    fixture_version: str
    budget_version: str
    candidates: tuple

    @classmethod
    def parse(cls, raw):
        fields(raw, 'mode schema_version target budget limits authorization fixture_instance_id contract_version matrix_version candidate_version fixture_version budget_version candidates')
        if raw['mode'] != 'http-local' or raw['schema_version'] != 'http-core-v1':
            raise InvalidInput('HTTP_SCHEMA_REQUIRED')
        target = raw['target']
        fields(target, 'scheme host port')
        if (target['scheme'] != 'http' or target['host'] != '127.0.0.1'
                or type(target['port']) is not int or not 1 <= target['port'] <= 65535):
            raise InvalidInput('INVALID_TARGET')
        b = raw['budget']; fields(b, 'max_checks logical_timeout_seconds concurrency')
        if (type(b['max_checks']) is not int or b['max_checks'] <= 0
                or type(b['concurrency']) is not int or b['concurrency'] != 1):
            raise InvalidInput('INVALID_BUDGET')
        number(b['logical_timeout_seconds'], True)
        lim = raw['limits']; fields(lim, 'header_bytes body_bytes response_bytes')
        if any(type(v) is not int or v <= 0 for v in lim.values()):
            raise InvalidInput('INVALID_LIMITS')
        if lim['response_bytes'] < lim['header_bytes'] + lim['body_bytes']:
            raise InvalidInput('INVALID_LIMITS')
        a = raw['authorization']; fields(a, 'authorization_id authorization_version registry_ref')
        for v in a.values(): identifier(v)
        versions = ('fixture_instance_id', 'contract_version', 'matrix_version', 'candidate_version', 'fixture_version', 'budget_version')
        for k in versions: identifier(raw[k])
        if raw['contract_version'] != 'p3-http-v1' or raw['matrix_version'] != 'p3-matrix-v1':
            raise InvalidInput('UNKNOWN_CONTRACT')
        if type(raw['candidates']) is not list:
            raise InvalidInput('INVALID_CANDIDATES')
        candidates = tuple(HttpCheck.parse(c) for c in raw['candidates'])
        if candidates != base_checks():
            raise InvalidInput('BASELINE_CANDIDATES_REQUIRED')
        return cls(target['port'], Budget(**b), Limits(**lim), **a,
                   **{k: raw[k] for k in versions}, candidates=candidates)

    def scope(self):
        return dict(target=['http', '127.0.0.1', self.port],
                    authorization=[self.authorization_id, self.authorization_version],
                    fixture_instance_id=self.fixture_instance_id,
                    versions=[self.contract_version, self.matrix_version, self.candidate_version,
                              self.fixture_version, self.budget_version],
                    budget=[self.budget.max_checks, self.budget.logical_timeout_seconds, 1],
                    limits=[self.limits.header_bytes, self.limits.body_bytes, self.limits.response_bytes],
                    endpoints=ENDPOINTS, identities=IDENTITIES,
                    candidates=[c.to_dict() for c in self.candidates])

    @property
    def scope_digest(self):
        return digest(self.scope())

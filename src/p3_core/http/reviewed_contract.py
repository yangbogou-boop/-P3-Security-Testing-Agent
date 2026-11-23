"""Inert, versioned declarations for reviewed in-memory fixtures.

Parsing only validates data. The internal binding function relies on provenance
verified by its trusted host caller, as LocalRegistry does. This module has no
runtime, transport, planner, or public configuration entry point.
"""
from dataclasses import dataclass
import re
from types import MappingProxyType
from typing import NamedTuple

from ..models import InvalidInput, fields, identifier
from .authorization import LocalRegistry, ReviewedMaterial
from .contract import HttpCheck, digest, strict_json


FORMAT = 'p3-reviewed-contract-v2'
MODE = 'offline-synthetic'
MAX_BYTES = 65536
MAX_ROWS = 64
MAX_BUDGET_SECONDS = 3600

_SEGMENT = re.compile(r'[A-Za-z0-9_-]{1,64}')
_PLACEHOLDER = re.compile(r'\{([A-Za-z0-9_-]{1,64})\}')
_TEXT = re.compile(r'[A-Za-z0-9_. -]{1,128}')
_PRIVATE_FIELD = re.compile(r'token|secret|password|credential|cookie|authorization|api[_-]?key', re.I)
_COMBINATION = 'endpoint_id method identity_ref path_params query expected'


def _freeze(value):
    if type(value) is dict:
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if type(value) is list:
        return tuple(_freeze(item) for item in value)
    return value


def _index(rows, key, validate):
    if type(rows) is not list or not 1 <= len(rows) <= MAX_ROWS:
        raise InvalidInput('INVALID_CONTRACT_ROWS')
    indexed = {}
    for row in rows:
        validate(row)
        name = identifier(row[key])
        if name in indexed:
            raise InvalidInput('DUPLICATE_CONTRACT_ID')
        indexed[name] = row
    return indexed


def _domain(value):
    if type(value) is not dict or len(value) > 8:
        raise InvalidInput('INVALID_PARAMETER_DOMAIN')
    for name, allowed in value.items():
        identifier(name)
        if (_PRIVATE_FIELD.search(name) or type(allowed) is not list or not 1 <= len(allowed) <= 16
                or any(type(v) is not str or not _SEGMENT.fullmatch(v) for v in allowed)
                or len(allowed) != len(set(allowed))):
            raise InvalidInput('INVALID_PARAMETER_DOMAIN')


def _endpoint(row):
    fields(row, 'endpoint_id method path_template path_domain query_domain')
    path = row['path_template']
    if row['method'] != 'GET' or type(path) is not str or not 2 <= len(path) <= 256 or not path.startswith('/'):
        raise InvalidInput('INVALID_ENDPOINT')
    parameters = []
    for segment in path[1:].split('/'):
        placeholder = _PLACEHOLDER.fullmatch(segment)
        if placeholder:
            parameters.append(placeholder[1])
        elif not _SEGMENT.fullmatch(segment):
            raise InvalidInput('INVALID_PATH_TEMPLATE')
    _domain(row['path_domain'])
    _domain(row['query_domain'])
    if (len(parameters) != len(set(parameters)) or set(parameters) != set(row['path_domain'])
            or set(parameters) & set(row['query_domain'])):
        raise InvalidInput('PATH_PARAMETER_MISMATCH')


def _identity(row):
    fields(row, 'identity_ref role credential_ref')
    identifier(row['role'])
    ref = row['credential_ref']
    if ref is not None and (type(ref) is not str or not re.fullmatch(r'fixture/[A-Za-z0-9_-]{1,64}', ref)):
        raise InvalidInput('INVALID_CREDENTIAL_REFERENCE')


def _response_rule(row):
    fields(row, 'rule_id status expected_fields evidence_fields')
    if type(row['status']) is not int or row['status'] not in (200, 401, 403):
        raise InvalidInput('INVALID_RESPONSE_STATUS')
    expected, evidence = row['expected_fields'], row['evidence_fields']
    if type(expected) is not dict or not 1 <= len(expected) <= 16:
        raise InvalidInput('INVALID_RESPONSE_FIELDS')
    for name, value in expected.items():
        identifier(name)
        if _PRIVATE_FIELD.search(name) or type(value) is not str or not _TEXT.fullmatch(value):
            raise InvalidInput('INVALID_RESPONSE_EXPECTATION')
    if (type(evidence) is not list or len(evidence) > len(expected)
            or any(type(name) is not str or name not in expected for name in evidence)
            or len(set(evidence)) != len(evidence)):
        raise InvalidInput('INVALID_EVIDENCE_FIELDS')


def _combination(check, endpoints, identities):
    endpoint = endpoints.get(check.endpoint_id)
    if endpoint is None or check.identity_ref not in identities:
        raise InvalidInput('UNREGISTERED_COMBINATION')
    for parameters, name in ((check.path_params, 'path_domain'), (check.query, 'query_domain')):
        domain = endpoint[name]
        if dict(parameters).keys() != domain.keys() or any(value not in domain[key] for key, value in parameters):
            raise InvalidInput('UNREGISTERED_PARAMETERS')
    return check.endpoint_id, check.method, check.identity_ref, check.path_params, check.query


def _validate_candidates(raw, endpoints, identities, rules):
    matrix = {}
    rows = raw['matrix']
    if type(rows) is not list or not 1 <= len(rows) <= 4 * MAX_ROWS:
        raise InvalidInput('INVALID_MATRIX_ROWS')
    for row in rows:
        fields(row, _COMBINATION)
        check = HttpCheck.parse(dict(row, check_id='matrix', control_id=None))
        key = _combination(check, endpoints, identities)
        if key in matrix:
            raise InvalidInput('DUPLICATE_MATRIX_CELL')
        matrix[key] = check.expected

    def candidate(row):
        fields(row, _COMBINATION + ' check_id control_id response_rule')
        check = HttpCheck.parse({key: value for key, value in row.items() if key != 'response_rule'})
        if matrix.get(_combination(check, endpoints, identities)) != check.expected:
            raise InvalidInput('CANDIDATE_MATRIX_MISMATCH')
        rule = rules.get(identifier(row['response_rule']))
        if rule is None or (rule['status'] == 200) != (check.expected == 'ALLOW'):
            raise InvalidInput('CANDIDATE_RESPONSE_MISMATCH')
        if check.expected == 'ALLOW' and check.control_id is not None:
            raise InvalidInput('INVALID_CONTROL')

    candidates = _index(raw['candidates'], 'check_id', candidate)
    for row in candidates.values():
        if row['expected'] == 'DENY':
            control = candidates.get(row['control_id'])
            same_request = ('endpoint_id', 'method', 'path_params', 'query')
            if (control is None or control['expected'] != 'ALLOW'
                    or control['identity_ref'] == row['identity_ref']
                    or any(control[key] != row[key] for key in same_request)):
                raise InvalidInput('INVALID_CONTROL')


@dataclass(frozen=True, init=False, repr=False)
class SyntheticContract:
    """Recursively read-only parsed content and its canonical V2 digest."""

    __slots__ = ('document', 'contract_digest')

    document: MappingProxyType
    contract_digest: str

    def __new__(cls, data):
        raw = _parse_document(data)
        contract = super().__new__(cls)
        object.__setattr__(contract, 'document', _freeze(raw))
        object.__setattr__(contract, 'contract_digest', digest(raw))
        return contract


def parse_contract(data):
    """Validate UTF-8 contract bytes without granting any authority."""
    return SyntheticContract(data)


def _parse_document(data):
    if type(data) is not bytes or not 1 <= len(data) <= MAX_BYTES:
        raise InvalidInput('INVALID_CONTRACT_BYTES')
    try:
        raw = strict_json(data.decode('utf-8', errors='strict'))
    except UnicodeError:
        raise InvalidInput('INVALID_CONTRACT_ENCODING') from None
    fields(raw, 'format mode contract_id contract_version target endpoints identities matrix candidates '
                'response_rules budget fixture evidence')
    if raw['format'] != FORMAT or raw['mode'] != MODE:
        raise InvalidInput('UNSUPPORTED_CONTRACT_FORMAT_OR_MODE')
    identifier(raw['contract_id'])
    # Each data revision still requires its own reviewed registry scope.
    if not re.fullmatch(r'v[1-9][0-9]{0,7}', identifier(raw['contract_version'])):
        raise InvalidInput('INVALID_CONTRACT_VERSION')

    target = raw['target']
    fields(target, 'scheme host port')
    if (target['scheme'] != 'http' or target['host'] != '127.0.0.1'
            or type(target['port']) is not int or not 1 <= target['port'] <= 65535):
        raise InvalidInput('INVALID_TARGET')

    budget = raw['budget']
    fields(budget, 'version max_checks logical_timeout_seconds concurrency')
    identifier(budget['version'])
    timeout = budget['logical_timeout_seconds']
    if (type(budget['max_checks']) is not int or not 1 <= budget['max_checks'] <= MAX_ROWS
            or type(timeout) not in (int, float) or not 0 < timeout <= MAX_BUDGET_SECONDS
            or type(budget['concurrency']) is not int or budget['concurrency'] != 1):
        raise InvalidInput('INVALID_BUDGET')

    fixture = raw['fixture']
    fields(fixture, 'type fixture_id version content_sha256')
    identifier(fixture['fixture_id'])
    identifier(fixture['version'])
    if (fixture['type'] != 'memory' or type(fixture['content_sha256']) is not str
            or not re.fullmatch(r'[0-9a-f]{64}', fixture['content_sha256'])):
        raise InvalidInput('INVALID_FIXTURE')

    evidence = raw['evidence']
    fields(evidence, 'format rule_version')
    if evidence['format'] != 'p3-synthetic-evidence-v1':
        raise InvalidInput('UNSUPPORTED_EVIDENCE_FORMAT')
    identifier(evidence['rule_version'])

    endpoints = _index(raw['endpoints'], 'endpoint_id', _endpoint)
    identities = _index(raw['identities'], 'identity_ref', _identity)
    refs = [row['credential_ref'] for row in identities.values() if row['credential_ref'] is not None]
    if len(set(refs)) != len(refs):
        raise InvalidInput('DUPLICATE_CREDENTIAL_REFERENCE')
    rules = _index(raw['response_rules'], 'rule_id', _response_rule)
    _validate_candidates(raw, endpoints, identities, rules)
    return raw


class _RegistryScope(NamedTuple):
    registry_ref: str
    authorization_id: str
    authorization_version: str
    scope_digest: str


def review_scope_digest(contract, *, registry_ref, authorization_id,
                        authorization_version, fixture_instance_id):
    """Compute a review scope without creating or granting permission."""
    if type(contract) is not SyntheticContract:
        raise InvalidInput('SYNTHETIC_CONTRACT_REQUIRED')
    return digest(dict(format=FORMAT, mode=MODE, contract_digest=contract.contract_digest,
                       registry_ref=identifier(registry_ref),
                       authorization_id=identifier(authorization_id),
                       authorization_version=identifier(authorization_version),
                       fixture_instance_id=identifier(fixture_instance_id)))


class ReviewedContractBinding(NamedTuple):
    """Verified offline association. Deliberately carries no runtime permit."""

    contract: SyntheticContract
    fixture_instance_id: str
    scope_digest: str
    review_ref: str
    snapshot_id: str
    valid_until: float


def _bind_reviewed_contract(review, *, registry, now, registry_ref, authorization_id,
                            authorization_version, fixture_instance_id):
    """Trusted-host only. Caller verifies the origin of review and registry.

    The review record carries the exact contract bytes, and the separately
    supplied registry must attest the same scope. A JSON flag, a successful
    parse, or a caller-provided digest alone cannot supply those records.
    """
    if (type(review) is not ReviewedMaterial or review.role != 'contract-review'
            or review.synthetic is not True or type(registry) is not LocalRegistry):
        raise InvalidInput('REVIEWED_SYNTHETIC_MATERIAL_REQUIRED')
    contract = parse_contract(review.content)
    scope_digest = review_scope_digest(
        contract, registry_ref=registry_ref, authorization_id=authorization_id,
        authorization_version=authorization_version, fixture_instance_id=fixture_instance_id)
    scope = _RegistryScope(registry_ref, authorization_id, authorization_version, scope_digest)
    snapshot = registry.snapshot(scope, now, simulation=True)
    review.verify(scope, now)
    if not snapshot.synthetic:
        raise InvalidInput('SYNTHETIC_REGISTRATION_REQUIRED')
    return ReviewedContractBinding(contract, fixture_instance_id, scope_digest, review.reference,
                                   snapshot.snapshot_id, min(review.valid_until, snapshot.valid_until))

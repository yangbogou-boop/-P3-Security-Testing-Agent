"""Immutable, private V2 review snapshot.

The snapshot is the only authorisation basis for a reviewed offline run.  It is
built by a trusted-host caller from a verified review binding plus an independent
fixture, and it stores primitive immutable values only: no live ``HttpCheck``
instance, no planner-visible object, no credential secret.

Pre-run expectations are derived from the fixture's declarative data through
``reference_expectation``.  The fixture's request/response pipeline is never
called during verification, so the review cannot be derived from the
implementation it is meant to check.
"""
from types import MappingProxyType
from typing import NamedTuple

from ..models import InvalidInput, identifier
from .reviewed_contract import ReviewedContractBinding, SyntheticContract
from .reviewed_fixture import FixturePort

# Bounded parsing limits for the V2 memory protocol (not a teacher-frozen budget).
LIMITS = None  # replaced below after the named tuple definition


class Limits(NamedTuple):
    header_bytes: int
    body_bytes: int
    response_bytes: int


LIMITS = Limits(4096, 65536, 69632)


class CandidateSpec(NamedTuple):
    check_id: str
    endpoint_id: str
    method: str
    identity_ref: str
    path_params: tuple
    query: tuple
    expected: str
    control_id: object
    response_rule: str


class IdentityRow(NamedTuple):
    identity_ref: str
    role: str
    credential_ref: object


class ResponseRule(NamedTuple):
    rule_id: str
    status: int
    expected_fields: tuple
    evidence_fields: tuple


class EndpointSpec(NamedTuple):
    endpoint_id: str
    path_template: str
    path_domain: tuple
    query_domain: tuple


def _pairs(mapping):
    return tuple(sorted((key, tuple(value)) for key, value in mapping.items()))


def _fields_pairs(mapping):
    return tuple(sorted((key, value) for key, value in mapping.items()))


def expected_status(identity_ref, expected):
    """Status a compliant fixture must return for one candidate."""
    if expected == 'ALLOW':
        return 200
    return 401 if identity_ref == 'anonymous' else 403


class ReviewedRunSnapshot(NamedTuple):
    """Recursively read-only review facts. Carries no runtime permit by itself.

    Implemented as a ``NamedTuple`` (``__slots__ == ()``) rather than a frozen
    dataclass: a frozen dataclass keeps an instance ``__dict__``, so
    ``object.__setattr__`` can replace fields.  A tuple subclass has no writable
    slot, and every mapping field is a ``MappingProxyType`` over a dict that no
    other code retains, so neither substitution nor in-place mutation is
    possible through the object.
    """

    snapshot_id: str
    contract_id: str
    contract_version: str
    contract_digest: str
    scope_digest: str
    registry_snapshot_id: str
    fixture_id: str
    fixture_version: str
    fixture_content_sha256: str
    fixture_instance_id: str
    budget_version: str
    max_checks: int
    logical_timeout_seconds: float
    concurrency: int
    evidence_format: str
    rule_version: str
    valid_until: float
    port: int
    limits: Limits
    identity_records: tuple
    resource_fingerprint: tuple
    candidates: object
    endpoints: object
    identities: object
    rules: object
    matrix: object

    def __repr__(self):
        return ('ReviewedRunSnapshot(snapshot_id=%r, contract_id=%r, contract_version=%r,'
                ' fixture_id=%r, fixture_version=%r, fixture_instance_id=%r)'
                % (self.snapshot_id, self.contract_id, self.contract_version,
                   self.fixture_id, self.fixture_version, self.fixture_instance_id))

    def candidate_ids(self):
        return tuple(self.candidates)

    def candidate(self, check_id):
        if type(check_id) is not str:
            return None
        return self.candidates.get(check_id)

    def identity(self, identity_ref):
        return self.identities.get(identity_ref)

    def rule(self, rule_id):
        return self.rules.get(rule_id)

    def endpoint(self, endpoint_id):
        return self.endpoints.get(endpoint_id)


def _require_port(fixture):
    for name in ('fixture_id', 'version', 'contract_version', 'instance_id',
                 'canonical_digest', 'identity_records', 'resource_records',
                 'credentials', 'reference_expectation', 'handle'):
        method = getattr(fixture, name, None)
        if not callable(method):
            raise InvalidInput('FIXTURE_PORT_INCOMPLETE')
        if getattr(type(fixture), name, None) is getattr(FixturePort, name, None) and hasattr(FixturePort, name):
            raise InvalidInput('FIXTURE_PORT_NOT_IMPLEMENTED')
    return fixture


def resource_fingerprint(fixture):
    """Deterministic, hash-free fingerprint of resources, ownership and ACL.

    Derived from the fixture's current data (never from contract expectations), so
    it can be compared cheaply before every dispatch without any digest work.
    """
    rows = tuple(fixture.resource_records())
    if not rows:
        raise InvalidInput('EMPTY_RESOURCE_RECORDS')
    for row in rows:
        if type(row) is not tuple or len(row) != 4:
            raise InvalidInput('INVALID_RESOURCE_RECORDS')
        resource_id, owner_id, marker, members = row
        if (type(resource_id) is not str or type(owner_id) is not str
                or type(marker) is not str or type(members) is not tuple
                or any(type(member) is not str for member in members)):
            raise InvalidInput('INVALID_RESOURCE_RECORDS')
    return tuple(sorted(rows))


def _expectation(fixture, spec_or_row):
    status, fields = fixture.reference_expectation(
        spec_or_row['identity_ref'], spec_or_row['endpoint_id'],
        tuple(sorted(spec_or_row['path_params'].items())),
        tuple(sorted(spec_or_row['query'].items())))
    if type(status) is not int or type(fields) is not dict:
        raise InvalidInput('INVALID_REFERENCE_EXPECTATION')
    return status, _fields_pairs(fields)


def _cross_check_identities(document, fixture):
    fixture_rows = tuple(fixture.identity_records())
    if any(type(row) is not tuple or len(row) != 4 for row in fixture_rows):
        raise InvalidInput('INVALID_FIXTURE_IDENTITIES')
    by_reference = {row[0]: row for row in fixture_rows}
    if len(by_reference) != len(fixture_rows):
        raise InvalidInput('DUPLICATE_FIXTURE_IDENTITY')
    identities = {}
    for row in document['identities']:
        reference = row['identity_ref']
        owner = by_reference.get(reference)
        if owner is None or owner[2] != row['role'] or owner[3] != row['credential_ref']:
            raise InvalidInput('IDENTITY_MISMATCH')
        identities[reference] = IdentityRow(reference, row['role'], row['credential_ref'])
    return MappingProxyType(identities), MappingProxyType(by_reference)


def build_snapshot(binding, fixture):
    """Trusted-host only: verify the fixture against a verified review binding."""
    if type(binding) is not ReviewedContractBinding:
        raise InvalidInput('REVIEWED_BINDING_REQUIRED')
    if type(binding.contract) is not SyntheticContract:
        raise InvalidInput('SYNTHETIC_CONTRACT_REQUIRED')
    fixture = _require_port(fixture)
    document = binding.contract.document

    if fixture.fixture_id() != document['fixture']['fixture_id']:
        raise InvalidInput('FIXTURE_ID_MISMATCH')
    if fixture.version() != document['fixture']['version']:
        raise InvalidInput('FIXTURE_VERSION_MISMATCH')
    if fixture.canonical_digest() != document['fixture']['content_sha256']:
        raise InvalidInput('FIXTURE_DIGEST_MISMATCH')
    if fixture.instance_id() != binding.fixture_instance_id:
        raise InvalidInput('FIXTURE_INSTANCE_MISMATCH')
    if fixture.contract_version() != document['contract_version']:
        raise InvalidInput('FIXTURE_CONTRACT_VERSION_MISMATCH')

    identities, fixture_identities = _cross_check_identities(document, fixture)
    identity_records = tuple(sorted(fixture.identity_records()))
    fingerprint = resource_fingerprint(fixture)

    endpoints = {}
    for row in document['endpoints']:
        endpoints[row['endpoint_id']] = EndpointSpec(
            row['endpoint_id'], row['path_template'],
            _pairs(row['path_domain']), _pairs(row['query_domain']))
    rules = {}
    for row in document['response_rules']:
        rules[row['rule_id']] = ResponseRule(
            row['rule_id'], row['status'],
            _fields_pairs(row['expected_fields']), tuple(sorted(row['evidence_fields'])))

    # Matrix cells: the fixture's declarative expectation must agree with the reviewed cell.
    matrix = {}
    for row in document['matrix']:
        status, fields = _expectation(fixture, row)
        if status != expected_status(row['identity_ref'], row['expected']):
            raise InvalidInput('MATRIX_MISMATCH')
        matrix[(row['endpoint_id'], row['method'], row['identity_ref'],
                tuple(sorted(row['path_params'].items())),
                tuple(sorted(row['query'].items())))] = row['expected']

    candidates = {}
    for row in document['candidates']:
        rule = rules.get(row['response_rule'])
        if rule is None:
            raise InvalidInput('MISSING_RESPONSE_RULE')
        status, fields = _expectation(fixture, row)
        if status != rule.status or fields != rule.expected_fields:
            raise InvalidInput('RESPONSE_RULE_MISMATCH')
        if status != expected_status(row['identity_ref'], row['expected']):
            raise InvalidInput('RESPONSE_RULE_MISMATCH')
        key = (row['endpoint_id'], row['method'], row['identity_ref'],
               tuple(sorted(row['path_params'].items())), tuple(sorted(row['query'].items())))
        if matrix.get(key) != row['expected']:
            raise InvalidInput('CANDIDATE_MATRIX_MISMATCH')
        candidates[row['check_id']] = CandidateSpec(
            row['check_id'], row['endpoint_id'], row['method'], row['identity_ref'],
            tuple(sorted(row['path_params'].items())), tuple(sorted(row['query'].items())),
            row['expected'], row['control_id'], row['response_rule'])
    if not candidates:
        raise InvalidInput('EMPTY_REVIEWED_CANDIDATES')

    budget = document['budget']
    if any(row['control_id'] is None for row in document['candidates'] if row['expected'] == 'DENY'):
        raise InvalidInput('INVALID_CONTROL')

    return ReviewedRunSnapshot(
        snapshot_id=binding.snapshot_id,
        contract_id=document['contract_id'],
        contract_version=document['contract_version'],
        contract_digest=binding.contract.contract_digest,
        scope_digest=binding.scope_digest,
        registry_snapshot_id=binding.snapshot_id,
        fixture_id=fixture.fixture_id(),
        fixture_version=fixture.version(),
        fixture_content_sha256=fixture.canonical_digest(),
        fixture_instance_id=fixture.instance_id(),
        budget_version=budget['version'],
        max_checks=budget['max_checks'],
        logical_timeout_seconds=budget['logical_timeout_seconds'],
        concurrency=budget['concurrency'],
        evidence_format=document['evidence']['format'],
        rule_version=document['evidence']['rule_version'],
        valid_until=binding.valid_until,
        port=document['target']['port'],
        limits=LIMITS,
        identity_records=identity_records,
        resource_fingerprint=fingerprint,
        candidates=MappingProxyType(candidates),
        endpoints=MappingProxyType(endpoints),
        identities=identities,
        rules=MappingProxyType(rules),
        matrix=MappingProxyType(matrix))

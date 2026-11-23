"""Two independent reviewed V2 synthetic business fixtures.

S1 ``documents``: per-document read permission.
S2 ``directories``: per-directory membership listing permission.

Both own their data, identity mapping, ACL and version.  Responses are produced
from that data; a contract's ``response_rules`` are never copied into a response.
No listener, socket or external client is imported or created.
"""
from typing import NamedTuple
import json
import re
import secrets
from uuid import uuid4

from .reviewed_fixture import FixturePort, canonical_digest, fixture_payload


class _Identity(NamedTuple):
    """Immutable identity record. A NamedTuple has no instance ``__dict__``."""

    reference: str
    user_id: object
    role: str
    credential_ref: object
    credential: object = None


class _Resource(NamedTuple):
    """Immutable resource record: ownership, marker and member ACL are read-only."""

    resource_id: str
    owner_id: str
    marker: str
    members: tuple = ()


class _ScenarioSpec(NamedTuple):
    """Immutable scenario definition; never a mutable module-level dict."""

    scenario: str
    fixture_id: str
    version: str
    endpoint_id: str
    param_name: str
    path_template: str
    resources: tuple
    identities: tuple


_SCENARIOS = (
    _ScenarioSpec(
        scenario='documents',
        fixture_id='catalog-documents',
        version='catalog-doc-v1',
        endpoint_id='document_read',
        param_name='document_id',
        path_template='/catalog/documents/{document_id}',
        resources=(
            _Resource('doc-a', 'u_owner', 'DOC_A_CANARY', ('u_reader',)),
            _Resource('doc-b', 'u_owner', 'DOC_B_CANARY', ()),
        ),
        identities=(
            ('anonymous', None, 'guest', None),
            ('doc-reader', 'u_reader', 'reader', 'fixture/catalog-doc-reader'),
            ('doc-owner', 'u_owner', 'owner', 'fixture/catalog-doc-owner'),
            ('doc-admin', 'u_admin', 'admin', 'fixture/catalog-doc-admin'),
        )),
    _ScenarioSpec(
        scenario='directories',
        fixture_id='catalog-directories',
        version='catalog-dir-v1',
        endpoint_id='directory_read',
        param_name='directory_id',
        path_template='/catalog/directories/{directory_id}',
        resources=(
            _Resource('dir-a', 'u_downer', 'DIR_A_CANARY', ('u_dviewer', 'u_deditor')),
            _Resource('dir-b', 'u_downer', 'DIR_B_CANARY', ()),
        ),
        identities=(
            ('anonymous', None, 'guest', None),
            ('dir-viewer', 'u_dviewer', 'viewer', 'fixture/catalog-dir-viewer'),
            ('dir-owner', 'u_downer', 'owner', 'fixture/catalog-dir-owner'),
            ('dir-admin', 'u_dadmin', 'admin', 'fixture/catalog-dir-admin'),
        )),
)

SCENARIOS = tuple(spec.scenario for spec in _SCENARIOS)

_DATA_FIELDS = frozenset(('_scenario', '_spec', '_instance', '_contract_version',
                          '_identities', '_resources'))


def _scenario(name):
    """Look up an immutable scenario definition; no module-level mutable mapping."""
    for spec in _SCENARIOS:
        if spec.scenario == name:
            return spec
    raise ValueError('UNKNOWN_CATALOG_SCENARIO')


class CatalogFixture(FixturePort):
    """Private, immutable business data with an independent credential set.

    The scenario definition is an immutable tuple record; each instance builds its
    own credential set and keeps resources and identities as tuples of NamedTuples.
    Ordinary attribute assignment cannot replace the business data references, and
    no mutable container is exposed to callers.
    """

    __slots__ = ('_scenario', '_spec', '_instance', '_contract_version',
                 '_identities', '_resources', '_sealed')

    def __init__(self, scenario):
        spec = _scenario(scenario)
        object.__setattr__(self, '_scenario', spec.scenario)
        object.__setattr__(self, '_spec', spec)
        instance = uuid4().hex
        object.__setattr__(self, '_instance', instance)
        object.__setattr__(self, '_contract_version', 'v1')
        object.__setattr__(self, '_identities', tuple(
            _Identity(reference, user_id, role, credential_ref,
                      None if credential_ref is None else
                      'catalog_' + instance + '_' + reference.replace('-', '_') + '_'
                      + secrets.token_hex(16))
            for reference, user_id, role, credential_ref in spec.identities))
        # Fresh per-instance tuple of immutable resource records; no shared aliases.
        object.__setattr__(self, '_resources',
                           tuple(_Resource(row.resource_id, row.owner_id, row.marker,
                                           tuple(row.members)) for row in spec.resources))
        object.__setattr__(self, '_sealed', True)

    def __setattr__(self, name, value):
        if getattr(self, '_sealed', False) and name in _DATA_FIELDS:
            raise AttributeError('FIXTURE_DATA_IMMUTABLE')
        object.__setattr__(self, name, value)

    def __delattr__(self, name):
        if getattr(self, '_sealed', False) and name in _DATA_FIELDS:
            raise AttributeError('FIXTURE_DATA_IMMUTABLE')
        object.__delattr__(self, name)

    # -- FixturePort ---------------------------------------------------------
    def scenario(self):
        return self._scenario

    def fixture_id(self):
        return self._spec.fixture_id

    def version(self):
        return self._spec.version

    def contract_version(self):
        return self._contract_version

    def instance_id(self):
        return 'fixture_' + self._instance

    def endpoint_id(self):
        return self._spec.endpoint_id

    def path_template(self):
        return self._spec.path_template

    def param_name(self):
        return self._spec.param_name

    def resource_ids(self):
        return tuple(sorted(row.resource_id for row in self._resources))

    def resource_records(self):
        """Immutable ``((resource_id, owner_id, marker, members), ...)`` for binding checks."""
        return tuple(sorted((row.resource_id, row.owner_id, row.marker,
                             tuple(row.members)) for row in self._resources))

    def identity_records(self):
        return tuple((row.reference, row.user_id, row.role, row.credential_ref)
                     for row in self._identities)

    def credentials(self):
        return {row.credential_ref: row.credential
                for row in self._identities if row.credential_ref is not None}

    def canonical_digest(self):
        resources = self.resource_records()
        return canonical_digest(fixture_payload(
            scenario=self._scenario, fixture_id=self.fixture_id(), version=self.version(),
            contract_version=self._contract_version,
            identities=self.identity_records(),
            resources=[list(row) for row in resources],
            acl=[(row[0], member) for row in resources for member in row[3]],
            markers=[row[2] for row in resources]))

    # -- declarative reference expectation (never parses a request) ----------
    def _identity_by_reference(self, reference):
        for row in self._identities:
            if row.reference == reference:
                return row
        return None

    def _public_fields(self, resource):
        return {'resource_id': resource.resource_id, 'owner_id': resource.owner_id,
                'marker': resource.marker}

    def _permitted(self, identity, resource):
        if identity.user_id is None:
            return False
        if identity.role == 'admin':
            return True
        if identity.user_id == resource.owner_id:
            return True
        return identity.user_id in resource.members

    def _resource(self, resource_id):
        """Linear lookup over the immutable tuple; no mutable mapping is retained."""
        for row in self._resources:
            if row.resource_id == resource_id:
                return row
        return None

    def reference_expectation(self, identity_ref, endpoint_id, path_params, query):
        """Return ``(status, fields)`` derived from data and ACL only."""
        if endpoint_id != self.endpoint_id():
            raise ValueError('UNKNOWN_FIXTURE_ENDPOINT')
        if query:
            raise ValueError('FIXTURE_QUERY_NOT_DECLARED')
        identity = self._identity_by_reference(identity_ref)
        if identity is None:
            raise ValueError('UNKNOWN_FIXTURE_IDENTITY')
        params = dict(path_params)
        if set(params) != {self.param_name()}:
            raise ValueError('FIXTURE_PARAMETER_MISMATCH')
        resource = self._resource(params[self.param_name()])
        if identity.user_id is None:
            return 401, {'error_code': 'AUTHENTICATION_REQUIRED'}
        if resource is None or not self._permitted(identity, resource):
            return 403, {'error_code': 'ACCESS_DENIED'}
        return 200, self._public_fields(resource)

    # -- request handling (only for an accepted delivery) --------------------
    def _parse_wire(self, wire):
        if type(wire) is not bytes or b'\r\n\r\n' not in wire or len(wire) > 16384:
            raise ValueError('INVALID_FIXTURE_REQUEST')
        head = wire.split(b'\r\n\r\n', 1)[0]
        lines = head.split(b'\r\n')
        match = re.fullmatch(rb'GET ([^ ]+) HTTP/1\.1', lines[0])
        if not match:
            raise ValueError('INVALID_FIXTURE_REQUEST_LINE')
        target = match.group(1).decode('ascii')
        headers = {}
        for line in lines[1:]:
            if b':' not in line:
                raise ValueError('INVALID_FIXTURE_HEADER')
            name, value = line.split(b':', 1)
            name = name.strip().lower().decode('ascii', 'strict')
            if name in headers:
                raise ValueError('DUPLICATE_FIXTURE_HEADER')
            headers[name] = value.strip()
        action_id = headers.get('x-p3-action-id', b'').decode('ascii', 'strict')
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', action_id):
            raise ValueError('INVALID_ACTION_ID')
        bearer = None
        if 'authorization' in headers:
            value = headers['authorization']
            if not value.startswith(b'Bearer '):
                raise ValueError('INVALID_AUTHORIZATION')
            bearer = value[7:].decode('ascii', 'strict')
        return target, action_id, bearer

    def _match_target(self, target):
        template = self.path_template()
        prefix, suffix = template.split('{' + self.param_name() + '}')
        if not target.startswith(prefix) or (suffix and not target.endswith(suffix)):
            raise ValueError('UNKNOWN_FIXTURE_TARGET')
        middle = target[len(prefix):len(target) - len(suffix) if suffix else None]
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', middle):
            raise ValueError('UNKNOWN_FIXTURE_TARGET')
        return {self.param_name(): middle}

    def _identity_by_credential(self, credential):
        if credential is None:
            return self._identity_by_reference('anonymous')
        for row in self._identities:
            if row.credential is not None and secrets.compare_digest(row.credential, credential):
                return row
        return None

    def handle(self, wire):
        target, action_id, bearer = self._parse_wire(wire)
        path_params = self._match_target(target)
        identity = self._identity_by_credential(bearer)
        if identity is None:
            status, fields = 401, {'error_code': 'AUTHENTICATION_REQUIRED'}
        else:
            status, fields = self.reference_expectation(
                identity.reference, self.endpoint_id(), tuple(path_params.items()), ())
        body = json.dumps(dict(request_id=action_id, fixture_instance_id=self.instance_id(),
                               contract_version=self._contract_version, fields=fields),
                          sort_keys=True, ensure_ascii=False, allow_nan=False).encode('utf-8')
        reason = {200: 'OK', 401: 'Unauthorized', 403: 'Forbidden'}[status]
        head = ('HTTP/1.1 %d %s\r\nContent-Type: application/json\r\n'
                'Content-Length: %d\r\nConnection: close\r\n\r\n' % (status, reason, len(body)))
        return head.encode('ascii') + body

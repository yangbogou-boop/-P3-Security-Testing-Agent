"""Synthetic business responses only; independent of Agent verdict/matrix code.

The manager is a trusted local fixture interface, not an HTTP management API.
All credentials are minted here for synthetic identities; none are imported.
"""
from dataclasses import dataclass, field
from enum import Enum
import json
import re
import secrets
from uuid import uuid4


class RequestRejected(ValueError):
    """Fixed diagnostic only. Never include raw request data or exception text."""


class Mode(str, Enum):
    GOOD = 'Good'
    AUTH = 'Known Bad / AUTH'
    BOLA = 'Known Bad / BOLA'
    RBAC = 'Known Bad / RBAC'


@dataclass(frozen=True)
class MockRequest:
    # Even repr(request) must not leak credentials or unapproved paths/parameters.
    method: str = field(repr=False)
    target: str = field(repr=False)
    action_id: str = field(repr=False)
    credential: object = field(default=None, repr=False)


@dataclass(frozen=True)
class MockResponse:
    status: int
    headers: tuple
    body: bytes = field(repr=False)

    def to_bytes(self):
        reason = {200: 'OK', 401: 'Unauthorized', 403: 'Forbidden'}[self.status]
        head = ['HTTP/1.1 ' + str(self.status) + ' ' + reason]
        head.extend(name + ': ' + value for name, value in self.headers)
        return ('\r\n'.join(head) + '\r\n\r\n').encode('ascii') + self.body


@dataclass(frozen=True)
class _Identity:
    reference: str
    user_id: str
    role: str
    credential_ref: str
    credential: str = field(repr=False)


@dataclass(frozen=True)
class Fixture:
    fixture_instance_id: str
    _mode: Mode = field(repr=False)
    _identities: tuple = field(repr=False)
    contract_version: str = field(default='p3-http-v1', init=False)

    def credential_for(self, identity_ref):
        """Trusted harness only; this is not a client login or authorization API."""
        if type(identity_ref) is not str:
            raise RequestRejected('UNKNOWN_FIXTURE_IDENTITY')
        if identity_ref == 'anonymous':
            return None
        for identity in self._identities:
            if identity.reference == identity_ref:
                return identity.credential
        raise RequestRejected('UNKNOWN_FIXTURE_IDENTITY')

    def credential_bindings(self):
        """Fresh private mapping for a trusted run; never pass to logging/Evidence."""
        return {i.credential_ref: i.credential for i in self._identities}

    def _authenticate(self, credential):
        if credential is None:
            return None
        # Arbitrary or stale credentials do not establish an identity, in any mode.
        if type(credential) is not str or not credential.isascii() or len(credential) > 256:
            raise RequestRejected('INVALID_CREDENTIAL_INPUT')
        for identity in self._identities:
            if secrets.compare_digest(credential, identity.credential):
                return identity
        return None

    def _response(self, request_id, status, content):
        payload = dict(fixture_instance_id=self.fixture_instance_id,
                       contract_version=self.contract_version, request_id=request_id, **content)
        body = json.dumps(payload, ensure_ascii=True, separators=(',', ':'), allow_nan=False).encode('utf-8')
        return MockResponse(status, (('Content-Type', 'application/json'),
                                    ('Content-Length', str(len(body))), ('Connection', 'close')), body)

    def handle(self, request):
        """Handle one structured request without I/O or mutation of the fixture.

        The caller supplies the Controller's unique action_id. Repeating the same
        request is deterministic; this function neither retries nor grants test scope.
        """
        if type(request) is not MockRequest:
            raise RequestRejected('INVALID_REQUEST_STRUCTURE')
        if (type(request.action_id) is not str
                or not re.fullmatch(r'action_[0-9a-f]{32}', request.action_id)):
            raise RequestRejected('INVALID_ACTION_ID')
        targets = ('/v1/profile', '/v1/objects/obj-a', '/v1/objects/obj-b',
                   '/v1/admin/report?period=demo')
        if type(request.method) is not str or request.method != 'GET':
            raise RequestRejected('METHOD_NOT_ALLOWED')
        if type(request.target) is not str or request.target not in targets:
            raise RequestRejected('UNREGISTERED_REQUEST_TARGET')

        identity = self._authenticate(request.credential)
        # AUTH defect is deliberately limited to a truly anonymous profile access.
        # A supplied but invalid/stale credential is never treated as a valid user.
        anonymous_profile_bug = (self._mode == Mode.AUTH and request.target == '/v1/profile'
                                 and request.credential is None)
        if identity is None and not anonymous_profile_bug:
            return self._response(request.action_id, 401, {'error': {'code': 'AUTHENTICATION_REQUIRED'}})

        if request.target == '/v1/profile':
            user_id, role = ('alice', 'member') if anonymous_profile_bug else (identity.user_id, identity.role)
            return self._response(request.action_id, 200, {'data': dict(
                user_id=user_id, role=role, profile_marker=user_id.upper() + '_PROFILE_CANARY')})

        if request.target.startswith('/v1/objects/'):
            object_id = request.target.rsplit('/', 1)[1]
            owner, marker = {'obj-a': ('alice', 'OBJECT_A_CANARY'),
                             'obj-b': ('bob', 'OBJECT_B_CANARY')}[object_id]
            if self._mode != Mode.BOLA and identity.user_id != owner:
                return self._response(request.action_id, 403, {'error': {'code': 'ACCESS_DENIED'}})
            return self._response(request.action_id, 200, {'data': dict(
                object_id=object_id, owner_id=owner, protected_marker=marker)})

        if self._mode != Mode.RBAC and identity.role != 'admin':
            return self._response(request.action_id, 403, {'error': {'code': 'ACCESS_DENIED'}})
        return self._response(request.action_id, 200, {'data': dict(
            period='demo', audience='admin', report_marker='ADMIN_REPORT_CANARY')})


class FixtureManager:
    """Mint independent immutable instances. Reset never mutates an old instance.

    C-2's trusted supervisor must retire the old service/run before switching its
    active reference. A retained Python object is not a running HTTP service.
    """
    @staticmethod
    def reset(mode=Mode.GOOD):
        if type(mode) is not Mode:
            raise RequestRejected('INVALID_FIXTURE_MODE')
        instance = uuid4().hex
        identities = tuple(_Identity(ref, user, role, credential_ref,
                                     'mock_' + instance + '_' + user + '_' + secrets.token_hex(24))
                           for ref, user, role, credential_ref in (
                               ('user_alice', 'alice', 'member', 'fixture/alice'),
                               ('user_bob', 'bob', 'member', 'fixture/bob'),
                               ('admin_carol', 'carol', 'admin', 'fixture/carol')))
        return Fixture('fixture_' + instance, mode, identities)

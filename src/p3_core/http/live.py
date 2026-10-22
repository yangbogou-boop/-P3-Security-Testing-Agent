"""Gated real transport components. Import/construction never opens a socket.

No CLI can activate this path. The trusted host must supply real reviewed records
and a live fixture binding. Tests use explicit memory transport in SimulationRun.
"""
import errno
import socket
import select
import time
import hashlib
import json
from dataclasses import dataclass
from threading import Event, get_ident

from ..models import InvalidInput
from .machine import SimulationRun


class InstanceStatus:
    """Trusted supervisor invalidation bit; no callbacks or I/O in a dispatch gate."""
    def __init__(self):
        self._invalid = Event()

    def invalidate(self):
        self._invalid.set()

    @property
    def current(self):
        return not self._invalid.is_set()


def credential_binding_digest(credentials):
    """Trusted supervisor binding; never persist the raw generated credentials."""
    if (type(credentials) is not dict or not credentials or
            any(type(k) is not str or type(v) is not str for k,v in credentials.items())):
        raise InvalidInput('CREDENTIAL_BINDING_INVALID')
    return hashlib.sha256(json.dumps(credentials,sort_keys=True).encode('utf-8')).hexdigest()


@dataclass(frozen=True)
class FixtureBinding:
    instance_id: str
    scope_digest: str
    supervisor_record_ref: str
    status: InstanceStatus
    credential_digest: str

    def verify(self, config):
        from ..models import identifier
        identifier(self.supervisor_record_ref)
        if (self.instance_id != config.fixture_instance_id or self.scope_digest != config.scope_digest
                or type(self.status) is not InstanceStatus or not self.status.current):
            raise InvalidInput('FIXTURE_BINDING_INVALID')

    def verify_credentials(self, credentials):
        if credential_binding_digest(credentials)!=self.credential_digest:
            raise InvalidInput('CREDENTIAL_BINDING_INVALID')


class _SocketTransport:
    """Internal one-connection transport. It cannot choose a target or retry.

    Only created by AuthorizedHttpRun after approval. All socket creation/connect
    and send happen inside that Controller's gate. No urllib/proxy/redirect layer.
    """
    def __init__(self, owner, request):
        self._owner, self._request = owner, request
        self._socket = None
        self._connected = False
        self._closed = False

    def _guard(self):
        active = self._owner._active
        if (active is None or active['request'] is not self._request
                or active['transport'] is not self or active['generation'] != self._owner.generation
                or self._owner.state != 'RUNNING' or self._owner.snapshot.synthetic
                or self._owner._revoked or self._closed):
            raise InvalidInput('EXECUTION_OBJECT_NOT_CURRENT')

    def connect(self, address):
        self._guard()
        if self._socket is not None or address != ('127.0.0.1', self._owner.config.port):
            raise InvalidInput('CONNECTION_NOT_APPROVED')
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.setblocking(False)
        code = self._socket.connect_ex(address)
        if code == 0:
            return 'CONNECTED'
        if code in (errno.EINPROGRESS, errno.EWOULDBLOCK, errno.EALREADY, 10035, 10036, 10037):
            return 'PENDING'
        raise OSError('CONNECT_FAILED')

    def connected(self):
        self._guard()
        _, writable, exceptional = select.select([], [self._socket], [self._socket], 0)
        if not writable and not exceptional:
            return None
        if self._socket.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR):
            raise OSError('CONNECT_FAILED')
        peer = self._socket.getpeername()
        self._connected = peer == ('127.0.0.1', self._owner.config.port)
        return peer

    def send(self, buffer, offset):
        self._guard()
        active = self._owner._active
        if (not self._connected or offset != active['offset']
                or buffer != self._request.wire[offset:]):
            raise InvalidInput('REQUEST_BYTES_CHANGED')
        return self._socket.send(buffer)

    def receive(self):
        self._guard()
        return self._socket.recv(min(4096, self._owner.config.limits.response_bytes))

    def close(self):
        if self._owner._owner is not None and self._owner._owner!=get_ident():
            raise InvalidInput('SINGLE_IO_OWNER_REQUIRED')
        if not self._closed:
            if self._socket is not None:
                self._socket.close()
            self._closed = True


class AuthorizedHttpRun(SimulationRun):
    """Controller-owned live state machine; no arbitrary transport injection.

    snapshot(simulation=False) must succeed AND the trusted fixture binding must
    remain current. Synthetic material cannot be converted by a CLI flag.
    Host authenticity remains an operational trust boundary, not a signature claim.
    """
    simulation = False
    provenance = 'ACTUAL_HTTP'
    mode = 'http-local'
    io_event_kind = 'http_io'

    def __init__(self, raw, registry, *, binding, **kwargs):
        self.binding = binding
        super().__init__(raw, registry, **kwargs)

    def _snapshot_for_run(self, wall):
        snapshot = self._registry.snapshot(self.config, wall, simulation=False)
        if type(self.binding) is not FixtureBinding:
            raise InvalidInput('FIXTURE_BINDING_INVALID')
        self.binding.verify(self.config)
        self.binding.verify_credentials(self._credentials)
        return snapshot

    def _conditions_locked(self, error=None):
        reasons = super()._conditions_locked(error)
        if self.config is not None:
            try: self.binding.verify(self.config)
            except Exception:
                if 'AUTHORIZATION_INVALID' not in reasons:
                    reasons.insert(1 if reasons and reasons[0] == 'REVOKED' else 0, 'AUTHORIZATION_INVALID')
        return reasons

    def _make_transport(self, supplied, request):
        if supplied is not None:
            raise InvalidInput('LIVE_TRANSPORT_INJECTION_FORBIDDEN')
        if self.snapshot.synthetic:
            raise InvalidInput('PENDING_AUTHORIZATION')
        return _SocketTransport(self, request)

    def _first_send_locked(self):
        self._requests += 1

    def lifecycle_status(self):
        """Nonblocking observation; never closes another owner's socket."""
        if not self._lock.acquire(blocking=False):
            return dict(revoked=self._revoked, clean=False, failed=self._cleanup_failed or self._audit_gap)
        try:
            with self._gate:
                clean=self._revoked and (self._active is None or self._active.get('closed',False))
                return dict(revoked=self._revoked,clean=bool(clean),failed=self._cleanup_failed or self._audit_gap)
        finally: self._lock.release()

    def run_until_terminal(self):
        """Explicit trusted-host driver only. Never called by ordinary CLI/tests."""
        self.start()
        try:
            while self.state == 'RUNNING':
                self.step()
                self.settle()
                # Bounded scheduling wait outside the revocation gate.
                if self.state == 'RUNNING': time.sleep(0.001)
        finally:
            if self.state == 'RUNNING': self.poll('RUNTIME_ERROR')
            self._cleanup()
        return self.finalize()

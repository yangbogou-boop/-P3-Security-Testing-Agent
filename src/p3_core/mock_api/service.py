"""Permission-gated listener component; NEVER started by offline CLI or tests."""
import socketserver
import time
from threading import Lock

from ..models import InvalidInput
from ..http.live import FixtureBinding
from .adapter import ServiceAdapter
from .core import RequestRejected


class AuthorizedService:
    def __init__(self, config, registry, fixture, binding, *, wall_clock=time.time):
        self.config, self.registry, self.fixture, self.binding = config, registry, fixture, binding
        self.wall_clock = wall_clock
        self._gate = Lock()
        self._server = None
        self._revoked = False
        self.snapshot = None

    def _check(self):
        if self._revoked or type(self.binding) is not FixtureBinding:
            raise InvalidInput('PENDING_AUTHORIZATION')
        self.binding.verify(self.config)
        self.binding.verify_credentials(self.fixture.credential_bindings())
        if self.fixture.fixture_instance_id != self.config.fixture_instance_id:
            raise InvalidInput('FIXTURE_BINDING_INVALID')
        if self.snapshot is not None:
            if self.snapshot.synthetic or self.wall_clock() >= self.snapshot.valid_until:
                raise InvalidInput('PENDING_AUTHORIZATION')

    def start(self):
        # Material read/verification occurs before the short bind authorization gate.
        snapshot = self.registry.snapshot(self.config, self.wall_clock(), simulation=False)
        adapter = ServiceAdapter(self.fixture, self.config.port, self.config.limits.header_bytes)
        service = self

        class Handler(socketserver.BaseRequestHandler):
            def handle(self):
                # Server is serial, read-only, one request/connection, bounded in bytes/time.
                try:
                    service._check()
                    deadline=time.monotonic()+min(2.0, service.config.budget.logical_timeout_seconds)
                    raw = bytearray()
                    while b'\r\n\r\n' not in raw:
                        remaining=deadline-time.monotonic()
                        if remaining<=0: return
                        self.request.settimeout(remaining)
                        piece = self.request.recv(min(1024, adapter.header_limit + 1 - len(raw)))
                        if not piece: return
                        raw.extend(piece)
                        if len(raw) > adapter.header_limit: return
                    result = adapter.handle_bytes(bytes(raw))
                    service._check()
                    remaining=deadline-time.monotonic()
                    if remaining<=0: return
                    self.request.settimeout(remaining)
                    self.request.sendall(result)
                except (OSError, RequestRejected, InvalidInput):
                    return  # no raw request/error logging; socketserver closes connection.

        class Server(socketserver.TCPServer):
            allow_reuse_address = False
            def handle_error(self, request, client_address):
                pass  # do not dump credentials/locals/exception text.

        with self._gate:
            if self._server is not None: raise InvalidInput('SERVICE_ALREADY_STARTED')
            self.snapshot = snapshot
            self._check()
            self._server = Server(('127.0.0.1', self.config.port), Handler)
            self._server.timeout = 0.05

    def serve_once(self):
        self._check()
        if self._server is None: raise InvalidInput('SERVICE_NOT_STARTED')
        self._server.handle_request()

    def revoke(self):
        with self._gate:
            self._revoked = True
        # Active read/write bounded by timeout; no claim that sent bytes are retractable.

    def close(self):
        self.revoke()
        if self._server is not None:
            self._server.server_close()

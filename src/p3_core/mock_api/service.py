"""Permission-gated listener component; NEVER started by offline CLI or tests."""
import socketserver
import select
import time
from threading import Lock, get_ident

from ..models import InvalidInput, number
from ..evidence import unique_id
from ..http.live import FixtureBinding
from .adapter import ServiceAdapter
from .core import RequestRejected


class AuthorizedService:
    def __init__(self, config, registry, fixture, binding, *, wall_clock=time.time, clock=time.monotonic):
        self.config, self.registry, self.fixture, self.binding = config, registry, fixture, binding
        self.wall_clock = wall_clock
        self.clock = clock
        self._gate = Lock()
        self._server = None
        self._revoked = False
        self.snapshot = None
        self._permit_deadline = None
        self._last_clock = None
        self._owner = None
        self._handling = False
        self.gate_sequence = 0
        self.revoke_requested_at = None
        self.revoke_effective_sequence = None
        self.revoke_effective_at = None
        self.cleanup_failed = False
        self.last_connection = None

    def _check(self):
        if self._revoked:
            raise InvalidInput('REVOKED')
        if self.cleanup_failed:
            raise InvalidInput('RUNTIME_ERROR')
        if self.snapshot is None or type(self.binding) is not FixtureBinding:
            raise InvalidInput('PENDING_AUTHORIZATION')
        self.binding.verify(self.config)
        self.binding.verify_credentials(self.fixture.credential_bindings())
        if self.fixture.fixture_instance_id != self.config.fixture_instance_id:
            raise InvalidInput('FIXTURE_BINDING_INVALID')
        now=number(self.clock())
        if self._last_clock is not None and now<self._last_clock:
            raise InvalidInput('RUNTIME_ERROR')
        self._last_clock=now
        if (self.snapshot.synthetic or number(self.wall_clock()) >= self.snapshot.valid_until
                or self._permit_deadline is None or now>=self._permit_deadline):
            raise InvalidInput('AUTHORIZATION_INVALID')

    def _check_connection(self, deadline):
        self._check()
        if number(self.clock())>=deadline: raise InvalidInput('TIMEOUT')

    def _wait_ready(self, connection, writing, deadline):
        # Readiness is advisory, never a permission. No gate held while waiting.
        delay=max(0.0,min(0.01,deadline-number(self.clock())))
        readers,writers,_=select.select([] if writing else [connection],
                                        [connection] if writing else [],[],delay)
        return bool(writers if writing else readers)

    def _handle_connection(self, connection):
        with self._gate:
            if self._owner is None: self._owner=get_ident()
            if self._owner!=get_ident() or self._handling:
                raise InvalidInput('SINGLE_IO_OWNER_REQUIRED')
            self._handling=True
        record=dict(connection_id=unique_id('connection'),sent_bytes=0,received_bytes=0,
                    first_send_sequence=None,last_send_sequence=None,reason=None,cleanup_failed=False)
        try:
            connection.setblocking(False)
            with self._gate: self._check()
            deadline=number(self.clock())+min(2.0,self.config.budget.logical_timeout_seconds)
            adapter=ServiceAdapter(self.fixture,self.config.port,self.config.limits.header_bytes)
            raw=bytearray()
            while b'\r\n\r\n' not in raw:
                with self._gate: self._check_connection(deadline)
                if not self._wait_ready(connection,False,deadline): continue
                with self._gate: self._check_connection(deadline)
                try: piece=connection.recv(min(1024,adapter.header_limit+1-len(raw)))
                except BlockingIOError: continue
                if not piece: raise InvalidInput('TRUNCATED_REQUEST')
                raw.extend(piece);record['received_bytes']+=len(piece)
                if len(raw)>adapter.header_limit: raise InvalidInput('REQUEST_TOO_LARGE')
            result=adapter.handle_bytes(bytes(raw))
            while record['sent_bytes']<len(result):
                with self._gate: self._check_connection(deadline)
                if not self._wait_ready(connection,True,deadline): continue
                with self._gate:
                    self._check_connection(deadline)
                    self.gate_sequence+=1
                    try: n=connection.send(result[record['sent_bytes']:])
                    except BlockingIOError: continue
                    if type(n) is not int or not 0<n<=len(result)-record['sent_bytes']:
                        raise InvalidInput('TRANSPORT_ERROR')
                    if record['first_send_sequence'] is None:
                        record['first_send_sequence']=self.gate_sequence
                    record['sent_bytes']+=n
                    record['last_send_sequence']=self.gate_sequence
                    # Preserve bytes already accepted even if deadline crossed in send.
                    self._check_connection(deadline)
            record['reason']='RESPONSE_SENT'
        except InvalidInput as error:
            allowed={'REVOKED','TIMEOUT','AUTHORIZATION_INVALID','PENDING_AUTHORIZATION',
                     'FIXTURE_BINDING_INVALID','CREDENTIAL_BINDING_INVALID','RUNTIME_ERROR',
                     'TRUNCATED_REQUEST','REQUEST_TOO_LARGE','TRANSPORT_ERROR'}
            record['reason']=str(error) if str(error) in allowed else 'INVALID_REQUEST'
        except RequestRejected: record['reason']='INVALID_REQUEST'
        except TimeoutError: record['reason']='TIMEOUT'
        except OSError: record['reason']='TRANSPORT_ERROR'
        except Exception: record['reason']='RUNTIME_ERROR'
        finally:
            # The I/O owner closes outside the gate; revoke never waits for close.
            try: connection.close()
            except Exception:
                record['cleanup_failed']=True
                self.cleanup_failed=True
            with self._gate:
                if self._revoked: record['reason']='REVOKED'
                record['revoke_requested_at']=self.revoke_requested_at
                record['revoke_effective_sequence']=self.revoke_effective_sequence
                record['revoke_effective_at']=self.revoke_effective_at
                self.last_connection=record
                self._handling=False

    def start(self):
        # Material read/verification occurs before the short bind authorization gate.
        anchor=number(self.clock())
        wall=number(self.wall_clock())
        snapshot = self.registry.snapshot(self.config, wall, simulation=False)
        service = self

        class Handler(socketserver.BaseRequestHandler):
            def handle(self):
                service._handle_connection(self.request)

        class Server(socketserver.TCPServer):
            allow_reuse_address = False
            def handle_error(self, request, client_address):
                pass  # do not dump credentials/locals/exception text.
            def shutdown_request(self, request):
                # Idempotent close also covers failure before Handler ownership.
                # Do not use socketserver's blocking shutdown/write path.
                try: request.close()
                except Exception: service.cleanup_failed=True

        with self._gate:
            if self._server is not None: raise InvalidInput('SERVICE_ALREADY_STARTED')
            self.snapshot = snapshot
            self._permit_deadline=anchor+(snapshot.valid_until-wall)
            self._check()
            self._server = Server(('127.0.0.1', self.config.port), Handler)
            self._server.timeout = 0.05

    def serve_once(self):
        with self._gate:
            if self._owner is None: self._owner=get_ident()
            if self._owner!=get_ident(): raise InvalidInput('SINGLE_IO_OWNER_REQUIRED')
            self._check()
        if self._server is None: raise InvalidInput('SERVICE_NOT_STARTED')
        self._server.handle_request()

    def revoke(self):
        try: received=number(self.clock())
        except Exception: received=None
        with self._gate:
            if not self._revoked:
                self.revoke_requested_at=received
                self.gate_sequence+=1
                self.revoke_effective_sequence=self.gate_sequence
                try: self.revoke_effective_at=number(self.clock())
                except Exception: self.revoke_effective_at=None
                self._revoked=True
        # No waits, disk, or cross-thread close. Already accepted bytes cannot retract.

    def close(self):
        self.revoke()
        if self._server is not None:
            try: self._server.server_close()
            except Exception:
                self.cleanup_failed=True
                raise InvalidInput('SERVICE_CLOSE_FAILED') from None

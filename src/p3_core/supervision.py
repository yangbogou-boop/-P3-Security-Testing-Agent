"""Lifecycle coordination only: no start, network permission, dispatch or replay."""
from dataclasses import dataclass
from threading import Lock
import time

from .models import InvalidInput, identifier, number
from .http.contract import HttpConfig
from .http.live import AuthorizedHttpRun
from .mock_api.service import AuthorizedService
from .mock_api import FixtureManager
from .mock_api.core import Fixture
from .coordination import EvidenceCoordinator


@dataclass(frozen=True)
class RunBinding:
    run_id: str
    fixture_instance_id: str
    scope_digest: str
    authorization_version: str
    generation: int

    def __post_init__(self):
        for v in (self.run_id,self.fixture_instance_id,self.authorization_version): identifier(v)
        if type(self.scope_digest) is not str or (len(self.scope_digest)!=64 or any(c not in '0123456789abcdef' for c in self.scope_digest)):
            raise InvalidInput('INVALID_SCOPE')
        if type(self.generation) is not int or self.generation<0: raise InvalidInput('INVALID_GENERATION')


class LifecyclePort:
    """Trusted host adapter; exposes revoke and observation, never start/step."""
    def __init__(self, endpoint, binding):
        if type(endpoint) is AuthorizedHttpRun:
            config=endpoint.config or HttpConfig.parse(endpoint._raw)
            if endpoint.run_id!=binding.run_id: raise InvalidInput('RUN_MISMATCH')
            endpoint.binding.verify(config)
            endpoint.binding.verify_credentials(endpoint._credentials)
        elif type(endpoint) is AuthorizedService:
            config=endpoint.config
            endpoint.binding.verify(config)
            if endpoint.fixture.fixture_instance_id!=binding.fixture_instance_id:
                raise InvalidInput('FIXTURE_MISMATCH')
            endpoint.binding.verify_credentials(endpoint.fixture.credential_bindings())
        else: raise InvalidInput('INVALID_LIFECYCLE_ENDPOINT')
        if (config.fixture_instance_id!=binding.fixture_instance_id or config.scope_digest!=binding.scope_digest
                or config.authorization_version!=binding.authorization_version):
            raise InvalidInput('BINDING_MISMATCH')
        self.endpoint,self.binding=endpoint,binding

    def revoke(self): self.endpoint.revoke()
    def status(self): return self.endpoint.lifecycle_status()
    def invalidate(self): self.endpoint.binding.status.invalidate()

    def actions(self):
        if type(self.endpoint) is not AuthorizedHttpRun:raise InvalidInput('CLIENT_REQUIRED')
        if not self.endpoint._lock.acquire(blocking=False):raise InvalidInput('OWNER_BUSY')
        try:return tuple(s.action_id for s in self.endpoint._slots if s.action_id and s.authorization=='ALLOW')
        finally:self.endpoint._lock.release()

    def attach_consumer(self,consumer):
        if type(self.endpoint) is not AuthorizedService:raise InvalidInput('SERVICE_REQUIRED')
        self.endpoint.attach_summary_consumer(consumer)


class Supervisor:
    """One immutable run. Poll cleanup; I/O owners must do their own closing.

    Fake ports are for offline tests only. No constructor here grants permission.
    Revoke order is selectable for deterministic scheduling; no nested gate calls.
    """
    def __init__(self,binding,client,service,*,clock=time.monotonic,cleanup_timeout=5,evidence=None):
        if client.binding!=binding or service.binding!=binding: raise InvalidInput('BINDING_MISMATCH')
        if any(p.status()['revoked'] or p.status()['failed'] for p in (client,service)):
            raise InvalidInput('STALE_ENDPOINT')
        if number(cleanup_timeout)<=0: raise InvalidInput('INVALID_TIMEOUT')
        self.binding,self.client,self.service=binding,client,service
        self.clock,self.timeout,self.evidence=clock,cleanup_timeout,evidence
        self._lock=Lock();self._observation=Lock();self.state='BOUND';self.reason=None;self._deadline=None
        self._issued=False;self._revocation_done=False;self._last=None;self.audit_failed=False
        self.coordinator=None
        self._reset_reserved=False;self._transition_sequence=0
        self._failure_sequence=None;self._reset_commit_sequence=None
        self._reset_commit_count=0;self._committed_fixture_id=None;self._next_fixture=None

    def attach_evidence(self,coordinator):
        if type(coordinator) is not EvidenceCoordinator or coordinator.binding!=self.binding or self.state!='BOUND' or self.coordinator is not None:
            raise InvalidInput('BINDING_MISMATCH')
        coordinator.on_failure=self._evidence_failed
        def consume(row):
            result=coordinator.accept(row,self.binding)
            if result not in ('CORRELATED','DUPLICATE'):raise InvalidInput('EVIDENCE_INCOMPLETE')
        self.service.attach_consumer(consume)
        self.coordinator=coordinator

    def _latch_failure(self,reason):
        # Same short gate as reference publication: neither path does I/O here.
        with self._lock:
            self.audit_failed=True
            if self._failure_sequence is None:
                self._transition_sequence+=1
                self._failure_sequence=self._transition_sequence
                self.reason=reason
            self.state='FAILED'
            self._next_fixture=None

    def _evidence_failed(self):
        self._latch_failure('EVIDENCE_INCOMPLETE')
        self.revoke()

    def _evidence_status(self):
        if self.coordinator is None:return 'MISSING'
        try:status=self.coordinator.completion_status()
        except Exception:status='UNVERIFIED'
        if status not in ('PENDING','VERIFIED'):
            self._evidence_failed()
        return status

    def register_actions(self):
        """Declare expected actions after prepare, before the next owner step.

        This list alone is not a trusted source. The coordinator must separately
        capture the actual offline Controller before finish; without that root
        completion is SOURCE_UNVERIFIED and cannot authorize fixture retirement.
        This adapter does not certify live Controller or service provenance.
        """
        if self.state!='BOUND' or self.coordinator is None:raise InvalidInput('NOT_BOUND')
        try:
            for action in self.client.actions():self.coordinator.expect(action,self.binding)
        except Exception:
            self.revoke();raise InvalidInput('ACTION_REGISTRATION_FAILED') from None

    def _emit(self,kind):
        if self.evidence is None: return
        with self._lock:
            event=dict(kind=kind,run_id=self.binding.run_id,generation=self.binding.generation,
                       reset_commit_sequence=self._reset_commit_sequence,failure_sequence=self._failure_sequence,
                       reset_commit_count=self._reset_commit_count,committed_fixture_id=self._committed_fixture_id,
                       provenance='LIFECYCLE_ONLY',network_status='PENDING_AUTHORIZATION')
        try:self.evidence(event)
        except Exception:
            self._latch_failure('AUDIT_ERROR')

    def revoke(self,binding=None,*,service_first=False):
        if binding is not None and binding!=self.binding: raise InvalidInput('STALE_BINDING')
        with self._lock:
            if self._issued or self.state=='RETIRED':return
            self._issued=True
            if self.state!='FAILED':self.state='STOPPING'
            try:
                self._last=number(self.clock());self._deadline=self._last+self.timeout
            except Exception:self.state='FAILED';self.reason='CLOCK_ERROR'
        # Never hold Supervisor lock or one endpoint gate while calling the other.
        ports=(self.service,self.client) if service_first else (self.client,self.service)
        failed=False
        for port in ports:
            try:port.revoke()
            except Exception:failed=True
        if failed:
            with self._lock:self.state='FAILED';self.reason='REVOKE_ERROR'
        self._emit('revocation_requested')
        with self._lock:self._revocation_done=True

    def poll(self):
        if not self._observation.acquire(blocking=False):
            with self._lock:return self.report_unlocked()
        try:return self._poll()
        finally:self._observation.release()

    def _poll(self):
        cleaned=False
        with self._lock:
            if self.state!='STOPPING' or not self._revocation_done:return self.report_unlocked()
        try:
            rows=[self.client.status(),self.service.status()]
            if any(set(r)!= {'revoked','clean','failed'} or any(type(v) is not bool for v in r.values()) for r in rows):
                raise ValueError()
            evidence_status=self._evidence_status()
            now=number(self.clock())
            with self._lock:
                if self.state!='STOPPING':return self.report_unlocked()
                if now<self._last:raise ValueError()
                self._last=now
                if any(r['failed'] for r in rows):self.state='FAILED';self.reason='CLEANUP_FAILED'
                elif now>=self._deadline:self.state='FAILED';self.reason='CLEANUP_TIMEOUT'
                # STOPPED records resource cleanup, not permission to reset.
                # A lifecycle-only observer can finish without a sidecar, but
                # prepare_next still requires independently VERIFIED evidence.
                elif all(r['revoked'] and r['clean'] for r in rows) and evidence_status in ('VERIFIED','MISSING'):cleaned=True
        except Exception:
            with self._lock:self.state='FAILED';self.reason='OBSERVATION_ERROR'
        self._emit('cleanup_observed')
        with self._lock:
            if cleaned and self.state=='STOPPING':self.state='STOPPED'
            return self.report_unlocked()

    def report_unlocked(self):
        return dict(state=self.state,reason=self.reason,run_id=self.binding.run_id,
                    generation=self.binding.generation,audit_failed=self.audit_failed,
                    reset_commit_count=self._reset_commit_count,reset_commit_sequence=self._reset_commit_sequence,
                    failure_sequence=self._failure_sequence,committed_fixture_id=self._committed_fixture_id,
                    committed_generation=self.binding.generation+1 if self._reset_commit_count else None,
                    next_fixture_available=self._next_fixture is not None,
                    network_status='PENDING_AUTHORIZATION',replay_allowed=False)

    def prepare_next(self,mode):
        # Re-read completion outside the Supervisor lock, including disk checks.
        if self._evidence_status()!='VERIFIED':raise InvalidInput('EVIDENCE_NOT_COMPLETE')
        with self._lock:
            if self.state!='STOPPED' or self.audit_failed or self._reset_reserved:
                raise InvalidInput('OLD_RUN_NOT_CLEAN')
            self._reset_reserved=True  # one preparer; this is NOT the commit point
        try:
            for port in (self.client,self.service):
                s=port.status()
                if s!={'revoked':True,'clean':True,'failed':False}:raise InvalidInput('OLD_RUN_NOT_CLEAN')
            with self._lock:
                if self.state!='STOPPED' or self.audit_failed:raise InvalidInput('RESET_CANCELLED')
            # Allocation has no active-reference or old-generation side effects.
            fixture=FixtureManager.prepare(mode)
            if type(fixture) is not Fixture or fixture.fixture_instance_id==self.binding.fixture_instance_id:
                raise InvalidInput('INVALID_PREPARED_FIXTURE')
            if self._evidence_status()!='VERIFIED':raise InvalidInput('EVIDENCE_NOT_COMPLETE')
            self._emit('fixture_prepared')
            with self._lock:
                if self.state!='STOPPED' or self.audit_failed:raise InvalidInput('RESET_CANCELLED')
                # LINEARIZATION POINT: only bounded in-memory assignments.
                # A failure that won this gate prevents publication entirely.
                self._transition_sequence+=1
                self._reset_commit_sequence=self._transition_sequence
                self._reset_commit_count=1
                self._committed_fixture_id=fixture.fixture_instance_id
                self._next_fixture=fixture
                self.state='RETIRED'
            # These callbacks may fail/block, so never execute them in the gate.
            # A subsequent failure retains commit history, clears availability,
            # and does not claim the already committed switch was rolled back.
            self.client.invalidate();self.service.invalidate()
            self._emit('fixture_committed')
            with self._lock:
                if self.audit_failed or self.state!='RETIRED':raise InvalidInput('AUDIT_ERROR')
                return fixture
        except Exception:
            self._latch_failure('RESET_FAILED')
            raise InvalidInput('RESET_FAILED') from None

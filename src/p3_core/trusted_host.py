"""Offline host only. No listener, live run, permission upgrade or replay."""
import argparse
import json
from pathlib import Path
from threading import Lock

from .coordination import EvidenceCoordinator
from .evidence import JsonlEvidence, unique_id
from .experiments import configuration, synthetic_registry, MODES
from .http.audit import BoundedEvidence
from .http.machine import SimulationRun
from .http.transport import MemoryTransport
from .mock_api import FixtureManager
from .mock_api.adapter import ServiceAdapter
from .models import InvalidInput
from .supervision import RunBinding, Supervisor


class _ClientPort:
    def __init__(self, run, binding):
        self.run, self.binding = run, binding
        self.invalid = False

    def revoke(self):
        self.run.revoke()

    def status(self):
        r = self.run
        if not r._lock.acquire(blocking=False):
            return dict(revoked=r._revoked, clean=False, failed=r._audit_gap or r._cleanup_failed)
        try:
            return dict(revoked=r._revoked,
                        clean=r._revoked and (r._active is None or r._active.get('closed', False)),
                        failed=r._audit_gap or r._cleanup_failed)
        finally:
            r._lock.release()

    def invalidate(self):
        self.invalid = True


class _ServicePort:
    """Single-owner memory service, not AuthorizedService or real server proof."""
    def __init__(self, fixture, port, binding):
        self.binding = binding
        self.adapter = ServiceAdapter(fixture, port)
        self.revoked = self.invalid = self.failed = False
        self.consumer = None
        self.sequence = 0

    def attach_consumer(self, consumer):
        if self.consumer is not None: raise InvalidInput('ALREADY_BOUND')
        self.consumer = consumer

    def revoke(self):
        self.revoked = True

    def invalidate(self):
        self.invalid = True

    def status(self):
        return dict(revoked=self.revoked, clean=self.revoked, failed=self.failed)

    def respond(self, wire, omit=False):
        if self.revoked or self.invalid or self.failed: raise InvalidInput('SERVICE_STOPPED')
        response, action = self.adapter.handle_with_action(wire)
        self.sequence += 1
        # Counts describe bytes handed between in-memory adapters, never OS I/O.
        record=dict(connection_id=unique_id('connection'),action_id=action,
                    sent_bytes=len(response),received_bytes=len(wire),
                    first_send_sequence=self.sequence,last_send_sequence=self.sequence,
                    reason='RESPONSE_SENT',cleanup_failed=False,revoke_requested_at=None,
                    revoke_effective_sequence=None,revoke_effective_at=None,summary_sequence=self.sequence)
        try:
            if not omit: self.consumer(record)
        except Exception:
            self.failed = True
            self.revoke()
            raise InvalidInput('AUDIT_ERROR') from None
        return response


class _Wire(MemoryTransport):
    """Consumes only Controller-produced bytes; service sees fully sent frames."""
    def __init__(self, host, fault):
        super().__init__(writes=(1,) if fault=='partial_revoke' else ())
        self.host, self.fault = host, fault
        self.raw = bytearray()
        self.responded = False

    def send(self, buffer, offset):
        if self.closed or self.host.service.revoked: raise OSError('STOPPED')
        n = super().send(buffer, offset)
        self.raw.extend(buffer[:n])
        return n

    def receive(self):
        if self.responded: return b''
        self.responded = True
        try:
            return self.host.service.respond(bytes(self.raw), self.fault=='missing_summary')
        finally:
            self.raw.clear()

    def close(self):
        self.raw.clear()
        super().close()


class OfflineHost:
    """Trusted Python host; fixed synthetic scope, one run and one owner.

    Exposes no arbitrary URL, registry, credential or actual execution switch.
    Private Controller state is read, never rewritten to grant authority.
    """
    def __init__(self, output, mode='good'):
        if mode not in MODES: raise InvalidInput('INVALID_MODE')
        self.fixture = FixtureManager.prepare(MODES[mode])
        raw = configuration(self.fixture)
        self.client_sink = JsonlEvidence(output)
        self.run = SimulationRun(raw, synthetic_registry(raw),
                                 credentials=self.fixture.credential_bindings(),
                                 evidence=BoundedEvidence(self.client_sink))
        self.run.start()
        if self.run.state!='RUNNING': raise InvalidInput('OFFLINE_PREFLIGHT_FAILED')
        cfg = self.run.config
        self.binding = RunBinding(self.run.run_id, cfg.fixture_instance_id, cfg.scope_digest,
                                  cfg.authorization_version, self.run.generation)
        self.client = _ClientPort(self.run, self.binding)
        self.service = _ServicePort(self.fixture, cfg.port, self.binding)
        self.lifecycle_sink = JsonlEvidence(output)
        from .evidence import Redactor
        self.lifecycle_sink.open(unique_id('lifecycle'), Redactor())
        self.supervisor = Supervisor(self.binding, self.client, self.service,
                                     evidence=self.lifecycle_sink.emit)
        self.coordinator = EvidenceCoordinator(self.binding, sink=JsonlEvidence(output))
        self.supervisor.attach_evidence(self.coordinator)
        self.used = False
        self._entry = Lock()

    def verify_binding(self, binding):
        if binding!=self.binding or self.used or self.client.invalid or self.service.invalid:
            raise InvalidInput('STALE_HOST_BINDING')

    def execute(self, *, fault=None):
        if fault not in (None,'deny','audit','missing_summary','before_send_revoke','partial_revoke'):
            raise InvalidInput('INVALID_FAULT')
        with self._entry:
            self.verify_binding(self.binding)
            self.used = True
        run = self.run
        if fault=='deny':
            denied = run.config.candidates[0].to_dict()
            denied['check_id'] = 'unapproved'
            run.submit(denied)
        if fault=='audit':
            def fail(event): raise OSError('SYNTHETIC_AUDIT_FAILURE')
            self.coordinator.sink.emit = fail
        steps = 0
        try:
            while run.state=='RUNNING' and steps<200:
                steps += 1
                if run._active is None:
                    run.step(_Wire(self, fault))
                    if run._active is not None:
                        self.coordinator.capture_controller(run)
                        if fault=='before_send_revoke': self.supervisor.revoke()
                else:
                    run.step()
                    if fault=='partial_revoke' and run.counts['model_request_count']:
                        self.supervisor.revoke()
                run.settle()
            if run.state=='RUNNING': run.poll('RUNTIME_ERROR')
        except Exception:
            self.supervisor._evidence_failed()
        finally:
            self.supervisor.revoke()
            run.step()  # owner cleanup only: Controller terminal gate prohibits new sends
        client_report = run.finalize()
        self.coordinator.finish()
        state = self.supervisor.poll()
        next_fixture = None
        if state['state']=='STOPPED':
            try: next_fixture = self.supervisor.prepare_next(MODES['good'])
            except InvalidInput: pass
        state = self.supervisor.poll()
        result = dict(provenance='OFFLINE_SIMULATION',network_status='PENDING_AUTHORIZATION',
                      binding=self.binding.__dict__,client=client_report,sidecar=self.coordinator.report(),
                      lifecycle=state,next_fixture_id=next_fixture.fixture_instance_id if next_fixture else None,
                      nondispatch_proof='UNAVAILABLE',
                      send_observation=('UNKNOWN' if client_report['audit_gap'] else
                                        'MODEL_SEND_OBSERVED' if run.counts['model_request_count'] else
                                        'NO_MODEL_SEND_OBSERVED'),
                      evidence_directories=[self.client_sink.directory.name,self.coordinator.sink.directory.name,
                                            self.lifecycle_sink.directory.name])
        # A final host audit failure invalidates availability, preserving commit facts.
        try:
            self.lifecycle_sink.finish(dict(run_id=self.lifecycle_sink.directory.name,
                                            provenance='OFFLINE_SIMULATION'), result)
        except Exception:
            self.supervisor._evidence_failed()
            result['lifecycle']=self.supervisor.poll()
            result['next_fixture_id']=None
        return result


def main():
    parser=argparse.ArgumentParser(description='Offline simulation only; no network permission')
    parser.add_argument('--output', required=True)
    parser.add_argument('--mode', choices=sorted(MODES), default='good')
    parser.add_argument('--fault', choices=['deny','audit','missing_summary','before_send_revoke','partial_revoke'])
    args=parser.parse_args()
    print(json.dumps(OfflineHost(Path(args.output), args.mode).execute(fault=args.fault), indent=2))


if __name__=='__main__': main()

"""Single-owner no-network dispatch machine; revoke shares only a short gate.

Actual request_count is always zero. model_request_count models positive sends
from MemoryTransport, never actual HTTP. Offline Controller stays unchanged.
"""
import copy
from dataclasses import dataclass, field
from threading import Lock, RLock, get_ident
import time

from ..evidence import MemoryEvidence, Redactor, unique_id
from ..models import InvalidInput, number
from .contract import HttpConfig, HttpCheck, IDENTITIES
from .protocol import build_request, ResponseParser, evaluate
from .transport import MemoryTransport


@dataclass
class Slot:
    slot_id: str
    proposal_id: str
    check: object = field(repr=False)
    processed: bool = False
    authorization: str = 'NOT_EVALUATED'
    attempt_id: object = None
    action_id: object = None
    assertion: str = 'NOT_ATTEMPTED'
    simulated_conclusion: str = 'INCONCLUSIVE'


class SimulationRun:
    """Trusted host owns registry, credentials and revoke(); Planner only returns plans.

    step() is single-thread-owned and non-reentrant. It advances ONE operation;
    never waits for readiness. Injected transports must be memory test doubles.
    All audit I/O is outside gate, including during concurrent revocation.
    """
    def __init__(self, raw, registry, *, clock=time.monotonic, wall_clock=time.time,
                 evidence=None, credentials=None):
        self._raw = copy.deepcopy(raw)
        self._registry = registry
        self.clock, self.wall_clock = clock, wall_clock
        self._credentials = dict(credentials or {})
        self._redactor = Redactor(self._credentials.values())
        self.evidence = evidence if evidence is not None else MemoryEvidence()
        self._lock, self._gate = RLock(), Lock()
        self._owner = None
        self._stepping = False
        self.run_id = unique_id('run')
        self.state, self.reason, self.conditions = 'READY', None, []
        self.config = self.snapshot = None
        self._t0 = self._last = self._permit_deadline = None
        self._revoked = False
        self.generation = 0
        self.gate_sequence = 0
        self._revoke_received = self._revoke_effective = None
        self._attempts = self._model_requests = 0
        self._slots, self._by_id = [], {}
        self._active = None
        self._pending_controls = {}
        self._audit_gap = False
        self._finalized = False
        self._seq = 0
        try:
            self.evidence.open(self.run_id, self._redactor)
        except Exception:
            self._audit_gap = True
            self.state, self.reason, self.conditions = 'STOPPED', 'AUDIT_ERROR', ['AUDIT_ERROR']

    @property
    def counts(self):
        with self._gate:
            return self._counts_locked()

    def _counts_locked(self):
        return dict(plan_count=len(self._slots), attempt_count=self._attempts,
                    request_count=0, model_request_count=self._model_requests)

    def _conditions_locked(self, error=None):
        reasons = []
        if self._revoked: reasons.append('REVOKED')
        try:
            now = number(self.clock())
            if self._last is not None and now < self._last: raise ValueError()
            self._last = now
            if self.snapshot and (number(self.wall_clock()) >= self.snapshot.valid_until
                                  or now >= self._permit_deadline):
                reasons.append('AUTHORIZATION_INVALID')
        except Exception:
            now = self._last
            reasons.append('RUNTIME_ERROR')
        if self._audit_gap: reasons.append('AUDIT_ERROR')
        if error and error != 'TIMEOUT': reasons.append(error)
        if self.config and self._t0 is not None and now - self._t0 >= self.config.budget.logical_timeout_seconds:
            reasons.append('BUDGET_EXHAUSTED')
        if error == 'TIMEOUT': reasons.append(error)
        return list(dict.fromkeys(reasons))

    def _checkpoint_locked(self, error=None):
        if self.state != 'RUNNING': return False
        conditions = self._conditions_locked(error)
        if conditions:
            self.state, self.reason, self.conditions = 'STOPPED', conditions[0], conditions
            return False
        return True

    def poll(self, error=None):
        with self._gate: return self._checkpoint_locked(error)

    def revoke(self):
        # No Controller lock, no disk, no waiting for worker completion.
        received = None
        try: received = number(self.clock())
        except Exception: pass
        with self._gate:
            if not self._revoked:
                self._revoked = True
                self.generation += 1
                self.gate_sequence += 1
                self._revoke_received = received
                self._revoke_effective = self.gate_sequence
            self._checkpoint_locked()
        # I/O owner observes stop and closes on its next step; no cross-thread close.

    def _emit(self, kind, **safe):
        if self._audit_gap: return False
        self._seq += 1
        event = dict(mode='http-local-simulation', provenance='NO_NETWORK_SIMULATION',
                     run_id=self.run_id, evidence_id=unique_id('evidence'), sequence=self._seq,
                     kind=kind, counts=self.counts, **safe)
        try:
            self.evidence.emit(self._redactor.clean(event))
            return True
        except Exception:
            with self._gate:
                self._audit_gap = True
                self._checkpoint_locked('AUDIT_ERROR')
            return False

    def _register(self, check):
        slot = Slot(unique_id('slot'), unique_id('proposal'), check)
        with self._gate: self._slots.append(slot)
        if check: self._by_id[check.check_id] = slot
        return slot

    def start(self, planner=None):
        with self._lock:
            if self.state != 'READY': return
            try:
                self.config = HttpConfig.parse(self._raw)
                wall = number(self.wall_clock())
                self.snapshot = self._registry.snapshot(self.config, wall, simulation=True)
                # Verify credential bindings statically, without serializing their values.
                needed = {row[3] for row in IDENTITIES if row[3] is not None}
                if set(self._credentials) != needed: raise InvalidInput('MISSING_CREDENTIAL_BINDING')
                if len(set(self._credentials.values())) != len(needed): raise InvalidInput('DUPLICATE_CREDENTIAL')
            except Exception:
                with self._gate:
                    self.state, self.reason, self.conditions = 'STOPPED', 'INVALID_INPUT', ['INVALID_INPUT']
                self._emit('preflight_rejected', reason='INVALID_INPUT')
                return
            self._raw = None
            with self._gate:
                self.state = 'RUNNING'
                try:
                    self._t0 = self._last = number(self.clock())
                    self._permit_deadline = self._t0 + (self.snapshot.valid_until - wall)
                except Exception:
                    self.state, self.reason, self.conditions = 'STOPPED', 'RUNTIME_ERROR', ['RUNTIME_ERROR']
            if not self.poll(): return
            self._emit('started', snapshot_id=self.snapshot.snapshot_id)
            if not self.poll(): return
            try:
                plan = ([c.to_dict() for c in self.config.candidates] if planner is None
                        else planner.plan(self.config.candidates))
                if not self.poll(): return
                if type(plan) is not list or len(plan) > self.config.budget.max_checks:
                    raise InvalidInput('INVALID_PLAN')
                checks = [HttpCheck.parse(p) for p in plan]
                if len({c.check_id for c in checks}) != len(checks): raise InvalidInput('DUPLICATE_CHECK')
            except Exception:
                self.poll('INVALID_INPUT'); return
            for check in checks: self._register(check)
            self._emit('plan_registered')
            self.poll()

    def submit(self, raw):
        with self._lock:
            proposal_id = unique_id('proposal')
            if not self.poll():
                self._emit('proposal_rejected', proposal_id=proposal_id, reason='NOT_RUNNING'); return
            claimed = raw.get('check_id') if type(raw) is dict else None
            old = self._by_id.get(claimed) if type(claimed) is str else None
            if old:
                self._emit('proposal_rejected', proposal_id=proposal_id, slot_id=old.slot_id,
                           reason='REGISTERED_CHECK_IMMUTABLE'); return
            if len(self._slots) >= self.config.budget.max_checks:
                self._emit('proposal_rejected', proposal_id=proposal_id, reason='BUDGET_EXHAUSTED')
                self.poll('BUDGET_EXHAUSTED'); return
            try: check = HttpCheck.parse(raw)
            except Exception: check = None
            slot = self._register(check)
            self._emit('proposal_registered', proposal_id=slot.proposal_id, slot_id=slot.slot_id)
            if check is None: self._authorize(slot)

    def _authorize(self, slot):
        if not self.poll(): return False
        with self._gate: self._attempts += 1
        slot.attempt_id = unique_id('attempt')
        approved = slot.check in self.config.candidates
        slot.authorization = 'ALLOW' if approved else 'DENY'
        slot.assertion = 'APPROVED' if approved else 'NOT_APPROVED_CANDIDATE'
        if not approved: slot.processed = True
        self._emit('authorization', slot_id=slot.slot_id, proposal_id=slot.proposal_id,
                   attempt_id=slot.attempt_id, decision=slot.authorization, reason=slot.assertion)
        return approved and self.poll()

    def _cleanup(self):
        if self._active:
            if not self._active.get('closed'):
                try: self._active['transport'].close()
                except Exception: pass
                self._active['closed'] = True
            self._active['request'] = None

    def step(self, transport=None):
        """One nonblocking operation. WAIT means caller schedules another step."""
        with self._lock:
            if self._owner is None: self._owner = get_ident()
            if self._owner != get_ident() or self._stepping:
                raise InvalidInput('SINGLE_IO_OWNER_REQUIRED')
            self._stepping = True
            try: self._step(transport)
            finally:
                self._stepping = False
                if self.state == 'STOPPED': self._cleanup()

    def _step(self, transport):
        if not self.poll(): return
        if self._active is None:
            slot = next((s for s in self._slots if not s.processed), None)
            if slot is None: return
            if not self._authorize(slot): return
            if not isinstance(transport, MemoryTransport):
                self.poll('RUNTIME_ERROR'); return
            slot.action_id = unique_id('action')
            ref = next(row[3] for row in IDENTITIES if row[0] == slot.check.identity_ref)
            try:
                request = build_request(self.config, self.snapshot, slot.check, slot.action_id,
                                        self._credentials.get(ref))
            except Exception:
                self.poll('AUTHORIZATION_INVALID'); return
            self._active = dict(slot=slot, transport=transport, request=request, generation=self.generation,
                                phase='CONNECT', offset=0, sent=False, parser=ResponseParser(self.config.limits))
            self._emit('prepared', slot_id=slot.slot_id, action_id=slot.action_id)
            return
        active = self._active
        phase, io, slot = active['phase'], active['transport'], active['slot']
        if phase in ('CONNECT', 'WRITE'):
            error = None
            with self._gate:
                if not self._checkpoint_locked(): return
                if active['generation'] != self.generation:
                    self._checkpoint_locked('AUTHORIZATION_INVALID'); return
                self.gate_sequence += 1
                seq = self.gate_sequence
                try:
                    if phase == 'CONNECT':
                        outcome = io.connect(('127.0.0.1', self.config.port))
                        if outcome not in ('CONNECTED', 'PENDING'): raise OSError()
                        active['phase'] = 'CONNECTING'
                    else:
                        wire = active['request'].wire
                        n = io.send(wire[active['offset']:], active['offset'])
                        if type(n) is not int or not 0 < n <= len(wire) - active['offset']: raise OSError()
                        if not active['sent']:
                            active['sent'] = True
                            self._model_requests += 1
                        active['offset'] += n
                        if active['offset'] == len(wire): active['phase'] = 'READ'
                except BlockingIOError:
                    pass
                except TimeoutError: error = 'TIMEOUT'
                except OSError: error = 'TRANSPORT_ERROR'
                except Exception: error = 'RUNTIME_ERROR'
                self._checkpoint_locked(error)
            self._emit('model_io', action_id=slot.action_id, phase=phase, gate_sequence=seq,
                       sent_bytes=active['offset'], dispatch_started=active['sent'])
            return
        try:
            if phase == 'CONNECTING':
                peer = io.connected()
                if peer is None: return
                if peer != ('127.0.0.1', self.config.port):
                    self.poll('AUTHORIZATION_INVALID'); return
                active['phase'] = 'WRITE'
            elif phase == 'READ':
                chunk = io.receive()
                if not self.poll(): return  # late data cannot complete a stopped action.
                if chunk:
                    active['parser'].feed(chunk)
                    if active['parser']._failure:
                        self.poll('RESPONSE_ERROR')
                    return
                observation = active['parser'].finish()
                controls = {s.check.check_id: s for s in self._slots if s.check in self.config.candidates}
                control = controls.get(slot.check.control_id)
                verdict = evaluate(self.config, slot.check, slot.action_id, observation,
                                   control_pass=bool(control and control.simulated_conclusion == 'PASS'))
                # Persist only validated assertion codes; no raw body/headers/exceptions.
                if not self._emit('simulated_assertion', action_id=slot.action_id,
                                  assertion=verdict.assertion, simulated_conclusion=verdict.simulated_conclusion):
                    return
                with self._gate:
                    if not self._checkpoint_locked(): return
                    slot.simulated_conclusion, slot.assertion = verdict.simulated_conclusion, verdict.assertion
                    slot.processed = True
                if verdict.assertion == 'MISSING_CONTROL':
                    self._pending_controls[slot.slot_id] = (slot, observation)
                self._cleanup()
                self._active = None
                if self.poll(verdict.reason): self._resolve_controls()
        except BlockingIOError: return
        except TimeoutError: self.poll('TIMEOUT')
        except OSError: self.poll('TRANSPORT_ERROR')
        except Exception: self.poll('RUNTIME_ERROR')

    def _resolve_controls(self):
        for key, (slot, observation) in list(self._pending_controls.items()):
            control = self._by_id.get(slot.check.control_id)
            if not control or not control.processed: continue
            verdict = evaluate(self.config, slot.check, slot.action_id, observation,
                               control_pass=control.simulated_conclusion == 'PASS')
            if not self._emit('control_resolution', action_id=slot.action_id,
                              assertion=verdict.assertion, simulated_conclusion=verdict.simulated_conclusion): return
            with self._gate:
                if not self._checkpoint_locked(): return
                slot.simulated_conclusion, slot.assertion = verdict.simulated_conclusion, verdict.assertion
            del self._pending_controls[key]

    def settle(self, proposals=(), repeat=False):
        """Call after pending additions, just like offline round's completion phase."""
        with self._lock:
            for proposal in proposals: self.submit(proposal)
            if not self.poll() or self._active: return
            for slot, _ in self._pending_controls.values():
                if slot.check.control_id not in self._by_id:
                    control = next(c for c in self.config.candidates if c.check_id == slot.check.control_id)
                    self.submit(control.to_dict())
                    return
            remaining = [c for c in self.config.candidates if not any(
                s.check == c and s.processed and s.authorization == 'ALLOW' for s in self._slots)]
            if repeat and remaining:
                for c in remaining:
                    if c.check_id not in self._by_id:
                        self.submit(c.to_dict()); break
                return
            if all(s.processed for s in self._slots):
                self._emit('completion_ready')
                with self._gate:
                    if self._checkpoint_locked():
                        if repeat and not remaining:
                            self.state, self.reason, self.conditions = 'STOPPED', 'NO_NEW_EVIDENCE', ['NO_NEW_EVIDENCE']
                        else: self.state = 'COMPLETED'

    def observe_late(self, action_id):
        # Do not echo untrusted response payloads or arbitrary correlation strings.
        known = any(s.action_id == action_id for s in self._slots)
        self._emit('late_or_duplicate_event', known_action=known)

    def report(self):
        with self._lock:
            rows = []
            for s in self._slots:
                approved = self.config and s.check in self.config.candidates
                rows.append(dict(slot_id=s.slot_id, proposal_id=s.proposal_id,
                                 check_id=s.check.check_id if approved else None,
                                 attempt_id=s.attempt_id, action_id=s.action_id, processed=s.processed,
                                 authorization=s.authorization, execution='NOT_EXECUTED', conclusion='INCONCLUSIVE',
                                 simulated_conclusion=s.simulated_conclusion, assertion=s.assertion))
            return self._redactor.clean(dict(run_id=self.run_id, mode='http-local-simulation',
                provenance='NO_NETWORK_SIMULATION', state=self.state, reason=self.reason,
                stop_conditions=list(self.conditions), counts=self.counts, checks=rows,
                audit_gap=self._audit_gap, revoke_received=self._revoke_received,
                revoke_effective_sequence=self._revoke_effective,
                unperformed_approved_candidates=[] if not self.config else [c.check_id for c in self.config.candidates
                  if not any(s.check == c and s.processed and s.authorization == 'ALLOW' for s in self._slots)]))

    def finalize(self):
        with self._lock:
            if self.state not in ('STOPPED', 'COMPLETED'): raise InvalidInput('RUN_NOT_TERMINAL')
            if not self._finalized:
                self._cleanup()
                self._finalized = True
                try:
                    self.evidence.finish(dict(run_id=self.run_id, provenance='NO_NETWORK_SIMULATION',
                                              counts=self.counts, audit_gap=self._audit_gap), self.report())
                except Exception: self._audit_gap = True
            return self.report()

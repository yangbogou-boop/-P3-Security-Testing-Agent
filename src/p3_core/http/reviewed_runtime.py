"""Contract-driven reviewed offline run (V2).

Independent from ``SimulationRun``: it does not inherit it, does not import
``live``/``machine``/``transport``, and never touches V1's fixed identities or six
candidates.  It keeps the same defence properties V1 relies on (independent
authorisation, budget/validity checkpoints, single I/O owner, revocation
generation, bounded audit, terminal state) and adds an explicit memory delivery
ledger so that "accepted dispatch" and "fixture handled" are distinct, evidenced
facts.

Concurrency protocol
--------------------
* ``_gate`` is the only linearisation point.  Revocation, dispatch acceptance and
  every checkpoint run inside it, so ``gate_sequence`` gives one total order.
* Dispatch acceptance = storing a one-shot ``_Ticket`` and committing the counter
  inside ``_gate``.  The ticket is the sole capability for invoking the fixture.
* The fixture runs only outside ``_gate``; revocation therefore never waits for it.
* A delivery accepted before revocation still completes (already started); it is
  reported as ``REVOKED_DURING_DELIVERY`` and never retried.
"""
from dataclasses import dataclass, field
import hashlib
from threading import get_ident, Lock, RLock
import time

from ..evidence import MemoryEvidence, Redactor, unique_id
from ..models import InvalidInput
from .audit import BoundedEvidence
from .reviewed_protocol import build_request_v2, evaluate_v2, parse_response_v2, projection_v2
from .reviewed_snapshot import ReviewedRunSnapshot

COUNTER_KEYS = (
    'authorization_decisions', 'authorized_count', 'denied_count',
    'proposal_rejected_count', 'prepared_count', 'prepare_failed_count',
    'dispatch_accepted_count', 'delivery_consumed_count', 'delivery_aborted_count',
    'fixture_started_count', 'fixture_handled_count', 'fixture_failed_count',
    'dispatch_cancelled_count', 'response_observed_count',
)

REAL_NETWORK_NOT_MEASURED = 'NOT_MEASURED'


@dataclass
class _Ticket:
    """One-shot delivery capability. Private; never exposed to planner or strategy."""

    dispatch_seq: int
    action_id: str
    slot: object = field(repr=False)
    wire: bytes = field(repr=False)
    wire_sha256: str
    state: str = 'ACCEPTED'


@dataclass
class _Slot:
    slot_id: str
    check_id: str
    proposal_id: str
    spec: object
    phase: str = 'NEW'
    authorization: str = 'NOT_EVALUATED'
    assertion: str = 'NOT_ATTEMPTED'
    attempt_id: object = None
    action_id: object = None
    dispatch_seq: object = None
    simulated_conclusion: str = 'INCONCLUSIVE'
    processed: bool = False
    evidence_ids: list = field(default_factory=list)


class ReviewedOfflineRun:
    """Reviewed V2 offline run. No listener, socket, transport or real request."""

    simulation = True
    provenance = 'NO_NETWORK_SIMULATION'
    mode = 'reviewed-offline-simulation'

    def __init__(self, snapshot, fixture, *, evidence=None, credentials=None,
                 clock=time.monotonic, wall_clock=time.time):
        if type(snapshot) is not ReviewedRunSnapshot:
            raise InvalidInput('REVIEWED_SNAPSHOT_REQUIRED')
        self._snapshot = snapshot
        self._fixture = fixture
        self.clock, self.wall_clock = clock, wall_clock
        self._lock, self._gate = RLock(), Lock()
        self._owner = None
        self._stepping = False
        self.run_id = unique_id('run')
        self.state, self.reason, self.conditions = 'READY', None, []
        self._seq = 0
        self.gate_sequence = 0
        self._generation = 0
        self._revoked = False
        self._revoke_seq = None
        self._slots = []
        self._by_id = {}
        self._ledger = None
        self._requests = {}
        self._pending_controls = {}
        self._cancelled_slots = []
        self._aborted_tickets = []
        self._unpersisted_facts = []
        self._audit_gap = False
        self._finalized = False
        self._t0 = self._last = self._permit_deadline = None
        self._credentials = dict(credentials or {})
        self._redactor = Redactor(self._credentials.values())
        self.evidence = evidence if evidence is not None else MemoryEvidence()
        self._counters = {key: 0 for key in COUNTER_KEYS}
        try:
            self.evidence.open(self.run_id, self._redactor)
        except Exception:
            self._audit_gap = True
            self.state, self.reason, self.conditions = 'STOPPED', 'AUDIT_ERROR', ['AUDIT_ERROR']

    @property
    def snapshot(self):
        """Read-only review facts. ``ReviewedRunSnapshot`` has no writable slot."""
        return self._snapshot

    # -- counters -----------------------------------------------------------
    @property
    def counts(self):
        """V1-compatible four-key counter block (evaluator/summary stay compatible)."""
        with self._gate:
            return dict(plan_count=len(self._slots),
                        attempt_count=self._counters['authorization_decisions'],
                        request_count=0,
                        model_request_count=self._counters['dispatch_accepted_count'])

    def reviewed_counts(self):
        with self._gate:
            return dict(self._counters)

    def pending_request_count(self):
        """Requests still held in memory (0 after any terminal state)."""
        with self._gate:
            return len(self._requests)

    # -- lifecycle ----------------------------------------------------------
    def _needed_credentials(self):
        needed = set()
        for check_id in self._snapshot.candidate_ids():
            spec = self._snapshot.candidate(check_id)
            identity = self._snapshot.identity(spec.identity_ref)
            if identity is not None and identity.credential_ref is not None:
                needed.add(identity.credential_ref)
        return needed

    def _verify_fixture_binding(self, full=True):
        """The run refuses to start unless the real fixture matches the snapshot.

        ``full`` also recomputes the content digest; the cheap variant (identity,
        version, instance, identity records, resource/ACL fingerprint) is used before
        every dispatch and before every consumption and performs no hashing, so it
        never blocks the gate on a digest.
        """
        if not self._binding_unchanged():
            raise InvalidInput('FIXTURE_BINDING_MISMATCH')
        if full and not self._content_unchanged():
            raise InvalidInput('FIXTURE_BINDING_MISMATCH')
        return True

    def start(self):
        with self._lock:
            if self.state != 'READY':
                return False
            # Raised (not converted to STOPPED): a mis-bound fixture is a host error,
            # and nothing has been prepared or dispatched at this point.
            self._verify_fixture_binding(full=True)
            try:
                wall = self.wall_clock()
                if wall >= self._snapshot.valid_until:
                    raise InvalidInput('AUTHORIZATION_INVALID')
                needed = self._needed_credentials()
                if not needed <= set(self._credentials):
                    raise InvalidInput('MISSING_CREDENTIAL_BINDING')
                used = [self._credentials[ref] for ref in needed]
                if len(set(used)) != len(used):
                    raise InvalidInput('DUPLICATE_CREDENTIAL')
            except Exception as error:
                reason = str(error) if type(error) is InvalidInput else 'INVALID_INPUT'
                with self._gate:
                    self.state, self.reason = 'STOPPED', reason
                    self.conditions = [reason]
                self._emit('reviewed_preflight_rejected', reason=reason)
                return False
            with self._gate:
                self.state = 'RUNNING'
                self._t0 = self._last = self.clock()
                self._permit_deadline = self._t0 + (self._snapshot.valid_until - wall)
        return bool(self._emit('reviewed_started', snapshot_id=self._snapshot.snapshot_id,
                               contract_id=self._snapshot.contract_id,
                               fixture_instance_id=self._snapshot.fixture_instance_id))

    def _drain_stop_events(self):
        """Emit events for deliveries cancelled/aborted at stop time (outside the gate)."""
        while self._cancelled_slots:
            slot_id = self._cancelled_slots.pop(0)
            self._emit('reviewed_dispatch_cancelled', slot_id=slot_id, reason=self.reason)
        while self._aborted_tickets:
            action_id, dispatch_seq = self._aborted_tickets.pop(0)
            self._emit('reviewed_delivery_aborted', action_id=action_id,
                       dispatch_seq=dispatch_seq, revoke_seq=self._revoke_seq,
                       reason=self.reason)

    def _drain_cancelled(self):
        self._drain_stop_events()

    def revoke(self):
        """No disk I/O and no wait for the fixture; only the short gate is taken."""
        with self._gate:
            if not self._revoked:
                self._revoked = True
                self._generation += 1
                self.gate_sequence += 1
                self._revoke_seq = self.gate_sequence
            self._checkpoint_locked()
        self._drain_cancelled()

    # -- checkpoints --------------------------------------------------------
    def _abort_ticket_locked(self):
        """Abort the outstanding accepted delivery exactly once (memory only)."""
        ticket = self._ledger
        if ticket is None or ticket.state != 'ACCEPTED':
            return False
        ticket.state = 'ABORTED'
        self._ledger = None
        self._counters['delivery_aborted_count'] += 1
        self._aborted_tickets.append((ticket.action_id, ticket.dispatch_seq))
        return True

    def _stop_locked(self, reasons):
        """Single place that performs the stop bookkeeping (called under the gate)."""
        self.state, self.reason = 'STOPPED', reasons[0]
        self.conditions = list(dict.fromkeys(self.conditions + list(reasons)))
        # A prepared request that never reached the ledger is cancelled, never dispatched.
        for row in self._slots:
            if row.phase == 'PREPARED':
                row.phase = 'CANCELLED'
                self._counters['dispatch_cancelled_count'] += 1
                self._cancelled_slots.append(row.slot_id)
        # An accepted delivery that was not consumed can never be consumed now;
        # the acceptance itself is never rewritten.
        self._abort_ticket_locked()
        # Drop request bytes (they carry a Bearer credential) once no dispatch can use them.
        self._requests.clear()

    def _checkpoint_locked(self, error=None):
        if self.state != 'RUNNING':
            return False
        reasons = []
        if self._revoked:
            reasons.append('REVOKED')
        try:
            now = self.clock()
            if self._last is not None and now < self._last:
                raise ValueError()
            self._last = now
            if self.wall_clock() >= self._snapshot.valid_until or now >= self._permit_deadline:
                reasons.append('AUTHORIZATION_INVALID')
        except Exception:
            now = self._last
            reasons.append('RUNTIME_ERROR')
        if self._audit_gap:
            reasons.append('AUDIT_ERROR')
        if error and error != 'TIMEOUT':
            reasons.append(error)
        if (self._t0 is not None and now is not None
                and now - self._t0 >= self._snapshot.logical_timeout_seconds):
            reasons.append('BUDGET_EXHAUSTED')
        if error == 'TIMEOUT':
            reasons.append('TIMEOUT')
        if reasons:
            self._stop_locked(reasons)
            return False
        return True

    def poll(self, error=None):
        with self._gate:
            return self._checkpoint_locked(error)

    # -- audit --------------------------------------------------------------
    def _note_unpersisted(self, kind):
        """Record that a fact happened but its event was never persisted."""
        if kind not in self._unpersisted_facts:
            self._unpersisted_facts.append(kind)

    def _emit(self, kind, **safe):
        """Emit one in-memory event; None means the audit failed and the run stopped."""
        if self._audit_gap:
            self._note_unpersisted(kind)
            return None
        self._seq += 1
        evidence_id = unique_id('evidence')
        event = dict(mode=self.mode, provenance=self.provenance, run_id=self.run_id,
                     evidence_id=evidence_id, sequence=self._seq, kind=kind,
                     counts=self.counts, **safe)
        try:
            self.evidence.emit(self._redactor.clean(event))
        except Exception:
            self._audit_gap = True
            self._note_unpersisted(kind)
            with self._gate:
                self._checkpoint_locked('AUDIT_ERROR')
            return None
        action_id = safe.get('action_id')
        if action_id:
            for slot in self._slots:
                if slot.action_id == action_id:
                    slot.evidence_ids.append(evidence_id)
                    break
        return evidence_id

    # -- proposals ----------------------------------------------------------
    def submit_id(self, check_id):
        """Planner submits candidate IDs only; unknown IDs become DENY, never authority."""
        with self._lock:
            if self.state != 'RUNNING':
                self._emit('reviewed_proposal_rejected', reason='NOT_RUNNING')
                return False
            if type(check_id) is not str or not check_id:
                with self._gate:
                    self._counters['proposal_rejected_count'] += 1
                self._emit('reviewed_proposal_rejected', reason='INVALID_PROPOSAL')
                return False
            if check_id in self._by_id:
                with self._gate:
                    self._counters['proposal_rejected_count'] += 1
                self._emit('reviewed_proposal_rejected', reason='DUPLICATE_PROPOSAL',
                           candidate=check_id)
                return False
            if len(self._slots) >= self._snapshot.max_checks:
                with self._gate:
                    self._counters['proposal_rejected_count'] += 1
                    self._checkpoint_locked('BUDGET_EXHAUSTED')
                self._drain_stop_events()
                self._emit('reviewed_proposal_rejected', reason='BUDGET_EXHAUSTED',
                           candidate=check_id)
                return False
            slot = _Slot(unique_id('slot'), check_id, unique_id('proposal'),
                         self._snapshot.candidate(check_id))
            self._slots.append(slot)
            self._by_id[check_id] = slot
        return bool(self._emit('reviewed_proposal_registered', slot_id=slot.slot_id,
                               proposal_id=slot.proposal_id, candidate=check_id,
                               known=slot.spec is not None))

    # -- stepping -----------------------------------------------------------
    def step(self, transport=None):
        """One non-blocking step owned by a single thread. ``transport`` is unused."""
        with self._lock:
            if self._owner is None:
                self._owner = get_ident()
            if self._owner != get_ident():
                raise InvalidInput('SINGLE_IO_OWNER_REQUIRED')
            if self._stepping:
                raise InvalidInput('REENTRANT_STEP')
            self._stepping = True
            try:
                self._step()
            except Exception:
                with self._gate:
                    self._checkpoint_locked('RUNTIME_ERROR')
            finally:
                self._stepping = False

    def _step(self):
        """Advance exactly one phase, so tests can interleave revocation deterministically."""
        if not self.poll():
            self._drain_cancelled()
            return
        if self._ledger is not None:
            self._deliver()
            return
        prepared = next((row for row in self._slots if row.phase == 'PREPARED'), None)
        if prepared is not None:
            self._accept(prepared)
            return
        authorised = next((row for row in self._slots if row.phase == 'AUTHORIZED'), None)
        if authorised is not None:
            self._prepare(authorised)
            return
        pending = next((row for row in self._slots if row.phase == 'NEW'), None)
        if pending is not None:
            self._authorize(pending)
            return
        if self._slots and all(row.processed for row in self._slots):
            self._complete()

    def _authorize(self, slot):
        with self._gate:
            if not self._checkpoint_locked():
                return False
            self._counters['authorization_decisions'] += 1
            allowed = slot.spec is not None
            if allowed:
                self._counters['authorized_count'] += 1
                slot.phase = 'AUTHORIZED'
            else:
                self._counters['denied_count'] += 1
                slot.phase = 'DENIED'
            slot.attempt_id = unique_id('attempt')
            slot.authorization = 'ALLOW' if allowed else 'DENY'
            slot.assertion = 'APPROVED' if allowed else 'NOT_IN_REVIEW_SNAPSHOT'
            if not allowed:
                slot.processed = True
                slot.simulated_conclusion = 'INCONCLUSIVE'
        emitted = self._emit('reviewed_authorization', slot_id=slot.slot_id,
                             proposal_id=slot.proposal_id, attempt_id=slot.attempt_id,
                             decision=slot.authorization, reason=slot.assertion,
                             candidate=slot.check_id)
        if not allowed:
            self._resolve_controls()
            return False
        return bool(emitted)

    def _prepare(self, slot):
        spec = slot.spec
        identity = self._snapshot.identity(spec.identity_ref)
        credential = None
        if identity is not None and identity.credential_ref is not None:
            credential = self._credentials.get(identity.credential_ref)
        slot.action_id = unique_id('action')
        try:
            request = build_request_v2(self._snapshot, spec, slot.action_id, credential)
        except Exception:
            with self._gate:
                self._counters['prepare_failed_count'] += 1
                slot.phase = 'FAILED'
                self._checkpoint_locked('PREPARE_ERROR')
            self._emit('reviewed_prepare_failed', slot_id=slot.slot_id,
                       action_id=slot.action_id, reason='PREPARE_ERROR')
            return False
        with self._gate:
            self._counters['prepared_count'] += 1
            slot.phase = 'PREPARED'
            self._requests[slot.slot_id] = request
        emitted = self._emit('reviewed_prepared', slot_id=slot.slot_id,
                             action_id=slot.action_id, candidate=slot.check_id)
        return bool(emitted)

    def _accept(self, slot):
        request = self._requests.pop(slot.slot_id, None)
        accepted = False
        seq = None
        with self._gate:
            cancelled = False
            if request is None or not self._checkpoint_locked():
                cancelled = True
            elif not self._binding_unchanged():
                # The fixture binding changed after start(); never dispatch to it.
                self._stop_locked(['FIXTURE_BINDING_MISMATCH'])
                cancelled = True
            elif self._ledger is not None:
                cancelled = True
                self._checkpoint_locked('DISPATCH_OVERLAP_REJECTED')
            else:
                self.gate_sequence += 1
                seq = self.gate_sequence
                self._ledger = _Ticket(seq, slot.action_id, slot, request.wire,
                                       hashlib.sha256(request.wire).hexdigest())
                slot.dispatch_seq = seq
                slot.phase = 'ACCEPTED'
                self._counters['dispatch_accepted_count'] += 1
                accepted = True
            if cancelled:
                self._counters['dispatch_cancelled_count'] += 1
                slot.phase = 'CANCELLED'
        if not accepted:
            self._drain_stop_events()
            self._emit('reviewed_dispatch_cancelled', slot_id=slot.slot_id,
                       action_id=slot.action_id, reason=self.reason)
            return False
        return bool(self._emit('reviewed_dispatch_accepted', slot_id=slot.slot_id,
                               action_id=slot.action_id, dispatch_seq=seq,
                               wire_sha256=self._ledger.wire_sha256))

    def _binding_unchanged(self):
        """Cheap pre-dispatch/pre-consume binding check.

        Compares only strings and tuples (identity, version, instance, identity
        records, resource/ACL fingerprint): no hashing, so it is bounded and never
        blocks the gate on a digest computation.
        """
        fixture, snapshot = self._fixture, self._snapshot
        try:
            return (fixture.fixture_id() == snapshot.fixture_id
                    and fixture.version() == snapshot.fixture_version
                    and fixture.instance_id() == snapshot.fixture_instance_id
                    and tuple(sorted(fixture.identity_records())) == snapshot.identity_records
                    and tuple(sorted(fixture.resource_records())) == snapshot.resource_fingerprint)
        except Exception:
            return False

    def _content_unchanged(self):
        """Full digest re-check; called outside the gate because it may take longer."""
        try:
            return self._fixture.canonical_digest() == self._snapshot.fixture_content_sha256
        except Exception:
            return False

    def _fail_binding(self, ticket):
        """Stop on binding drift: abort the unconsumed ticket, never run the fixture."""
        with self._gate:
            if self._ledger is ticket and ticket.state == 'ACCEPTED':
                self._stop_locked(['FIXTURE_BINDING_MISMATCH'])
        self._drain_stop_events()

    # -- delivery (outside the gate) ---------------------------------------
    def _deliver(self):
        ticket = self._ledger
        if ticket is None:
            return
        # Outside the gate: the full content digest may take longer, and revocation
        # must never wait for it.  The in-gate cheap check below is the actual gate.
        if not self._content_unchanged():
            self._fail_binding(ticket)
            return
        with self._gate:
            if self._ledger is not ticket or ticket.state != 'ACCEPTED':
                # Already aborted/consumed by another path; never consume twice.
                return
            if not self._binding_unchanged():
                # Resource/ACL/identity drift detected at the consumption boundary.
                self._stop_locked(['FIXTURE_BINDING_MISMATCH'])
                aborted = True
            elif not self._checkpoint_locked():
                self._abort_ticket_locked()
                aborted = True
            else:
                self._ledger = None
                ticket.state = 'CONSUMED'
                self._counters['delivery_consumed_count'] += 1
                aborted = False
        if aborted:
            self._drain_stop_events()
            return
        if self._emit('reviewed_delivery_consumed', action_id=ticket.action_id,
                      dispatch_seq=ticket.dispatch_seq) is None:
            return
        with self._gate:
            self._counters['fixture_started_count'] += 1
        if self._emit('reviewed_fixture_started', action_id=ticket.action_id,
                      dispatch_seq=ticket.dispatch_seq) is None:
            return
        try:
            payload = self._fixture.handle(ticket.wire)
        except Exception:
            with self._gate:
                self._counters['fixture_failed_count'] += 1
                self._checkpoint_locked('FIXTURE_ERROR')
            self._emit('reviewed_fixture_failed', action_id=ticket.action_id,
                       dispatch_seq=ticket.dispatch_seq, reason='FIXTURE_ERROR')
            self._resolve_controls()
            return
        with self._gate:
            self._counters['fixture_handled_count'] += 1
        if self._emit('reviewed_fixture_handled', action_id=ticket.action_id,
                      dispatch_seq=ticket.dispatch_seq) is None:
            return
        if self._revoke_seq is not None and self._revoke_seq > ticket.dispatch_seq:
            # Revocation arrived while this already-accepted delivery was in progress.
            self._emit('reviewed_revoked_during_delivery', action_id=ticket.action_id,
                       dispatch_seq=ticket.dispatch_seq, revoke_seq=self._revoke_seq)
        try:
            observation = parse_response_v2(payload, self._snapshot)
        except Exception:
            observation = None
        spec = ticket.slot.spec
        if observation is None:
            from .protocol import Observation
            observation = Observation(False, None, None, 'RESPONSE_ERROR', 'INVALID_RESPONSE')
        verdict = evaluate_v2(self._snapshot, spec, observation, ticket.action_id,
                              control_pass=self._control_passed(spec))
        projection = projection_v2(self._snapshot, spec, observation, verdict, ticket.action_id)
        if self._emit('reviewed_response_evidence', action_id=ticket.action_id, **projection) is None:
            return
        if self._emit('reviewed_assertion', action_id=ticket.action_id,
                      assertion=verdict.assertion,
                      simulated_conclusion=verdict.simulated_conclusion) is None:
            return
        with self._gate:
            slot = ticket.slot
            slot.simulated_conclusion = verdict.simulated_conclusion
            slot.assertion = verdict.assertion
            slot.processed = True
            slot.phase = 'DONE'
            self._counters['response_observed_count'] += 1
        if verdict.assertion == 'MISSING_CONTROL':
            self._pending_controls[slot.slot_id] = (slot, observation, ticket.action_id)
        self._resolve_controls()

    def _control_passed(self, spec):
        if spec.control_id is None:
            return False
        control = self._by_id.get(spec.control_id)
        return bool(control is not None and control.processed
                    and control.simulated_conclusion == 'PASS')

    def _resolve_controls(self):
        for key, (slot, observation, action_id) in list(self._pending_controls.items()):
            spec = slot.spec
            if spec is None or not self._control_passed(spec):
                continue
            verdict = evaluate_v2(self._snapshot, spec, observation, action_id, control_pass=True)
            if self._emit('reviewed_control_resolution', action_id=action_id,
                          assertion=verdict.assertion,
                          simulated_conclusion=verdict.simulated_conclusion) is None:
                return
            with self._gate:
                slot.simulated_conclusion = verdict.simulated_conclusion
                slot.assertion = verdict.assertion
            del self._pending_controls[key]

    def _complete(self):
        with self._gate:
            if self.state != 'RUNNING':
                return
            if not self._checkpoint_locked():
                return
            self.state = 'COMPLETED'
        self._emit('reviewed_completion_ready')

    # -- reporting ----------------------------------------------------------
    def check_invariants(self):
        """Return violated invariant names; empty list means consistent."""
        counters = self.reviewed_counts()
        problems = []
        if counters['fixture_handled_count'] > counters['fixture_started_count']:
            problems.append('handled>started')
        if counters['fixture_started_count'] > counters['delivery_consumed_count']:
            problems.append('started>consumed')
        if counters['delivery_consumed_count'] > counters['dispatch_accepted_count']:
            problems.append('consumed>accepted')
        if counters['dispatch_accepted_count'] > counters['prepared_count']:
            problems.append('accepted>prepared')
        if counters['prepared_count'] > counters['authorized_count']:
            problems.append('prepared>authorized')
        if (counters['authorization_decisions']
                != counters['authorized_count'] + counters['denied_count']):
            problems.append('decisions!=authorized+denied')
        terminal = self.state in ('COMPLETED', 'STOPPED')
        if (counters['prepared_count'] + counters['prepare_failed_count']
                > counters['authorized_count']):
            problems.append('prepared+failed>authorized')
        if terminal and (counters['delivery_consumed_count']
                         + counters['delivery_aborted_count']
                         != counters['dispatch_accepted_count']):
            problems.append('terminal:consumed+aborted!=accepted')
        counts = self.counts
        if counts['model_request_count'] != counters['dispatch_accepted_count']:
            problems.append('model_request_count!=accepted')
        if not counts['model_request_count'] <= counts['attempt_count'] <= counts['plan_count']:
            problems.append('count_order')
        return problems

    def report(self):
        with self._lock:
            rows = []
            for slot in self._slots:
                rows.append(dict(slot_id=slot.slot_id, proposal_id=slot.proposal_id,
                                 check_id=slot.check_id if slot.spec is not None else None,
                                 attempt_id=slot.attempt_id, action_id=slot.action_id,
                                 dispatch_seq=slot.dispatch_seq,
                                 authorization=slot.authorization,
                                 execution='NOT_EXECUTED',
                                 conclusion='INCONCLUSIVE',
                                 simulated_conclusion=slot.simulated_conclusion,
                                 assertion=slot.assertion, processed=slot.processed,
                                 evidence_ids=list(slot.evidence_ids)))
            return self._redactor.clean(dict(
                run_id=self.run_id, mode=self.mode, provenance=self.provenance,
                strategy_id='reviewed-v2', state=self.state, reason=self.reason,
                stop_conditions=list(self.conditions), counts=self.counts,
                reviewed_counts=dict(self._counters),
                checks=rows, audit_gap=self._audit_gap,
                evidence_complete=not self._audit_gap,
                unpersisted_event_kinds=list(self._unpersisted_facts),
                snapshot_id=self._snapshot.snapshot_id,
                contract_id=self._snapshot.contract_id,
                contract_version=self._snapshot.contract_version,
                contract_digest=self._snapshot.contract_digest,
                scope_digest=self._snapshot.scope_digest,
                fixture_id=self._snapshot.fixture_id,
                fixture_version=self._snapshot.fixture_version,
                fixture_content_sha256=self._snapshot.fixture_content_sha256,
                fixture_instance_id=self._snapshot.fixture_instance_id,
                resource_fingerprint=[list(row) for row in self._snapshot.resource_fingerprint],
                revoke_sequence=self._revoke_seq,
                real_network_requests=REAL_NETWORK_NOT_MEASURED,
                network_latency=REAL_NETWORK_NOT_MEASURED,
                OS_SEND_PROOF='UNAVAILABLE',
                unperformed_approved_candidates=[
                    check_id for check_id in self._snapshot.candidate_ids()
                    if not any(row.check_id == check_id and row.processed for row in self._slots)]))

    def finalize(self):
        with self._lock:
            if self.state not in ('STOPPED', 'COMPLETED'):
                raise InvalidInput('RUN_NOT_TERMINAL')
            if not self._finalized:
                self._finalized = True
                # Terminal: no dispatch can use these request bytes any more.
                with self._gate:
                    self._requests.clear()
                report = self.report()
                manifest = dict(run_id=self.run_id, provenance=self.provenance,
                                counts=report['counts'], audit_gap=self._audit_gap,
                                evidence_complete=report['evidence_complete'],
                                snapshot_id=self._snapshot.snapshot_id,
                                contract_digest=self._snapshot.contract_digest,
                                fixture_content_sha256=self._snapshot.fixture_content_sha256)
                try:
                    self.evidence.finish(manifest, report)
                except Exception:
                    self._audit_gap = True
                    self._note_unpersisted('report_finalization')
            return self.report()

"""Serial RC2 state machine. All dispatch here is explicitly offline."""
import copy
import math
from threading import RLock
import time

from .dispatch import OfflineDispatcher, Revocation
from .evidence import MemoryEvidence, Redactor, unique_id
from .models import (AuthorizationDecision as AD, Check, CheckResult, Configuration,
                     ExecutionState as ES, InvalidInput, RunState)
from .planner import FixedPlanner


class Controller:
    def __init__(self, raw_config, *, clock=time.monotonic, wall_clock=time.time,
                 dispatcher=None, evidence=None, revocation=None, secrets=()):
        self._raw = copy.deepcopy(raw_config)
        self._clock = clock
        self._wall_clock = wall_clock
        self._dispatcher = dispatcher if dispatcher is not None else OfflineDispatcher()
        self._evidence = evidence if evidence is not None else MemoryEvidence()
        self._revocation = revocation if revocation is not None else Revocation()
        self._redactor = Redactor(secrets)
        self._lock = RLock()
        self._state = RunState.READY
        self._config = None
        self._results = []
        self._by_id = {}
        self._proposal_ids = {}
        self._uncovered_proposals = []
        self._attempt_count = 0
        self._request_count = 0  # Reserved for real HTTP; fake dispatch NEVER increments it.
        self._offline_dispatch_count = 0
        self._t0 = None
        self._last_clock = None
        self._elapsed = 0.0
        self._planning_seconds = 0.0
        self._reason = None
        self._conditions = []
        self._audit_gap = False
        self._inflight = None
        self._finalized = False
        self._event_sequence = 0
        self._strategy_id = "fixed"
        self.run_id = unique_id("run")
        try:
            self._evidence.open(self.run_id, self._redactor)
        except Exception:
            self._audit_gap = True
            self._state = RunState.STOPPED
            self._reason = "AUDIT_ERROR"
            self._conditions = ["AUDIT_ERROR"]

    @property
    def state(self):
        return self._state

    @property
    def reason(self):
        return self._reason

    @property
    def counts(self):
        return {"plan_count": len(self._results), "attempt_count": self._attempt_count,
                "request_count": self._request_count, "offline_dispatch_count": self._offline_dispatch_count}

    @property
    def results(self):
        return copy.deepcopy(self._results)

    def _emit(self, kind, **data):
        if self._audit_gap:
            return None
        eid = unique_id("evidence")
        self._event_sequence += 1
        event = dict(run_id=self.run_id, evidence_id=eid, sequence=self._event_sequence,
                     kind=kind, mode="offline", elapsed=self._elapsed, counts=self.counts, **data)
        try:
            self._evidence.emit(self._redactor.clean(event))
        except Exception:
            self._audit_gap = True
            if self._state not in (RunState.STOPPED, RunState.COMPLETED):
                # Preserve precedence without trying a recursively failing audit sink.
                reasons = self._stop_conditions("AUDIT_ERROR")
                self._state = RunState.STOPPED
                self._reason = reasons[0]
                self._conditions = reasons
            return None
        return eid

    def _stop_conditions(self, error=None):
        reasons = []
        if self._revocation.revoked:
            reasons.append("REVOKED")
        if self._config:
            try:
                now_wall = self._wall_clock()
                if not math.isfinite(now_wall) or now_wall >= self._config.authorization.valid_until_epoch:
                    reasons.append("AUTHORIZATION_INVALID")
            except Exception:
                reasons.append("AUTHORIZATION_INVALID")
        clock_error = False
        if self._t0 is not None:
            try:
                now = self._clock()
                if not math.isfinite(now) or now < self._last_clock:
                    clock_error = True
                else:
                    self._last_clock = now
                    self._elapsed = now - self._t0
            except Exception:
                clock_error = True
        if clock_error:
            reasons.append("RUNTIME_ERROR")
        if error and error != "TIMEOUT":
            reasons.append(error)
        if self._config and self._t0 is not None and self._elapsed >= self._config.budget.logical_timeout_seconds:
            reasons.append("BUDGET_EXHAUSTED")
        if error == "TIMEOUT":
            reasons.append(error)
        return list(dict.fromkeys(reasons))

    def _checkpoint(self, error=None):
        if self._state != RunState.RUNNING:
            return False
        reasons = self._stop_conditions(error)
        if reasons:
            self._stop(reasons)
            return False
        return True

    def _stop(self, reasons):
        if self._state in (RunState.STOPPED, RunState.COMPLETED):
            return
        self._state = RunState.STOPPED
        self._reason = reasons[0]
        self._conditions = reasons
        self._emit("stopped", reasons=reasons, inflight_slot=self._inflight)

    def start(self, planner=None):
        with self._lock:
            if self._state != RunState.READY:
                self._emit("terminal_or_started_rejection")
                return
            try:
                self._config = Configuration.parse(self._raw)
                if self._wall_clock() >= self._config.authorization.valid_until_epoch:
                    raise InvalidInput("EXPIRED_AUTHORIZATION")
            except (InvalidInput, TypeError, ValueError, KeyError):
                self._stop(["INVALID_INPUT"])
                return
            self._raw = None
            self._state = RunState.RUNNING
            try:
                self._t0 = self._clock()
                if not math.isfinite(self._t0):
                    raise ValueError()
                self._last_clock = self._t0
            except Exception:
                self._t0 = None
                self._stop(["RUNTIME_ERROR"])
                return
            if not self._checkpoint():
                return
            self._emit("started", metadata=self._metadata())
            if not self._checkpoint():
                return
            planning_start = self._last_clock
            try:
                planning_start = self._clock()
                self._strategy_id = "fixed" if planner is None or type(planner) is FixedPlanner else "injected-test-planner"
                plan = (planner if planner is not None else FixedPlanner()).plan(self._config.candidates)
            except Exception:
                self._checkpoint("RUNTIME_ERROR")
                self._planning_seconds = max(0, self._last_clock - planning_start)
                return
            if not self._checkpoint():
                self._planning_seconds = max(0, self._last_clock - planning_start)
                return
            self._planning_seconds = max(0, self._last_clock - planning_start)
            try:
                if type(plan) is not list or len(plan) > self._config.budget.max_checks:
                    raise InvalidInput("INVALID_PLAN")
                checks = [Check.parse(p) for p in plan]
                if len({c.check_id for c in checks}) != len(checks):
                    raise InvalidInput("DUPLICATE_CHECK")
            except (InvalidInput, TypeError, ValueError):
                self._checkpoint("INVALID_INPUT")
                return
            if not self._checkpoint():
                return
            for check in checks:
                self._register(check, "initial")
            self._emit("plan_registered", checks=[
                {"slot_id": r.slot_id, "proposal_id": self._proposal_ids[r.slot_id],
                 "check_id": self._audit_check_id(r.check)} for r in self._results])
            self._checkpoint()

    def _register(self, check, source):
        result = CheckResult(unique_id("check"), check, source)
        self._results.append(result)
        self._proposal_ids[result.slot_id] = unique_id("proposal")
        if check:
            self._by_id[check.check_id] = result
        return result

    def _authorize(self, check):
        endpoint = next((e for e in self._config.endpoints if e.endpoint_id == check.endpoint_id), None)
        if not endpoint:
            return "UNREGISTERED_ENDPOINT"
        if check.method != endpoint.method:
            return "METHOD_NOT_ALLOWED"
        if check.identity_ref not in self._config.identities:
            return "UNREGISTERED_IDENTITY"
        if tuple(k for k, v in check.params) != endpoint.parameter_names:
            return "PARAMETERS_NOT_ALLOWED"
        matrix = {p.key(): p.expected for p in self._config.permissions}
        if matrix.get(check.permission_key()) != check.expected:
            return "PARAMETER_COMBINATION_OR_EXPECTATION_NOT_ALLOWED"
        candidate = next((c for c in self._config.candidates if c.check_id == check.check_id), None)
        if candidate != check:
            return "NOT_APPROVED_CANDIDATE"
        return None

    def _attempt(self, result, forced_reason=None):
        if self._inflight is not None:
            self._emit("reentrant_dispatch_rejected", slot_id=self._inflight)
            return
        if not self._checkpoint():
            return
        if result.processed:
            self._emit("duplicate_rejected", slot_id=result.slot_id)
            return
        self._attempt_count += 1
        result.attempt_id = unique_id("attempt")
        denial = forced_reason or self._authorize(result.check)
        result.authorization = AD.DENY if denial else AD.ALLOW
        result.reason = denial or "OFFLINE_ONLY_NO_HTTP_RESPONSE"
        eid = self._emit("authorization_decision", slot_id=result.slot_id,
                         check=self._audit_check(result.check),
                         proposal_id=self._proposal_ids[result.slot_id],
                         attempt_id=result.attempt_id, decision=result.authorization.value, reason=result.reason)
        if eid:
            result.evidence_ids.append(eid)
        # The decision must be recorded and authorization/time rechecked before dispatch.
        if not self._checkpoint():
            result.processed = True
            return
        if not denial:
            self._inflight = result.slot_id
            try:
                def dispatch():
                    if self._checkpoint():
                        self._offline_dispatch_count += 1
                        self._dispatcher.record(result.check, self._config.budget.logical_timeout_seconds - self._elapsed, self._revocation)
                self._revocation.dispatch_if_active(dispatch)
            except TimeoutError:
                result.execution = ES.TIMEOUT
                result.reason = "OFFLINE_DISPATCH_TIMEOUT"
                self._checkpoint("TIMEOUT")
            except Exception:
                result.execution = ES.ERROR
                result.reason = "OFFLINE_DISPATCH_ERROR"
                self._checkpoint("RUNTIME_ERROR")
            finally:
                if not self._checkpoint() and result.execution == ES.NOT_EXECUTED:
                    result.execution = ES.CANCELLED
                    result.reason = "OFFLINE_ACTION_INTERRUPTED"
                self._inflight = None
        result.processed = True
        eid = self._emit("check_processed", slot_id=result.slot_id, attempt_id=result.attempt_id,
                         authorization=result.authorization.value, execution=result.execution.value,
                         conclusion=result.conclusion.value, reason=result.reason)
        if eid:
            result.evidence_ids.append(eid)
        self._checkpoint()

    def submit(self, proposal):
        """Register a pending addition; malformed new proposals consume an attempt now."""
        with self._lock:
            if not self._checkpoint():
                self._emit("addition_rejected", reason=self._reason or "NOT_RUNNING", proposal=self._proposal_summary(proposal))
                return
            check = None
            try:
                check = Check.parse(proposal)
            except (InvalidInput, TypeError, ValueError):
                pass
            # Even a malformed duplicate bearing a registered ID cannot replace a slot.
            claimed_id = proposal.get("check_id") if type(proposal) is dict else None
            existing = self._by_id.get(claimed_id) if isinstance(claimed_id, str) else None
            if existing:
                if existing.processed:
                    self._emit("duplicate_rejected", slot_id=existing.slot_id,
                               reason="ALREADY_PROCESSED", proposal=self._proposal_summary(proposal))
                elif check != existing.check:
                    # Reject the conflicting proposal, not the registered check.
                    # No new slot or first attempt is consumed for this duplicate ID.
                    self._emit("conflicting_proposal_rejected", slot_id=existing.slot_id,
                               reason="REGISTERED_CHECK_IMMUTABLE",
                               proposal=self._proposal_summary(proposal))
                else:
                    self._emit("already_registered", slot_id=existing.slot_id)
                return
            if len(self._results) >= self._config.budget.max_checks:
                self._uncovered_proposals.append(dict(self._proposal_summary(proposal), reason="BUDGET_EXHAUSTED"))
                self._emit("addition_budget_rejected", proposal=self._uncovered_proposals[-1])
                self._checkpoint("BUDGET_EXHAUSTED")
                return
            result = self._register(check, "additional")
            self._emit("addition_registered", slot_id=result.slot_id, check_id=self._audit_check_id(check),
                       proposal=self._proposal_summary(proposal, self._proposal_ids[result.slot_id]))
            if check is None:
                self._attempt(result, "INVALID_INTENT")

    def _remaining_value(self):
        # No status-code, vulnerability claim or Planner opinion determines value.
        # Conservatively treat every unprocessed approved candidate as valuable/unknown.
        return [c for c in self._config.candidates if not self._candidate_processed(c)]

    def _candidate_processed(self, candidate):
        result = self._by_id.get(candidate.check_id)
        return (result is not None and result.check == candidate and result.processed
                and result.authorization == AD.ALLOW)

    def _audit_check_id(self, check):
        # IDs supplied by a proposal can themselves contain sensitive text.
        # Only expose an ID already present in the trusted candidate registry.
        if check is not None and self._config is not None:
            return next((c.check_id for c in self._config.candidates
                         if c.check_id == check.check_id), None)
        return None

    def _audit_check(self, check):
        # Syntax is not approval. Serialize only an exact trusted candidate;
        # unknown IDs/parameters and denied variants never reach an evidence sink.
        if check is not None and self._config is not None:
            candidate = next((c for c in self._config.candidates if c == check), None)
            if candidate is not None:
                return candidate.to_dict()
        return None

    def _proposal_summary(self, proposal, proposal_id=None):
        summary = {"proposal_id": proposal_id or unique_id("proposal")}
        try:
            check = Check.parse(proposal)
        except (InvalidInput, TypeError, ValueError):
            return dict(summary, invalid_structure=True, content_omitted=True)
        approved = self._audit_check(check)
        if approved is not None:
            return dict(summary, check=approved)
        # No raw payload, attacker-supplied keys, exception text or payload hash.
        # A generated ID plus trusted linkage is sufficient for rejection tracing.
        return dict(summary, approved_candidate=False, content_omitted=True,
                    check_id=self._audit_check_id(check))

    def round(self, proposals=(), repeat=False):
        """Process one registered check, then additions/continuation, THEN completion."""
        with self._lock:
            if self._inflight is not None:
                self._emit("reentrant_round_rejected", slot_id=self._inflight)
                return
            if not self._checkpoint():
                self._emit("round_rejected", reason=self._reason or "NOT_RUNNING")
                return
            pending = next((r for r in self._results if not r.processed), None)
            if pending:
                self._attempt(pending)
            for proposal in proposals:
                self.submit(proposal)
            if not self._checkpoint():
                return
            if repeat:
                remaining = self._remaining_value()
                self._emit("continuation_review", remaining_check_ids=[c.check_id for c in remaining],
                           required_controls=[c.control_id for c in remaining if c.control_id],
                           repeated_proposal="continue_without_new_evidence", inflight_slot=self._inflight)
                if not self._checkpoint():
                    return
                if remaining:
                    # Include omitted approved controls/candidates rather than accepting premature stop.
                    for c in remaining:
                        if c.check_id not in self._by_id:
                            self.submit(c.to_dict())
                            break
                elif self._inflight is None and all(r.processed for r in self._results):
                    self._stop(["NO_NEW_EVIDENCE"])
                    return
            if self._checkpoint() and all(r.processed for r in self._results):
                # Audit the completion preparation while still RUNNING; its cost counts.
                self._emit("completion_ready")
                if self._checkpoint():
                    self._state = RunState.COMPLETED

    def run(self, planner=None):
        self.start(planner)
        while self._state == RunState.RUNNING:
            self.round()
        return self.finalize()

    def poll(self):
        """Trusted scheduler checks revocation/time even without an action."""
        with self._lock:
            self._checkpoint()

    def _metadata(self):
        c = self._config
        if not c:
            return {}
        return {"authorization_id": c.authorization.authorization_id, "authorization_version": c.authorization.version,
                "permission_ref": c.authorization.permission_ref, "origin": c.authorization.origin,
                "contract_version": c.contract_version, "matrix_version": c.matrix_version,
                "fixture_version": c.fixture_version, "strategy_id": self._strategy_id, "strategy_version": c.strategy_version,
                "candidate_checks": [x.to_dict() for x in c.candidates],
                "budget": vars(c.budget), "budget_status": "trial_not_teacher_frozen"}

    def report(self):
        with self._lock:
            registered = set(self._by_id)
            records = [{"slot_id": r.slot_id, "check_id": self._audit_check_id(r.check),
                        "proposal_id": self._proposal_ids[r.slot_id],
                        "check": self._audit_check(r.check),
                        "source": r.source, "attempt_id": r.attempt_id, "authorization": r.authorization.value,
                        "execution": r.execution.value, "conclusion": r.conclusion.value, "reason": r.reason,
                        "processed": r.processed, "evidence_ids": list(r.evidence_ids)} for r in self._results]
            return self._redactor.clean({"run_id": self.run_id, "mode": "offline", "state": self._state.value,
                    "reason": self._reason, "stop_conditions": self._conditions[:], "counts": self.counts,
                    "initial_count": sum(r.source == "initial" for r in self._results),
                    "additional_count": sum(r.source == "additional" for r in self._results),
                    "processed_count": sum(r.processed for r in self._results),
                    "t0": self._t0, "elapsed": self._elapsed, "planning_seconds": self._planning_seconds,
                    "metadata": self._metadata(), "checks": records,
                    "uncovered_candidates": [c.check_id for c in self._config.candidates if c.check_id not in registered] if self._config else [],
                    "unperformed_approved_candidates": [c.check_id for c in self._remaining_value()] if self._config else [],
                    "rejected_additions": copy.deepcopy(self._uncovered_proposals),
                    "unfinished_slots": [r.slot_id for r in self._results if not r.processed],
                    "conclusion_counts": {"PASS": 0, "FAIL": 0, "INCONCLUSIVE": len(records)},
                    "actual_api_coverage": 0, "audit_gap": self._audit_gap,
                    "audit_error": "AUDIT_ERROR" if self._audit_gap else None,
                    "limitations": ["No HTTP requests or responses; no API security conclusion.",
                                    "Offline controller checks are not formal course acceptance.",
                                    "No measured LLM tokens or fixed/dynamic comparison."]})

    def finalize(self):
        with self._lock:
            if self._state not in (RunState.COMPLETED, RunState.STOPPED):
                raise RuntimeError("RUN_NOT_TERMINAL")
            if not self._finalized:
                self._finalized = True
                report = self.report()
                manifest = {"run_id": self.run_id, "schema_version": "offline-v1", "mode": "offline",
                            "metadata": self._metadata(), "counts": self.counts, "audit_gap": self._audit_gap,
                            "events": "events.jsonl", "report": "report.json", "state": self._state.value}
                try:
                    if not self._audit_gap:
                        self._evidence.finish(self._redactor.clean(manifest), report)
                except Exception:
                    # Terminal state cannot reopen/change; report the post-terminal evidence failure.
                    self._audit_gap = True
            return self.report()

import copy
import json
from pathlib import Path
import socket
import tempfile
import threading
import unittest
from unittest.mock import patch

from p3_core.controller import Controller
from p3_core.dispatch import OfflineDispatcher, Revocation
from p3_core.evidence import JsonlEvidence, MemoryEvidence
from p3_core.models import Configuration, RunState
from p3_core.planner import FixedPlanner
from p3_core.__main__ import main


def config(count=8):
    candidates = [dict(check_id="c" + str(i), kind="control", endpoint_id="object",
                       method="GET", identity_ref="owner", params={"id": str(i)},
                       expected="ALLOW", control_id=None) for i in range(count)]
    return dict(mode="offline", authorization=dict(authorization_id="offline-authorization",
                version="v1", approved_by="offline-fixture", permission_ref="offline-test-only",
                active=True, valid_until_epoch=4102444800, origin="http://127.0.0.1:8765"),
                budget=dict(max_checks=8, logical_timeout_seconds=90, concurrency=1),
                endpoints=[dict(endpoint_id="object", method="GET", path="/objects",
                                read_only=True, parameter_names=["id"])],
                identities=["owner", "other", "anonymous"], candidates=candidates,
                permissions=[{k: c[k] for k in ("endpoint_id", "method", "identity_ref", "params", "expected")} for c in candidates],
                contract_version="offline-v1", matrix_version="offline-v1", fixture_version="offline-v1", strategy_version="fixed-v1")


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


class Planner:
    def __init__(self, plan):
        self.value = plan

    def plan(self, candidates):
        return copy.deepcopy(self.value)


class CallbackDispatcher(OfflineDispatcher):
    def __init__(self, callback):
        super().__init__()
        self.callback = callback

    def record(self, check, remaining_seconds, revocation):
        super().record(check, remaining_seconds, revocation)
        return self.callback(check, remaining_seconds, revocation)


class FailingEvidence(MemoryEvidence):
    def __init__(self, fail_kind):
        super().__init__()
        self.fail_kind = fail_kind

    def emit(self, event):
        if event["kind"] == self.fail_kind:
            raise OSError("secret raw exception must not be logged")
        super().emit(event)


class CoreTests(unittest.TestCase):
    def setUp(self):
        # Any accidental network socket construction fails the offline suite.
        self.socket_guard = patch.object(socket, "socket", side_effect=AssertionError("NETWORK_FORBIDDEN"))
        self.socket_guard.start()
        self.addCleanup(self.socket_guard.stop)
        self.clock = Clock()
        self.dispatcher = OfflineDispatcher()
        self.evidence = MemoryEvidence()

    def controller(self, raw=None, **kwargs):
        return Controller(raw if raw is not None else config(), clock=self.clock,
                          dispatcher=kwargs.pop("dispatcher", self.dispatcher),
                          evidence=kwargs.pop("evidence", self.evidence), **kwargs)

    def assert_counts(self, c, plan, attempt, fake):
        self.assertEqual(c.counts, dict(plan_count=plan, attempt_count=attempt,
                                     request_count=0, offline_dispatch_count=fake))

    def test_fixed_plan_is_deterministic_and_does_not_mutate_config(self):
        raw = config(2)
        parsed = Configuration.parse(raw)
        self.assertEqual(FixedPlanner().plan(parsed.candidates), FixedPlanner().plan(parsed.candidates))
        c = self.controller(raw)
        raw["candidates"][0]["params"]["id"] = "tampered"
        c.run()
        self.assertEqual(self.dispatcher.calls[0][0].params, (("id", "0"),))

    def test_valid_eighth_finishes_without_http_or_api_verdict(self):
        c = self.controller()
        report = c.run()
        self.assertEqual(c.state, RunState.COMPLETED)
        self.assert_counts(c, 8, 8, 8)
        self.assertEqual(report["conclusion_counts"], {"PASS": 0, "FAIL": 0, "INCONCLUSIVE": 8})
        self.assertEqual({r["execution"] for r in report["checks"]}, {"NOT_EXECUTED"})

    def test_malformed_initial_plans_stop_without_registration(self):
        valid = config(1)["candidates"][0]
        malformed = [None, {}, "{}", [None], [valid, valid], [dict(valid, extra=True)],
                     [dict(valid, params=[])], [dict(valid, check_id=4)]]
        for plan in malformed:
            with self.subTest(plan=plan):
                c = self.controller()
                c.start(Planner(plan))
                self.assertEqual(c.reason, "INVALID_INPUT")
                self.assert_counts(c, 0, 0, 0)

    def test_initial_nine_is_not_silently_trimmed(self):
        c = self.controller(config(9))
        c.run()
        self.assertEqual(c.reason, "INVALID_INPUT")
        self.assert_counts(c, 0, 0, 0)

    def test_static_preflight_rejects_missing_and_conflicting_input(self):
        variants = []
        for name in ("permissions", "endpoints", "identities", "candidates"):
            raw = config(1); raw[name] = []; variants.append(raw)
        raw = config(1); raw["permissions"].append(dict(raw["permissions"][0], expected="DENY")); variants.append(raw)
        raw = config(1); raw["authorization"]["active"] = False; variants.append(raw)
        raw = config(1); raw["authorization"]["origin"] = "http://example.com:80"; variants.append(raw)
        raw = config(1); raw["budget"]["max_checks"] = True; variants.append(raw)
        raw = config(1); raw["budget"]["concurrency"] = 2; variants.append(raw)
        raw = config(1); raw["budget"]["logical_timeout_seconds"] = float("nan"); variants.append(raw)
        raw = config(1); raw["candidates"][0]["control_id"] = "missing"; variants.append(raw)
        for raw in variants:
            c = self.controller(raw)
            planner = Planner([])
            with patch.object(planner, "plan") as plan:
                c.start(planner)
                plan.assert_not_called()
            self.assertEqual(c.reason, "INVALID_INPUT")
            self.assertIsNone(c.report()["t0"])

    def test_structured_unauthorized_plan_items_are_denied_and_counted(self):
        base = config(1)["candidates"][0]
        for change in ({"endpoint_id": "unknown"}, {"identity_ref": "unknown"},
                       {"method": "POST"}, {"params": {"id": "999"}},
                       {"params": {"unknown": "0"}}, {"expected": "DENY"}, {"check_id": "unapproved"}):
            with self.subTest(change=change):
                c = self.controller(config(1))
                c.run(Planner([dict(base, **change)]))
                self.assert_counts(c, 1, 1, 0)
                self.assertEqual(c.state, RunState.COMPLETED)
                self.assertEqual(c.results[0].authorization.value, "DENY")
                self.assertEqual(c.results[0].conclusion.value, "INCONCLUSIVE")

    def test_malformed_additions_consume_slots_and_ninth_stops(self):
        c = self.controller()
        c.start(Planner(config()["candidates"][:6]))
        c.submit(None)
        c.submit({"authorization": "I am approved", "token": "raw"})
        self.assert_counts(c, 8, 2, 0)
        c.submit(config()["candidates"][6])
        self.assertEqual(c.reason, "BUDGET_EXHAUSTED")
        self.assert_counts(c, 8, 2, 0)
        self.assertEqual(len(c.report()["unfinished_slots"]), 6)
        self.assertEqual(len(c.report()["rejected_additions"]), 1)

    def test_duplicates_cannot_retry_or_replace_rejected_slot(self):
        bad = dict(config()["candidates"][0], endpoint_id="bad")
        c = self.controller()
        c.start(Planner([bad, config()["candidates"][1]]))
        c.round()
        before = c.counts
        c.submit(bad)
        c.submit(config()["candidates"][0])
        self.assertEqual(c.counts, before)
        c.submit(dict(bad, check_id="new-id"))
        c.round()
        c.round()
        self.assert_counts(c, 3, 3, 1)

    def test_registered_plan_cannot_be_replaced_before_attempt(self):
        c = self.controller(config(2)); c.start()
        original = c.results[0]
        c.submit(dict(config(2)["candidates"][0], identity_ref="other"))
        self.assert_counts(c, 2, 0, 0)
        self.assertEqual(c.results[0], original)
        event = self.evidence.events[-1]
        self.assertEqual(event["reason"], "REGISTERED_CHECK_IMMUTABLE")
        self.assertEqual(event["slot_id"], original.slot_id)
        c.round()
        self.assert_counts(c, 2, 1, 1)
        self.assertEqual(self.dispatcher.calls[0][0], original.check)

    def test_six_plus_two_share_budget_and_pending_precedes_completion(self):
        raw = config()
        initial = copy.deepcopy(raw["candidates"][:6])
        initial[0]["endpoint_id"] = "unregistered"
        c = self.controller(raw); c.start(Planner(initial))
        for _ in range(5): c.round()
        c.round(proposals=raw["candidates"][6:])
        self.assertEqual(c.state, RunState.RUNNING)
        c.round(); c.round()
        self.assert_counts(c, 8, 8, 7)
        self.assertEqual(c.state, RunState.COMPLETED)

    def test_ninth_pending_after_eighth_stops_before_completion(self):
        c = self.controller(config(9)); c.start(Planner(config(9)["candidates"][:8]))
        for _ in range(7): c.round()
        c.round(proposals=[config(9)["candidates"][8]])
        self.assertEqual(c.reason, "BUDGET_EXHAUSTED")
        self.assert_counts(c, 8, 8, 8)

    def test_completed_and_stopped_are_irreversible(self):
        for stop in (False, True):
            c = self.controller(config(1)); c.start()
            if stop: self.clock.now = 90
            c.round()
            snapshot = (c.state, c.reason, c.counts, c.results)
            c.start(); c.submit(config(2)["candidates"][1]); c.round(); c.poll()
            self.assertEqual((c.state, c.reason, c.counts, c.results), snapshot)
            self.clock.now = 0

    def test_planning_consumes_timeout_from_t0(self):
        clock = self.clock
        class SlowPlanner:
            def plan(self, candidates):
                clock.now = 90
                return [c.to_dict() for c in candidates]
        c = self.controller(); c.start(SlowPlanner())
        self.assertEqual(c.reason, "BUDGET_EXHAUSTED")
        self.assert_counts(c, 0, 0, 0)
        self.assertEqual(c.report()["planning_seconds"], 90)

    def test_planner_error_retains_start_and_elapsed(self):
        clock = self.clock
        class BrokenPlanner:
            def plan(self, candidates):
                clock.now = 4
                raise ValueError("private")
        c = self.controller(); c.start(BrokenPlanner())
        self.assertEqual(c.reason, "RUNTIME_ERROR")
        self.assertEqual(c.report()["elapsed"], 4)
        self.assertEqual(c.report()["t0"], 0)

    def test_exact_90_vs_89_and_remaining_deadline(self):
        for end in (89, 90):
            self.clock.now = 0
            def record(check, remaining, revoke):
                self.assertEqual(remaining, 60)
                self.clock.now = end
            d = CallbackDispatcher(record)
            c = self.controller(config(1), dispatcher=d); c.start()
            self.clock.now = 30
            c.round()
            self.assertEqual(c.state, RunState.COMPLETED if end == 89 else RunState.STOPPED)
            if end == 90: self.assertEqual(c.reason, "BUDGET_EXHAUSTED")

    def test_audit_processing_time_is_included(self):
        clock = self.clock
        class SlowEvidence(MemoryEvidence):
            def emit(self, event):
                super().emit(event)
                if event["kind"] == "completion_ready": clock.now = 90
        c = self.controller(config(1), evidence=SlowEvidence()); c.run()
        self.assertEqual(c.reason, "BUDGET_EXHAUSTED")

    def test_wall_clock_rollback_does_not_extend_monotonic_budget(self):
        wall = [100]
        c = self.controller(config(2), wall_clock=lambda: wall[0]); c.start()
        self.clock.now = 50; c.round()
        wall[0] = 0; self.clock.now = 90; c.round()
        self.assertEqual(c.reason, "BUDGET_EXHAUSTED")
        self.assert_counts(c, 2, 1, 1)

    def test_monotonic_clock_regression_safely_stops(self):
        c = self.controller(config(2)); c.start()
        self.clock.now = 5; c.round()
        self.clock.now = 4; c.round()
        self.assertEqual(c.reason, "RUNTIME_ERROR")

    def test_revocation_priority_records_all_conditions(self):
        revoke = Revocation()
        raw = config(); raw["authorization"]["valid_until_epoch"] = 100
        wall = [1]
        c = self.controller(raw, revocation=revoke, wall_clock=lambda: wall[0]); c.start()
        revoke.revoke(); wall[0] = 100; self.clock.now = 90; c.poll()
        self.assertEqual(c.reason, "REVOKED")
        self.assertEqual(c.report()["stop_conditions"], ["REVOKED", "AUTHORIZATION_INVALID", "BUDGET_EXHAUSTED"])
        c.submit(config()["candidates"][0]); c.round()
        self.assert_counts(c, 8, 0, 0)

    def test_revocation_during_authorization_audit_blocks_dispatch(self):
        revoke = Revocation()
        class RevokingEvidence(MemoryEvidence):
            def emit(self, event):
                super().emit(event)
                if event["kind"] == "authorization_decision": revoke.revoke()
        c = self.controller(config(1), revocation=revoke, evidence=RevokingEvidence()); c.run()
        self.assertEqual(c.reason, "REVOKED")
        self.assert_counts(c, 1, 1, 0)

    def test_revocation_during_fake_action_never_upgrades_conclusion(self):
        d = CallbackDispatcher(lambda check, remaining, revocation: revocation.revoke())
        c = self.controller(config(2), dispatcher=d); c.run()
        self.assertEqual(c.reason, "REVOKED")
        self.assert_counts(c, 2, 1, 1)
        self.assertEqual(c.results[0].execution.value, "CANCELLED")
        self.assertEqual(c.results[0].conclusion.value, "INCONCLUSIVE")

    def test_expiration_during_run(self):
        raw = config(); raw["authorization"]["valid_until_epoch"] = 2
        wall = [1]
        c = self.controller(raw, wall_clock=lambda: wall[0]); c.start()
        wall[0] = 2; c.round()
        self.assertEqual(c.reason, "AUTHORIZATION_INVALID")
        self.assert_counts(c, 8, 0, 0)

    def test_timeout_priority_and_runtime_failure(self):
        for exception, at, reason in ((TimeoutError, 90, "BUDGET_EXHAUSTED"),
                                      (TimeoutError, 1, "TIMEOUT"), (ValueError, 1, "RUNTIME_ERROR")):
            self.clock.now = 0
            def fail(*args):
                self.clock.now = at
                raise exception("private")
            c = self.controller(config(2), dispatcher=CallbackDispatcher(fail)); c.run()
            self.assertEqual(c.reason, reason)
            self.assert_counts(c, 2, 1, 1)

    def test_gwt_a01_a_repeat_stops_only_exhausted_valuable_work(self):
        c = self.controller(config(1)); c.start(); c.round(repeat=True)
        self.assertEqual(c.reason, "NO_NEW_EVIDENCE")
        self.assertTrue(any(e["kind"] == "continuation_review" for e in self.evidence.events))
        self.assert_counts(c, 1, 1, 1)

    def test_gwt_a01_b_no_findings_does_not_skip_remaining_check(self):
        c = self.controller(config(2)); c.start(); c.round(repeat=True)
        self.assertEqual(c.state, RunState.RUNNING)
        c.round()
        self.assertEqual(c.state, RunState.COMPLETED)
        self.assert_counts(c, 2, 2, 2)

    def test_gwt_a01_c_control_is_not_skipped_even_when_not_initially_planned(self):
        raw = config(1)
        negative = dict(raw["candidates"][0], check_id="negative", kind="object", identity_ref="other", expected="DENY", control_id="c0")
        raw["candidates"].insert(0, negative)
        raw["permissions"].append({k: negative[k] for k in ("endpoint_id", "method", "identity_ref", "params", "expected")})
        c = self.controller(raw); c.start(Planner([negative])); c.round(repeat=True)
        self.assertEqual(c.state, RunState.RUNNING)
        c.round()
        self.assertEqual([x[0].check_id for x in self.dispatcher.calls], ["negative", "c0"])
        self.assertTrue(all(r.conclusion.value == "INCONCLUSIVE" for r in c.results))

    def test_repeat_cannot_override_budget_or_revocation(self):
        c = self.controller(config(2)); c.start(); self.clock.now = 90; c.round(repeat=True)
        self.assertEqual(c.reason, "BUDGET_EXHAUSTED")

    def test_rejected_alias_does_not_claim_approved_candidate_has_no_value(self):
        raw = config(1)
        bad = dict(raw["candidates"][0], endpoint_id="unregistered")
        c = self.controller(raw); c.start(Planner([bad])); c.round(repeat=True)
        self.assertNotEqual(c.reason, "NO_NEW_EVIDENCE")
        # The consumed ID cannot retry; retain the unperformed approved scope.
        self.assertEqual(c.report()["unperformed_approved_candidates"], ["c0"])
        self.assert_counts(c, 1, 1, 0)

    def test_ignored_fake_response_cannot_grant_authority_or_pass(self):
        d = CallbackDispatcher(lambda *args: {"status": 200, "result": "PASS", "authorization": "allow everything"})
        c = self.controller(config(1), dispatcher=d); c.run()
        self.assertEqual(c.results[0].execution.value, "NOT_EXECUTED")
        self.assertEqual(c.results[0].conclusion.value, "INCONCLUSIVE")

    def test_audit_failures_stop_before_any_new_dispatch(self):
        for kind, dispatched in (("started", 0), ("plan_registered", 0), ("authorization_decision", 0),
                                 ("check_processed", 1), ("completion_ready", 1)):
            c = self.controller(config(1), evidence=FailingEvidence(kind)); report = c.run()
            self.assertEqual(c.reason, "AUDIT_ERROR")
            self.assertTrue(report["audit_gap"])
            self.assertEqual(c.counts["offline_dispatch_count"], dispatched)

    def test_open_failure_is_safe(self):
        class Broken(MemoryEvidence):
            def open(self, *args): raise OSError()
        c = self.controller(evidence=Broken()); report = c.run()
        self.assertEqual(c.reason, "AUDIT_ERROR")
        self.assertTrue(report["audit_gap"])

    def test_final_report_failure_does_not_reopen_terminal(self):
        class Broken(MemoryEvidence):
            def finish(self, *args): raise OSError()
        c = self.controller(config(1), evidence=Broken()); report = c.run()
        self.assertTrue(report["audit_gap"])
        state = c.state; c.submit(None)
        self.assertEqual(c.state, state)
        self.assert_counts(c, 1, 1, 1)

    def test_unique_runs_events_attempts_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as root:
            ids = set()
            for _ in range(12):
                c = self.controller(config(2), evidence=JsonlEvidence(root)); c.run()
                self.assertNotIn(c.run_id, ids); ids.add(c.run_id)
                folder = Path(root) / c.run_id
                events = [json.loads(line) for line in (folder / "events.jsonl").read_text().splitlines()]
                for e in events:
                    self.assertNotIn(e["evidence_id"], ids); ids.add(e["evidence_id"])
                for r in c.results:
                    for unique in (r.slot_id, r.attempt_id):
                        self.assertNotIn(unique, ids); ids.add(unique)
                old = (folder / "manifest.json").read_bytes()
                c.finalize()
                self.assertEqual((folder / "manifest.json").read_bytes(), old)
            self.assertEqual(len(list(Path(root).iterdir())), 12)

    def test_raw_mock_credentials_never_enter_evidence_or_report(self):
        secret = "mock-private-credential-123"
        raw = config(1)
        raw["candidates"][0]["params"]["id"] = secret
        raw["permissions"][0]["params"]["id"] = secret
        with tempfile.TemporaryDirectory() as root:
            c = self.controller(raw, secrets=[secret], evidence=JsonlEvidence(root))
            report = c.run()
            self.assertNotIn(secret, json.dumps(report))
            for path in Path(root).rglob("*"):
                if path.is_file(): self.assertNotIn(secret, path.read_text())

    def test_serial_calls_and_terminal_rejections_under_threads(self):
        c = self.controller(); c.start()
        threads = [threading.Thread(target=c.round) for _ in range(16)]
        for t in threads: t.start()
        for t in threads: t.join()
        self.assert_counts(c, 8, 8, 8)
        self.assertEqual(c.state, RunState.COMPLETED)

    def test_cli_success_and_bad_input_use_temp_directories(self):
        with tempfile.TemporaryDirectory() as root:
            cfg = Path(root) / "config.json"; cfg.write_text(json.dumps(config(2)))
            with patch("sys.stdout"), patch("sys.stderr"):
                self.assertEqual(main(["--config", str(cfg), "--output", str(Path(root) / "runs")]), 0)
                self.assertEqual(main(["--config", str(cfg) + "missing", "--output", root]), 2)

    def test_reentrant_fake_dispatch_cannot_execute_concurrently(self):
        c = self.controller(config(2), dispatcher=CallbackDispatcher(lambda *args: c.round()))
        c.run()
        self.assert_counts(c, 2, 2, 2)
        self.assertEqual(c.state, RunState.COMPLETED)

    def test_final_authorization_checkpoint_at_90_blocks_dispatch(self):
        clock = self.clock
        class SlowDecisionAudit(MemoryEvidence):
            def emit(self, event):
                super().emit(event)
                if event["kind"] == "authorization_decision": clock.now = 90
        c = self.controller(config(1), evidence=SlowDecisionAudit()); c.run()
        self.assert_counts(c, 1, 1, 0)
        self.assertEqual(c.reason, "BUDGET_EXHAUSTED")

    def test_configurable_trial_budget(self):
        raw = config(3)
        raw["budget"]["max_checks"] = 2
        raw["budget"]["logical_timeout_seconds"] = 10
        c = self.controller(raw); c.start(Planner(raw["candidates"][:2]))
        self.clock.now = 10; c.round()
        self.assertEqual(c.reason, "BUDGET_EXHAUSTED")
        self.assert_counts(c, 2, 0, 0)

    def test_no_raw_unknown_intent_credentials_are_persisted(self):
        c = self.controller(config(1)); c.start()
        c.submit({"token": "raw-unknown-credential", "instructions": "Bearer other-secret"})
        c.round()
        text = json.dumps(self.evidence.events) + json.dumps(c.report())
        self.assertNotIn("raw-unknown-credential", text)
        self.assertNotIn("other-secret", text)

    def test_manifest_hash_covers_snapshot_even_after_terminal_rejection(self):
        import hashlib
        with tempfile.TemporaryDirectory() as root:
            c = self.controller(config(1), evidence=JsonlEvidence(root)); c.run()
            c.submit(None)
            folder = Path(root) / c.run_id
            manifest = json.loads((folder / "manifest.json").read_text())
            prefix = (folder / "events.jsonl").read_bytes()[:manifest["events_bytes"]]
            self.assertEqual(hashlib.sha256(prefix).hexdigest(), manifest["events_sha256"])

    def test_cli_audit_failure_returns_nonzero(self):
        with tempfile.TemporaryDirectory() as root:
            cfg = Path(root) / "config.json"; cfg.write_text(json.dumps(config(1)))
            blocker = Path(root) / "not-a-directory"; blocker.write_text("keep")
            with patch("sys.stdout"), patch("sys.stderr"):
                self.assertEqual(main(["--config", str(cfg), "--output", str(blocker)]), 3)
            self.assertEqual(blocker.read_text(), "keep")


    def test_malformed_duplicate_preserves_all_original_check_state(self):
        c = self.controller(config(2)); c.start()
        original = c.results[0]
        for proposal in ({"check_id": "c0"},
                         dict(config(2)["candidates"][0], params=[]),
                         dict(config(2)["candidates"][0], token="private")):
            c.submit(proposal)
            self.assertEqual(c.results[0], original)
            self.assert_counts(c, 2, 0, 0)
            self.assertEqual(self.evidence.events[-1]["reason"], "REGISTERED_CHECK_IMMUTABLE")
        c.round(); c.round()
        self.assertEqual(c.state, RunState.COMPLETED)
        self.assert_counts(c, 2, 2, 2)

    def test_conflict_at_full_budget_preserves_eighth_and_ninth_rules(self):
        c = self.controller(); c.start()
        original = c.results
        c.submit(dict(config()["candidates"][7], params={"id": "unapproved"}))
        self.assertEqual(c.results, original)
        self.assertEqual(c.state, RunState.RUNNING)
        self.assert_counts(c, 8, 0, 0)
        c.submit(dict(config()["candidates"][7], check_id="ninth"))
        self.assertEqual(c.reason, "BUDGET_EXHAUSTED")
        self.assert_counts(c, 8, 0, 0)

    def test_conflicts_do_not_consume_new_malformed_proposal_budget(self):
        c = self.controller(); c.start(Planner(config()["candidates"][:6]))
        c.submit({"check_id": "c0"})
        c.submit(None); c.submit({"check_id": "new-malformed"})
        self.assert_counts(c, 8, 2, 0)
        self.assertFalse(c.results[0].processed)
        c.submit(config()["candidates"][6])
        self.assertEqual(c.reason, "BUDGET_EXHAUSTED")
        self.assert_counts(c, 8, 2, 0)

    def test_unapproved_payloads_absent_from_all_evidence_and_reports(self):
        markers = ("UNAPPROVED_PARAM_SENTINEL", "UNAPPROVED_ID_SENTINEL")
        class ObservedEvidence(JsonlEvidence):
            def __init__(self, root):
                super().__init__(root)
                self.observed = []
            def emit(self, event):
                self.observed.append(copy.deepcopy(event))
                super().emit(event)
        for route in ("initial", "addition", "conflict", "budget", "terminal", "malformed", "prestart"):
            with self.subTest(route=route), tempfile.TemporaryDirectory() as root:
                sink = ObservedEvidence(root)
                c = self.controller(evidence=sink)  # No secrets list / Bearer pattern shortcut.
                bad = dict(config()["candidates"][0], check_id=markers[1], params={"id": markers[0]})
                snapshots = []
                if route == "initial":
                    c.start(Planner([bad]))
                elif route == "prestart":
                    c.submit(bad); c.start()
                elif route == "terminal":
                    c.run(); c.submit(bad)
                else:
                    c.start(Planner([]) if route in ("addition", "malformed") else None)
                    if route == "conflict": bad["check_id"] = "c0"
                    if route == "malformed": bad["extra"] = markers[0]
                    c.submit(bad)
                snapshots.append(c.report())  # Includes registered-but-not-yet-attempted proposals.
                while c.state == RunState.RUNNING:
                    c.round()
                snapshots.append(c.finalize())
                artifacts = [json.dumps(snapshots), json.dumps(sink.observed)]
                artifacts += [p.read_text(encoding="utf-8") for p in Path(root).rglob("*") if p.is_file()]
                for artifact in artifacts:
                    for marker in markers:
                        self.assertNotIn(marker, artifact)
                folder = Path(root) / c.run_id
                self.assertTrue((folder / "manifest.json").exists())
                self.assertTrue((folder / "report.json").exists())

    def test_rejected_proposal_ids_correlate_without_raw_check(self):
        c = self.controller(config(1)); c.start(Planner([]))
        c.submit(dict(config(1)["candidates"][0], params={"id": "private-value"}))
        c.round(); report = c.finalize()
        row = report["checks"][0]
        self.assertIsNone(row["check"])
        self.assertTrue(row["proposal_id"].startswith("proposal_"))
        decision = next(e for e in self.evidence.events if e["kind"] == "authorization_decision")
        registered = next(e for e in self.evidence.events if e["kind"] == "addition_registered")
        self.assertEqual(decision["proposal_id"], row["proposal_id"])
        self.assertEqual(registered["proposal"]["proposal_id"], row["proposal_id"])
        self.assertEqual(decision["slot_id"], row["slot_id"])
        self.assertEqual(decision["attempt_id"], row["attempt_id"])
        self.assertEqual(decision["decision"], "DENY")
        self.assertEqual(decision["reason"], row["reason"])
        self.assert_counts(c, 1, 1, 0)

    def test_approved_check_evidence_association_is_preserved(self):
        raw = config(1)
        c = self.controller(raw); report = c.run()
        row = report["checks"][0]
        self.assertEqual(row["check"], raw["candidates"][0])
        self.assertEqual(row["check_id"], "c0")
        ids = {e["evidence_id"] for e in self.evidence.events}
        self.assertTrue(set(row["evidence_ids"]).issubset(ids))
        decision = next(e for e in self.evidence.events if e["kind"] == "authorization_decision")
        self.assertEqual(decision["check"], raw["candidates"][0])
        self.assertEqual(decision["proposal_id"], row["proposal_id"])

    def test_exception_body_absent_from_files_and_report(self):
        marker = "EXCEPTION_PRIVATE_SENTINEL"
        def fail(*args):
            raise RuntimeError(marker)
        with tempfile.TemporaryDirectory() as root:
            c = self.controller(config(1), dispatcher=CallbackDispatcher(fail), evidence=JsonlEvidence(root))
            report = c.run()
            self.assertEqual(c.reason, "RUNTIME_ERROR")
            self.assertNotIn(marker, json.dumps(report))
            for path in Path(root).rglob("*"):
                if path.is_file(): self.assertNotIn(marker, path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()

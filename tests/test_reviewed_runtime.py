"""Offline-only checks for the V2 reviewed run: dispatch ledger, revocation
linearisation, counter invariants and audit boundaries.

All concurrency tests use ``threading.Event`` barriers; no test sleeps.
"""
import tempfile
import threading
import unittest
from pathlib import Path

from p3_core.evidence import JsonlEvidence
from p3_core.http.audit import BoundedEvidence, verify_run
from p3_core.http.catalog_fixture import CatalogFixture
from p3_core.http.reviewed_contract import _bind_reviewed_contract
from p3_core.http.reviewed_runtime import COUNTER_KEYS, ReviewedOfflineRun
from p3_core.http.reviewed_snapshot import build_snapshot
from p3_core.models import InvalidInput

try:
    from tests.test_catalog_fixture import make_contract_document, reviewed_inputs
except Exception:  # pragma: no cover - discovery imports modules as top level
    from test_catalog_fixture import make_contract_document, reviewed_inputs

ALLOW = 'CAT-C-DOC-A-READER'
DENY = 'CAT-N-DOC-B-READER'
CONTROL = 'CAT-C-DOC-B-OWNER'
ANON = 'CAT-N-DOC-A-ANON'
DIR_ALLOW = 'CAT-C-DIR-A-VIEWER'


def bound(scenario='documents', *, fixture=None, evidence=None, mutate=None, **kwargs):
    """Build a snapshot bound to exactly the fixture the run will use."""
    fixture = fixture if fixture is not None else CatalogFixture(scenario)
    document = make_contract_document(scenario, fixture)
    if mutate is not None:
        mutate(document)
    binding, review, registry = reviewed_inputs(document, fixture.instance_id())
    bound_contract = _bind_reviewed_contract(review, registry=registry, now=10, **binding)
    snapshot = build_snapshot(bound_contract, fixture)
    run = ReviewedOfflineRun(snapshot, fixture, evidence=evidence,
                             credentials=fixture.credentials(), **kwargs)
    return run, fixture, snapshot


class _BlockingFixture(CatalogFixture):
    def __init__(self, scenario='documents'):
        super().__init__(scenario)
        self.entered = threading.Event()
        self.release = threading.Event()

    def handle(self, wire):
        self.entered.set()
        self.release.wait(5)
        return super().handle(wire)


class _FailingHandle(CatalogFixture):
    def handle(self, wire):
        raise RuntimeError('FIXTURE_BOOM')


class MutableVersionFixture(CatalogFixture):
    """Fixture whose reported version can change after construction (binding drift)."""

    def __init__(self, scenario='documents'):
        super().__init__(scenario)
        self.override = None

    def version(self):
        return self.override or super().version()


class DriftingFixture(CatalogFixture):
    """Test double for content drift that normal code cannot trigger.

    The real fixture's data is immutable (F1); this double simulates a hostile or
    buggy component that changes what the fixture reports after review, so the
    runtime's re-checks can be exercised.
    """

    def __init__(self, scenario='documents'):
        super().__init__(scenario)
        self.digest_drift = False
        self.fingerprint_drift = False

    def canonical_digest(self):
        return 'f' * 64 if self.digest_drift else super().canonical_digest()

    def resource_records(self):
        rows = tuple(super().resource_records())
        if self.fingerprint_drift:
            return rows + (('doc-z', 'u_attacker', 'INJECTED', ()),)
        return rows


class _FailingSink:
    def __init__(self, fail_after):
        self.fail_after = fail_after
        self.count = 0
        self.events = []

    def open(self, run_id, redactor):
        self.count = 0

    def emit(self, event):
        self.count += 1
        if self.count > self.fail_after:
            raise OSError('AUDIT_FAILURE')
        self.events.append(event)

    def finish(self, manifest, report):
        raise OSError('AUDIT_FAILURE')


class ReviewedRuntimeTests(unittest.TestCase):
    def test_single_legal_dispatch_reaches_pass(self):
        run, _, _ = bound()
        self.assertTrue(run.start())
        self.assertTrue(run.submit_id(ALLOW))
        for _ in range(8):
            run.step()
        report = run.finalize()
        counts = report['reviewed_counts']
        self.assertEqual(report['state'], 'COMPLETED')
        self.assertEqual(counts['authorized_count'], 1)
        self.assertEqual(counts['prepared_count'], 1)
        self.assertEqual(counts['dispatch_accepted_count'], 1)
        self.assertEqual(counts['delivery_consumed_count'], 1)
        self.assertEqual(counts['fixture_handled_count'], 1)
        self.assertEqual(report['checks'][0]['simulated_conclusion'], 'PASS')
        self.assertEqual(run.check_invariants(), [])

    def test_prepared_only_never_calls_fixture(self):
        run, _, _ = bound()
        run.start()
        run.submit_id(ALLOW)
        run.step()  # authorize
        run.step()  # prepare
        counts = run.reviewed_counts()
        self.assertEqual(counts['prepared_count'], 1)
        self.assertEqual(counts['dispatch_accepted_count'], 0)
        self.assertEqual(counts['fixture_started_count'], 0)

    def test_revoke_after_prepare_before_dispatch(self):
        run, _, _ = bound()
        run.start()
        run.submit_id(ALLOW)
        run.step()  # authorize
        run.step()  # prepare
        self.assertEqual(run.reviewed_counts()['prepared_count'], 1)
        run.revoke()
        run.step()  # dispatch attempt after revocation
        counts = run.reviewed_counts()
        self.assertEqual(counts['dispatch_accepted_count'], 0)
        self.assertEqual(counts['fixture_started_count'], 0)
        self.assertEqual(counts['fixture_handled_count'], 0)
        self.assertEqual(counts['dispatch_cancelled_count'], 1)
        self.assertEqual(run.state, 'STOPPED')
        kinds = [event['kind'] for event in run.evidence.events]
        self.assertIn('reviewed_dispatch_cancelled', kinds)
        self.assertNotIn('reviewed_dispatch_accepted', kinds)

    def test_duplicate_id_gets_no_extra_budget(self):
        run, _, _ = bound()
        run.start()
        self.assertTrue(run.submit_id(ALLOW))
        self.assertFalse(run.submit_id(ALLOW))
        self.assertEqual(run.counts['plan_count'], 1)
        self.assertEqual(run.reviewed_counts()['proposal_rejected_count'], 1)

    def test_unknown_id_is_denied_without_dispatch(self):
        run, _, _ = bound()
        run.start()
        self.assertTrue(run.submit_id('NOT-A-REVIEWED-CANDIDATE'))
        run.step()  # authorize -> DENY
        counts = run.reviewed_counts()
        self.assertEqual(counts['denied_count'], 1)
        self.assertEqual(counts['authorized_count'], 0)
        self.assertEqual(counts['prepared_count'], 0)
        self.assertEqual(counts['fixture_started_count'], 0)

    def test_accepted_delivery_consumed_at_most_once(self):
        run, _, _ = bound()
        run.start()
        run.submit_id(ALLOW)
        for _ in range(3):
            run.step()  # authorize, prepare, accept
        self.assertEqual(run.reviewed_counts()['dispatch_accepted_count'], 1)
        run.step()  # deliver + observe
        run.step()  # must not deliver again
        counts = run.reviewed_counts()
        self.assertEqual(counts['delivery_consumed_count'], 1)
        self.assertEqual(counts['fixture_handled_count'], 1)
        self.assertEqual(counts['response_observed_count'], 1)

    def test_revoke_during_delivery_is_recorded_in_order(self):
        fixture = _BlockingFixture('documents')
        run, _, _ = bound('documents', fixture=fixture)
        errors = []

        def worker():
            try:
                run.start()
                run.submit_id(ALLOW)
                for _ in range(4):  # authorize, prepare, accept, deliver(blocking)
                    run.step()
            except Exception as error:  # pragma: no cover - surfaced below
                errors.append(error)

        thread = threading.Thread(target=worker)
        thread.start()
        self.assertTrue(fixture.entered.wait(5))
        run.revoke()
        fixture.release.set()
        thread.join(5)
        self.assertFalse(thread.is_alive())
        self.assertEqual(errors, [])
        kinds = [event['kind'] for event in run.evidence.events]
        self.assertIn('reviewed_revoked_during_delivery', kinds)
        accepted = [e for e in run.evidence.events if e['kind'] == 'reviewed_dispatch_accepted'][0]
        revoked = [e for e in run.evidence.events if e['kind'] == 'reviewed_revoked_during_delivery'][0]
        self.assertLess(accepted['dispatch_seq'], revoked['revoke_seq'])
        counts = run.reviewed_counts()
        self.assertEqual(counts['dispatch_accepted_count'], 1)
        self.assertEqual(counts['fixture_handled_count'], 1)

    def test_fixture_error_never_creates_false_handled(self):
        fixture = _FailingHandle('documents')
        run, _, _ = bound('documents', fixture=fixture)
        run.start()
        run.submit_id(ALLOW)
        for _ in range(6):
            run.step()
        counts = run.reviewed_counts()
        self.assertEqual(counts['dispatch_accepted_count'], 1)
        self.assertEqual(counts['fixture_started_count'], 1)
        self.assertEqual(counts['fixture_handled_count'], 0)
        self.assertEqual(counts['fixture_failed_count'], 1)
        self.assertEqual(run.state, 'STOPPED')
        self.assertEqual(run.reason, 'FIXTURE_ERROR')

    def test_audit_failure_blocks_new_fixture_work(self):
        sink = _FailingSink(fail_after=3)
        run, _, _ = bound(evidence=BoundedEvidence(sink))
        run.start()  # event 1
        run.submit_id(ALLOW)  # event 2
        for _ in range(6):
            run.step()
        counts = run.reviewed_counts()
        self.assertEqual(counts['fixture_started_count'], 0)
        self.assertEqual(counts['fixture_handled_count'], 0)
        self.assertTrue(run.report()['audit_gap'])
        self.assertEqual(run.state, 'STOPPED')

    def test_expired_licence_blocks_start(self):
        fixture = CatalogFixture('documents')
        run, _, snapshot = bound('documents', fixture=fixture,
                                 wall_clock=lambda: 5e9)
        run.start()
        self.assertEqual(run.state, 'STOPPED')
        self.assertEqual(run.reason, 'AUTHORIZATION_INVALID')
        self.assertEqual(run.reviewed_counts()['fixture_started_count'], 0)

    def test_budget_exhaustion_blocks_further_proposals(self):
        def shrink(document):
            document['budget']['max_checks'] = 1

        run, _, _ = bound(mutate=shrink)
        run.start()
        self.assertTrue(run.submit_id(ALLOW))
        self.assertFalse(run.submit_id(DENY))
        self.assertEqual(run.counts['plan_count'], 1)
        self.assertEqual(run.reviewed_counts()['proposal_rejected_count'], 1)
        self.assertEqual(run.state, 'STOPPED')

    def test_control_resolution_turns_missing_control_into_pass(self):
        run, _, _ = bound()
        run.start()
        run.submit_id(DENY)
        run.submit_id(CONTROL)
        for _ in range(16):
            run.step()
        report = run.finalize()
        rows = {row['check_id']: row for row in report['checks']}
        self.assertEqual(rows[CONTROL]['simulated_conclusion'], 'PASS')
        self.assertEqual(rows[DENY]['simulated_conclusion'], 'PASS')
        self.assertEqual(rows[DENY]['assertion'], 'REFUSAL_WITH_CONTROL')

    def test_anonymous_deny_candidate_passes_with_control(self):
        run, _, _ = bound()
        run.start()
        run.submit_id(ANON)
        run.submit_id(ALLOW)
        for _ in range(16):
            run.step()
        report = run.finalize()
        rows = {row['check_id']: row for row in report['checks']}
        self.assertEqual(rows[ANON]['simulated_conclusion'], 'PASS')

    def test_two_scenarios_share_one_run_interface(self):
        for scenario, allow in (('documents', ALLOW), ('directories', DIR_ALLOW)):
            run, _, _ = bound(scenario)
            self.assertTrue(run.start())
            self.assertTrue(run.submit_id(allow))
            for _ in range(8):
                run.step()
            report = run.finalize()
            self.assertEqual(report['state'], 'COMPLETED')
            self.assertEqual(report['checks'][0]['simulated_conclusion'], 'PASS')
            self.assertTrue(report['fixture_version'].startswith('catalog-'))

    def test_cross_thread_step_rejected(self):
        run, _, _ = bound()
        run.start()
        run.submit_id(ALLOW)
        run.step()
        errors = []

        def worker():
            try:
                run.step()
            except Exception as error:
                errors.append(error)

        thread = threading.Thread(target=worker)
        thread.start()
        thread.join(5)
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], InvalidInput)

    def test_no_dispatch_after_terminal(self):
        run, _, _ = bound()
        run.start()
        run.submit_id(ALLOW)
        for _ in range(8):
            run.step()
        before = run.reviewed_counts()
        run.step()
        run.submit_id(CONTROL)
        after = run.reviewed_counts()
        self.assertEqual(before['dispatch_accepted_count'], after['dispatch_accepted_count'])

    def test_report_is_verify_run_compatible(self):
        with tempfile.TemporaryDirectory() as root:
            sink = JsonlEvidence(root)
            run, _, _ = bound(evidence=BoundedEvidence(sink))
            run.start()
            run.submit_id(ALLOW)
            for _ in range(8):
                run.step()
            report = run.finalize()
            self.assertEqual(set(report['counts']),
                             {'plan_count', 'attempt_count', 'request_count', 'model_request_count'})
            self.assertEqual(report['counts']['request_count'], 0)
            self.assertEqual(report['counts']['model_request_count'],
                             report['reviewed_counts']['dispatch_accepted_count'])
            self.assertEqual(report['provenance'], 'NO_NETWORK_SIMULATION')
            self.assertEqual(report['real_network_requests'], 'NOT_MEASURED')
            self.assertEqual(report['network_latency'], 'NOT_MEASURED')
            verified = verify_run(Path(root) / report['run_id'])
            self.assertEqual(verified['integrity'], 'VERIFIED')
            self.assertEqual(verified['appended_bytes'], 0)

    def test_invariants_hold_across_paths(self):
        run, _, _ = bound()
        run.start()
        run.submit_id(ALLOW)
        run.submit_id('UNKNOWN-ID')
        run.submit_id(ALLOW)  # duplicate
        for _ in range(20):
            run.step()
            self.assertEqual(run.check_invariants(), [], run.reviewed_counts())
        run.finalize()
        self.assertEqual(run.check_invariants(), [])
        counters = run.reviewed_counts()
        self.assertEqual(counters['authorization_decisions'],
                         counters['authorized_count'] + counters['denied_count'])
        self.assertEqual(counters['prepared_count'] + counters['prepare_failed_count'],
                         counters['authorized_count'])

    def test_counters_cover_all_declared_keys(self):
        run, _, _ = bound()
        run.start()
        self.assertEqual(set(run.reviewed_counts()), set(COUNTER_KEYS))

    # -- post-review remediation: accepted-but-unconsumed delivery -----------
    def test_revoke_between_accept_and_consume_aborts_ticket(self):
        run, _, _ = bound()
        run.start()
        run.submit_id(ALLOW)
        for _ in range(3):
            run.step()  # authorize, prepare, accept
        self.assertEqual(run.reviewed_counts()['dispatch_accepted_count'], 1)
        run.revoke()
        run.step()
        counts = run.reviewed_counts()
        self.assertEqual(counts['delivery_consumed_count'], 0)
        self.assertEqual(counts['delivery_aborted_count'], 1)
        self.assertEqual(counts['fixture_started_count'], 0)
        self.assertEqual(counts['fixture_handled_count'], 0)
        self.assertEqual(run.check_invariants(), [])
        kinds = [event['kind'] for event in run.evidence.events]
        self.assertIn('reviewed_dispatch_accepted', kinds)
        self.assertIn('reviewed_delivery_aborted', kinds)
        self.assertLess(kinds.index('reviewed_dispatch_accepted'),
                        kinds.index('reviewed_delivery_aborted'))

    def test_accept_event_failure_aborts_ticket_safely(self):
        sink = _FailingSink(fail_after=4)  # acceptance counter commits, its event fails
        run, _, _ = bound(evidence=BoundedEvidence(sink))
        run.start()
        run.submit_id(ALLOW)
        for _ in range(6):
            run.step()
        counts = run.reviewed_counts()
        report = run.report()
        self.assertEqual(counts['dispatch_accepted_count'], 1)
        self.assertEqual(counts['delivery_aborted_count'], 1)
        self.assertEqual(counts['fixture_started_count'], 0)
        self.assertEqual(run.check_invariants(), [])
        self.assertTrue(report['audit_gap'])
        self.assertFalse(report['evidence_complete'])
        self.assertIn('reviewed_dispatch_accepted', report['unpersisted_event_kinds'])
        self.assertIn('reviewed_delivery_aborted', report['unpersisted_event_kinds'])
        persisted = [event['kind'] for event in sink.events]
        self.assertNotIn('reviewed_delivery_aborted', persisted)

    def test_licence_expiry_between_accept_and_consume_aborts_ticket(self):
        holder = {'wall': 100.0}
        run, _, snapshot = bound(wall_clock=lambda: holder['wall'])
        run.start()
        run.submit_id(ALLOW)
        for _ in range(3):
            run.step()
        self.assertEqual(run.reviewed_counts()['dispatch_accepted_count'], 1)
        holder['wall'] = snapshot.valid_until + 1
        run.step()
        counts = run.reviewed_counts()
        self.assertEqual(counts['delivery_consumed_count'], 0)
        self.assertEqual(counts['delivery_aborted_count'], 1)
        self.assertEqual(counts['fixture_started_count'], 0)
        self.assertEqual(run.reason, 'AUTHORIZATION_INVALID')
        self.assertEqual(run.check_invariants(), [])

    def test_terminal_delivery_accounting_invariant(self):
        # Normal terminal run.
        run, _, _ = bound()
        run.start()
        run.submit_id(ALLOW)
        for _ in range(8):
            run.step()
        run.finalize()
        counters = run.reviewed_counts()
        self.assertEqual(counters['delivery_consumed_count']
                         + counters['delivery_aborted_count'],
                         counters['dispatch_accepted_count'])
        self.assertEqual(run.check_invariants(), [])
        # Aborted terminal run.
        aborted, _, _ = bound()
        aborted.start()
        aborted.submit_id(ALLOW)
        for _ in range(3):
            aborted.step()
        aborted.revoke()
        aborted.step()
        aborted.finalize()
        counters = aborted.reviewed_counts()
        self.assertEqual(counters['delivery_consumed_count']
                         + counters['delivery_aborted_count'],
                         counters['dispatch_accepted_count'])
        self.assertEqual(aborted.check_invariants(), [])

    def test_aborted_ticket_cannot_be_consumed(self):
        run, _, _ = bound()
        run.start()
        run.submit_id(ALLOW)
        for _ in range(3):
            run.step()
        run.revoke()
        run.step()          # abort
        before = run.reviewed_counts()
        run.step()          # no further delivery is possible
        run.step()
        after = run.reviewed_counts()
        self.assertEqual(after['delivery_consumed_count'], before['delivery_consumed_count'])
        self.assertEqual(after['fixture_started_count'], 0)
        self.assertEqual(after['fixture_handled_count'], 0)
        self.assertEqual(after['delivery_aborted_count'], 1)

    def test_consumed_ticket_is_not_aborted_again(self):
        run, _, _ = bound()
        run.start()
        run.submit_id(ALLOW)
        for _ in range(4):
            run.step()      # through delivery
        self.assertEqual(run.reviewed_counts()['delivery_consumed_count'], 1)
        run.revoke()
        run.step()
        counts = run.reviewed_counts()
        self.assertEqual(counts['delivery_aborted_count'], 0)
        self.assertEqual(counts['delivery_consumed_count'], 1)
        self.assertEqual(run.check_invariants(), [])

    # -- post-review remediation: fixture binding ---------------------------
    def test_wrong_fixture_at_start_rejected(self):
        _, _, snapshot = bound()
        other = CatalogFixture('documents')
        run = ReviewedOfflineRun(snapshot, other, credentials=other.credentials())
        with self.assertRaises(InvalidInput) as caught:
            run.start()
        self.assertEqual(str(caught.exception), 'FIXTURE_BINDING_MISMATCH')
        self.assertEqual(run.state, 'READY')
        self.assertEqual(run.reviewed_counts()['dispatch_accepted_count'], 0)

    def test_binding_change_before_dispatch_rejected(self):
        fixture = MutableVersionFixture('documents')
        run, _, _ = bound('documents', fixture=fixture)
        self.assertTrue(run.start())
        run.submit_id(ALLOW)
        run.step()   # authorize
        run.step()   # prepare
        fixture.override = 'catalog-doc-v9'   # binding changed after start
        run.step()   # accept attempt must refuse
        counts = run.reviewed_counts()
        self.assertEqual(run.state, 'STOPPED')
        self.assertEqual(run.reason, 'FIXTURE_BINDING_MISMATCH')
        self.assertEqual(counts['dispatch_accepted_count'], 0)
        self.assertEqual(counts['fixture_started_count'], 0)
        self.assertEqual(counts['fixture_handled_count'], 0)

    # -- post-review remediation: audit honesty and request cleanup ---------
    def test_audit_failure_has_no_fabricated_persisted_events(self):
        sink = _FailingSink(fail_after=4)
        run, _, _ = bound(evidence=BoundedEvidence(sink))
        run.start()
        run.submit_id(ALLOW)
        for _ in range(6):
            run.step()
        report = run.report()
        persisted = {event['kind'] for event in sink.events}
        self.assertTrue(set(report['unpersisted_event_kinds']))
        for kind in report['unpersisted_event_kinds']:
            self.assertNotIn(kind, persisted)
        self.assertEqual(report['evidence_complete'], False)
        self.assertTrue(report['audit_gap'])

    def test_terminal_run_drops_request_references(self):
        run, _, _ = bound()
        run.start()
        run.submit_id(ALLOW)
        run.step()   # authorize
        run.step()   # prepare: one request is held
        self.assertEqual(run.pending_request_count(), 1)
        for _ in range(6):
            run.step()
        run.finalize()
        self.assertEqual(run.pending_request_count(), 0)

    # -- F3: consumption-boundary binding re-checks -------------------------
    def test_digest_drift_after_accept_aborts_before_delivery(self):
        fixture = DriftingFixture('documents')
        run, _, _ = bound('documents', fixture=fixture)
        run.start()
        run.submit_id(ALLOW)
        for _ in range(3):
            run.step()   # authorize, prepare, accept
        self.assertEqual(run.reviewed_counts()['dispatch_accepted_count'], 1)
        # Cheap check cannot see a digest-only change; the delivery-time digest does.
        fixture.digest_drift = True
        self.assertTrue(run._binding_unchanged())
        self.assertFalse(run._content_unchanged())
        run.step()   # delivery attempt
        counts = run.reviewed_counts()
        self.assertEqual(counts['delivery_consumed_count'], 0)
        self.assertEqual(counts['delivery_aborted_count'], 1)
        self.assertEqual(counts['fixture_started_count'], 0)
        self.assertEqual(counts['fixture_handled_count'], 0)
        self.assertEqual(run.state, 'STOPPED')
        self.assertEqual(run.reason, 'FIXTURE_BINDING_MISMATCH')

    def test_fingerprint_drift_rejects_new_dispatch(self):
        fixture = DriftingFixture('documents')
        run, _, _ = bound('documents', fixture=fixture)
        run.start()
        run.submit_id(ALLOW)
        run.step()   # authorize
        run.step()   # prepare
        fixture.fingerprint_drift = True
        self.assertFalse(run._binding_unchanged())
        run.step()   # accept attempt
        counts = run.reviewed_counts()
        self.assertEqual(counts['dispatch_accepted_count'], 0)
        self.assertEqual(counts['fixture_started_count'], 0)
        self.assertEqual(run.state, 'STOPPED')
        self.assertEqual(run.reason, 'FIXTURE_BINDING_MISMATCH')

    def test_licence_expiry_before_delivery_blocks_fixture(self):
        holder = {'wall': 100.0}
        run, _, snapshot = bound(wall_clock=lambda: holder['wall'])
        run.start()
        run.submit_id(ALLOW)
        for _ in range(3):
            run.step()   # authorize, prepare, accept
        holder['wall'] = snapshot.valid_until + 1
        run.step()   # delivery attempt
        counts = run.reviewed_counts()
        self.assertEqual(counts['fixture_started_count'], 0)
        self.assertEqual(counts['delivery_consumed_count'], 0)
        self.assertEqual(counts['delivery_aborted_count'], 1)
        self.assertEqual(run.reason, 'AUTHORIZATION_INVALID')

    def test_drift_failure_keeps_terminal_invariants(self):
        fixture = DriftingFixture('documents')
        run, _, _ = bound('documents', fixture=fixture)
        run.start()
        run.submit_id(ALLOW)
        for _ in range(3):
            run.step()
        fixture.fingerprint_drift = True
        run.step()
        run.finalize()
        counters = run.reviewed_counts()
        self.assertEqual(counters['delivery_consumed_count']
                         + counters['delivery_aborted_count'],
                         counters['dispatch_accepted_count'])
        self.assertEqual(counters['fixture_started_count'], 0)
        self.assertEqual(run.check_invariants(), [])

    def test_drift_does_not_produce_security_conclusion(self):
        fixture = DriftingFixture('documents')
        run, _, _ = bound('documents', fixture=fixture)
        run.start()
        run.submit_id(ALLOW)
        for _ in range(3):
            run.step()
        fixture.fingerprint_drift = True
        for _ in range(4):
            run.step()
        report = run.finalize()
        rows = {row['check_id']: row for row in report['checks']}
        row = rows[ALLOW]
        self.assertEqual(row['simulated_conclusion'], 'INCONCLUSIVE')
        self.assertNotIn(row['assertion'],
                         ('AUTHORIZED_CONTENT', 'REFUSAL_WITH_CONTROL',
                          'CONFIRMED_OVERDENIAL', 'CONFIRMED_DISCLOSURE'))
        self.assertFalse(row['processed'])
        verdicts = [r['simulated_conclusion'] for r in report['checks']]
        self.assertNotIn('PASS', verdicts)
        self.assertNotIn('FAIL', verdicts)

"""Offline-only tests for the independent V2 evidence verifier.

Every counterexample is built from a real, freshly produced synthetic evidence
directory; the expected verdicts are written here by hand and are never produced
by the module under test.  Re-sealing a report hash inside a test only proves that
the checks are about internal consistency, not that the bytes came from a trusted
source.
"""
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path

from p3_core.evidence import JsonlEvidence
from p3_core.http import reviewed_evidence
from p3_core.http.audit import BoundedEvidence
from p3_core.http.catalog_fixture import CatalogFixture
from p3_core.http.reviewed_contract import _bind_reviewed_contract
from p3_core.http.reviewed_runtime import COUNTER_KEYS, ReviewedOfflineRun
from p3_core.http.reviewed_snapshot import build_snapshot
from p3_core.offline_summary import summarize

try:
    from tests.test_catalog_fixture import make_contract_document, reviewed_inputs
except Exception:  # pragma: no cover - discovery imports modules as top level
    from test_catalog_fixture import make_contract_document, reviewed_inputs

ROOT = Path(__file__).resolve().parents[1]
V1_EVIDENCE = ROOT / 'evidence/course_ch03/eval_20261028_02/artifacts/run_ce4b0027ae024f05a72d81173c9f05e2'

DOCUMENTS = ['CAT-C-DOC-A-READER', 'CAT-N-DOC-B-READER', 'CAT-C-DOC-B-OWNER',
             'CAT-N-DOC-A-ANON']
DIRECTORIES = ['CAT-C-DIR-A-VIEWER', 'CAT-N-DIR-B-VIEWER', 'CAT-C-DIR-B-OWNER']


def _hash(blob):
    return hashlib.sha256(blob).hexdigest()


class Harness(unittest.TestCase):
    """Builds real V2 evidence, then lets a test rewrite a sealed copy."""

    def setUp(self):
        self._temp = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp.cleanup)
        self.root = Path(self._temp.name)

    def build(self, scenario='documents', shape='complete'):
        fixture = CatalogFixture(scenario)
        document = make_contract_document(scenario, fixture)
        binding, review, registry = reviewed_inputs(document, fixture.instance_id())
        snapshot = build_snapshot(
            _bind_reviewed_contract(review, registry=registry, now=10, **binding),
            fixture)
        directory = self.root
        run = ReviewedOfflineRun(snapshot, fixture,
                                 evidence=BoundedEvidence(JsonlEvidence(directory)),
                                 credentials=fixture.credentials())
        run.start()
        ids = DOCUMENTS if scenario == 'documents' else DIRECTORIES
        if shape == 'complete':
            for check_id in ids:
                run.submit_id(check_id)
            for _ in range(40):
                run.step()
        else:
            run.submit_id(ids[0])
            if shape == 'prepared_revoke':
                run.step(); run.step(); run.revoke(); run.step()
            elif shape == 'accepted_revoke':
                for _ in range(3):
                    run.step()
                run.revoke(); run.step()
            else:
                raise ValueError(shape)
        report = run.finalize()
        return directory / report['run_id'], report

    def load(self, directory):
        report = json.loads((directory / 'report.json').read_text(encoding='utf-8'))
        manifest = json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))
        events = [json.loads(line) for line in
                  (directory / 'events.jsonl').read_text(encoding='utf-8').splitlines()]
        return report, manifest, events

    def write(self, directory, report, events, *, reseal=True, audit_gap=None,
              evidence_complete=None):
        for index, event in enumerate(events, 1):
            event['sequence'] = index
        text = '\n'.join(json.dumps(event, sort_keys=True, ensure_ascii=False)
                         for event in events) + '\n'
        blob = text.encode('utf-8')
        (directory / 'events.jsonl').write_bytes(blob)
        (directory / 'report.json').write_text(
            json.dumps(report, sort_keys=True, ensure_ascii=False), encoding='utf-8')
        canonical = json.dumps(report, sort_keys=True, ensure_ascii=False,
                               allow_nan=False).encode('utf-8')
        manifest = dict(
            run_id=report['run_id'], provenance=report['provenance'],
            counts=report['counts'],
            audit_gap=report['audit_gap'] if audit_gap is None else audit_gap,
            evidence_complete=(report.get('evidence_complete')
                               if evidence_complete is None else evidence_complete),
            events_bytes=len(blob),
            events_sha256=_hash(blob),
            report_sha256=_hash(canonical) if reseal else '0' * 64)
        (directory / 'manifest.json').write_text(
            json.dumps(manifest, sort_keys=True, ensure_ascii=False), encoding='utf-8')

    def verify(self, directory):
        return reviewed_evidence.verify(directory)


class ValidEvidenceTests(Harness):
    def test_complete_s1_evidence_is_consistent(self):
        directory, report = self.build('documents')
        result = self.verify(directory)
        self.assertTrue(result['consistent'])
        self.assertEqual(result['gaps'], [])
        self.assertEqual(result['violations'], [])
        self.assertEqual(result['counts_replayed']['dispatch_accepted_count'], 4)
        self.assertEqual(result['counts_replayed']['fixture_handled_count'], 4)
        self.assertEqual(result['counts_replayed'], report['reviewed_counts'])
        self.assertFalse(result['approval_verified'])
        self.assertFalse(result['source_authenticated'])
        self.assertFalse(result['runtime_authorisation_verified'])

    def test_complete_s2_evidence_is_consistent(self):
        directory, report = self.build('directories')
        result = self.verify(directory)
        self.assertTrue(result['consistent'])
        self.assertEqual(result['counts_replayed']['dispatch_accepted_count'], 3)
        self.assertEqual(result['counts_replayed'], report['reviewed_counts'])

    def test_stopped_evidence_is_consistent(self):
        for shape in ('prepared_revoke', 'accepted_revoke'):
            with self.subTest(shape=shape):
                directory, report = self.build('documents', shape=shape)
                result = self.verify(directory)
                self.assertTrue(result['consistent'], (result['gaps'], result['violations']))
                self.assertEqual(result['axes']['delivery_association'], 'CONSISTENT')

    def test_counter_names_match_runtime(self):
        self.assertEqual(reviewed_evidence.COUNTERS, COUNTER_KEYS)

    def test_verifier_does_not_import_the_runner(self):
        source = Path(reviewed_evidence.__file__).read_text(encoding='utf-8')
        code = source.split('"""', 2)[-1]          # ignore the module docstring
        imports = ' '.join(line.strip() for line in code.splitlines()
                           if line.strip().startswith(('from ', 'import ')))
        for forbidden in ('reviewed_runtime', 'ReviewedOfflineRun', 'fixture',
                          'handle', 'socket', 'urllib', 'http.client'):
            self.assertNotIn(forbidden, imports)

    def test_unverifiable_items_are_declared(self):
        directory, _ = self.build()
        items = {entry['item'] for entry in self.verify(directory)['unverifiable']}
        self.assertTrue(any('contract_digest' in item for item in items))
        self.assertTrue(any('fixture_content_sha256' in item for item in items))
        self.assertTrue(any('budget' in item for item in items))


class CounterTamperTests(Harness):
    def test_tampered_reviewed_counts_is_detected(self):
        directory, report = self.build()
        report['reviewed_counts']['dispatch_accepted_count'] += 1
        _, _, events = self.load(directory)
        self.write(directory, report, events)
        result = self.verify(directory)
        self.assertEqual(result['axes']['counter_consistency'], 'MISMATCH')
        self.assertIn('dispatch_accepted_count', result['counts_mismatch'])
        self.assertFalse(result['consistent'])

    def test_tampered_event_counters_are_detected(self):
        directory, report = self.build()
        _, _, events = self.load(directory)
        events[-1]['counts']['model_request_count'] += 1
        self.write(directory, report, events)
        result = self.verify(directory)
        self.assertIn('EVENT_COUNTS_FINAL_MISMATCH', result['violations'])
        self.assertFalse(result['consistent'])

    def test_result_counts_block_must_match_replay(self):
        directory, report = self.build()
        report['counts']['attempt_count'] += 1
        _, _, events = self.load(directory)
        self.write(directory, report, events)
        result = self.verify(directory)
        self.assertIn('RESULT_COUNTS_INCONSISTENT', result['gaps'])
        self.assertFalse(result['consistent'])


class DeliveryTamperTests(Harness):
    def test_deleted_dispatch_accepted_is_detected(self):
        directory, report = self.build()
        _, _, events = self.load(directory)
        kept = [event for event in events if event['kind'] != 'reviewed_dispatch_accepted']
        self.write(directory, report, kept)
        result = self.verify(directory)
        self.assertIn('DELIVERY_WITHOUT_ACCEPT', result['violations'])
        self.assertEqual(result['counts_replayed']['dispatch_accepted_count'], 0)
        self.assertFalse(result['consistent'])

    def test_duplicate_delivery_consumed_is_detected(self):
        directory, report = self.build()
        _, _, events = self.load(directory)
        consumed = [event for event in events if event['kind'] == 'reviewed_delivery_consumed'][0]
        events.insert(events.index(consumed) + 1, dict(consumed))
        self.write(directory, report, events)
        result = self.verify(directory)
        self.assertIn('CONSUMED_TWICE', result['violations'])
        # S1 has four deliveries; the duplicated event makes five.
        self.assertEqual(result['counts_replayed']['delivery_consumed_count'], 5)
        self.assertEqual(result['counts_mismatch']['delivery_consumed_count'],
                         {'replayed': 5, 'reported': 4})
        self.assertFalse(result['consistent'])

    def test_duplicate_dispatch_cancelled_is_detected(self):
        directory, report = self.build(shape='prepared_revoke')
        _, _, events = self.load(directory)
        cancelled = [event for event in events
                     if event['kind'] == 'reviewed_dispatch_cancelled'][0]
        events.insert(events.index(cancelled) + 1, dict(cancelled))
        report['reviewed_counts']['dispatch_cancelled_count'] = 2   # the old double count
        self.write(directory, report, events)
        result = self.verify(directory)
        self.assertIn('CANCEL_REPEATED', result['violations'])
        # One slot cancelled twice must replay as one cancellation.
        self.assertEqual(result['counts_replayed']['dispatch_cancelled_count'], 1)
        self.assertEqual(result['counts_mismatch']['dispatch_cancelled_count'],
                         {'replayed': 1, 'reported': 2})
        self.assertFalse(result['consistent'])

    def test_accepted_without_terminal_is_detected(self):
        directory, report = self.build()
        _, _, events = self.load(directory)
        kept = [event for event in events if event['kind'] != 'reviewed_delivery_consumed']
        self.write(directory, report, kept)
        result = self.verify(directory)
        self.assertIn('UNTERMINATED_DELIVERY', result['violations'])
        self.assertFalse(result['consistent'])

    def test_fixture_after_abort_is_detected(self):
        directory, report = self.build(shape='accepted_revoke')
        _, _, events = self.load(directory)
        aborted = [event for event in events
                   if event['kind'] == 'reviewed_delivery_aborted'][0]
        started = dict(aborted, kind='reviewed_fixture_started')
        started.pop('revoke_seq', None)
        started.pop('reason', None)
        started['dispatch_seq'] = aborted['dispatch_seq']
        events.append(started)
        self.write(directory, report, events)
        result = self.verify(directory)
        self.assertIn('FIXTURE_STARTED_AFTER_ABORT', result['violations'])
        self.assertFalse(result['consistent'])

    def test_handled_without_started_is_detected(self):
        directory, report = self.build()
        _, _, events = self.load(directory)
        kept = [event for event in events if event['kind'] != 'reviewed_fixture_started']
        self.write(directory, report, kept)
        result = self.verify(directory)
        self.assertIn('HANDLED_WITHOUT_STARTED', result['violations'])
        self.assertFalse(result['consistent'])

    def test_wrong_dispatch_seq_is_detected(self):
        directory, report = self.build()
        _, _, events = self.load(directory)
        consumed = [event for event in events if event['kind'] == 'reviewed_delivery_consumed'][0]
        consumed['dispatch_seq'] = 999
        self.write(directory, report, events)
        result = self.verify(directory)
        self.assertIn('DELIVERY_SEQ_MISMATCH', result['violations'])
        self.assertFalse(result['consistent'])

    def test_revoke_order_conflict_is_detected(self):
        directory, report = self.build(shape='accepted_revoke')
        # Keep report and event consistent with each other, but claim a revocation
        # gate sequence lower than the dispatch it must follow.
        report['revoke_sequence'] = 0
        _, _, events = self.load(directory)
        for event in events:
            if event.get('revoke_seq') is not None:
                event['revoke_seq'] = 0
        self.write(directory, report, events)
        result = self.verify(directory)
        self.assertIn('DISPATCH_AFTER_REVOKE', result['violations'])
        self.assertFalse(result['consistent'])

    def test_unknown_event_kind_breaks_completeness(self):
        directory, report = self.build()
        _, _, events = self.load(directory)
        events.append(dict(mode=report['mode'], provenance=report['provenance'],
                           run_id=report['run_id'], evidence_id='evidence_' + '0' * 32,
                           sequence=len(events) + 1, kind='reviewed_unknown',
                           counts=report['counts']))
        self.write(directory, report, events)
        result = self.verify(directory)
        self.assertIn('UNKNOWN_EVENT_KIND', result['gaps'])
        self.assertEqual(result['axes']['evidence_completeness'], 'INCOMPLETE')
        self.assertFalse(result['consistent'])


class IntegrityTamperTests(Harness):
    def test_audit_hash_mismatch_is_detected(self):
        directory, report = self.build()
        _, _, events = self.load(directory)
        self.write(directory, report, events, reseal=False)
        result = self.verify(directory)
        self.assertEqual(result['axes']['file_integrity'], 'INCOMPLETE_OR_INVALID')
        self.assertFalse(result['consistent'])

    def test_event_bytes_tamper_without_reseal_is_detected(self):
        directory, report = self.build()
        blob = (directory / 'events.jsonl').read_bytes().replace(b'reviewed_prepared',
                                                                 b'reviewed_preparex')
        (directory / 'events.jsonl').write_bytes(blob)
        result = self.verify(directory)
        self.assertEqual(result['axes']['file_integrity'], 'INCOMPLETE_OR_INVALID')
        self.assertFalse(result['consistent'])

    def test_audit_gap_true_but_completed_is_detected(self):
        directory, report = self.build()
        _, _, events = self.load(directory)
        self.write(directory, report, events, audit_gap=True, evidence_complete=False)
        result = self.verify(directory)
        self.assertIn('AUDIT_GAP', result['gaps'])
        self.assertEqual(result['axes']['evidence_completeness'], 'INCOMPLETE')
        self.assertFalse(result['consistent'])

    def test_unpersisted_event_kinds_is_incomplete(self):
        directory, report = self.build()
        report['unpersisted_event_kinds'] = ['reviewed_delivery_consumed']
        _, _, events = self.load(directory)
        self.write(directory, report, events)
        result = self.verify(directory)
        self.assertIn('UNPERSISTED_EVENTS', result['gaps'])
        self.assertFalse(result['consistent'])

    def test_sequence_gap_is_incomplete(self):
        directory, report = self.build()
        _, _, events = self.load(directory)
        events[2]['sequence'] = 99
        text = '\n'.join(json.dumps(event, sort_keys=True, ensure_ascii=False)
                         for event in events) + '\n'
        blob = text.encode('utf-8')
        (directory / 'events.jsonl').write_bytes(blob)
        manifest = json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))
        manifest['events_bytes'] = len(blob)
        manifest['events_sha256'] = _hash(blob)
        (directory / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
        result = self.verify(directory)
        self.assertIn('EVENT_SEQUENCE_GAP', result['gaps'])
        self.assertFalse(result['consistent'])

    def test_digest_tamper_is_declared_unverifiable(self):
        for field in ('contract_digest', 'fixture_content_sha256'):
            with self.subTest(field=field):
                directory, report = self.build()
                report[field] = 'a' * 64
                _, _, events = self.load(directory)
                self.write(directory, report, events)
                result = self.verify(directory)
                # No persisted event binds these digests, so an honest verifier
                # can only declare the item unverifiable, never "verified".
                self.assertTrue(result['consistent'])
                self.assertTrue(any(field.split('_')[0] in entry['item']
                                    for entry in result['unverifiable']))
                self.assertFalse(result['source_authenticated'])

    def test_non_v2_report_is_not_checked(self):
        directory, report = self.build()
        report['mode'] = 'http-local-simulation'
        _, _, events = self.load(directory)
        self.write(directory, report, events)
        result = self.verify(directory)
        self.assertIn('NOT_A_REVIEWED_V2_RUN', result['gaps'])
        self.assertFalse(result['consistent'])

    def test_missing_artifact_is_not_checkable(self):
        directory, _ = self.build()
        (directory / 'events.jsonl').unlink()
        result = self.verify(directory)
        self.assertEqual(result['axes']['file_integrity'], 'INCOMPLETE_OR_INVALID')
        self.assertEqual(result['axes']['counter_consistency'], 'NOT_CHECKABLE')
        self.assertFalse(result['consistent'])


class StrictOrderingTests(Harness):
    """MAJOR-1/MAJOR-2: the delivery chain and its slot linkage are ordered."""

    def test_fixture_started_before_consumed_is_detected(self):
        directory, report = self.build()
        _, _, events = self.load(directory)
        consumed_index = next(i for i, event in enumerate(events)
                              if event['kind'] == 'reviewed_delivery_consumed')
        action = events[consumed_index]['action_id']
        started_index = next(i for i, event in enumerate(events)
                             if event['kind'] == 'reviewed_fixture_started'
                             and event['action_id'] == action)
        started = events.pop(started_index)
        events.insert(consumed_index, started)
        self.write(directory, report, events)
        result = self.verify(directory)
        self.assertIn('FIXTURE_STARTED_BEFORE_CONSUMED', result['violations'])
        self.assertIn('DELIVERY_AFTER_FIXTURE_STARTED', result['violations'])
        self.assertFalse(result['consistent'])

    def test_fixture_started_twice_is_detected(self):
        directory, report = self.build()
        _, _, events = self.load(directory)
        started = next(event for event in events
                       if event['kind'] == 'reviewed_fixture_started')
        events.insert(events.index(started) + 1, dict(started))
        self.write(directory, report, events)
        result = self.verify(directory)
        self.assertIn('FIXTURE_STARTED_TWICE', result['violations'])
        self.assertFalse(result['consistent'])

    def test_accepted_slot_mismatch_is_detected(self):
        directory, report = self.build()
        _, _, events = self.load(directory)
        accepted = next(event for event in events
                        if event['kind'] == 'reviewed_dispatch_accepted')
        other = next(event['slot_id'] for event in events
                     if event['kind'] == 'reviewed_proposal_registered'
                     and event['slot_id'] != accepted['slot_id'])
        accepted['slot_id'] = other
        self.write(directory, report, events)
        result = self.verify(directory)
        self.assertIn('ACCEPT_SLOT_MISMATCH', result['violations'])
        self.assertFalse(result['consistent'])

    def test_slot_accepted_twice_is_detected(self):
        directory, report = self.build()
        _, _, events = self.load(directory)
        accepted = next(event for event in events
                        if event['kind'] == 'reviewed_dispatch_accepted')
        events.insert(events.index(accepted) + 1, dict(accepted))
        self.write(directory, report, events)
        result = self.verify(directory)
        self.assertIn('SLOT_ACCEPTED_TWICE', result['violations'])
        self.assertFalse(result['consistent'])


class RevokeBindingTests(Harness):
    """MAJOR-3: the reported revoke sequence must be proven by events."""

    def test_cleared_revoke_sequence_is_detected(self):
        directory, report = self.build(shape='accepted_revoke')
        self.assertIsNotNone(report['revoke_sequence'])
        report['revoke_sequence'] = None
        _, _, events = self.load(directory)
        self.write(directory, report, events)
        result = self.verify(directory)
        self.assertIn('REVOKE_SEQUENCE_MISSING', result['violations'])
        self.assertFalse(result['consistent'])

    def test_tampered_event_revoke_seq_is_detected(self):
        directory, report = self.build(shape='accepted_revoke')
        _, _, events = self.load(directory)
        aborted = next(event for event in events
                       if event['kind'] == 'reviewed_delivery_aborted')
        aborted['revoke_seq'] = aborted['revoke_seq'] + 5
        self.write(directory, report, events)
        result = self.verify(directory)
        self.assertIn('REVOKE_SEQUENCE_MISMATCH', result['violations'])
        self.assertFalse(result['consistent'])

    def test_conflicting_revoke_sequences_are_detected(self):
        directory, report = self.build(shape='accepted_revoke')
        _, _, events = self.load(directory)
        aborted = next(event for event in events
                       if event['kind'] == 'reviewed_delivery_aborted')
        conflicting = dict(mode=report['mode'], provenance=report['provenance'],
                           run_id=report['run_id'],
                           evidence_id='evidence_' + '1' * 32,
                           sequence=len(events) + 1,
                           kind='reviewed_revoked_during_delivery',
                           counts=report['counts'],
                           action_id=aborted['action_id'],
                           dispatch_seq=aborted['dispatch_seq'],
                           revoke_seq=aborted['revoke_seq'] + 4)
        events.append(conflicting)
        self.write(directory, report, events)
        result = self.verify(directory)
        self.assertIn('REVOKE_SEQUENCE_CONFLICT', result['violations'])
        self.assertFalse(result['consistent'])

    def test_prepared_then_revoke_is_not_misjudged(self):
        directory, report = self.build(shape='prepared_revoke')
        result = self.verify(directory)
        self.assertIsNotNone(report['revoke_sequence'])
        self.assertEqual(result['violations'], [])
        self.assertTrue(result['consistent'])
        self.assertTrue(any('revoke sequence binding' in entry['item']
                            for entry in result['unverifiable']))


class CounterTransitionTests(Harness):
    """MAJOR-E: event counters must follow the per-kind transition table."""

    def test_event_counter_transition_tamper_is_detected(self):
        directory, report = self.build()
        _, _, events = self.load(directory)
        index = next(i for i, event in enumerate(events)
                     if event['kind'] == 'reviewed_authorization')
        # Remove the increment carried by the authorization event while keeping the
        # block monotone and the final counts identical to the report.
        events[index]['counts'] = dict(events[index - 1]['counts'])
        self.write(directory, report, events)
        self.assertEqual(events[-1]['counts'], report['counts'])
        result = self.verify(directory)
        self.assertIn('EVENT_COUNT_TRANSITION_MISMATCH', result['violations'])
        self.assertFalse(result['consistent'])

    def test_unrelated_event_must_not_change_counters(self):
        directory, report = self.build()
        _, _, events = self.load(directory)
        index = next(i for i, event in enumerate(events)
                     if event['kind'] == 'reviewed_fixture_handled')
        block = dict(events[index]['counts'])
        block['attempt_count'] = min(256, block['attempt_count'] + 1)
        events[index]['counts'] = block
        for later in events[index + 1:]:
            later['counts'] = dict(later['counts'], attempt_count=block['attempt_count'])
        report['counts'] = dict(report['counts'], attempt_count=block['attempt_count'])
        self.write(directory, report, events)
        result = self.verify(directory)
        self.assertIn('EVENT_COUNT_TRANSITION_MISMATCH', result['violations'])
        self.assertFalse(result['consistent'])

    def test_audit_gap_records_unverifiable_transitions(self):
        directory, report = self.build()
        report['audit_gap'] = True
        report['evidence_complete'] = False
        report['unpersisted_event_kinds'] = ['reviewed_delivery_consumed']
        _, _, events = self.load(directory)
        self.write(directory, report, events, audit_gap=True, evidence_complete=False)
        result = self.verify(directory)
        self.assertEqual(result['axes']['evidence_completeness'], 'INCOMPLETE')
        self.assertIn('UNPERSISTED_EVENTS', result['gaps'])
        self.assertNotIn('EVENT_COUNT_TRANSITION_MISMATCH', result['violations'])
        self.assertTrue(any('event counter transitions' in entry['item']
                            for entry in result['unverifiable']))
        self.assertFalse(result['consistent'])


class SummaryIntegrationTests(Harness):
    def test_v2_consistent_evidence_is_not_reported_complete(self):
        directory, _ = self.build()
        summary = summarize(directory)
        self.assertEqual(summary['status'], 'V2_EVIDENCE_CONSISTENT')
        self.assertFalse(summary['approval_verified'])
        self.assertFalse(summary['source_authenticated'])
        self.assertFalse(summary['reviewed_evidence']['runtime_authorisation_verified'])

    def test_v2_tampered_counts_is_inconsistent(self):
        directory, report = self.build()
        report['reviewed_counts']['fixture_handled_count'] += 1
        _, _, events = self.load(directory)
        self.write(directory, report, events)
        self.assertEqual(summarize(directory)['status'], 'V2_EVIDENCE_INCONSISTENT')

    def test_v2_audit_gap_is_insufficient(self):
        directory, report = self.build()
        _, _, events = self.load(directory)
        self.write(directory, report, events, audit_gap=True, evidence_complete=False)
        self.assertEqual(summarize(directory)['status'], 'INSUFFICIENT_EVIDENCE')

    def test_v2_mode_tamper_is_still_gated(self):
        directory, report = self.build()
        report['mode'] = 'http-local-simulation'
        _, _, events = self.load(directory)
        self.write(directory, report, events)
        self.assertNotEqual(summarize(directory)['status'], 'COMPLETE')

    def test_v1_summary_behaviour_is_unchanged(self):
        summary = summarize(V1_EVIDENCE)
        self.assertEqual(summary['status'], 'COMPLETE')
        self.assertEqual(summary['provenance'], 'NO_NETWORK_SIMULATION')
        self.assertEqual(summary['integrity']['integrity'], 'VERIFIED')
        self.assertFalse(summary['approval_verified'])
        self.assertNotIn('reviewed_evidence', summary)


if __name__ == '__main__':  # pragma: no cover
    unittest.main()

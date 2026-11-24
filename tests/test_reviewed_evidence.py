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

    def build(self, scenario='documents', shape='complete', budget=None, proposals=None):
        fixture = CatalogFixture(scenario)
        document = make_contract_document(scenario, fixture)
        if budget is not None:
            document['budget'].update(budget)
        binding, review, registry = reviewed_inputs(document, fixture.instance_id())
        snapshot = build_snapshot(
            _bind_reviewed_contract(review, registry=registry, now=10, **binding),
            fixture)
        directory = self.root
        run = ReviewedOfflineRun(snapshot, fixture,
                                 evidence=BoundedEvidence(JsonlEvidence(directory)),
                                 credentials=fixture.credentials())
        run.start()
        ids = proposals if proposals is not None else (
            DOCUMENTS if scenario == 'documents' else DIRECTORIES)
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
              evidence_complete=None, reseal_scope=False, legacy_scope=False):
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
        previous = json.loads((directory / 'manifest.json').read_bytes())
        for name in ('evidence_version', 'reviewed_scope_sha256', 'snapshot_id',
                     'contract_digest', 'fixture_content_sha256'):
            if name in previous:
                manifest[name] = previous[name]
        if legacy_scope:
            manifest.pop('evidence_version', None)
            manifest.pop('reviewed_scope_sha256', None)
        if reseal_scope:
            manifest['reviewed_scope_sha256'] = _hash(json.dumps(
                report['reviewed_scope'], sort_keys=True,
                separators=(',', ':'), allow_nan=False).encode('utf-8'))
            manifest['contract_digest'] = report['contract_digest']
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
        result = self.verify(directory)
        items = {entry['item'] for entry in result['unverifiable']}
        self.assertTrue(any('contract_digest' in item for item in items))
        self.assertTrue(any('fixture_content_sha256' in item for item in items))
        # 3B-2A evidence binds budget and candidates, so they are no longer listed
        # as unverifiable; only their external authority remains unproven.
        self.assertNotIn('authorised budget', items)
        self.assertNotIn('reviewed candidate universe', items)
        self.assertEqual(result['axes']['scope_binding_consistency'], 'CONSISTENT')


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

    def test_single_field_digest_tamper_is_detected(self):
        attacks = (
            ('contract_digest', 'a' * 64, 'SCOPE_CONTRACT_DIGEST_MISMATCH'),
            ('scope_digest', 'b' * 64, 'SCOPE_SCOPE_DIGEST_MISMATCH'),
            ('fixture_content_sha256', 'c' * 64,
             'SCOPE_FIXTURE_CONTENT_SHA256_MISMATCH'),
            ('fixture_instance_id', 'fixture_' + '1' * 32,
             'SCOPE_FIXTURE_INSTANCE_ID_MISMATCH'),
            ('snapshot_id', 'snapshot_' + '0' * 32, 'SCOPE_SNAPSHOT_ID_MISMATCH'),
        )
        for field, value, code in attacks:
            with self.subTest(field=field):
                directory, report = self.build()
                report[field] = value
                _, _, events = self.load(directory)
                self.write(directory, report, events)
                result = self.verify(directory)
                self.assertIn(code, result['violations'])
                self.assertEqual(result['axes']['scope_binding_consistency'],
                                 'MISMATCH')
                self.assertFalse(result['consistent'])

    def test_consistent_digest_rewrite_stays_unverifiable(self):
        directory, report = self.build()
        report['contract_digest'] = 'a' * 64
        report['reviewed_scope']['contract_digest'] = 'a' * 64
        _, _, events = self.load(directory)
        for event in events:
            if event['kind'] == 'reviewed_scope_binding':
                event['contract_digest'] = 'a' * 64
        self.write(directory, report, events, reseal_scope=True)
        result = self.verify(directory)
        # Internally consistent, but no external authority attests the digest.
        self.assertTrue(result['consistent'])
        self.assertTrue(any('contract_digest' in entry['item']
                            for entry in result['unverifiable']))
        self.assertFalse(result['source_authenticated'])
        self.assertFalse(result['runtime_authorisation_verified'])

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


class ScopeBindingTests(Harness):
    """3B-2A: reviewed budget, candidate universe and digest set are bound."""

    def test_s1_scope_binding_is_consistent(self):
        directory, report = self.build('documents')
        result = self.verify(directory)
        scope = report['reviewed_scope']
        self.assertEqual(result['axes']['scope_binding_consistency'], 'CONSISTENT')
        self.assertTrue(result['consistent'])
        self.assertEqual(scope['evidence_version'], 'p3-reviewed-evidence-v2')
        self.assertEqual(len(scope['candidates']), 4)
        self.assertEqual(scope['candidates'], sorted(scope['candidates']))
        self.assertEqual(scope['candidates'], ['CAT-C-DOC-A-READER', 'CAT-C-DOC-B-OWNER',
                                               'CAT-N-DOC-A-ANON', 'CAT-N-DOC-B-READER'])

    def test_s2_scope_binding_is_consistent(self):
        directory, report = self.build('directories',
                                       budget=dict(max_checks=3))
        result = self.verify(directory)
        self.assertEqual(result['axes']['scope_binding_consistency'], 'CONSISTENT')
        self.assertEqual(len(report['reviewed_scope']['candidates']), 3)

    def test_budget_smaller_than_candidates(self):
        directory, report = self.build('documents', budget=dict(max_checks=2))
        result = self.verify(directory)
        scope = report['reviewed_scope']
        self.assertEqual(scope['max_checks'], 2)
        self.assertEqual(len(scope['candidates']), 4)          # universe untouched
        self.assertEqual(len(report['checks']), 2)             # only two submitted
        self.assertEqual(report['counts']['plan_count'], 2)
        self.assertTrue(result['consistent'])
        self.assertEqual(result['axes']['scope_binding_consistency'], 'CONSISTENT')

    def test_budget_equal_to_candidates(self):
        directory, report = self.build('documents', budget=dict(max_checks=4))
        result = self.verify(directory)
        self.assertEqual(len(report['checks']), 4)
        self.assertEqual(report['reviewed_scope']['max_checks'], 4)
        self.assertTrue(result['consistent'])

    def test_budget_larger_than_candidates(self):
        directory, report = self.build('documents', budget=dict(max_checks=8))
        result = self.verify(directory)
        self.assertEqual(len(report['checks']), 4)
        self.assertEqual(report['reviewed_scope']['max_checks'], 8)
        self.assertTrue(result['consistent'])
        # The budget must not be inferred from the candidate count.
        self.assertNotEqual(report['reviewed_scope']['max_checks'],
                            len(report['reviewed_scope']['candidates']))

    def test_report_max_checks_tamper_is_detected(self):
        directory, report = self.build()
        report['reviewed_scope']['max_checks'] += 1
        _, _, events = self.load(directory)
        self.write(directory, report, events)
        result = self.verify(directory)
        self.assertIn('SCOPE_FIELD_MISMATCH', result['violations'])
        self.assertFalse(result['consistent'])

    def test_report_budget_version_tamper_is_detected(self):
        directory, report = self.build()
        report['reviewed_scope']['budget_version'] = 'tampered_version'
        _, _, events = self.load(directory)
        self.write(directory, report, events)
        result = self.verify(directory)
        self.assertIn('SCOPE_FIELD_MISMATCH', result['violations'])
        self.assertFalse(result['consistent'])

    def test_event_budget_tamper_is_detected(self):
        directory, report = self.build()
        _, _, events = self.load(directory)
        event = next(event for event in events
                     if event['kind'] == 'reviewed_scope_binding')
        event['max_checks'] = 99
        self.write(directory, report, events)
        result = self.verify(directory)
        self.assertIn('SCOPE_FIELD_MISMATCH', result['violations'])
        self.assertFalse(result['consistent'])

    def test_removed_candidate_is_detected(self):
        directory, report = self.build()
        report['reviewed_scope']['candidates'] = report['reviewed_scope']['candidates'][1:]
        _, _, events = self.load(directory)
        self.write(directory, report, events)
        result = self.verify(directory)
        self.assertIn('SCOPE_FIELD_MISMATCH', result['violations'])
        self.assertIn('CANDIDATE_NOT_REVIEWED', result['violations'])
        self.assertFalse(result['consistent'])

    def test_added_unknown_candidate_is_detected(self):
        directory, report = self.build()
        report['reviewed_scope']['candidates'] = sorted(
            report['reviewed_scope']['candidates'] + ['ZZZ-UNREVIEWED'])
        _, _, events = self.load(directory)
        self.write(directory, report, events)
        result = self.verify(directory)
        self.assertIn('SCOPE_FIELD_MISMATCH', result['violations'])
        self.assertFalse(result['consistent'])

    def test_duplicate_candidate_is_detected(self):
        directory, report = self.build()
        candidates = report['reviewed_scope']['candidates']
        duplicated = sorted(candidates + [candidates[0]])
        report['reviewed_scope']['candidates'] = duplicated
        _, _, events = self.load(directory)
        for event in events:
            if event['kind'] == 'reviewed_scope_binding':
                event['candidates'] = list(duplicated)
        self.write(directory, report, events)
        result = self.verify(directory)
        self.assertIn('CANDIDATE_DUPLICATE', result['violations'])
        self.assertFalse(result['consistent'])

    def test_candidate_order_must_be_deterministic(self):
        directory, report = self.build()
        asserters = report['reviewed_scope']['candidates']
        reversed_candidates = list(reversed(asserters))
        report['reviewed_scope']['candidates'] = reversed_candidates
        _, _, events = self.load(directory)
        for event in events:
            if event['kind'] == 'reviewed_scope_binding':
                event['candidates'] = list(reversed_candidates)
        self.write(directory, report, events)
        result = self.verify(directory)
        self.assertIn('CANDIDATE_ORDER', result['violations'])
        self.assertFalse(result['consistent'])

    def test_row_outside_reviewed_universe_is_detected(self):
        directory, report = self.build()
        row = dict(report['checks'][0])
        row['check_id'] = 'ZZZ-UNREVIEWED'
        row['slot_id'] = 'slot_' + '9' * 32
        report['checks'].append(row)
        _, _, events = self.load(directory)
        self.write(directory, report, events)
        result = self.verify(directory)
        self.assertIn('CANDIDATE_NOT_REVIEWED', result['violations'])
        self.assertFalse(result['consistent'])

    def test_budget_exceeded_by_rows_is_detected(self):
        directory, report = self.build('documents', budget=dict(max_checks=4))
        report['reviewed_scope']['max_checks'] = 2
        _, _, events = self.load(directory)
        for event in events:
            if event['kind'] == 'reviewed_scope_binding':
                event['max_checks'] = 2
        self.write(directory, report, events)
        result = self.verify(directory)
        self.assertIn('BUDGET_EXCEEDED', result['violations'])
        self.assertFalse(result['consistent'])

    def test_missing_scope_event_is_detected(self):
        directory, report = self.build()
        _, _, events = self.load(directory)
        kept = [event for event in events if event['kind'] != 'reviewed_scope_binding']
        self.write(directory, report, kept)
        result = self.verify(directory)
        self.assertIn('SCOPE_BINDING_MISSING', result['violations'])
        self.assertFalse(result['consistent'])

    def test_duplicate_scope_event_is_detected(self):
        directory, report = self.build()
        _, _, events = self.load(directory)
        event = next(event for event in events
                     if event['kind'] == 'reviewed_scope_binding')
        events.append(dict(event))
        self.write(directory, report, events)
        result = self.verify(directory)
        self.assertIn('SCOPE_BINDING_REPEATED', result['violations'])
        self.assertFalse(result['consistent'])

    def test_evidence_version_mismatch_is_detected(self):
        directory, report = self.build()
        report['evidence_version'] = 'p3-reviewed-evidence-v3'
        _, _, events = self.load(directory)
        self.write(directory, report, events)
        result = self.verify(directory)
        self.assertIn('EVIDENCE_VERSION_MISMATCH', result['violations'])
        self.assertFalse(result['consistent'])

    def test_old_format_evidence_is_not_checkable(self):
        directory, report = self.build()
        report.pop('evidence_version')
        report.pop('reviewed_scope')
        _, _, events = self.load(directory)
        kept = [event for event in events if event['kind'] != 'reviewed_scope_binding']
        self.write(directory, report, kept, legacy_scope=True)
        result = self.verify(directory)
        self.assertEqual(result['axes']['scope_binding_consistency'], 'NOT_CHECKABLE')
        self.assertIn('SCOPE_BINDING_ABSENT', result['scope_notes'])
        # Old evidence keeps its old meaning: six axes still pass.
        self.assertTrue(result['consistent'])
        items = {entry['item'] for entry in result['unverifiable']}
        self.assertIn('authorised budget', items)
        self.assertIn('reviewed candidate universe', items)

    def test_audit_gap_with_scope_does_not_pass(self):
        directory, report = self.build()
        report['audit_gap'] = True
        report['evidence_complete'] = False
        report['unpersisted_event_kinds'] = ['reviewed_delivery_consumed']
        _, _, events = self.load(directory)
        self.write(directory, report, events, audit_gap=True, evidence_complete=False)
        result = self.verify(directory)
        self.assertEqual(result['axes']['scope_binding_consistency'], 'CONSISTENT')
        self.assertEqual(result['axes']['evidence_completeness'], 'INCOMPLETE')
        self.assertFalse(result['consistent'])
        self.assertNotIn('candidate_lifecycle', result)

    def test_identifiers_and_versions_in_report_match_started_scope(self):
        for field in ('contract_id', 'contract_version', 'fixture_id', 'fixture_version'):
            with self.subTest(field=field):
                directory, report = self.build()
                _, _, events = self.load(directory)
                report[field] = 'changed-v2'
                self.write(directory, report, events)
                result = self.verify(directory)
                self.assertIn('SCOPE_' + field.upper() + '_MISMATCH', result['violations'])
                self.assertFalse(result['consistent'])

    def test_budget_types_and_limits_match_the_contract(self):
        for key, value in (('budget_version', []), ('max_checks', True),
                           ('max_checks', 65), ('logical_timeout_seconds', True),
                           ('logical_timeout_seconds', 3601), ('concurrency', True),
                           ('concurrency', 1.0), ('concurrency', 2)):
            with self.subTest(key=key, value=value):
                directory, report = self.build()
                _, _, events = self.load(directory)
                report['reviewed_scope'][key] = value
                events[1][key] = value
                self.write(directory, report, events, reseal_scope=True)
                result = self.verify(directory)
                self.assertEqual(result['violations'], ['BUDGET_INVALID'])
                self.assertFalse(result['consistent'])

    def test_scope_seal_detects_joint_report_and_event_budget_change(self):
        directory, report = self.build()
        _, _, events = self.load(directory)
        self.assertNotEqual(report['reviewed_scope']['max_checks'], 7)
        report['reviewed_scope']['max_checks'] = events[1]['max_checks'] = 7
        self.write(directory, report, events)
        result = self.verify(directory)
        self.assertEqual(result['violations'], ['SCOPE_MANIFEST_HASH_MISMATCH'])
        self.assertFalse(result['consistent'])

    def test_scope_event_must_precede_first_proposal(self):
        directory, report = self.build()
        _, _, events = self.load(directory)
        binding, first_proposal = events[1:3]
        binding['counts'] = dict(first_proposal['counts'])
        events[1:3] = [first_proposal, binding]
        self.write(directory, report, events)
        result = self.verify(directory)
        self.assertEqual(result['violations'], ['SCOPE_BINDING_ORDER'])
        self.assertFalse(result['consistent'])

    def test_manifest_marker_prevents_partial_legacy_downgrade(self):
        directory, report = self.build()
        _, _, events = self.load(directory)
        del report['evidence_version'], report['reviewed_scope']
        self.write(directory, report, [e for e in events if e['kind'] != 'reviewed_scope_binding'])
        result = self.verify(directory)
        self.assertIn('SCOPE_BLOCK_MISSING', result['violations'])
        self.assertFalse(result['consistent'])

    def test_new_scope_requires_closed_field_set(self):
        for key, mode in (('concurrency', 'missing'), ('extra_field', 'extra')):
            with self.subTest(mode=mode):
                directory, report = self.build()
                _, _, events = self.load(directory)
                scope = report['reviewed_scope']
                if mode == 'missing':
                    del scope[key], events[1][key]
                else:
                    scope[key] = 'unexpected'
                self.write(directory, report, events, reseal_scope=True)
                result = self.verify(directory)
                self.assertIn('SCOPE_FIELDS_INVALID', result['violations'])
                self.assertFalse(result['consistent'])

    def test_unperformed_checklist_is_reconstructed(self):
        directory, report = self.build('documents', budget=dict(max_checks=2))
        _, _, events = self.load(directory)
        report['unperformed_approved_candidates'].pop()
        self.write(directory, report, events)
        result = self.verify(directory)
        self.assertEqual(result['violations'], ['CANDIDATE_UNPERFORMED_MISMATCH'])
        self.assertFalse(result['consistent'])

    def test_revoked_proposal_is_submitted_but_not_performed(self):
        directory, _ = self.build(shape='accepted_revoke')
        result = self.verify(directory)
        self.assertTrue(result['consistent'])
        lifecycle = result['candidate_lifecycle']
        for phase in ('submitted', 'authorized', 'prepared', 'dispatch_accepted'):
            self.assertEqual(lifecycle[phase], DOCUMENTS[:1])
        self.assertEqual(lifecycle['processed'], [])
        self.assertEqual(lifecycle['decided'], [])
        self.assertEqual(lifecycle['unperformed'], sorted(DOCUMENTS))

    def test_unknown_proposal_does_not_count_as_an_approved_candidate(self):
        unknown = 'NOT-REVIEWED'
        directory, report = self.build(proposals=[unknown, DOCUMENTS[0]])
        result = self.verify(directory)
        self.assertTrue(result['consistent'])
        self.assertEqual(report['checks'][0]['authorization'], 'DENY')
        self.assertIsNone(report['checks'][0]['check_id'])
        self.assertEqual(result['candidate_lifecycle']['submitted'], DOCUMENTS[:1])
        self.assertEqual(result['candidate_lifecycle']['decided'], DOCUMENTS[:1])
        _, _, events = self.load(directory)
        report['checks'][0]['simulated_conclusion'] = 'PASS'
        self.write(directory, report, events)
        result = self.verify(directory)
        self.assertEqual(result['violations'], ['UNREVIEWED_CANDIDATE_CONCLUSION'])
        self.assertNotIn('candidate_lifecycle', result)

    def test_report_cannot_relabel_row_as_another_reviewed_candidate(self):
        directory, report = self.build()
        _, _, events = self.load(directory)
        report['checks'][0]['check_id'] = DOCUMENTS[1]
        self.write(directory, report, events)
        result = self.verify(directory)
        self.assertEqual(result['violations'], ['CANDIDATE_ROW_MISMATCH'])
        self.assertFalse(result['consistent'])

    def test_two_contracts_share_one_verifier(self):
        for scenario, expected in (('documents', 4), ('directories', 3)):
            with self.subTest(scenario=scenario):
                directory, report = self.build(scenario)
                result = self.verify(directory)
                self.assertTrue(result['consistent'])
                self.assertEqual(len(report['reviewed_scope']['candidates']), expected)
        source = Path(reviewed_evidence.__file__).read_text(encoding='utf-8')
        self.assertNotIn('documents', source)
        self.assertNotIn('directories', source)


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

    def test_manifest_scope_marker_blocks_fallback_to_v1(self):
        directory, report = self.build()
        _, _, events = self.load(directory)
        report['mode'] = 'http-local-simulation'
        for marker in ('reviewed_counts', 'resource_fingerprint', 'evidence_complete',
                       'unpersisted_event_kinds', 'fixture_content_sha256',
                       'evidence_version', 'reviewed_scope'):
            del report[marker]
        for row in report['checks']:
            del row['dispatch_seq']
        for event in events:
            event['kind'] = 'unclassified'
        self.write(directory, report, events, evidence_complete=True)
        self.assertEqual(summarize(directory)['status'], 'INSUFFICIENT_EVIDENCE')

    def test_v1_summary_behaviour_is_unchanged(self):
        summary = summarize(V1_EVIDENCE)
        self.assertEqual(summary['status'], 'COMPLETE')
        self.assertEqual(summary['provenance'], 'NO_NETWORK_SIMULATION')
        self.assertEqual(summary['integrity']['integrity'], 'VERIFIED')
        self.assertFalse(summary['approval_verified'])
        self.assertNotIn('reviewed_evidence', summary)


if __name__ == '__main__':  # pragma: no cover
    unittest.main()

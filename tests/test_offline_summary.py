import contextlib
import io
from pathlib import Path
import socket
import tempfile
import unittest
from unittest.mock import patch
from p3_core.delivery import main
from p3_core.experiments import run_scenario
from p3_core.offline_summary import summarize, render


class OfflineSummaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in ('socket', 'create_connection', 'getaddrinfo', 'gethostbyname'):
            guard = patch.object(socket, name, side_effect=AssertionError('NETWORK_FORBIDDEN'))
            guard.start()
            self.addCleanup(guard.stop)

    def run_case(self, mode='good', fault=None):
        result = run_scenario(mode, output=self.root, fault=fault)
        return self.root / result['report']['run_id'], result

    def test_good_and_defects(self):
        for mode in ('good', 'auth', 'bola', 'rbac'):
            with self.subTest(mode=mode):
                path, original = self.run_case(mode)
                summary = summarize(path)
                self.assertEqual(summary['report'], original['report'])
                self.assertEqual(summary['status'], 'COMPLETE')
                self.assertIn('simulated_conclusion', render(summary))
                self.assertFalse(summary['approval_verified'])
                self.assertEqual(summary['report']['counts']['request_count'], 0)
                if mode != 'good':
                    self.assertIn('FAIL', [r['simulated_conclusion'] for r in summary['report']['checks']])

    def test_safety_stops_and_insufficient(self):
        for fault in ('malformed', 'truncated', 'timeout', 'audit', 'empty'):
            with self.subTest(fault=fault):
                path, _ = self.run_case(fault=fault)
                self.assertIn(summarize(path)['status'], ('SAFETY_STOP', 'INSUFFICIENT_EVIDENCE', 'NO_VALID_TESTS'))

    def test_missing_tampered_and_appended(self):
        for name in ('report.json', 'manifest.json', 'events.jsonl'):
            path, _ = self.run_case()
            (path/name).unlink()
            self.assertIsNone(summarize(path)['report'])
        for name in ('report.json', 'events.jsonl'):
            path, _ = self.run_case()
            with (path/name).open('ab') as stream:
                stream.write(b'{}')
            self.assertEqual(summarize(path)['status'], 'INSUFFICIENT_EVIDENCE')

    def test_no_valid_checks_and_unknown(self):
        path, _ = self.run_case()
        from p3_core.offline_summary import strict_json
        from p3_core.evaluator import read_snapshot
        blobs = read_snapshot(path)
        report = strict_json(blobs['report.json'])
        report['checks'] = []
        import json
        blobs['report.json'] = json.dumps(report).encode()
        with patch('p3_core.offline_summary.read_snapshot', return_value=blobs), patch(
                'p3_core.offline_summary.verify_run', return_value={'integrity':'VERIFIED','appended_bytes':0}):
            self.assertEqual(summarize(path)['status'], 'NO_VALID_TESTS')
        self.assertIn('unknown', render(dict(status='INSUFFICIENT_EVIDENCE', report=None,
                      evidence_directory=str(path), provenance='unknown', integrity='unknown')))

    def test_cli_and_read_only(self):
        path, _ = self.run_case()
        before = {p.name:p.read_bytes() for p in path.iterdir()}
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(['offline', '--run', str(path)]), 0)
            self.assertEqual(main(['offline', '--output', str(self.root), '--mode', 'bola']), 0)
        self.assertIn('PENDING_AUTHORIZATION', output.getvalue())
        self.assertEqual(before, {p.name:p.read_bytes() for p in path.iterdir()})

    def test_duplicate_manifest_and_events_rejected(self):
        for name in ('manifest.json', 'events.jsonl'):
            path,_=self.run_case()
            f=path/name
            f.write_bytes(f.read_bytes().replace(b'{',b'{"audit_gap":false,"audit_gap":false,',1))
            self.assertEqual(summarize(path)['status'],'INSUFFICIENT_EVIDENCE')

    def test_unsafe_output_before_runner(self):
        for value in ('https://example.invalid/x','//host/share','../escape'):
            with patch('p3_core.delivery.run_scenario',side_effect=AssertionError('NO_RUN')):
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(main(['offline','--output',value]),2)

    def test_size_and_text_escape(self):
        path,_=self.run_case()
        (path/'report.json').write_bytes(b' ' * 1048577)
        self.assertEqual(summarize(path)['status'],'INSUFFICIENT_EVIDENCE')
        text=render(dict(status='INSUFFICIENT_EVIDENCE',report=None,evidence_directory='x\\n\\u001b',provenance='unknown',integrity='unknown'))
        self.assertIn('COMPLETE: completed offline record',text)

    def test_read_command_never_runs_product(self):
        path,_=self.run_case()
        with patch('p3_core.delivery.run_scenario',side_effect=AssertionError('NO_RUN')):
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(['offline','--run',str(path)]),0)


class ReviewedSummaryTests(unittest.TestCase):
    """A V2 record must never be summarised on generic integrity alone."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in ('socket', 'create_connection', 'getaddrinfo', 'gethostbyname'):
            guard = patch.object(socket, name, side_effect=AssertionError('NETWORK_FORBIDDEN'))
            guard.start()
            self.addCleanup(guard.stop)

    def reviewed_case(self):
        from p3_core.evidence import JsonlEvidence
        from p3_core.http.audit import BoundedEvidence
        from p3_core.http.catalog_fixture import CatalogFixture
        from p3_core.http.reviewed_contract import _bind_reviewed_contract
        from p3_core.http.reviewed_runtime import ReviewedOfflineRun
        from p3_core.http.reviewed_snapshot import build_snapshot
        try:
            from tests.test_catalog_fixture import make_contract_document, reviewed_inputs
        except Exception:  # pragma: no cover
            from test_catalog_fixture import make_contract_document, reviewed_inputs
        fixture = CatalogFixture('documents')
        document = make_contract_document('documents', fixture)
        binding, review, registry = reviewed_inputs(document, fixture.instance_id())
        snapshot = build_snapshot(
            _bind_reviewed_contract(review, registry=registry, now=10, **binding), fixture)
        run = ReviewedOfflineRun(snapshot, fixture,
                                 evidence=BoundedEvidence(JsonlEvidence(self.root)),
                                 credentials=fixture.credentials())
        run.start()
        for check_id in ('CAT-C-DOC-A-READER', 'CAT-N-DOC-B-READER',
                         'CAT-C-DOC-B-OWNER', 'CAT-N-DOC-A-ANON'):
            run.submit_id(check_id)
        for _ in range(40):
            run.step()
        report = run.finalize()
        return self.root / report['run_id'], report

    def test_v2_is_not_reported_complete(self):
        path, report = self.reviewed_case()
        self.assertEqual(report['mode'], 'reviewed-offline-simulation')
        summary = summarize(path)
        self.assertNotEqual(summary['status'], 'COMPLETE')
        self.assertEqual(summary['status'], 'V2_EVIDENCE_CONSISTENT')
        self.assertFalse(summary['approval_verified'])
        self.assertFalse(summary['source_authenticated'])
        self.assertFalse(summary['reviewed_evidence']['runtime_authorisation_verified'])

    def test_v2_inconsistent_counts_is_flagged(self):
        import hashlib
        import json
        path, report = self.reviewed_case()
        report['reviewed_counts']['dispatch_accepted_count'] += 1
        canonical = json.dumps(report, sort_keys=True, ensure_ascii=False,
                               allow_nan=False).encode('utf-8')
        (path / 'report.json').write_text(
            json.dumps(report, sort_keys=True, ensure_ascii=False), encoding='utf-8')
        manifest = json.loads((path / 'manifest.json').read_text(encoding='utf-8'))
        manifest['report_sha256'] = hashlib.sha256(canonical).hexdigest()
        (path / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
        self.assertEqual(summarize(path)['status'], 'V2_EVIDENCE_INCONSISTENT')

    def test_v1_summary_has_no_reviewed_evidence_branch(self):
        result = run_scenario('good', output=self.root)
        path = self.root / result['report']['run_id']
        summary = summarize(path)
        self.assertEqual(summary['status'], 'COMPLETE')
        self.assertNotIn('reviewed_evidence', summary)

    def test_v2_double_field_removal_is_still_gated(self):
        """Removing mode *and* reviewed_counts must not turn V2 into V1 COMPLETE."""
        import hashlib
        import json
        path, report = self.reviewed_case()
        report['mode'] = 'http-local-simulation'
        report.pop('reviewed_counts')
        canonical = json.dumps(report, sort_keys=True, ensure_ascii=False,
                               allow_nan=False).encode('utf-8')
        (path / 'report.json').write_text(
            json.dumps(report, sort_keys=True, ensure_ascii=False), encoding='utf-8')
        manifest = json.loads((path / 'manifest.json').read_text(encoding='utf-8'))
        manifest['report_sha256'] = hashlib.sha256(canonical).hexdigest()
        (path / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
        summary = summarize(path)
        self.assertNotEqual(summary['status'], 'COMPLETE')
        self.assertEqual(summary['status'], 'INSUFFICIENT_EVIDENCE')

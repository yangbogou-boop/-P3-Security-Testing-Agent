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

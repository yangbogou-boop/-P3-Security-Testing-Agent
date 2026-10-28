"""Offline client artifact contract; corruption is confined to temporary copies."""
import hashlib
import json
import shutil
import socket
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from p3_core.coordination import check_sidecar
from p3_core.http.audit import BoundedEvidence, verify_run
from p3_core.trusted_host import OfflineHost


class HostEvidenceContractTests(unittest.TestCase):
    def setUp(self):
        for name in ('socket', 'create_connection', 'getaddrinfo',
                     'gethostbyname', 'gethostbyname_ex'):
            guard = patch.object(socket, name, side_effect=AssertionError('NETWORK_FORBIDDEN'))
            guard.start()
            self.addCleanup(guard.stop)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)

    def host(self):
        return OfflineHost(self.temp.name, mode='good')

    def assert_client(self, host):
        directory = host.client_sink.directory
        manifest = json.loads((directory / 'manifest.json').read_text())
        report = json.loads((directory / 'report.json').read_text())
        events = (directory / 'events.jsonl').read_bytes()
        self.assertEqual(verify_run(directory)['integrity'], 'VERIFIED')
        canonical = json.dumps(report, sort_keys=True, ensure_ascii=False,
                               allow_nan=False).encode('utf-8')
        self.assertEqual(manifest['report_sha256'], hashlib.sha256(canonical).hexdigest())
        self.assertEqual(manifest['events_sha256'], hashlib.sha256(events).hexdigest())
        self.assertEqual(manifest['events_bytes'], len(events))
        self.assertEqual(manifest['run_id'], report['run_id'])
        self.assertEqual(manifest['counts'], report['counts'])
        self.assertFalse(manifest['audit_gap'])
        self.assertFalse(verify_run(directory)['approval_verified'])
        return report, [json.loads(line) for line in events.splitlines()]

    def test_normal_client_manifest_contract(self):
        host = self.host()
        secrets = list(host.fixture.credential_bindings().values())
        host.execute()
        report, _ = self.assert_client(host)
        self.assertEqual(report['counts']['request_count'], 0)
        content = ''.join(p.read_text() for p in host.client_sink.directory.iterdir())
        for secret in secrets:
            self.assertNotIn(secret, content)

    def test_denied_candidate_has_linked_audit_but_no_dispatch(self):
        host = self.host()
        host.execute(fault='deny')
        report, events = self.assert_client(host)
        denied = [r for r in report['checks'] if r['authorization'] == 'DENY']
        self.assertEqual(len(denied), 1)
        row = denied[0]
        self.assertEqual(row['execution'], 'NOT_EXECUTED')
        self.assertEqual(row['conclusion'], 'INCONCLUSIVE')
        self.assertEqual(row['assertion'], 'NOT_APPROVED_CANDIDATE')
        self.assertIsNone(row['action_id'])
        auth = [e for e in events if e['kind'] == 'authorization'
                and e.get('slot_id') == row['slot_id']]
        self.assertEqual(len(auth), 1)
        for key in ('slot_id', 'proposal_id', 'attempt_id'):
            self.assertIsNotNone(row[key])
            self.assertEqual(auth[0][key], row[key])
        self.assertEqual(auth[0]['decision'], 'DENY')
        self.assertFalse(any(e['kind'] in ('prepared', 'model_io')
                             and e.get('slot_id') == row['slot_id'] for e in events))
        allowed = {r['action_id'] for r in report['checks'] if r['authorization'] == 'ALLOW'}
        prepared = [e for e in events if e['kind'] == 'prepared']
        self.assertEqual(len(prepared), 6)
        self.assertEqual({e['action_id'] for e in prepared}, allowed)
        self.assertTrue({e['action_id'] for e in events if e['kind'] == 'model_io'} <= allowed)
        self.assertEqual(report['counts'], dict(plan_count=7, attempt_count=7,
                                               request_count=0, model_request_count=6))

    def test_temporary_corruption_is_rejected(self):
        host = self.host()
        host.execute()
        self.assert_client(host)
        for mutation in ('missing_hash', 'report', 'event_prefix', 'missing_manifest'):
            with self.subTest(mutation=mutation):
                copy = Path(self.temp.name) / mutation
                shutil.copytree(host.client_sink.directory, copy)
                if mutation == 'missing_hash':
                    manifest = json.loads((copy / 'manifest.json').read_text())
                    del manifest['report_sha256']
                    (copy / 'manifest.json').write_text(json.dumps(manifest))
                elif mutation == 'report':
                    report = json.loads((copy / 'report.json').read_text())
                    report['counts']['model_request_count'] += 1
                    (copy / 'report.json').write_text(json.dumps(report))
                elif mutation == 'event_prefix':
                    p = copy / 'events.jsonl'
                    p.write_bytes(b' ' + p.read_bytes()[1:])
                else:
                    (copy / 'manifest.json').unlink()
                self.assertEqual(verify_run(copy)['integrity'], 'INCOMPLETE_OR_INVALID')
        self.assert_client(host)  # The original temporary run was not modified.

    def test_capacity_failure_cannot_verify(self):
        host = self.host()
        self.assertIsInstance(host.run.evidence, BoundedEvidence)
        host.run.evidence.limit = host.run.evidence.used + host.run.evidence.reserve + 1
        result = host.execute()
        self.assertTrue(result['client']['audit_gap'])
        self.assertEqual(result['client']['state'], 'STOPPED')
        self.assertNotEqual(verify_run(host.client_sink.directory)['integrity'], 'VERIFIED')
        self.assertEqual(result['lifecycle']['reset_commit_count'], 0)

    def test_event_write_failure_cannot_verify(self):
        host = self.host()
        with patch.object(host.client_sink, 'emit', side_effect=OSError('TEST_WRITE_FAILURE')):
            result = host.execute()
        self.assertTrue(result['client']['audit_gap'])
        self.assertNotEqual(verify_run(host.client_sink.directory)['integrity'], 'VERIFIED')
        self.assertEqual(result['lifecycle']['reset_commit_count'], 0)

    def test_manifest_write_failure_cannot_verify(self):
        host = self.host()
        with patch.object(host.client_sink, 'finish', side_effect=OSError('TEST_FINISH_FAILURE')):
            result = host.execute()
        self.assertTrue(result['client']['audit_gap'])
        self.assertNotEqual(verify_run(host.client_sink.directory)['integrity'], 'VERIFIED')
        self.assertEqual(result['lifecycle']['reset_commit_count'], 0)

    def test_sidecar_and_lifecycle_keep_separate_contracts(self):
        host = self.host()
        result = host.execute()
        self.assert_client(host)
        sidecar = check_sidecar(host.coordinator.sink.directory)
        self.assertEqual(sidecar['integrity'], 'CONSISTENT_OFFLINE_SIDECAR')
        self.assertEqual(sidecar['registration_status'], 'SOURCE_UNVERIFIED')
        self.assertFalse(sidecar['source_verified'])
        self.assertEqual(result['sidecar']['completion'], 'OFFLINE_VERIFIED')
        self.assertNotEqual(verify_run(host.lifecycle_sink.directory)['integrity'], 'VERIFIED')
        self.assertEqual(result['network_status'], 'PENDING_AUTHORIZATION')
        self.assertEqual(result['nondispatch_proof'], 'UNAVAILABLE')

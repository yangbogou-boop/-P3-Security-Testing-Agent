"""End-to-end memory integration; network forbidden, including test discovery."""
import json
import socket
import tempfile
import threading
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from p3_core.trusted_host import OfflineHost
from p3_core.models import InvalidInput
from p3_core.mock_api import Mode, FixtureManager


class HostTests(unittest.TestCase):
    def setUp(self):
        for name in ('socket','create_connection','getaddrinfo','gethostbyname','gethostbyname_ex'):
            p=patch.object(socket,name,side_effect=AssertionError('NETWORK_FORBIDDEN'))
            p.start();self.addCleanup(p.stop)
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)

    def host(self, mode='good'):
        return OfflineHost(self.temp.name,mode)

    def test_good_complete_workflow(self):
        h=self.host();r=h.execute()
        self.assertEqual(r['client']['counts']['request_count'],0)
        self.assertEqual(r['client']['counts']['model_request_count'],6)
        self.assertEqual(r['sidecar']['completion'],'OFFLINE_VERIFIED')
        self.assertEqual(r['lifecycle']['reset_commit_count'],1)
        self.assertEqual(r['lifecycle']['state'],'RETIRED')
        self.assertTrue(all(c['simulated_conclusion']=='PASS' for c in r['client']['checks']))
        self.assertTrue(all(c['execution']=='NOT_EXECUTED' and c['conclusion']=='INCONCLUSIVE' for c in r['client']['checks']))

    def test_three_independent_defects(self):
        for mode in ('auth','bola','rbac'):
            with self.subTest(mode=mode):
                r=self.host(mode).execute()
                failures=[c['check_id'] for c in r['client']['checks'] if c['simulated_conclusion']=='FAIL']
                self.assertEqual(failures,['HTTP-N-'+mode.upper()])
                self.assertEqual(r['sidecar']['completion'],'OFFLINE_VERIFIED')

    def test_controller_denies_unapproved_candidate(self):
        r=self.host().execute(fault='deny')
        denied=[c for c in r['client']['checks'] if c['authorization']=='DENY']
        self.assertEqual(len(denied),1)
        self.assertIsNone(denied[0]['action_id'])
        self.assertEqual(denied[0]['execution'],'NOT_EXECUTED')
        self.assertEqual(r['client']['counts']['model_request_count'],6)

    def test_missing_summary_blocks_commit(self):
        r=self.host().execute(fault='missing_summary')
        self.assertEqual(r['sidecar']['integrity'],'EVIDENCE_INCOMPLETE')
        self.assertEqual(r['lifecycle']['reset_commit_count'],0)
        self.assertEqual(r['lifecycle']['state'],'FAILED')

    def test_audit_failure_stops_both(self):
        h=self.host();r=h.execute(fault='audit')
        self.assertTrue(h.client.status()['revoked'] and h.service.status()['revoked'])
        self.assertEqual(r['lifecycle']['reset_commit_count'],0)
        self.assertLessEqual(r['client']['counts']['model_request_count'],1)
        self.assertEqual(r['sidecar']['completion'],'AUDIT_FAILED')

    def test_revoke_before_send_is_not_missing_summary_exemption(self):
        r=self.host().execute(fault='before_send_revoke')
        self.assertEqual(r['client']['counts']['model_request_count'],0)
        self.assertEqual(r['send_observation'],'NO_MODEL_SEND_OBSERVED')
        self.assertEqual(r['nondispatch_proof'],'UNAVAILABLE')
        self.assertEqual(r['lifecycle']['reset_commit_count'],0)
        self.assertTrue(r['sidecar']['missing_actions'])

    def test_partial_send_remains_incomplete(self):
        r=self.host().execute(fault='partial_revoke')
        self.assertEqual(r['client']['counts']['model_request_count'],1)
        self.assertEqual(r['send_observation'],'MODEL_SEND_OBSERVED')
        self.assertEqual(r['sidecar']['integrity'],'EVIDENCE_INCOMPLETE')
        self.assertEqual(r['lifecycle']['reset_commit_count'],0)

    def test_run_scope_fixture_generation_version_mismatch(self):
        h=self.host()
        for key,value in [('run_id','other'),('fixture_instance_id','other'),('scope_digest','f'*64),
                          ('generation',9),('authorization_version','other')]:
            with self.subTest(key=key),self.assertRaises(InvalidInput):
                h.verify_binding(replace(h.binding,**{key:value}))

    def test_other_run_binding_rejected(self):
        a=self.host();b=self.host()
        with self.assertRaises(InvalidInput):a.verify_binding(b.binding)

    def test_old_host_cannot_reopen(self):
        h=self.host();h.execute()
        with self.assertRaises(InvalidInput):h.execute()
        with self.assertRaises(InvalidInput):h.verify_binding(h.binding)

    def test_failed_host_cannot_retry(self):
        h=self.host();h.execute(fault='audit')
        with self.assertRaises(InvalidInput):h.execute()

    def test_no_credentials_or_wire_on_disk(self):
        h=self.host();secrets=list(h.fixture.credential_bindings().values());r=h.execute()
        text=json.dumps(r)+''.join(p.read_text() for p in Path(self.temp.name).rglob('*.json*'))
        for secret in secrets:self.assertNotIn(secret,text)
        self.assertNotIn('Authorization: Bearer',text)
        self.assertNotIn('SYNTHETIC_AUDIT_FAILURE',text)

    def test_new_fixture_credentials_are_fresh(self):
        h=self.host();h.execute();next_fixture=h.supervisor._next_fixture
        self.assertNotEqual(h.fixture.fixture_instance_id,next_fixture.fixture_instance_id)
        self.assertFalse(set(h.fixture.credential_bindings().values()) & set(next_fixture.credential_bindings().values()))

    def test_missing_controller_root_fails(self):
        h=self.host()
        with patch.object(h.coordinator,'capture_controller',return_value=None):r=h.execute()
        self.assertEqual(r['lifecycle']['reset_commit_count'],0)
        self.assertNotEqual(r['sidecar']['completion'],'OFFLINE_VERIFIED')

    def test_failure_at_commit_boundary_is_latched(self):
        h=self.host();original=h.supervisor.evidence
        def emit(event):
            original(event)
            if event['kind']=='fixture_prepared':h.supervisor._evidence_failed()
        h.supervisor.evidence=emit;r=h.execute()
        self.assertEqual(r['lifecycle']['reset_commit_count'],0)

    def test_final_host_audit_failure_retains_commit_fact(self):
        h=self.host()
        with patch.object(h.lifecycle_sink,'finish',side_effect=OSError('secret')):r=h.execute()
        self.assertEqual(r['lifecycle']['reset_commit_count'],1)
        self.assertEqual(r['lifecycle']['state'],'FAILED')
        self.assertIsNone(r['next_fixture_id'])

    def test_actual_acceptance_never_promoted(self):
        r=self.host().execute()
        self.assertEqual(r['network_status'],'PENDING_AUTHORIZATION')
        self.assertEqual(r['sidecar']['network_status'],'PENDING_AUTHORIZATION')

    def test_client_audit_failure_is_unknown(self):
        h=self.host()
        with patch.object(h.client_sink,'emit',side_effect=OSError('secret')):r=h.execute()
        self.assertEqual(r['send_observation'],'UNKNOWN')
        self.assertEqual(r['lifecycle']['reset_commit_count'],0)

    def test_concurrent_host_entry_has_one_owner(self):
        h=self.host();barrier=threading.Barrier(3);results=[]
        def execute():
            barrier.wait()
            try:results.append(h.execute()['lifecycle']['reset_commit_count'])
            except InvalidInput:results.append('REJECTED')
        threads=[threading.Thread(target=execute) for _ in range(2)]
        for thread in threads:thread.start()
        barrier.wait()
        for thread in threads:thread.join(5);self.assertFalse(thread.is_alive())
        self.assertCountEqual(results,[1,'REJECTED'])

    def test_no_sidecar_cannot_commit_even_after_complete_model_run(self):
        h=self.host();h.supervisor.coordinator=None
        r=h.execute()
        self.assertEqual(r['lifecycle']['state'],'STOPPED')
        self.assertEqual(r['lifecycle']['reset_commit_count'],0)
        self.assertEqual(h.supervisor._evidence_status(),'MISSING')

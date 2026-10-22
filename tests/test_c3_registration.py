"""Disk tampering regressions: synthetic evidence, never network execution."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from test_c3_supervisor import FakePort, summary, ACTION
from p3_core.supervision import RunBinding, Supervisor
from p3_core.coordination import EvidenceCoordinator, check_sidecar
from p3_core.evidence import JsonlEvidence
from p3_core.mock_api import Mode
from p3_core.models import InvalidInput
from p3_core.experiments import configuration, synthetic_registry
from p3_core.http.machine import SimulationRun
from p3_core.http.transport import MemoryTransport
from p3_core.mock_api import FixtureManager
from unittest.mock import patch
import socket


def rewrite(directory, mutate, report_mutate=None):
    path=directory/'events.jsonl'
    rows=[json.loads(line) for line in path.read_text().splitlines()]
    mutate(rows)
    data=('\n'.join(json.dumps(row) for row in rows)+'\n').encode()
    path.write_bytes(data)
    manifest=json.loads((directory/'manifest.json').read_text())
    manifest.update(events_bytes=len(data),events_sha256=hashlib.sha256(data).hexdigest())
    if report_mutate:
        report=json.loads((directory/'report.json').read_text());report_mutate(report)
        (directory/'report.json').write_text(json.dumps(report))
        manifest['report_sha256']=hashlib.sha256(json.dumps(report,sort_keys=True).encode()).hexdigest()
    (directory/'manifest.json').write_text(json.dumps(manifest))


class RegistrationTests(unittest.TestCase):
    def setUp(self):
        for name in ('socket','create_connection','getaddrinfo','gethostbyname','gethostbyname_ex'):
            guard=patch.object(socket,name,side_effect=AssertionError('NETWORK_FORBIDDEN'))
            guard.start();self.addCleanup(guard.stop)

    def trusted_sidecar(self,finish=True):
        root=tempfile.TemporaryDirectory();self.addCleanup(root.cleanup)
        fixture=FixtureManager.prepare(Mode.GOOD);raw=configuration(fixture)
        controller=SimulationRun(raw,synthetic_registry(raw),credentials=fixture.credential_bindings())
        controller.start();controller.step(MemoryTransport())
        binding=RunBinding(controller.run_id,fixture.fixture_instance_id,controller.config.scope_digest,'v1',1)
        c=EvidenceCoordinator(binding,sink=JsonlEvidence(root.name));c.capture_controller(controller)
        action=controller._slots[0].action_id
        c.accept(summary(action_id=action),binding)
        if finish:c.finish()
        return c,c.sink.directory,controller

    def setup_sidecar(self):
        root=tempfile.TemporaryDirectory();self.addCleanup(root.cleanup)
        binding=RunBinding('run_test','fixture_test','a'*64,'v1',1)
        sink=JsonlEvidence(root.name);c=EvidenceCoordinator(binding,sink=sink)
        c.expect(ACTION,binding);c.accept(summary(),binding);c.finish()
        return c,sink.directory

    def test_null_action_rehashed(self):
        c,path=self.setup_sidecar()
        rewrite(path,lambda rows:rows[0]['summary'].update(action_id=None))
        self.assertEqual(check_sidecar(path)['integrity'],'EVIDENCE_INCOMPLETE')

    def test_unregistered_action_rehashed(self):
        c,path=self.setup_sidecar()
        rewrite(path,lambda rows:rows[0]['summary'].update(action_id='action_'+'c'*32))
        self.assertEqual(check_sidecar(path)['integrity'],'EVIDENCE_INCOMPLETE')

    def test_missing_controller_root_blocks_reset(self):
        c,path=self.setup_sidecar();events=[]
        a=FakePort(c.binding,'client',events);b=FakePort(c.binding,'service',events)
        s=Supervisor(c.binding,a,b);s.attach_evidence(c);s.revoke()
        a.clean=b.clean=True;s.poll()
        self.assertNotEqual(c.completion_status(),'VERIFIED')
        with self.assertRaises(InvalidInput):s.prepare_next(Mode.GOOD)
        self.assertEqual(s.poll()['reset_commit_count'],0)

    def test_public_report_after_finish_not_pending(self):
        c,path=self.setup_sidecar()
        self.assertNotEqual(c.report()['completion'],'PENDING')

    def test_other_run_registered_action_rejected(self):
        c,path,controller=self.trusted_sidecar()
        other,_,other_controller=self.trusted_sidecar()
        rewrite(path,lambda rows:rows[0]['summary'].update(action_id=other_controller._slots[0].action_id))
        self.assertEqual(check_sidecar(path)['integrity'],'EVIDENCE_INCOMPLETE')
        self.assertEqual(c.completion_status(),'AUDIT_FAILED')

    def test_editing_all_files_cannot_replace_independent_root(self):
        c,path,controller=self.trusted_sidecar()
        fake='action_'+'e'*32
        def replace_report(report):
            report['expected_actions']=[fake];report['connections'][0]['action_id']=fake
        rewrite(path,lambda rows:rows[0]['summary'].update(action_id=fake),replace_report)
        structural=check_sidecar(path)
        self.assertEqual(structural['integrity'],'CONSISTENT_OFFLINE_SIDECAR')
        self.assertEqual(structural['registration_status'],'SOURCE_UNVERIFIED')
        self.assertFalse(structural['source_verified'])
        self.assertEqual(c.completion_status(),'AUDIT_FAILED')

    def test_real_offline_controller_snapshot_positive(self):
        c,path,controller=self.trusted_sidecar()
        self.assertEqual(c.completion_status(),'VERIFIED')
        self.assertEqual(c.report()['completion'],'OFFLINE_VERIFIED')
        self.assertFalse(check_sidecar(path)['source_verified'])
        self.assertEqual(controller.counts['request_count'],0)

    def test_lifecycle_null_cannot_masquerade_as_action(self):
        c,path,controller=self.trusted_sidecar()
        def mutate(rows):
            rows[0]['kind']='revocation_requested';rows[0]['summary']['action_id']=None
        rewrite(path,mutate)
        self.assertEqual(check_sidecar(path)['integrity'],'EVIDENCE_INCOMPLETE')
        # Legitimate lifecycle observations use the separate Supervisor stream.
        events=[];a=FakePort(c.binding,'client',[]);b=FakePort(c.binding,'service',[])
        s=Supervisor(c.binding,a,b,evidence=events.append);s.revoke()
        self.assertEqual(events[0]['kind'],'revocation_requested')
        self.assertNotIn('action_id',events[0])

    def test_connection_association_rehashed_rejected(self):
        c,path,controller=self.trusted_sidecar()
        rewrite(path,lambda rows:rows[0]['summary'].update(connection_id='connection_'+'f'*32))
        self.assertEqual(check_sidecar(path)['integrity'],'EVIDENCE_INCOMPLETE')

    def test_failure_blocks_supervisor_commit(self):
        c,path,controller=self.trusted_sidecar();events=[]
        a=FakePort(c.binding,'client',events);b=FakePort(c.binding,'service',events)
        s=Supervisor(c.binding,a,b);s.attach_evidence(c);s.revoke();a.clean=b.clean=True
        self.assertEqual(s.poll()['state'],'STOPPED')
        rewrite(path,lambda rows:rows[0]['summary'].update(action_id=None))
        with patch.object(FixtureManager,'prepare',wraps=FixtureManager.prepare) as prepare:
            with self.assertRaises(InvalidInput):s.prepare_next(Mode.GOOD)
            self.assertEqual(prepare.call_count,0)
        self.assertEqual(s.poll()['state'],'FAILED')
        self.assertEqual(s.poll()['reset_commit_count'],0)

    def test_report_lifecycle_states(self):
        c,path,controller=self.trusted_sidecar(finish=False)
        self.assertEqual(c.report()['completion'],'PENDING')
        with patch.object(c,'completion_status',return_value='PENDING'):
            c.finish()
        self.assertEqual(c.report()['completion'],'WRITTEN_UNVERIFIED')
        self.assertEqual(c.completion_status(),'VERIFIED')
        self.assertEqual(c.report()['completion'],'OFFLINE_VERIFIED')
        c._fail(audit=True)
        self.assertEqual(c.report()['completion'],'AUDIT_FAILED')

    def test_untrusted_report_and_gap_states(self):
        c,path=self.setup_sidecar()
        self.assertEqual(c.report()['completion'],'SOURCE_UNVERIFIED')
        c._fail()
        self.assertEqual(c.report()['completion'],'EVIDENCE_INCOMPLETE')

    def test_planner_dictionary_cannot_supply_root(self):
        c,path=self.setup_sidecar()
        with self.assertRaises(InvalidInput):c.capture_controller({'approved':True,'actions':[ACTION]})
        self.assertEqual(c.completion_status(),'SOURCE_UNVERIFIED')

    def test_all_binding_fields_checked_on_disk(self):
        for key,value in (('linked_run_id','other'),('fixture_instance_id','other'),
                          ('generation',2),('scope_digest','b'*64),('authorization_version','v2')):
            with self.subTest(key=key):
                c,path,controller=self.trusted_sidecar()
                rewrite(path,lambda rows:rows[0].update({key:value}))
                self.assertEqual(check_sidecar(path)['integrity'],'EVIDENCE_INCOMPLETE')

    def test_missing_duplicate_and_sequence_gap(self):
        for mode in ('missing','duplicate','gap'):
            with self.subTest(mode=mode):
                c,path,controller=self.trusted_sidecar()
                def mutate(rows):
                    if mode=='missing':rows.clear()
                    elif mode=='duplicate':rows.append(dict(rows[0]))
                    else:rows[0]['summary']['summary_sequence']=2
                rewrite(path,mutate)
                self.assertEqual(check_sidecar(path)['integrity'],'EVIDENCE_INCOMPLETE')

    def test_controller_audit_failure_invalidates_completion(self):
        c,path,controller=self.trusted_sidecar()
        controller._audit_gap=True
        self.assertEqual(c.completion_status(),'AUDIT_FAILED')
        self.assertEqual(c.report()['completion'],'AUDIT_FAILED')

    def test_non_dispatched_action_not_filled_with_fake_summary(self):
        c,path,controller=self.trusted_sidecar(finish=False)
        # This adapter has no trusted non-dispatch proof format: fail closed.
        c.expect('action_'+'d'*32,c.binding);c.finish()
        self.assertEqual(c.completion_status(),'INCOMPLETE')
        self.assertEqual(c.report()['missing_actions'],['action_'+'d'*32])

    def test_action_wrong_types_rehashed(self):
        for value in (False,17,[],{}):
            with self.subTest(value=value):
                c,path=self.setup_sidecar()
                rewrite(path,lambda rows:rows[0]['summary'].update(action_id=value))
                self.assertEqual(check_sidecar(path)['integrity'],'EVIDENCE_INCOMPLETE')

    def test_other_controller_cannot_bind_root(self):
        c,path,controller=self.trusted_sidecar(finish=False)
        other,_,other_controller=self.trusted_sidecar()
        with self.assertRaises(InvalidInput):c.capture_controller(other_controller)
        c.finish()
        self.assertEqual(c.completion_status(),'VERIFIED')

    def test_markers_remain_fail_closed_with_root(self):
        for name in ('manifest','report'):
            for key,value in (('audit_gap',True),('audit_gap',None),('completion','PENDING')):
                with self.subTest(name=name,key=key,value=value):
                    c,path,controller=self.trusted_sidecar()
                    p=path/(name+'.json');doc=json.loads(p.read_text());doc[key]=value;p.write_text(json.dumps(doc))
                    self.assertEqual(check_sidecar(path)['integrity'],'EVIDENCE_INCOMPLETE')
                    self.assertEqual(c.completion_status(),'AUDIT_FAILED')

"""NO_NETWORK_SIMULATION: fake lifecycle and summaries are not live evidence."""
import copy
import io
import json
import socket
import tempfile
import threading
import unittest
from contextlib import redirect_stdout
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from p3_core.supervision import Supervisor, RunBinding, LifecyclePort
from p3_core.coordination import EvidenceCoordinator, check_sidecar
from p3_core.preflight import authorization_preflight
from p3_core.acceptance import acceptance_plan, offline_status, validate_management_record
from p3_core.delivery import main
from p3_core.evidence import MemoryEvidence, JsonlEvidence
from p3_core.models import InvalidInput
from p3_core.experiments import configuration, synthetic_registry
from p3_core.http.contract import HttpConfig
from p3_core.http.live import AuthorizedHttpRun, FixtureBinding, InstanceStatus, credential_binding_digest
from p3_core.mock_api import FixtureManager, Mode
from p3_core.mock_api.service import AuthorizedService


ACTION='action_'+'a'*32


class FakePort:
    def __init__(self,binding,name,events):
        self.binding,self.name,self.events=binding,name,events
        self.revoked=False;self.clean=False;self.failed=False;self.invalidated=False
    def revoke(self):self.events.append(self.name);self.revoked=True
    def status(self):return dict(revoked=self.revoked,clean=self.clean,failed=self.failed)
    def invalidate(self):self.invalidated=True
    def actions(self):return (ACTION,)
    def attach_consumer(self,consumer):self.consumer=consumer


def summary(**changes):
    row=dict(connection_id='connection_'+'b'*32,action_id=ACTION,sent_bytes=10,received_bytes=20,
             first_send_sequence=1,last_send_sequence=1,reason='RESPONSE_SENT',cleanup_failed=False,
             revoke_requested_at=None,revoke_effective_sequence=None,revoke_effective_at=None,summary_sequence=1)
    row.update(changes);return row


class SupervisorTests(unittest.TestCase):
    def setUp(self):
        for name in ('socket','create_connection','getaddrinfo','gethostbyname','gethostbyname_ex'):
            guard=patch.object(socket,name,side_effect=AssertionError('NETWORK_FORBIDDEN'))
            guard.start();self.addCleanup(guard.stop)
        self.binding=RunBinding('run_test','fixture_test','a'*64,'v1',1)
        self.events=[];self.now=0
        self.client=FakePort(self.binding,'client',self.events)
        self.service=FakePort(self.binding,'service',self.events)
        self.supervisor=Supervisor(self.binding,self.client,self.service,clock=lambda:self.now)

    def clean(self):
        self.client.clean=self.service.clean=True
        return self.supervisor.poll()

    def test_missing_sidecar_never_creates_or_commits_fixture(self):
        self.supervisor.revoke()
        self.assertEqual(self.clean()['state'],'STOPPED')
        with patch.object(FixtureManager,'prepare',wraps=FixtureManager.prepare) as prepared:
            for _ in range(2):
                with self.assertRaises(InvalidInput):self.supervisor.prepare_next(Mode.GOOD)
            self.assertEqual(prepared.call_count,0)
        self.assertEqual(self.supervisor.poll()['reset_commit_count'],0)
        self.assertFalse(self.client.invalidated or self.service.invalidated)
        self.assertNotEqual(self.supervisor._evidence_status(),'VERIFIED')

    def coordinator(self,**kw):
        c=EvidenceCoordinator(self.binding,**kw);c.expect(ACTION,self.binding);return c

    def verified_sidecar_fixture(self):
        controller=self.trusted_controller_fixture()
        root=tempfile.TemporaryDirectory();self.addCleanup(root.cleanup)
        coordinator=EvidenceCoordinator(self.binding,sink=JsonlEvidence(root.name))
        self.supervisor.attach_evidence(coordinator)
        coordinator.capture_controller(controller)
        coordinator.accept(summary(),self.binding);coordinator.finish()
        self.assertEqual(coordinator.completion_status(),'VERIFIED')

    def trusted_controller_fixture(self):
        # Preserve the lifecycle assertions, but replace the old self-claimed
        # action fixture with an actual offline Controller approval.
        from p3_core.http.machine import SimulationRun
        from p3_core.http.transport import MemoryTransport
        global ACTION
        original=ACTION
        fixture=FixtureManager.prepare(Mode.GOOD);raw=configuration(fixture)
        run=SimulationRun(raw,synthetic_registry(raw),credentials=fixture.credential_bindings())
        run.start();run.step(MemoryTransport())
        ACTION=run._slots[0].action_id
        self.addCleanup(lambda:globals().__setitem__('ACTION',original))
        self.binding=RunBinding(run.run_id,fixture.fixture_instance_id,run.config.scope_digest,'v1',1)
        self.client=FakePort(self.binding,'client',self.events)
        self.service=FakePort(self.binding,'service',self.events)
        self.supervisor=Supervisor(self.binding,self.client,self.service,clock=lambda:self.now)
        return run

    def document(self):
        fixture=FixtureManager.reset(Mode.GOOD);raw=configuration(fixture);cfg=HttpConfig.parse(raw)
        def material(role):return dict(reference='reference',source='offline-placeholder',sha256='a'*64,
            authorization_version=cfg.authorization_version,scope_digest=cfg.scope_digest,
            valid_from=0,valid_until=100,role=role,principal='reviewer',delegation_ref=None)
        return dict(config=raw,owner=material('owner'),teacher_catalog=material('teacher'),
            fixture_binding=dict(fixture_instance_id=cfg.fixture_instance_id,scope_digest=cfg.scope_digest,
                credential_digest='b'*64,supervisor_record_ref='record'),budget_record='record',
            revocation_responsibility='record',experiment_scope=['GOOD_PAIRED_CONTROLS'],exception_permissions=[])

    def test_both_revocation_orders(self):
        for first in (False,True):
            events=[];a=FakePort(self.binding,'client',events);b=FakePort(self.binding,'service',events)
            s=Supervisor(self.binding,a,b);s.revoke(service_first=first)
            self.assertEqual(events,['service','client'] if first else ['client','service'])
            self.assertTrue(a.revoked and b.revoked)

    def test_simultaneous_revocation_is_idempotent(self):
        barrier=threading.Barrier(3)
        threads=[threading.Thread(target=lambda:(barrier.wait(),self.supervisor.revoke())) for _ in range(2)]
        for t in threads:t.start()
        barrier.wait()
        for t in threads:t.join(2);self.assertFalse(t.is_alive())
        self.assertEqual(self.events,['client','service'])

    def test_pending_cleanup_does_not_block_revoke(self):
        self.supervisor.revoke();self.assertEqual(self.supervisor.poll()['state'],'STOPPING')
        self.supervisor.revoke();self.assertTrue(self.service.revoked)
        self.assertEqual(self.clean()['state'],'STOPPED')

    def test_cleanup_failure_is_terminal(self):
        self.supervisor.revoke();self.client.failed=True
        self.assertEqual(self.clean()['state'],'FAILED')
        self.client.failed=False
        self.assertEqual(self.supervisor.poll()['state'],'FAILED')
        with self.assertRaises(InvalidInput):self.supervisor.prepare_next(Mode.GOOD)

    def test_timeout_does_not_claim_cleanup(self):
        self.supervisor.revoke();self.now=5
        self.assertEqual(self.supervisor.poll()['reason'],'CLEANUP_TIMEOUT')
        self.assertEqual(self.clean()['state'],'FAILED')

    def test_clock_regression_fails_closed(self):
        self.supervisor.revoke();self.now=-1
        self.assertEqual(self.supervisor.poll()['state'],'FAILED')

    def test_revoke_exception_still_reaches_other_endpoint(self):
        self.client.revoke=lambda:(_ for _ in ()).throw(ValueError('secret'))
        self.supervisor.revoke()
        self.assertTrue(self.service.revoked);self.assertEqual(self.supervisor.poll()['reason'],'REVOKE_ERROR')

    def test_reset_requires_both_clean_and_new_instance(self):
        self.verified_sidecar_fixture()
        self.supervisor.revoke();self.client.clean=True
        with self.assertRaises(InvalidInput):self.supervisor.prepare_next(Mode.GOOD)
        self.assertFalse(self.client.invalidated)
        self.clean();fixture=self.supervisor.prepare_next(Mode.GOOD)
        self.assertNotEqual(fixture.fixture_instance_id,self.binding.fixture_instance_id)
        self.assertTrue(self.client.invalidated and self.service.invalidated)
        with self.assertRaises(InvalidInput):self.supervisor.prepare_next(Mode.GOOD)

    def test_concurrent_reset_has_one_winner(self):
        self.verified_sidecar_fixture()
        self.supervisor.revoke();self.clean();results=[];barrier=threading.Barrier(3)
        def reset():
            barrier.wait()
            try:self.supervisor.prepare_next(Mode.GOOD);results.append('prepared')
            except InvalidInput:results.append('rejected')
        ts=[threading.Thread(target=reset) for _ in range(2)]
        for t in ts:t.start()
        barrier.wait()
        for t in ts:t.join(2);self.assertFalse(t.is_alive())
        self.assertCountEqual(results,['prepared','rejected'])

    def test_stale_binding_and_endpoint_rejected(self):
        with self.assertRaises(InvalidInput):self.supervisor.revoke(replace(self.binding,generation=0))
        self.supervisor.revoke()
        with self.assertRaises(InvalidInput):Supervisor(self.binding,self.client,self.service)
        with self.assertRaises(InvalidInput):Supervisor(replace(self.binding,run_id='run_other'),self.client,self.service)

    def test_audit_failure_revoke_and_no_reset(self):
        self.supervisor.evidence=lambda event:(_ for _ in ()).throw(OSError('secret'))
        self.supervisor.revoke();self.clean()
        self.assertTrue(self.client.revoked and self.service.revoked)
        self.assertEqual(self.supervisor.poll()['state'],'FAILED')
        with self.assertRaises(InvalidInput):self.supervisor.prepare_next(Mode.GOOD)

    def test_poll_cannot_race_revocation_audit(self):
        entered=threading.Event();release=threading.Event()
        def audit(event):entered.set();release.wait(2)
        self.supervisor.evidence=audit
        t=threading.Thread(target=self.supervisor.revoke);t.start()
        try:
            self.assertTrue(entered.wait(1));self.client.clean=self.service.clean=True
            self.assertEqual(self.supervisor.poll()['state'],'STOPPING')
            with self.assertRaises(InvalidInput):self.supervisor.prepare_next(Mode.GOOD)
        finally:release.set();t.join(2)
        self.assertEqual(self.supervisor.poll()['state'],'STOPPED')

    def test_evidence_valid_duplicate_and_missing(self):
        c=self.coordinator();self.assertEqual(c.accept(summary(),self.binding),'CORRELATED')
        self.assertEqual(c.accept(summary(),self.binding),'DUPLICATE')
        self.assertEqual(c.report()['connection_count'],1)
        c.expect('action_'+'c'*32,self.binding)
        self.assertEqual(c.finish()['integrity'],'EVIDENCE_INCOMPLETE')

    def test_conflicting_duplicate_rejected(self):
        c=self.coordinator();c.accept(summary(),self.binding)
        self.assertEqual(c.accept(summary(sent_bytes=11),self.binding),'EVIDENCE_INCOMPLETE')

    def test_cross_run_and_unknown_action_rejected(self):
        c=self.coordinator()
        self.assertEqual(c.accept(summary(),replace(self.binding,run_id='run_other')),'EVIDENCE_INCOMPLETE')
        c=self.coordinator()
        self.assertEqual(c.accept(summary(action_id='action_'+'d'*32),self.binding),'UNKNOWN')

    def test_overwritten_or_gapped_summary_detected(self):
        c=self.coordinator()
        self.assertEqual(c.accept(summary(summary_sequence=2),self.binding),'EVIDENCE_INCOMPLETE')

    def test_partial_send_stays_unknown(self):
        c=self.coordinator();c.accept(summary(reason='REVOKED',revoke_requested_at=2,
            revoke_effective_at=3,revoke_effective_sequence=2),self.binding)
        self.assertEqual(c.sink.events[0]['outcome'],'UNKNOWN')
        self.assertEqual(c.finish()['api_conclusion'],'INCONCLUSIVE')

    def test_close_failure_prevents_complete_evidence(self):
        c=self.coordinator();c.accept(summary(cleanup_failed=True),self.binding)
        self.assertEqual(c.report()['integrity'],'EVIDENCE_INCOMPLETE')

    def test_invalid_summary_does_not_echo_secrets(self):
        for row in (summary(token='SENSITIVE_TOKEN'),summary(reason='SENSITIVE_EXCEPTION'),summary(action_id='SENSITIVE_PARAM')):
            c=self.coordinator();c.accept(row,self.binding);c.finish()
            self.assertNotIn('SENSITIVE',json.dumps([c.sink.events,c.sink.report,c.sink.manifest]))

    def test_sidecar_audit_failure_revokes_both(self):
        c=EvidenceCoordinator(self.binding);self.supervisor.attach_evidence(c);self.supervisor.register_actions()
        c.sink.emit=lambda row:(_ for _ in ()).throw(OSError('secret'))
        with self.assertRaises(InvalidInput):self.service.consumer(summary())
        self.assertTrue(self.client.revoked and self.service.revoked)
        self.assertTrue(c.report()['audit_gap'])

    def test_sidecar_roundtrip_and_tamper(self):
        with tempfile.TemporaryDirectory() as root:
            sink=JsonlEvidence(root);c=self.coordinator(sink=sink);c.accept(summary(),self.binding);c.finish()
            self.assertEqual(check_sidecar(sink.directory)['integrity'],'CONSISTENT_OFFLINE_SIDECAR')
            (sink.directory/'events.jsonl').write_text('secret')
            self.assertEqual(check_sidecar(sink.directory)['integrity'],'EVIDENCE_INCOMPLETE')

    def test_empty_or_capacity_exceeded_not_complete(self):
        self.assertEqual(EvidenceCoordinator(self.binding).finish()['integrity'],'EVIDENCE_INCOMPLETE')
        c=self.coordinator(limit=1)
        with self.assertRaises(InvalidInput):c.expect('action_'+'c'*32,self.binding)

    def test_complete_fields_are_not_authorization(self):
        result=authorization_preflight(self.document(),now=1)
        self.assertEqual(result['status'],'PENDING_AUTHORIZATION');self.assertFalse(result['execution_allowed'])
        self.assertEqual(sum(i['category']=='SOURCE_UNVERIFIED' for i in result['issues']),2)

    def test_missing_teacher_owner_and_planner_flag(self):
        doc=self.document();doc.pop('owner');doc.pop('teacher_catalog');doc['active']=True
        result=authorization_preflight(doc,now=1)
        self.assertIn(dict(category='MISSING',field='teacher_catalog'),result['issues'])
        self.assertIn(dict(category='MISSING',field='owner'),result['issues'])
        self.assertIn(dict(category='INVALID_FORMAT',field='unknown_fields'),result['issues'])

    def test_human_lookup_still_needs_runtime_binding(self):
        result=authorization_preflight(self.document(),now=1,review_source=lambda field,digest:True)
        self.assertTrue(result['human_review_observed']);self.assertFalse(result['execution_allowed'])
        self.assertIn(dict(category='RUN_BINDING_PENDING',field='trusted_host'),result['issues'])

    def test_material_conflicts_and_exception_permission(self):
        doc=self.document();doc['owner']['scope_digest']='f'*64;doc['experiment_scope']=['TIMEOUT']
        result=authorization_preflight(doc,now=101)
        self.assertIn(dict(category='CONFLICT',field='owner.scope'),result['issues'])
        self.assertIn(dict(category='CONFLICT',field='owner.validity'),result['issues'])
        self.assertIn(dict(category='CONFLICT',field='exception_permissions'),result['issues'])

    def test_malformed_lists_and_lookup_failure_are_safe(self):
        doc=self.document();doc['experiment_scope']=[{}]
        result=authorization_preflight(doc,now=1,review_source=lambda *args:(_ for _ in ()).throw(OSError('secret')))
        self.assertFalse(result['execution_allowed']);self.assertNotIn('secret',json.dumps(result))
        self.assertIn(dict(category='INVALID_FORMAT',field='experiment_scope'),result['issues'])

    def test_all_fourteen_remain_pending(self):
        plan=acceptance_plan();self.assertEqual(len(plan['cases']),14)
        for row in plan['cases']:row['status']='VERIFIED'
        result=offline_status(plan)
        self.assertTrue(all(r['status']=='PENDING_AUTHORIZATION' for r in result['cases']))
        self.assertIsNone(result['execution_entrypoint'])

    def test_management_format_does_not_authenticate(self):
        row=acceptance_plan()['cases'][0];row['status']='VERIFIED'
        with self.assertRaises(InvalidInput):validate_management_record(row)
        row['result'].update(execution_proof='untrusted',reviewer_record='untrusted')
        self.assertFalse(validate_management_record(row)['source_verified'])

    def test_read_only_cli_no_network(self):
        for command in ('supervisor-plan','integration-status'):
            out=io.StringIO()
            with redirect_stdout(out):self.assertEqual(main([command]),0)
            self.assertEqual(json.loads(out.getvalue())['network_status'],'PENDING_AUTHORIZATION')
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'input.json';path.write_text(json.dumps(self.document()))
            before=path.read_bytes();out=io.StringIO()
            with redirect_stdout(out):self.assertEqual(main(['authorization-preflight',str(path)]),0)
            self.assertEqual(path.read_bytes(),before);self.assertFalse(json.loads(out.getvalue())['execution_allowed'])

    def test_real_ports_only_observe_and_revoke_without_permission(self):
        fixture=FixtureManager.reset(Mode.GOOD);raw=configuration(fixture);cfg=HttpConfig.parse(raw)
        registry=synthetic_registry(raw)
        fb=FixtureBinding(fixture.fixture_instance_id,cfg.scope_digest,'host',InstanceStatus(),
                          credential_binding_digest(fixture.credential_bindings()))
        run=AuthorizedHttpRun(raw,registry,credentials=fixture.credential_bindings(),binding=fb)
        service=AuthorizedService(cfg,registry,fixture,fb)
        binding=RunBinding(run.run_id,fixture.fixture_instance_id,cfg.scope_digest,cfg.authorization_version,1)
        sup=Supervisor(binding,LifecyclePort(run,binding),LifecyclePort(service,binding))
        sup.revoke();self.assertEqual(sup.poll()['state'],'STOPPED')
        self.assertIsNone(service._server)

    def test_missing_summary_blocks_fixture_reset(self):
        c=EvidenceCoordinator(self.binding)
        self.supervisor.attach_evidence(c);self.supervisor.register_actions()
        self.supervisor.revoke();self.clean()
        with self.assertRaises(InvalidInput):self.supervisor.prepare_next(Mode.GOOD)
        c.finish()
        self.assertEqual(self.supervisor.poll()['state'],'FAILED')

    def test_sidecar_failure_after_revoke_is_latched(self):
        c=EvidenceCoordinator(self.binding)
        self.supervisor.attach_evidence(c);self.supervisor.register_actions()
        self.supervisor.revoke()
        c.sink.emit=lambda row:(_ for _ in ()).throw(OSError('secret'))
        with self.assertRaises(InvalidInput):c.accept(summary(),self.binding)
        self.assertEqual(self.clean()['state'],'FAILED')
        with self.assertRaises(InvalidInput):self.supervisor.prepare_next(Mode.GOOD)
        self.assertEqual(self.events,['client','service'])

    def test_manifest_completion_required_before_reset(self):
        controller=self.trusted_controller_fixture()
        with tempfile.TemporaryDirectory() as root:
            sink=JsonlEvidence(root);c=EvidenceCoordinator(self.binding,sink=sink)
            c.capture_controller(controller)
            self.supervisor.attach_evidence(c);self.supervisor.register_actions()
            c.accept(summary(),self.binding);self.supervisor.revoke();self.clean()
            with self.assertRaises(InvalidInput):self.supervisor.prepare_next(Mode.GOOD)
            entered=threading.Event();release=threading.Event();original=sink.finish
            def blocked(*args):entered.set();release.wait(2);original(*args)
            sink.finish=blocked
            worker=threading.Thread(target=c.finish);worker.start()
            try:
                self.assertTrue(entered.wait(1));self.supervisor.poll()
                with self.assertRaises(InvalidInput):self.supervisor.prepare_next(Mode.GOOD)
            finally:release.set();worker.join(2)
            self.assertFalse(worker.is_alive())
            self.assertEqual(self.supervisor.poll()['state'],'STOPPED')
            self.assertIsNotNone(self.supervisor.prepare_next(Mode.GOOD))

    def test_manifest_audit_markers_fail_closed(self):
        for value in (True,None,0,'false','MISSING'):
            with self.subTest(value=value),tempfile.TemporaryDirectory() as root:
                sink=JsonlEvidence(root);c=self.coordinator(sink=sink)
                c.accept(summary(),self.binding);c.finish()
                path=sink.directory/'manifest.json';manifest=json.loads(path.read_text())
                if value=='MISSING':manifest.pop('audit_gap')
                else:manifest['audit_gap']=value
                path.write_text(json.dumps(manifest))
                self.assertEqual(check_sidecar(sink.directory)['integrity'],'EVIDENCE_INCOMPLETE')

    def test_manifest_identity_provenance_completion(self):
        for key,value in (('run_id','other'),('provenance','REAL_HTTP'),('completion','PENDING')):
            with self.subTest(key=key),tempfile.TemporaryDirectory() as root:
                sink=JsonlEvidence(root);c=self.coordinator(sink=sink)
                c.accept(summary(),self.binding);c.finish()
                self.assertEqual(check_sidecar(sink.directory)['integrity'],'CONSISTENT_OFFLINE_SIDECAR')
                path=sink.directory/'manifest.json';manifest=json.loads(path.read_text());manifest[key]=value
                path.write_text(json.dumps(manifest))
                self.assertEqual(check_sidecar(sink.directory)['integrity'],'EVIDENCE_INCOMPLETE')

    def test_memory_correlation_is_not_verified_completion(self):
        c=EvidenceCoordinator(self.binding)
        self.supervisor.attach_evidence(c);self.supervisor.register_actions()
        c.accept(summary(),self.binding);c.finish();self.supervisor.revoke();self.clean()
        with self.assertRaises(InvalidInput):self.supervisor.prepare_next(Mode.GOOD)

    def test_sidecar_tamper_after_stopped_blocks_reset(self):
        controller=self.trusted_controller_fixture()
        with tempfile.TemporaryDirectory() as root:
            sink=JsonlEvidence(root);c=EvidenceCoordinator(self.binding,sink=sink)
            c.capture_controller(controller)
            self.supervisor.attach_evidence(c);self.supervisor.register_actions()
            c.accept(summary(),self.binding);c.finish();self.supervisor.revoke()
            self.assertEqual(self.clean()['state'],'STOPPED')
            path=sink.directory/'manifest.json';manifest=json.loads(path.read_text());manifest['audit_gap']=True
            path.write_text(json.dumps(manifest))
            with self.assertRaises(InvalidInput):self.supervisor.prepare_next(Mode.GOOD)
            self.assertFalse(self.client.invalidated)

    def test_report_audit_markers_fail_even_with_updated_hash(self):
        import hashlib
        for value in (None,0,'false','MISSING',True):
            with self.subTest(value=value),tempfile.TemporaryDirectory() as root:
                sink=JsonlEvidence(root);c=self.coordinator(sink=sink)
                c.accept(summary(),self.binding);c.finish()
                path=sink.directory/'report.json';report=json.loads(path.read_text())
                if value=='MISSING':report.pop('audit_gap')
                else:report['audit_gap']=value
                path.write_text(json.dumps(report))
                path=sink.directory/'manifest.json';manifest=json.loads(path.read_text())
                manifest['report_sha256']=hashlib.sha256(json.dumps(report,sort_keys=True).encode()).hexdigest()
                path.write_text(json.dumps(manifest))
                self.assertEqual(check_sidecar(sink.directory)['integrity'],'EVIDENCE_INCOMPLETE')

    def test_manifest_write_failure_after_revoke_blocks_reset(self):
        with tempfile.TemporaryDirectory() as root:
            sink=JsonlEvidence(root);c=EvidenceCoordinator(self.binding,sink=sink)
            self.supervisor.attach_evidence(c);self.supervisor.register_actions()
            c.accept(summary(),self.binding);self.supervisor.revoke()
            sink.finish=lambda *args:(_ for _ in ()).throw(OSError('secret'))
            self.assertTrue(c.finish()['audit_gap'])
            self.assertEqual(c.completion_status(),'AUDIT_FAILED')
            self.assertEqual(self.clean()['state'],'FAILED')
            with self.assertRaises(InvalidInput):self.supervisor.prepare_next(Mode.GOOD)
            self.assertEqual(self.events,['client','service'])

    def test_completion_io_is_outside_supervisor_lock(self):
        controller=self.trusted_controller_fixture()
        with tempfile.TemporaryDirectory() as root:
            sink=JsonlEvidence(root);c=EvidenceCoordinator(self.binding,sink=sink)
            c.capture_controller(controller)
            self.supervisor.attach_evidence(c);self.supervisor.register_actions()
            c.accept(summary(),self.binding);c.finish();self.supervisor.revoke()
            from p3_core.coordination import check_sidecar as original
            def checked(*args,**kwargs):
                acquired=self.supervisor._lock.acquire(blocking=False)
                self.assertTrue(acquired)
                if acquired:self.supervisor._lock.release()
                return original(*args,**kwargs)
            with patch('p3_core.coordination.check_sidecar',side_effect=checked):
                self.assertEqual(self.clean()['state'],'STOPPED')
                self.supervisor.prepare_next(Mode.GOOD)

    def test_reset_failure_at_endpoint_barrier_has_no_creation(self):
        self.verified_sidecar_fixture()
        from p3_core.mock_api.core import Fixture
        self.supervisor.revoke();self.clean()
        entered=threading.Event();release=threading.Event();old_status=self.client.status
        def status():entered.set();self.assertTrue(release.wait(2));return old_status()
        self.client.status=status;results=[]
        def run():
            try:self.supervisor.prepare_next(Mode.GOOD);results.append('returned')
            except InvalidInput:results.append('rejected')
        with patch('p3_core.mock_api.core.Fixture',wraps=Fixture) as created:
            worker=threading.Thread(target=run);worker.start()
            try:
                self.assertTrue(entered.wait(1));self.supervisor._evidence_failed()
            finally:release.set();worker.join(2)
            self.assertFalse(worker.is_alive());self.assertEqual(created.call_count,0)
        self.assertEqual(results,['rejected']);self.assertFalse(self.client.invalidated)
        self.assertEqual(self.supervisor.binding.generation,1)
        self.assertEqual(self.supervisor.poll()['reset_commit_count'],0)

    def test_prepared_candidate_failure_before_commit_never_published(self):
        self.verified_sidecar_fixture()
        from p3_core.mock_api.core import Fixture
        self.supervisor.revoke();self.clean()
        prepare=getattr(FixtureManager,'prepare',FixtureManager.reset)
        entered=threading.Event();release=threading.Event();outcomes=[]
        def blocked(mode):
            fixture=prepare(mode);entered.set();self.assertTrue(release.wait(2));return fixture
        def run():
            try:self.supervisor.prepare_next(Mode.GOOD);outcomes.append('returned')
            except InvalidInput:outcomes.append('rejected')
        with patch.object(FixtureManager,'prepare',side_effect=blocked,create=True),patch('p3_core.mock_api.core.Fixture',wraps=Fixture) as created:
            worker=threading.Thread(target=run);worker.start()
            try:
                self.assertTrue(entered.wait(1));self.supervisor._evidence_failed()
            finally:release.set();worker.join(2)
            self.assertFalse(worker.is_alive());self.assertEqual(created.call_count,1)
        self.assertEqual(outcomes,['rejected']);self.assertFalse(self.client.invalidated)
        report=self.supervisor.poll()
        self.assertEqual(report['reset_commit_count'],0);self.assertFalse(report['next_fixture_available'])

    def test_commit_wins_then_failure_records_order_and_stops(self):
        self.verified_sidecar_fixture()
        from p3_core.mock_api.core import Fixture
        self.supervisor.revoke();self.clean()
        def audit(event):
            if event['kind']=='fixture_committed':self.supervisor._evidence_failed()
        self.supervisor.evidence=audit
        with patch('p3_core.mock_api.core.Fixture',wraps=Fixture) as created:
            with self.assertRaises(InvalidInput):self.supervisor.prepare_next(Mode.GOOD)
            self.assertEqual(created.call_count,1)
        report=self.supervisor.poll()
        self.assertEqual(report['reset_commit_count'],1)
        self.assertLess(report['reset_commit_sequence'],report['failure_sequence'])
        self.assertIsNotNone(report['committed_fixture_id'])
        self.assertFalse(report['next_fixture_available']);self.assertEqual(report['state'],'FAILED')
        with self.assertRaises(InvalidInput):self.supervisor.prepare_next(Mode.GOOD)

    def test_two_reset_threads_only_one_actual_creation_and_commit(self):
        self.verified_sidecar_fixture()
        from p3_core.mock_api.core import Fixture
        self.supervisor.revoke();self.clean();barrier=threading.Barrier(3);results=[]
        def run():
            barrier.wait()
            try:self.supervisor.prepare_next(Mode.GOOD);results.append('returned')
            except InvalidInput:results.append('rejected')
        with patch('p3_core.mock_api.core.Fixture',wraps=Fixture) as created:
            workers=[threading.Thread(target=run) for _ in range(2)]
            for worker in workers:worker.start()
            barrier.wait()
            for worker in workers:worker.join(2);self.assertFalse(worker.is_alive())
            self.assertEqual(created.call_count,1)
        self.assertCountEqual(results,['returned','rejected'])
        self.assertEqual(self.supervisor.poll()['reset_commit_count'],1)

    def test_precommit_audit_failure_has_zero_commits_and_no_retry(self):
        self.verified_sidecar_fixture()
        from p3_core.mock_api.core import Fixture
        self.supervisor.revoke();self.clean()
        def audit(event):
            if event['kind']=='fixture_prepared':raise OSError('secret')
        self.supervisor.evidence=audit
        with patch('p3_core.mock_api.core.Fixture',wraps=Fixture) as created:
            with self.assertRaises(InvalidInput):self.supervisor.prepare_next(Mode.GOOD)
            with self.assertRaises(InvalidInput):self.supervisor.prepare_next(Mode.GOOD)
            self.assertEqual(created.call_count,1)
        self.assertEqual(self.supervisor.poll()['reset_commit_count'],0)
        self.assertFalse(self.client.invalidated)

    def test_endpoint_exception_has_no_creation_and_no_retry(self):
        self.verified_sidecar_fixture()
        from p3_core.mock_api.core import Fixture
        self.supervisor.revoke();self.clean()
        self.client.status=lambda:(_ for _ in ()).throw(ValueError('secret'))
        with patch('p3_core.mock_api.core.Fixture',wraps=Fixture) as created:
            for _ in range(2):
                with self.assertRaises(InvalidInput):self.supervisor.prepare_next(Mode.GOOD)
            self.assertEqual(created.call_count,0)
        self.assertEqual(self.supervisor.poll()['reset_commit_count'],0)

    def test_reset_old_generation_wrong_instance_and_repeat_failure(self):
        self.verified_sidecar_fixture()
        self.supervisor.revoke();self.clean();fixture=self.supervisor.prepare_next(Mode.GOOD)
        with self.assertRaises(InvalidInput):self.supervisor.revoke(replace(self.binding,generation=0))
        with self.assertRaises(InvalidInput):Supervisor(replace(self.binding,fixture_instance_id=fixture.fixture_instance_id),self.client,self.service)
        self.supervisor._evidence_failed();first=self.supervisor.poll()['failure_sequence']
        self.supervisor._evidence_failed()
        self.assertEqual(self.supervisor.poll()['failure_sequence'],first)
        with self.assertRaises(InvalidInput):self.supervisor.prepare_next(Mode.GOOD)
        self.assertEqual(self.supervisor.poll()['reset_commit_count'],1)

    def test_reset_preparation_audit_and_invalidation_outside_gate(self):
        self.verified_sidecar_fixture()
        self.supervisor.revoke();self.clean();observed=[]
        prepare=FixtureManager.prepare
        def outside(name):
            acquired=self.supervisor._lock.acquire(blocking=False)
            self.assertTrue(acquired)
            if acquired:self.supervisor._lock.release()
            observed.append(name)
        def factory(mode):outside('prepare');return prepare(mode)
        def audit(event):outside(event['kind'])
        def invalidate():outside('invalidate');self.client.invalidated=True
        self.supervisor.evidence=audit;self.client.invalidate=invalidate
        with patch.object(FixtureManager,'prepare',side_effect=factory):
            self.supervisor.prepare_next(Mode.GOOD)
        self.assertEqual(observed,['prepare','fixture_prepared','invalidate','fixture_committed'])

    def test_postcommit_audit_write_failure_preserves_commit_fact(self):
        self.verified_sidecar_fixture()
        from p3_core.mock_api.core import Fixture
        self.supervisor.revoke();self.clean()
        def audit(event):
            if event['kind']=='fixture_committed':raise OSError('secret')
        self.supervisor.evidence=audit
        with patch('p3_core.mock_api.core.Fixture',wraps=Fixture) as created:
            with self.assertRaises(InvalidInput):self.supervisor.prepare_next(Mode.GOOD)
            self.assertEqual(created.call_count,1)
        report=self.supervisor.poll()
        self.assertEqual(report['reset_commit_count'],1)
        self.assertLess(report['reset_commit_sequence'],report['failure_sequence'])
        self.assertFalse(report['next_fixture_available'])
        self.assertNotIn('secret',json.dumps(report))

    def test_wrong_prepared_instance_cannot_commit_or_retry(self):
        self.verified_sidecar_fixture()
        from p3_core.mock_api.core import Fixture
        self.supervisor.revoke();self.clean()
        candidate=replace(FixtureManager.prepare(Mode.GOOD),fixture_instance_id=self.binding.fixture_instance_id)
        with patch.object(FixtureManager,'prepare',return_value=candidate) as prepared:
            for _ in range(2):
                with self.assertRaises(InvalidInput):self.supervisor.prepare_next(Mode.GOOD)
            self.assertEqual(prepared.call_count,1)
        self.assertEqual(self.supervisor.poll()['reset_commit_count'],0)
        self.assertFalse(self.client.invalidated)

    def service_fixture(self):
        # Reuse the existing deterministic fake connection, never its listener.
        import test_c3_preflight as helpers
        helper=helpers.C3Tests();helper.setUp();self.addCleanup(helper.doCleanups)
        service,connection,clock=helper.component()
        return helper,service,connection,clock

    def test_service_handoff_preserves_each_connection(self):
        helper,service,connection,_=self.service_fixture();records=[]
        service.attach_summary_consumer(records.append)
        helper.handle(service,connection);helper.handle(service,type(connection)())
        self.assertEqual(len(records),2)
        self.assertEqual([r['summary_sequence'] for r in records],[1,2])
        self.assertNotEqual(records[0]['connection_id'],records[1]['connection_id'])
        self.assertEqual(records[0]['action_id'],'action_'+'b'*32)
        with self.assertRaises(InvalidInput):service.attach_summary_consumer(records.append)

    def test_blocked_summary_sink_does_not_block_revocation(self):
        helper,service,connection,_=self.service_fixture()
        entered=threading.Event();release=threading.Event()
        def consume(row):entered.set();release.wait(2)
        service.attach_summary_consumer(consume)
        worker=threading.Thread(target=lambda:helper.handle(service,connection));worker.start()
        try:
            self.assertTrue(entered.wait(1));service.revoke()
            self.assertTrue(service.lifecycle_status()['revoked'])
            self.assertFalse(service.lifecycle_status()['clean'])
        finally:release.set();worker.join(2)
        self.assertFalse(worker.is_alive());self.assertTrue(service.lifecycle_status()['clean'])

    def test_service_handoff_failure_prevents_next_send(self):
        helper,service,connection,_=self.service_fixture()
        service.attach_summary_consumer(lambda row:(_ for _ in ()).throw(OSError('SECRET_FAILURE')))
        helper.handle(service,connection)
        second=type(connection)();helper.handle(service,second)
        self.assertEqual(second.sent,0);self.assertTrue(service.lifecycle_status()['failed'])
        self.assertNotIn('SECRET_FAILURE',json.dumps(service.last_connection))

    def test_cleanup_audit_must_complete_before_reset(self):
        self.verified_sidecar_fixture()
        self.supervisor.revoke();self.client.clean=self.service.clean=True
        entered=threading.Event();release=threading.Event()
        self.supervisor.evidence=lambda event:(entered.set(),release.wait(2))
        worker=threading.Thread(target=self.supervisor.poll);worker.start()
        try:
            self.assertTrue(entered.wait(1))
            with self.assertRaises(InvalidInput):self.supervisor.prepare_next(Mode.GOOD)
            self.assertEqual(self.supervisor.poll()['state'],'STOPPING')
        finally:release.set();worker.join(2)
        self.assertEqual(self.supervisor.poll()['state'],'STOPPED')


if __name__=='__main__':unittest.main()

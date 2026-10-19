"""NO_NETWORK_SIMULATION. Boundary stubs are NOT permission or HTTP evidence."""
import socket
import threading
import json
from dataclasses import replace
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from p3_core.experiments import configuration, synthetic_registry
from p3_core.http.contract import HttpConfig
from p3_core.http.live import FixtureBinding, InstanceStatus, credential_binding_digest, AuthorizedHttpRun
from p3_core.http.machine import SimulationRun
from p3_core.http.transport import MemoryTransport
from p3_core.evidence import MemoryEvidence
from p3_core.models import InvalidInput
from p3_core.http.protocol import build_request
from p3_core.mock_api import FixtureManager, Mode
from p3_core.mock_api.service import AuthorizedService


class C3Tests(unittest.TestCase):
    def setUp(self):
        for name in ('socket','create_connection','getaddrinfo'):
            guard=patch.object(socket,name,side_effect=AssertionError('NETWORK_FORBIDDEN'))
            guard.start();self.addCleanup(guard.stop)
        self.fixture=FixtureManager.reset(Mode.GOOD)
        self.raw=configuration(self.fixture);self.cfg=HttpConfig.parse(self.raw)
        self.registry=synthetic_registry(self.raw)
        self.binding=FixtureBinding(self.fixture.fixture_instance_id,self.cfg.scope_digest,'unit-supervisor',
                                   InstanceStatus(),credential_binding_digest(self.fixture.credential_bindings()))

    def test_revoke_between_final_check_and_send_blocks_response(self):
        service=AuthorizedService(self.cfg,self.registry,self.fixture,self.binding,wall_clock=lambda:1)
        capture={}
        class FakeServer:
            def __init__(self,address,handler): capture['handler']=handler
        # Isolated handler control-flow test: no registration is relabelled, no
        # permission file exists, and TCPServer is replaced before start is called.
        with patch('p3_core.mock_api.service.socketserver.TCPServer',FakeServer), \
             patch.object(self.registry,'snapshot',return_value=SimpleNamespace(synthetic=False,valid_until=100)):
            service.start()
        snap=self.registry.snapshot(self.cfg,1,simulation=True)
        wire=build_request(self.cfg,snap,self.cfg.candidates[0],'action_'+'a'*32,
                           self.fixture.credential_bindings()['fixture/alice']).wire
        class FakeConnection:
            writes=0
            def setblocking(self,value): pass
            def close(self): pass
            def settimeout(self,value):
                if getattr(self,'read',False): service.revoke()
            def recv(self,size): self.read=True;return wire
            def sendall(self,data): self.writes+=1
            def send(self,data): self.writes+=1;return len(data)
        connection=FakeConnection()
        def ready(connection,writing,deadline):
            if writing: service.revoke()
            return True
        # Same final-check boundary, readiness hook replaces legacy settimeout hook.
        with patch.object(service,'_wait_ready',side_effect=ready):
            capture['handler'](connection,('127.0.0.1',1234),None)
        self.assertEqual(connection.writes,0,'response started after effective revocation')
        self.assertEqual(service.last_connection['reason'],'REVOKED')

    def component(self):
        clock=SimpleNamespace(now=1.0)
        service=AuthorizedService(self.cfg,self.registry,self.fixture,self.binding,
                                  wall_clock=lambda:clock.now,clock=lambda:clock.now)
        # Branch fixture only. Not a permit, not persisted, not usable for listener
        # start (which independently requires registry.snapshot(simulation=False)).
        service.snapshot=SimpleNamespace(synthetic=False,valid_until=100)
        service._permit_deadline=100
        snap=self.registry.snapshot(self.cfg,1,simulation=True)
        wire=build_request(self.cfg,snap,self.cfg.candidates[0],'action_'+'b'*32,
                          self.fixture.credential_bindings()['fixture/alice']).wire
        class Connection:
            def __init__(self): self.sent=0;self.closed=False;self.calls=0;self.nonblocking=False
            def setblocking(self,value): self.nonblocking=not value
            def recv(self,size): return wire
            def send(self,data):
                assert self.nonblocking
                self.calls+=1;self.sent+=len(data);return len(data)
            def close(self): self.closed=True
        return service,Connection(),clock

    def handle(self,service,connection,ready=None):
        with patch.object(service,'_wait_ready',side_effect=ready or (lambda *args:True)):
            service._handle_connection(connection)

    def test_service_revoke_during_wait_does_not_block(self):
        service,connection,_=self.component();waiting=threading.Event();release=threading.Event()
        def ready(c,writing,deadline):
            if writing:
                waiting.set();self.assertTrue(release.wait(2))
            return True
        worker=threading.Thread(target=lambda:self.handle(service,connection,ready))
        worker.start()
        revoked=threading.Event()
        revoker=threading.Thread(target=lambda:(service.revoke(),revoked.set()))
        try:
            self.assertTrue(waiting.wait(2))
            revoker.start()
            self.assertTrue(revoked.wait(1),'revoke waited on readiness I/O')
        finally:
            release.set();worker.join(2)
            if revoker.ident is not None:revoker.join(2)
        self.assertFalse(worker.is_alive());self.assertEqual(connection.sent,0)
        self.assertTrue(connection.closed);self.assertEqual(service.last_connection['reason'],'REVOKED')

    def test_service_partial_send_then_effective_revoke(self):
        service,connection,_=self.component()
        def send(data): connection.sent+=1;return 1
        connection.send=send
        def ready(c,writing,deadline):
            if writing and connection.sent: service.revoke()
            return True
        self.handle(service,connection,ready)
        r=service.last_connection
        self.assertEqual(r['sent_bytes'],1)
        self.assertLess(r['first_send_sequence'],r['revoke_effective_sequence'])
        self.assertEqual(r['last_send_sequence'],r['first_send_sequence'])

    def test_service_send_and_revoke_have_total_gate_order(self):
        service,connection,_=self.component();requested=threading.Event();effective=threading.Event()
        def revoke(): requested.set();service.revoke();effective.set()
        threads=[]
        def send(data):
            t=threading.Thread(target=revoke);threads.append(t);t.start()
            self.assertTrue(requested.wait(2));self.assertFalse(effective.is_set())
            connection.sent+=1;return 1
        connection.send=send
        def ready(c,writing,deadline):
            if connection.sent: self.assertTrue(effective.wait(2))
            return True
        self.handle(service,connection,ready)
        for t in threads:t.join(2)
        r=service.last_connection
        self.assertEqual(r['sent_bytes'],1);self.assertLess(r['last_send_sequence'],r['revoke_effective_sequence'])

    def test_service_deadline_at_write_blocks_send(self):
        service,c,clock=self.component()
        def ready(c,writing,deadline):
            if writing:clock.now=deadline
            return True
        self.handle(service,c,ready)
        self.assertEqual(c.sent,0);self.assertEqual(service.last_connection['reason'],'TIMEOUT')

    def test_service_expiry_partial_send_keeps_bytes(self):
        service,c,clock=self.component()
        def send(data): clock.now=100;c.sent=1;return 1
        c.send=send;self.handle(service,c)
        self.assertEqual(service.last_connection['sent_bytes'],1)
        self.assertEqual(service.last_connection['reason'],'AUTHORIZATION_INVALID')

    def test_service_wouldblock_wait_is_outside_gate(self):
        service,c,_=self.component();attempts=[]
        def send(data):
            attempts.append(1)
            if len(attempts)==1:raise BlockingIOError()
            c.sent+=len(data);return len(data)
        c.send=send;self.handle(service,c)
        self.assertEqual(len(attempts),2);self.assertEqual(service.last_connection['reason'],'RESPONSE_SENT')
        self.assertEqual(service.last_connection['sent_bytes'],c.sent)

    def test_service_zero_send_and_exception_close_without_raw_text(self):
        for outcome in (0,OSError('PRIVATE-ERROR'),TimeoutError('PRIVATE-ERROR')):
            service,c,_=self.component()
            def send(data):
                if isinstance(outcome,Exception):raise outcome
                return outcome
            c.send=send;self.handle(service,c)
            self.assertTrue(c.closed);self.assertEqual(service.last_connection['sent_bytes'],0)
            self.assertNotIn('PRIVATE-ERROR',json.dumps(service.last_connection))

    def test_service_close_failure_visible_and_no_more_send(self):
        service,c,_=self.component()
        def close(): raise OSError('PRIVATE-CLOSE')
        c.close=close;self.handle(service,c)
        self.assertTrue(service.cleanup_failed);self.assertTrue(service.last_connection['cleanup_failed'])
        self.assertNotIn('PRIVATE',json.dumps(service.last_connection))
        with self.assertRaises(InvalidInput): service._check()

    def test_service_missing_and_synthetic_permission_never_construct_server(self):
        service=AuthorizedService(self.cfg,self.registry,self.fixture,self.binding)
        with self.assertRaises(InvalidInput):service._check()
        with patch('p3_core.mock_api.service.socketserver.TCPServer') as factory:
            with self.assertRaises(InvalidInput): service.start()
            factory.assert_not_called()

    def test_service_binding_instance_and_old_credentials_fail_closed(self):
        for mutation in ('instance','credentials','scope','invalidated'):
            service,c,_=self.component()
            if mutation=='instance':service.binding=replace(self.binding,instance_id='wrong')
            elif mutation=='credentials':service.binding=replace(self.binding,credential_digest='wrong')
            elif mutation=='scope':service.binding=replace(self.binding,scope_digest='wrong')
            else:service.binding.status.invalidate()
            self.handle(service,c);self.assertEqual(c.sent,0)
            self.assertNotEqual(service.last_connection['reason'],'RESPONSE_SENT')

    def test_service_wall_rollback_cannot_extend_monotonic_permission(self):
        service,c,clock=self.component();service.wall_clock=lambda:1
        def ready(c,writing,deadline):
            if writing:clock.now=100
            return True
        self.handle(service,c,ready)
        self.assertEqual(service.last_connection['reason'],'AUTHORIZATION_INVALID');self.assertEqual(c.sent,0)

    def test_live_missing_registry_and_synthetic_material_stop_before_transport(self):
        for registry in (None,self.registry):
            r=AuthorizedHttpRun(self.raw,registry,binding=self.binding,credentials=self.fixture.credential_bindings())
            with patch('p3_core.http.live._SocketTransport') as transport:
                r.start();r.step();transport.assert_not_called()
            self.assertEqual(r.state,'STOPPED');self.assertEqual(r.counts['request_count'],0)

    def test_live_rejects_changed_target_without_creating_transport(self):
        raw=dict(self.raw,target=dict(scheme='http',host='192.0.2.1',port=8765))
        r=AuthorizedHttpRun(raw,self.registry,binding=self.binding,credentials=self.fixture.credential_bindings())
        with patch('p3_core.http.live._SocketTransport') as t:r.start();r.step();t.assert_not_called()
        self.assertEqual(r.state,'STOPPED')

    def test_first_positive_counter_hook_once_for_partial_model_io(self):
        # Test the live accounting method on the shared gate in memory, never
        # initialize a live permit or persist this instrumentation as real evidence.
        class Discard:
            def open(self,*args): pass
            def emit(self,*args): pass
            def finish(self,*args): pass
        r=SimulationRun(self.raw,self.registry,credentials=self.fixture.credential_bindings(),evidence=Discard())
        r.start();t=MemoryTransport(writes=[BlockingIOError(),1,1])
        with patch.object(r,'_first_send_locked',side_effect=lambda:AuthorizedHttpRun._first_send_locked(r)):
            r.step(t);r.step();r.step();r.step()
            self.assertEqual(r.counts['request_count'],0)
            r.step();self.assertEqual(r.counts['request_count'],1)
            r.step();self.assertEqual(r.counts['request_count'],1)
            r.revoke();r.step();self.assertEqual(r.counts['request_count'],1)
        self.assertEqual(r.counts['model_request_count'],0)

    def test_service_timeout_read_and_partial_write_close(self):
        for partial in (False,True):
            service,c,clock=self.component()
            if partial:
                def send(data):c.sent+=1;return 1
                c.send=send
            def ready(c,writing,deadline):
                if (not partial) or c.sent:clock.now=deadline
                return True
            self.handle(service,c,ready)
            self.assertEqual(service.last_connection['reason'],'TIMEOUT')
            self.assertEqual(service.last_connection['sent_bytes'],int(partial));self.assertTrue(c.closed)

    def test_service_revoke_idempotent_no_reopen(self):
        service,c,_=self.component();service.revoke();seq=service.revoke_effective_sequence
        service.revoke();self.assertEqual(service.revoke_effective_sequence,seq)
        self.handle(service,c)
        self.assertEqual(c.sent,0);self.assertTrue(c.closed)
        self.assertEqual(service.last_connection['reason'],'REVOKED')

    def test_service_listener_close_failure_is_recorded(self):
        service,_,_=self.component()
        class Broken:
            def server_close(self):raise OSError('PRIVATE-SERVER')
        service._server=Broken()
        with self.assertRaises(InvalidInput) as caught:service.close()
        self.assertTrue(service.cleanup_failed);self.assertNotIn('PRIVATE',str(caught.exception))

    def test_service_invalidation_during_wait_blocks_write(self):
        service,c,_=self.component()
        def ready(c,writing,deadline):
            if writing:self.binding.status.invalidate()
            return True
        self.handle(service,c,ready)
        self.assertEqual(c.sent,0);self.assertEqual(service.last_connection['reason'],'FIXTURE_BINDING_INVALID')

    def test_service_owner_rejection_does_not_send(self):
        service,c,_=self.component();self.handle(service,c)
        errors=[]
        def other():
            try:service._handle_connection(c)
            except InvalidInput as e:errors.append(str(e))
        t=threading.Thread(target=other);t.start();t.join(2)
        self.assertEqual(errors,['SINGLE_IO_OWNER_REQUIRED'])

    def test_budget_before_first_send_blocks_memory_dispatch(self):
        clock=SimpleNamespace(now=0)
        r=SimulationRun(self.raw,self.registry,credentials=self.fixture.credential_bindings(),clock=lambda:clock.now)
        r.start();t=MemoryTransport();r.step(t);r.step();r.step();clock.now=90;r.step()
        self.assertEqual(r.reason,'BUDGET_EXHAUSTED');self.assertEqual(r.counts['request_count'],0)
        self.assertEqual(r.counts['model_request_count'],0)

    def test_service_close_wait_does_not_hold_revoke_gate(self):
        service,c,_=self.component();closing=threading.Event();release=threading.Event()
        def close():closing.set();self.assertTrue(release.wait(2));c.closed=True
        c.close=close
        worker=threading.Thread(target=lambda:self.handle(service,c));worker.start()
        revoked=threading.Event()
        revoker=threading.Thread(target=lambda:(service.revoke(),revoked.set()))
        try:
            self.assertTrue(closing.wait(2));revoker.start()
            self.assertTrue(revoked.wait(1),'revoke waited on resource close')
        finally:
            release.set();worker.join(2)
            if revoker.ident is not None:revoker.join(2)
        self.assertFalse(worker.is_alive());self.assertTrue(c.closed)

    def test_planner_target_override_is_denied_without_io(self):
        class Planner:
            def plan(self,candidates):return [dict(candidates[0].to_dict(),url='http://unapproved')]
        r=SimulationRun(self.raw,self.registry,credentials=self.fixture.credential_bindings())
        r.start(Planner());t=MemoryTransport();r.step(t)
        self.assertEqual(r.state,'STOPPED');self.assertEqual(t.calls,[])

    def test_audit_failure_cannot_confirm_response(self):
        class Broken(MemoryEvidence):
            def emit(self,event):
                if event['kind']=='response_evidence':raise OSError('PRIVATE-AUDIT')
                super().emit(event)
        from p3_core.mock_api.adapter import ServiceAdapter
        r=SimulationRun(self.raw,self.registry,credentials=self.fixture.credential_bindings(),evidence=Broken())
        r.start();t=MemoryTransport();r.step(t)
        t.chunks.append(ServiceAdapter(self.fixture,8765).handle_bytes(r._active['request'].wire))
        for _ in range(10):r.step()
        report=r.finalize()
        self.assertEqual(report['reason'],'AUDIT_ERROR')
        self.assertTrue(all(row['simulated_conclusion']=='INCONCLUSIVE' for row in report['checks']))
        self.assertNotIn('PRIVATE-AUDIT',json.dumps(report))


if __name__=='__main__': unittest.main()

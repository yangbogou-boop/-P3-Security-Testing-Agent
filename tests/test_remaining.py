"""NO_NETWORK_SIMULATION: no socket creation, no integration approval claim."""
import contextlib
import io
import json
from pathlib import Path
import socket
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from p3_core.experiments import configuration, synthetic_registry, run_scenario, compare_strategies
from p3_core.delivery import main, integration_plan
from p3_core.http.audit import verify_run, BoundedEvidence, inspect_dispatch_prefix
from p3_core.http.contract import HttpConfig
from p3_core.http.live import AuthorizedHttpRun, FixtureBinding, InstanceStatus, _SocketTransport, credential_binding_digest
from p3_core.http.machine import SimulationRun
from p3_core.http.protocol import build_request, ResponseParser
from p3_core.http.strategies import EvidenceSelection, FixedSelection
from p3_core.http.transport import MemoryTransport
from p3_core.mock_api import FixtureManager, Mode
from p3_core.mock_api.adapter import ServiceAdapter
from p3_core.mock_api.service import AuthorizedService
from p3_core.models import InvalidInput
from p3_core.evidence import MemoryEvidence


class RemainingTests(unittest.TestCase):
    def setUp(self):
        for name in ('socket','create_connection','getaddrinfo'):
            guard=patch.object(socket,name,side_effect=AssertionError('NETWORK_FORBIDDEN'))
            guard.start();self.addCleanup(guard.stop)
        self.fixture=FixtureManager.reset(Mode.GOOD)
        self.raw=configuration(self.fixture);self.cfg=HttpConfig.parse(self.raw)
        self.registry=synthetic_registry(self.raw)
        self.binding=FixtureBinding(self.fixture.fixture_instance_id,self.cfg.scope_digest,'unit-supervisor',InstanceStatus(),
                                    credential_binding_digest(self.fixture.credential_bindings()))

    def model(self, **kwargs):
        return SimulationRun(self.raw,self.registry,credentials=self.fixture.credential_bindings(),**kwargs)

    def request(self):
        snap=self.registry.snapshot(self.cfg,1,simulation=True)
        return build_request(self.cfg,snap,self.cfg.candidates[0],'action_'+'a'*32,
                             self.fixture.credential_bindings()['fixture/alice']).wire

    def test_good_all_six_fixed(self):
        r=run_scenario()
        self.assertEqual(r['report']['state'],'COMPLETED')
        self.assertEqual(r['metrics']['coverage']['numerator'],6)
        self.assertEqual(r['metrics']['observed_model_dispatches'],6)
        self.assertEqual(r['metrics']['cost']['actual_requests'],0)

    def test_good_dynamic_controls_resolve(self):
        r=run_scenario(strategy='dynamic')
        self.assertEqual(r['metrics']['coverage']['numerator'],6)
        self.assertEqual(len(set(r['order'])),6)
        self.assertNotEqual(r['order'],run_scenario()['order'])

    def test_three_defects_both_strategies(self):
        for mode in ('auth','bola','rbac'):
            for strategy in ('fixed','dynamic'):
                with self.subTest(mode=mode,strategy=strategy):
                    r=run_scenario(mode,strategy)
                    self.assertEqual(r['metrics']['detected']['numerator'],1)
                    self.assertEqual(r['metrics']['false_confirmations'],0)
                    self.assertEqual(r['metrics']['unauthorized_dispatches'],0)
                    self.assertEqual(r['metrics']['coverage']['numerator'],6)

    def test_faults_do_not_confirm_leaks(self):
        for fault in ('malformed','truncated','redirect','timeout','transport','audit','empty','server_error','duplicate_length'):
            with self.subTest(fault=fault):
                r=run_scenario(fault=fault)
                self.assertEqual(r['report']['state'],'STOPPED')
                self.assertFalse(any(c['simulated_conclusion']=='FAIL' for c in r['report']['checks']))

    def test_disk_evidence_integrity_and_no_tokens(self):
        with tempfile.TemporaryDirectory() as root:
            r=run_scenario(output=root)
            self.assertEqual(r['integrity']['integrity'],'VERIFIED')
            files=list(Path(root).rglob('*.json*'))
            text=''.join(p.read_text(encoding='utf-8') for p in files)
            self.assertNotIn('mock_',text)
            self.assertIn('response_evidence',text)
            self.assertIn('ALICE_PROFILE_CANARY',text)
            self.assertTrue(all(c['conclusion']=='INCONCLUSIVE' and c['execution']=='NOT_EXECUTED' for c in r['report']['checks']))

    def test_corrupt_evidence_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            r=run_scenario(output=root);directory=Path(root)/r['report']['run_id']
            p=directory/'events.jsonl';p.write_bytes(p.read_bytes().replace(b'prepared',b'PREPARED',1))
            self.assertEqual(verify_run(directory)['integrity'],'INCOMPLETE_OR_INVALID')

    def test_missing_manifest_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            self.assertEqual(verify_run(root)['integrity'],'INCOMPLETE_OR_INVALID')

    def test_strategy_repeatable(self):
        self.assertEqual(run_scenario(strategy='dynamic')['order'],run_scenario(strategy='dynamic')['order'])

    def test_strategy_evidence_changes_next_choice(self):
        s=EvidenceSelection();c=self.cfg.candidates
        first=s.choose(c,{})
        negative=next(x for x in c if x.check_id==first)
        self.assertEqual(s.choose(c,{first:'MISSING_CONTROL'}),negative.control_id)
        self.assertNotEqual(s.choose(c,{first:'CONFIRMED_DISCLOSURE'}),first)
        self.assertIsNone(s.choose(c,{x.check_id:'AUTHORIZED_CONTENT' for x in c}))

    def test_bad_selector_fails_closed(self):
        class Bad:
            strategy_id='bad-test'
            def choose(self,*args): return 'unregistered'
        r=self.model(selection=Bad());r.start();r.step(MemoryTransport())
        self.assertEqual(r.reason,'RUNTIME_ERROR');self.assertEqual(r.counts['model_request_count'],0)

    def test_synthetic_permission_cannot_start_live_run(self):
        r=AuthorizedHttpRun(self.raw,self.registry,binding=self.binding,credentials=self.fixture.credential_bindings())
        r.start();r.step();report=r.finalize()
        self.assertEqual(report['state'],'STOPPED');self.assertEqual(report['counts']['request_count'],0)

    def test_synthetic_permission_cannot_start_listener(self):
        service=AuthorizedService(self.cfg,self.registry,self.fixture,self.binding)
        with self.assertRaises(InvalidInput): service.start()
        self.assertIsNone(service._server)

    def test_binding_invalidation(self):
        self.binding.verify(self.cfg);self.binding.status.invalidate()
        with self.assertRaises(InvalidInput): self.binding.verify(self.cfg)

    def test_wrong_instance_credentials_do_not_prove_overdenial(self):
        self.binding.verify_credentials(self.fixture.credential_bindings())
        other=FixtureManager.reset(Mode.GOOD)
        with self.assertRaises(InvalidInput): self.binding.verify_credentials(other.credential_bindings())

    def test_adapter_exact_request(self):
        self.assertTrue(ServiceAdapter(self.fixture,8765).handle_bytes(self.request()).startswith(b'HTTP/1.1 200'))

    def test_adapter_rejects_header_and_target_mutations(self):
        wire=self.request()
        variants=[wire.replace(b'127.0.0.1',b'localhost'),wire.replace(b'/v1/profile',b'http://evil/v1/profile'),
                  wire.replace(b'/v1/profile',b'/v1/%70rofile'),wire.replace(b'/v1/profile',b'/v1/profile?extra=SECRET'),
                  wire.replace(b'\r\n\r\n',b'\r\nX-Unapproved: SECRET\r\n\r\n'),wire+b'SECRET',
                  wire.replace(b'\r\n\r\n',b'\r\nTransfer-Encoding: chunked\r\n\r\n')]
        for value in variants:
            with self.subTest(value_length=len(value)):
                with self.assertRaises(ValueError) as caught: ServiceAdapter(self.fixture,8765).handle_bytes(value)
                self.assertNotIn('SECRET',str(caught.exception))

    def test_audit_capacity_fails_closed(self):
        r=self.model(evidence=BoundedEvidence(MemoryEvidence(),200,100));r.start()
        self.assertEqual(r.reason,'AUDIT_ERROR');self.assertEqual(r.counts['request_count'],0)

    def test_cli_network_plan_pending(self):
        with contextlib.redirect_stdout(io.StringIO()) as out: code=main(['network-plan'])
        self.assertEqual(code,0);self.assertIn('PENDING_AUTHORIZATION',out.getvalue())
        self.assertTrue(all(x['status']=='PENDING_AUTHORIZATION' for x in integration_plan()['cases']))

    def test_cli_no_live_mode_or_raw_argument_echo(self):
        with contextlib.redirect_stderr(io.StringIO()) as out:
            with self.assertRaises(SystemExit): main(['live-SECRET'])
        self.assertNotIn('SECRET',out.getvalue())

    def test_cli_validate_does_not_grant_permission(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root)/'config.json';p.write_text(json.dumps(self.raw),encoding='utf-8')
            with contextlib.redirect_stdout(io.StringIO()) as out: code=main(['validate',str(p)])
            self.assertEqual(code,0);self.assertIn('PENDING_AUTHORIZATION',out.getvalue())

    def test_cli_duplicate_json_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root)/'config.json';p.write_text('{"secret":"SECRET","secret":2}',encoding='utf-8')
            with contextlib.redirect_stdout(io.StringIO()) as out: code=main(['validate',str(p)])
            self.assertEqual(code,2);self.assertNotIn('SECRET',out.getvalue())

    def test_comparison_records_actual_observations(self):
        with tempfile.TemporaryDirectory() as root:
            result=compare_strategies(root,1)
            self.assertEqual(len(result['runs']),12)
            self.assertTrue(all(r['metrics']['cost']['actual_requests']==0 for r in result['runs']))
            self.assertEqual(len({r['report']['run_id'] for r in result['runs']}),12)

    def test_report_tamper_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            r=run_scenario(output=root);directory=Path(root)/r['report']['run_id']
            p=directory/'report.json';p.write_bytes(p.read_bytes().replace(b'INCONCLUSIVE',b'PASS',1))
            self.assertEqual(verify_run(directory)['integrity'],'INCOMPLETE_OR_INVALID')

    def test_recovery_unknown_not_zero_and_no_replay(self):
        # Artificial audit records only; NOT a real permission or actual-send claim.
        records=[dict(provenance='ACTUAL_HTTP',kind='prepared',action_id='unit-action')]
        out=inspect_dispatch_prefix(records)
        self.assertEqual(out['send_unknown'],1);self.assertFalse(out['replay_allowed'])
        records.append(dict(provenance='ACTUAL_HTTP',kind='http_io',action_id='unit-action',dispatch_started=True))
        self.assertEqual(inspect_dispatch_prefix(records)['confirmed_sent'],1)
        self.assertEqual(inspect_dispatch_prefix(records+records)['confirmed_sent'],1)

    def test_cleanup_failure_is_explicit(self):
        class Broken(MemoryTransport):
            def close(self): raise OSError('SECRET')
        r=self.model();r.start();r.step(Broken());r.revoke();report=r.finalize()
        self.assertTrue(report['cleanup_failed']);self.assertNotIn('SECRET',json.dumps(report))

    def test_transport_constructor_has_no_io_and_requires_current_object(self):
        owner=SimpleNamespace(_active=None)
        t=_SocketTransport(owner,object())
        with self.assertRaises(InvalidInput): t.connect(('127.0.0.1',8765))
        self.assertIsNone(t._socket)

    def test_transport_methods_with_fake_socket_only(self):
        # Isolated byte-adapter test. No registry, no AuthorizedHttpRun, no real counters.
        request=SimpleNamespace(wire=b'approved-bytes')
        owner=SimpleNamespace(_owner=None,generation=1,state='RUNNING',snapshot=SimpleNamespace(synthetic=False),
                              _revoked=False,config=self.cfg)
        t=_SocketTransport(owner,request)
        owner._active=dict(request=request,transport=t,generation=1,offset=0)
        class FakeSocket:
            closed=False
            def setblocking(self,value): self.nonblocking=not value
            def connect_ex(self,address): self.address=address;return 0
            def getsockopt(self,*args): return 0
            def getpeername(self): return ('127.0.0.1',8765)
            def send(self,data): return min(3,len(data))
            def recv(self,size): return b'unit-response'
            def close(self): self.closed=True
        fake=FakeSocket()
        with patch('p3_core.http.live.socket.socket',return_value=fake) as factory:
            self.assertEqual(t.connect(('127.0.0.1',8765)),'CONNECTED')
            with patch('p3_core.http.live.select.select',return_value=([],[fake],[])):
                self.assertEqual(t.connected(),('127.0.0.1',8765))
            self.assertEqual(t.send(request.wire,0),3)
            with self.assertRaises(InvalidInput): t.send(b'changed',0)
            with self.assertRaises(InvalidInput): t.connect(('127.0.0.1',8765))
            owner._revoked=True
            with self.assertRaises(InvalidInput): t.send(request.wire,0)
            t.close();t.close();self.assertTrue(fake.closed);self.assertEqual(factory.call_count,1)

    def test_partial_send_then_revocation_retains_one_model_send(self):
        r=self.model();r.start();transport=MemoryTransport(writes=[1,1])
        r.step(transport);r.step();r.step();r.step()
        self.assertEqual(r.counts['model_request_count'],1)
        r.revoke();calls=len(transport.calls);r.step();r.step()
        self.assertEqual(r.counts['model_request_count'],1);self.assertEqual(r.counts['request_count'],0)
        self.assertFalse(any(c[0]=='send' for c in transport.calls[calls:]))

    def test_header_fact_survives_incomplete_body_without_verdict(self):
        p=ResponseParser(self.cfg.limits)
        p.feed(b'HTTP/1.1 200 OK\r\nContent-Length: 100\r\nContent-Type: application/json\r\n\r\n{')
        self.assertTrue(p.headers_observed);self.assertEqual(p.status_observed,200)
        self.assertFalse(p.finish().valid)

    def test_ambiguous_length_has_http_fact_but_invalid_evidence(self):
        p=ResponseParser(self.cfg.limits)
        p.feed(b'HTTP/1.1 200 OK\r\nContent-Length: 1\r\nContent-Length: 2\r\n\r\n{}')
        self.assertTrue(p.headers_observed);self.assertFalse(p.finish().valid)

    def test_header_timeout_model_never_claims_actual_execution(self):
        r=self.model();r.start();t=MemoryTransport()
        r.step(t);t.chunks.extend([b'HTTP/1.1 200 OK\r\nContent-Length: 5\r\n\r\n{',TimeoutError()])
        for _ in range(8): r.step()
        row=r.finalize()['checks'][0]
        self.assertTrue(row['headers_received']);self.assertEqual(row['execution'],'NOT_EXECUTED')
        self.assertEqual(row['conclusion'],'INCONCLUSIVE');self.assertEqual(row['transport_issue'],'TIMEOUT')


if __name__=='__main__': unittest.main()

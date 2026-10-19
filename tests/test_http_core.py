"""NO_NETWORK_SIMULATION: contract/model tests, NOT HTTP integration evidence."""
import copy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import socket
import tempfile
import threading
import unittest
from unittest.mock import patch

from p3_core.evidence import JsonlEvidence, MemoryEvidence
from p3_core.models import InvalidInput
from p3_core.http.contract import HttpConfig, HttpCheck, base_checks, matrix_expectation
from p3_core.http.authorization import ReviewedMaterial, LocalRegistry
from p3_core.http.protocol import build_request, ResponseParser, evaluate
from p3_core.http.machine import SimulationRun
from p3_core.http.transport import MemoryTransport
from p3_core.http.recovery import inspect_model_prefix


def config():
    return dict(mode='http-local', schema_version='http-core-v1',
                target=dict(scheme='http', host='127.0.0.1', port=8765),
                budget=dict(max_checks=8, logical_timeout_seconds=90, concurrency=1),
                limits=dict(header_bytes=1024, body_bytes=4096, response_bytes=5120),
                authorization=dict(authorization_id='test-auth', authorization_version='v1', registry_ref='test-registry'),
                fixture_instance_id='test-instance', contract_version='p3-http-v1', matrix_version='p3-matrix-v1',
                candidate_version='six-v1', fixture_version='fixture-v1', budget_version='trial-v1',
                candidates=[c.to_dict() for c in base_checks()])


def registry(raw=None, *, until=1000, revoked=False):
    cfg = HttpConfig.parse(raw or config())
    material = b'ARTIFICIAL APPROVAL FIXTURE - NEVER A REAL PERMISSION'
    mats = [ReviewedMaterial(ref, material, hashlib.sha256(material).hexdigest(),
                             'unit-test-fixture', 'test-reviewer', 'test-principal', role,
                             cfg.scope_digest, 0, until, revoked, True)
            for ref, role in (('owner-record', 'owner'), ('catalog-record', 'teacher'))]
    row = dict(registry_ref=cfg.registry_ref, authorization_id=cfg.authorization_id,
               authorization_version=cfg.authorization_version, scope_digest=cfg.scope_digest,
               owner_ref='owner-record', catalog_ref='catalog-record', delegation_ref=None)
    return LocalRegistry(json.dumps(row).encode(), mats)


CREDS = {'fixture/alice': 'SENSITIVE_ALICE_TOKEN', 'fixture/bob': 'SENSITIVE_BOB_TOKEN',
         'fixture/carol': 'SENSITIVE_ADMIN_TOKEN'}


class Clock:
    now = 0
    def __call__(self): return self.now


class Planner:
    def __init__(self, rows): self.rows = rows
    def plan(self, _): return copy.deepcopy(self.rows)


def body(check, action='action-test', *, bad=False, denied=False):
    row = dict(fixture_instance_id='test-instance', contract_version='p3-http-v1', request_id=action)
    if (check.expected == 'DENY' and not bad) or denied:
        row['error'] = dict(code='AUTHENTICATION_REQUIRED' if check.identity_ref == 'anonymous' else 'ACCESS_DENIED')
    elif check.endpoint_id == 'profile_read':
        row['data'] = dict(user_id='alice', role='member', profile_marker='ALICE_PROFILE_CANARY')
    elif check.endpoint_id == 'object_read':
        row['data'] = dict(object_id='obj-b', owner_id='bob', protected_marker='OBJECT_B_CANARY')
    else:
        row['data'] = dict(period='demo', audience='admin', report_marker='ADMIN_REPORT_CANARY')
    return row


def response(data, status=200, extra=b'', payload=None):
    b = json.dumps(data).encode() if payload is None else payload
    return (b'HTTP/1.1 ' + str(status).encode() + b' Test\r\nContent-Type: application/json\r\nContent-Length: '
            + str(len(b)).encode() + b'\r\n' + extra + b'\r\n' + b)


class HttpTests(unittest.TestCase):
    def setUp(self):
        for target in ('socket', 'create_connection', 'getaddrinfo'):
            guard = patch.object(socket, target, side_effect=AssertionError('NETWORK_FORBIDDEN'))
            guard.start(); self.addCleanup(guard.stop)
        self.raw = config()
        self.cfg = HttpConfig.parse(self.raw)
        self.clock = Clock()
        self.reg = registry()
        self.snap = self.reg.snapshot(self.cfg, 1, simulation=True)

    def run_model(self, raw=None, **kw):
        raw = raw or self.raw
        return SimulationRun(raw, kw.pop('registry', registry(raw)), clock=self.clock,
                             wall_clock=lambda: 1, credentials=CREDS, **kw)

    def parse(self, wire):
        parser = ResponseParser(self.cfg.limits)
        for offset in range(0, len(wire), 13): parser.feed(wire[offset:offset+13])
        return parser.finish()

    def prepare(self, run, *, index=0, transport=None):
        run.start(Planner([self.raw['candidates'][index]]))
        io = transport or MemoryTransport()
        run.step(io)
        return io

    def execute(self, run, io=None, *, bad=False, status=None):
        io = io or MemoryTransport()
        run.step(io)  # prepare current candidate
        if run._active is None: return io
        active = run._active
        check = active['slot'].check
        if status is None:
            status = 200 if check.expected == 'ALLOW' or bad else (401 if check.identity_ref == 'anonymous' else 403)
        io.chunks.append(response(body(check, active['slot'].action_id, bad=bad), status))
        for _ in range(30):
            if run.state != 'RUNNING' or run._active is None: break
            run.step()
        return io

    def test_six_checks_and_complete_permission_matrix(self):
        self.assertEqual(len(self.cfg.candidates), 6)
        for c in self.cfg.candidates:
            self.assertEqual(matrix_expectation(c.endpoint_id, c.identity_ref, c.path_params, c.query), c.expected)
        self.assertEqual(matrix_expectation('object_read', 'admin_carol', (('object_id','obj-b'),)), 'DENY')
        self.assertEqual(matrix_expectation('object_read', 'user_alice', (('object_id','obj-a'),)), 'ALLOW')

    def test_schema_rejects_offline_and_unknown_fields(self):
        for raw in (dict(self.raw, mode='offline'), dict(self.raw, active=True), dict(self.raw, approved_by='teacher')):
            with self.assertRaises(InvalidInput): HttpConfig.parse(raw)

    def test_targets_are_literal_and_exact(self):
        for key, value in (('host','localhost'),('host','::1'),('host','example.test'),('scheme','https'),('port',True),('port',0)):
            raw=copy.deepcopy(self.raw); raw['target'][key]=value
            with self.assertRaises(InvalidInput): HttpConfig.parse(raw)

    def test_nonfinite_budget_and_limits_fail(self):
        for key,value in (('max_checks',True),('concurrency',2),('logical_timeout_seconds',float('nan'))):
            raw=copy.deepcopy(self.raw);raw['budget'][key]=value
            with self.assertRaises(InvalidInput): HttpConfig.parse(raw)
        raw=copy.deepcopy(self.raw);raw['limits']['body_bytes']=True
        with self.assertRaises(InvalidInput): HttpConfig.parse(raw)

    def test_no_real_approval_from_synthetic_materials(self):
        with self.assertRaises(InvalidInput): self.reg.snapshot(self.cfg,1)
        self.assertTrue(self.snap.synthetic)

    def test_t32_missing_approval_and_expiration(self):
        for reg in (LocalRegistry(self.reg._bytes, ()), registry(until=1), registry(revoked=True)):
            with self.assertRaises(InvalidInput): reg.snapshot(self.cfg,1,simulation=True)

    def test_t32_scope_and_version_mismatch(self):
        for key in ('port','authorization_version','fixture_version','fixture_instance_id'):
            changed=replace(self.cfg, **{key:8766 if key=='port' else 'changed'})
            with self.assertRaises(InvalidInput): self.reg.snapshot(changed,1,simulation=True)

    def test_t32_material_hash_and_delegation(self):
        for item in (replace(self.reg._materials[0], content=b'changed'),
                     replace(self.reg._materials[0], role='delegate'),
                     replace(self.reg._materials[0], source='')):
            reg=LocalRegistry(self.reg._bytes,(item,self.reg._materials[1]))
            with self.assertRaises(InvalidInput): reg.snapshot(self.cfg,1,simulation=True)

    def test_t33_snapshot_bytes_are_immutable(self):
        mutable=bytearray(self.reg._bytes)
        reg=LocalRegistry(bytes(mutable),self.reg._materials)
        snap=reg.snapshot(self.cfg,1,simulation=True)
        mutable[:]=b'expanded authorization'
        self.assertEqual(reg.snapshot(self.cfg,1,simulation=True).scope_digest,snap.scope_digest)
        with self.assertRaises(Exception): snap.scope_digest='expanded'

    def test_preflight_fail_has_no_plan_or_io(self):
        c=self.run_model(registry=LocalRegistry(b'{}',()));c.start()
        self.assertEqual(c.reason,'INVALID_INPUT');self.assertEqual(c.counts['plan_count'],0)

    def test_registered_get_bytes_and_anonymous_no_token(self):
        for c in self.cfg.candidates:
            token=None if c.identity_ref=='anonymous' else 'TEST_TOKEN'
            req=build_request(self.cfg,self.snap,c,'action-test',token)
            self.assertTrue(req.wire.startswith(b'GET /v1/'))
            self.assertIn(b'Host: 127.0.0.1:8765',req.wire)
            self.assertEqual(b'Authorization:' in req.wire,token is not None)
            self.assertNotIn('TEST_TOKEN',repr(req))

    def test_arbitrary_url_identity_header_and_parameters_rejected(self):
        c=self.cfg.candidates[0]
        for bad in (replace(c,endpoint_id='https://elsewhere'),replace(c,identity_ref='intruder'),
                    replace(c,query=(('extra','value'),)),replace(c,method='POST')):
            with self.assertRaises(InvalidInput): build_request(self.cfg,self.snap,bad,'a','TOKEN')
        with self.assertRaises(TypeError): build_request(self.cfg,self.snap,c,'a','TOKEN',headers={})
        with self.assertRaises(InvalidInput): build_request(self.cfg,self.snap,c,'a','token\r\nHeader: injected')

    def test_encoded_paths_and_duplicate_query_are_invalid(self):
        for value in ('%2e%2e','../','//','a\\b','a?b','非英文','a\r\nb'):
            raw=copy.deepcopy(self.raw['candidates'][2]);raw['path_params']['object_id']=value
            with self.assertRaises(InvalidInput): HttpCheck.parse(raw)
        raw=copy.deepcopy(self.raw['candidates'][4]);raw['query']=[['period','demo'],['period','demo']]
        with self.assertRaises(InvalidInput): HttpCheck.parse(raw)

    def test_good_three_denials_and_controls(self):
        for check in self.cfg.candidates:
            status=200 if check.expected=='ALLOW' else (401 if check.identity_ref=='anonymous' else 403)
            verdict=evaluate(self.cfg,check,'action-test',self.parse(response(body(check),status)),control_pass=True)
            self.assertEqual(verdict.simulated_conclusion,'PASS')
            self.assertEqual(verdict.execution,'NOT_EXECUTED');self.assertEqual(verdict.conclusion,'INCONCLUSIVE')

    def test_known_bad_all_three_confirmed(self):
        for check in self.cfg.candidates[1::2]:
            v=evaluate(self.cfg,check,'action-test',self.parse(response(body(check,bad=True))))
            self.assertEqual(v.simulated_conclusion,'FAIL')

    def test_overdenial_requires_identity_evidence(self):
        check=self.cfg.candidates[0];obs=self.parse(response(body(check,denied=True),403))
        self.assertEqual(evaluate(self.cfg,check,'action-test',obs).simulated_conclusion,'FAIL')
        self.assertEqual(evaluate(self.cfg,check,'action-test',obs,identity_verified=False).simulated_conclusion,'INCONCLUSIVE')

    def test_negative_without_control_inconclusive(self):
        check=self.cfg.candidates[1]
        self.assertEqual(evaluate(self.cfg,check,'action-test',self.parse(response(body(check),401))).simulated_conclusion,'INCONCLUSIVE')

    def test_wrong_instance_and_unknown_fields(self):
        check=self.cfg.candidates[0]
        for data in (dict(body(check),extra='SECRET'),dict(body(check),fixture_instance_id='other')):
            self.assertEqual(evaluate(self.cfg,check,'action-test',self.parse(response(data))).simulated_conclusion,'INCONCLUSIVE')

    def test_t34_canary_cannot_rescue_malformed_framing_or_json(self):
        check=self.cfg.candidates[3];data=body(check,bad=True)
        for payload in (b'',b'{"a":1,"a":2}',b'{"x":"OBJECT_B_CANARY"',b'\xffOBJECT_B_CANARY',b'null'):
            obs=self.parse(response(data,payload=payload))
            self.assertFalse(obs.valid)
            self.assertEqual(evaluate(self.cfg,check,'action-test',obs).simulated_conclusion,'INCONCLUSIVE')
        good=response(data)
        extras=(b'Content-Length: 1\r\n',b'Content-Length: '+str(len(json.dumps(data).encode())).encode()+b'\r\n',b'Transfer-Encoding: chunked\r\n')
        for wire in [response(data,extra=x) for x in extras]+[good[:-1],good+b'extra',b'HTTP/2 200 Test\r\n\r\n']:
            obs=self.parse(wire);self.assertFalse(obs.valid)
            self.assertEqual(evaluate(self.cfg,check,'action-test',obs).simulated_conclusion,'INCONCLUSIVE')

    def test_response_size_bounds_and_content_type(self):
        for wire in (b'x'*1025,response({},payload=b'x'*4097),response({}).replace(b'application/json',b'text/plain')):
            self.assertFalse(self.parse(wire).valid)
        parser=ResponseParser(self.cfg.limits);parser.feed(b'x'*6000)
        self.assertEqual(len(parser._buffer),0);self.assertFalse(parser.finish().valid)

    def test_t35_5xx_complete_vs_truncated_leak(self):
        check=self.cfg.candidates[3];wire=response(body(check,bad=True),500)
        valid=evaluate(self.cfg,check,'action-test',self.parse(wire))
        invalid=evaluate(self.cfg,check,'action-test',self.parse(wire[:-1]))
        self.assertEqual((valid.simulated_conclusion,valid.reason),('FAIL','RESPONSE_ERROR'))
        self.assertEqual(invalid.simulated_conclusion,'INCONCLUSIVE')
        self.assertEqual(valid.simulated_conclusion,'FAIL')  # separate observation stays immutable.

    def test_404_and_5xx_no_leak_are_inconclusive(self):
        check=self.cfg.candidates[1]
        for status in (404,500,302):
            v=evaluate(self.cfg,check,'action-test',self.parse(response(body(check),status)),control_pass=True)
            self.assertEqual((v.simulated_conclusion,v.reason),('INCONCLUSIVE','RESPONSE_ERROR'))

    def test_run_all_six_good_and_known_bad(self):
        for bad_index in (None,1,3,5):
            c=self.run_model();c.start()
            for i in range(6): self.execute(c,bad=i==bad_index);c.settle()
            report=c.finalize()
            self.assertEqual(c.state,'COMPLETED')
            self.assertEqual(c.counts,dict(plan_count=6,attempt_count=6,request_count=0,model_request_count=6))
            self.assertEqual([r['simulated_conclusion'] for r in report['checks']],['FAIL' if i==bad_index else 'PASS' for i in range(6)])
            self.assertTrue(all(r['conclusion']=='INCONCLUSIVE' and r['execution']=='NOT_EXECUTED' for r in report['checks']))

    def test_t27_revoke_before_connect(self):
        c=self.run_model();io=self.prepare(c);c.revoke();c.step()
        self.assertEqual(c.reason,'REVOKED');self.assertNotIn('connect',[x[0] for x in io.calls])
        self.assertEqual(c.counts['model_request_count'],0)

    def test_t27_connect_then_revoke_before_first_send(self):
        c=self.run_model();io=self.prepare(c,transport=MemoryTransport(connect='PENDING'))
        c.step();c.revoke();c.step()
        self.assertEqual([x[0] for x in io.calls].count('connect'),1)
        self.assertNotIn('send',[x[0] for x in io.calls]);self.assertEqual(c.counts['model_request_count'],0)

    def test_t29_partial_and_wouldblock_count_once(self):
        c=self.run_model();io=self.prepare(c,transport=MemoryTransport(writes=('WAIT',3,4)))
        c.step();c.step();c.step();self.assertEqual(c.counts['model_request_count'],0)
        c.step();self.assertEqual(c.counts['model_request_count'],1)
        c.step();self.assertEqual(c._active['offset'],7);self.assertEqual(c.counts['model_request_count'],1)
        c.revoke();c.step();self.assertEqual(len([x for x in io.calls if x[0]=='send']),3)

    def test_t29_zero_and_failed_send_no_retry(self):
        for writes,expected in (((0,),0),((OSError('PRIVATE'),),0),((3,OSError('PRIVATE')),1)):
            c=self.run_model();io=self.prepare(c,transport=MemoryTransport(writes=writes))
            for _ in range(7): c.step()
            self.assertEqual(c.reason,'TRANSPORT_ERROR');self.assertEqual(c.counts['model_request_count'],expected)
            self.assertEqual(len([x for x in io.calls if x[0]=='connect']),1)

    def test_t28_send_return_and_count_are_one_gate_transaction(self):
        entered,release=threading.Event(),threading.Event()
        class PausedSend(MemoryTransport):
            def send(self,buffer,offset):
                entered.set()
                if not release.wait(3): raise RuntimeError('test barrier timeout')
                return 3
        c=self.run_model();c.start(Planner([self.raw['candidates'][0]]));io=PausedSend()
        errors=[]
        def owner():
            try:
                c.step(io);c.step();c.step();c.step()
            except Exception as e: errors.append(type(e).__name__)
        worker=threading.Thread(target=owner);worker.start()
        self.assertTrue(entered.wait(3))
        started,done=threading.Event(),threading.Event()
        def revoke(): started.set();c.revoke();done.set()
        revoker=threading.Thread(target=revoke);revoker.start();self.assertTrue(started.wait(3))
        self.assertFalse(done.is_set());release.set()
        worker.join(3);revoker.join(3)
        self.assertFalse(worker.is_alive());self.assertFalse(revoker.is_alive());self.assertFalse(errors)
        self.assertEqual(c.counts['model_request_count'],1);self.assertEqual(c._active['offset'],3)
        self.assertEqual(c.reason,'REVOKED')

    def test_t30_time_boundary_after_send_preserves_count(self):
        clock=self.clock
        class Advancing(MemoryTransport):
            def send(self,b,o): clock.now=90;return 3
        c=self.run_model();self.prepare(c,transport=Advancing())
        c.step();c.step();c.step()
        self.assertEqual(c.reason,'BUDGET_EXHAUSTED');self.assertEqual(c.counts['model_request_count'],1)

    def test_t30_initial_planning_in_budget(self):
        clock=self.clock
        class Slow:
            def plan(self,candidates): clock.now=90;return [x.to_dict() for x in candidates]
        c=self.run_model();c.start(Slow())
        self.assertEqual(c.reason,'BUDGET_EXHAUSTED');self.assertEqual(c.counts['plan_count'],0)

    def test_deadline_before_first_write_and_timeout_priority(self):
        c=self.run_model();io=self.prepare(c);c.step();c.step();self.clock.now=90;c.step()
        self.assertNotIn('send',[x[0] for x in io.calls]);self.assertEqual(c.reason,'BUDGET_EXHAUSTED')
        self.clock.now=0;c=self.run_model();self.prepare(c);self.clock.now=90;c.poll('TIMEOUT')
        self.assertEqual(c.conditions,['BUDGET_EXHAUSTED','TIMEOUT'])

    def test_t31_revoke_idempotence_duplicate_and_late_events(self):
        c=self.run_model();self.prepare(c);c.step();c.step();c.step();c.revoke()
        count=c.counts.copy();generation=c.generation;c.revoke()
        c.observe_late(c._active['slot'].action_id);c.submit(self.raw['candidates'][1]);c.step()
        self.assertEqual(c.counts,count);self.assertEqual(c.generation,generation)
        self.assertEqual(c.report()['checks'][0]['simulated_conclusion'],'INCONCLUSIVE')

    def test_single_io_owner_and_serial_lifecycle(self):
        c=self.run_model();self.prepare(c)
        errors=[]
        def other():
            try:c.step()
            except InvalidInput:errors.append('rejected')
        t=threading.Thread(target=other);t.start();t.join(3)
        self.assertEqual(errors,['rejected'])

    def test_peer_mismatch_blocks_credential_write(self):
        c=self.run_model();io=self.prepare(c,transport=MemoryTransport(peer=('127.0.0.1',8766)))
        c.step();c.step();c.step()
        self.assertEqual(c.reason,'AUTHORIZATION_INVALID');self.assertNotIn('send',[x[0] for x in io.calls])

    def test_audit_failure_before_dispatch_and_after_send(self):
        for kind,expected in (('prepared',0),('model_io',0),('simulated_assertion',1)):
            class Fail(MemoryEvidence):
                def emit(self,event):
                    if event['kind']==kind:raise OSError('RAW_PRIVATE_EXCEPTION')
                    super().emit(event)
            c=self.run_model(evidence=Fail());c.start(Planner([self.raw['candidates'][0]]));self.execute(c)
            self.assertEqual(c.reason,'AUDIT_ERROR');self.assertEqual(c.counts['model_request_count'],expected)
            self.assertEqual(c.report()['checks'][0]['simulated_conclusion'],'INCONCLUSIVE')

    def test_revocation_during_audit_does_not_need_controller_lock(self):
        c=self.run_model()
        class Revoke(MemoryEvidence):
            def emit(self,event):
                if event['kind']=='prepared':
                    t=threading.Thread(target=c.revoke);t.start();t.join(2)
                    if t.is_alive():raise AssertionError('revoke blocked by audit')
                super().emit(event)
        c.evidence=Revoke();c.evidence.open(c.run_id,c._redactor)
        io=self.prepare(c);c.step()
        self.assertEqual(c.reason,'REVOKED');self.assertNotIn('connect',[x[0] for x in io.calls])

    def test_denials_consume_budget_and_eighth_ninth_boundary(self):
        c=self.run_model();c.start()
        for i in (7,8):c.submit(dict(self.raw['candidates'][0],check_id='unapproved'+str(i)))
        self.assertEqual(c.counts['plan_count'],8)
        original=copy.deepcopy(c._slots[0]);c.submit(dict(self.raw['candidates'][0],query={'bad':'SENSITIVE'}))
        self.assertEqual(c._slots[0],original);self.assertEqual(c.counts['attempt_count'],0)
        for _ in range(6):self.execute(c)
        c.step(MemoryTransport());c.step(MemoryTransport())
        self.assertEqual(c.counts['attempt_count'],8);self.assertEqual(c.counts['model_request_count'],6)
        c.submit(dict(self.raw['candidates'][0],check_id='ninth'))
        self.assertEqual(c.reason,'BUDGET_EXHAUSTED');self.assertEqual(c.counts['plan_count'],8)

    def test_malformed_addition_and_conflict_do_not_replace_original(self):
        c=self.run_model();c.start();old=copy.deepcopy(c._slots[0])
        c.submit({'check_id':'HTTP-C-AUTH'});self.assertEqual(c._slots[0],old)
        c.submit(None);self.assertEqual(c.counts['attempt_count'],1)
        self.assertEqual(c.counts['plan_count'],7)

    def test_initial_overbudget_is_rejected_without_truncation(self):
        raw=copy.deepcopy(self.raw);raw['budget']['max_checks']=5
        c=self.run_model(raw);c.start()
        self.assertEqual(c.reason,'INVALID_INPUT');self.assertEqual(c.counts['plan_count'],0)

    def test_no_new_evidence_does_not_skip_checks_or_controls(self):
        c=self.run_model();c.start(Planner([self.raw['candidates'][1]]));self.execute(c);c.settle(repeat=True)
        self.assertEqual(c.state,'RUNNING');self.assertEqual(c.counts['plan_count'],2)
        self.execute(c);self.assertEqual(c._slots[0].simulated_conclusion,'PASS')
        c.settle(repeat=True);self.assertEqual(c.state,'RUNNING')

    def test_repeat_exhausted_and_completed_are_terminal(self):
        for repeat in (True,False):
            c=self.run_model();c.start()
            for _ in range(6):self.execute(c)
            c.settle(repeat=repeat);state=c.state;counts=c.counts
            self.assertEqual(c.reason,'NO_NEW_EVIDENCE' if repeat else None)
            c.start();c.submit(None);c.step();c.settle()
            self.assertEqual(c.state,state);self.assertEqual(c.counts,counts)

    def test_artifacts_never_contain_credentials_parameters_or_exception_body(self):
        marker='UNAPPROVED_PRIVATE_PARAMETER'
        with tempfile.TemporaryDirectory() as folder:
            c=self.run_model(evidence=JsonlEvidence(folder));c.start()
            c.submit(dict(self.raw['candidates'][0],check_id='unknown',query={'secret':marker}))
            c.submit({'credential':marker});self.execute(c)
            c.revoke();report=c.finalize()
            all_text=json.dumps(report)+''.join(p.read_text(encoding='utf-8') for p in Path(folder).rglob('*') if p.is_file())
            for secret in [marker]+list(CREDS.values()):self.assertNotIn(secret,all_text)
            self.assertIn('NO_NETWORK_SIMULATION',all_text)

    def test_unique_ids_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            ids=set()
            for _ in range(3):
                c=self.run_model(evidence=JsonlEvidence(folder));c.start();c.revoke();c.finalize()
                self.assertNotIn(c.run_id,ids);ids.add(c.run_id)
            self.assertEqual(len(list(Path(folder).iterdir())),3)

    def test_final_audit_failure_preserves_terminal(self):
        class Fail(MemoryEvidence):
            def finish(self,*args):raise OSError('PRIVATE')
        c=self.run_model(evidence=Fail());c.start();c.revoke();r=c.finalize()
        self.assertTrue(r['audit_gap']);self.assertEqual(c.reason,'REVOKED')

    def test_t30_audit_gap_after_positive_send_is_unknown_on_recovery(self):
        class FailAfterSend(MemoryEvidence):
            def emit(self,event):
                if event['kind']=='model_io' and event['dispatch_started']:
                    raise OSError('SIMULATED_CRASH_SECRET')
                super().emit(event)
        sink=FailAfterSend();c=self.run_model(evidence=sink);io=self.prepare(c)
        c.step();c.step();c.step()
        self.assertEqual(c.reason,'AUDIT_ERROR');self.assertEqual(c.counts['model_request_count'],1)
        recovered=inspect_model_prefix(sink.events)
        self.assertEqual(recovered['model_send_unknown'],1)
        self.assertEqual(recovered['model_confirmed_sent'],0)
        self.assertFalse(recovered['replay_allowed'])
        self.assertNotIn('SIMULATED_CRASH_SECRET',json.dumps(sink.events))

    def test_expiry_and_revoke_priority_and_monotonic_rollback(self):
        c=self.run_model(registry=registry(until=3));self.prepare(c);self.clock.now=2;c.poll()
        self.assertEqual(c.reason,'AUTHORIZATION_INVALID')
        self.clock.now=0;c=self.run_model();self.prepare(c);self.clock.now=10;c.poll();self.clock.now=9;c.poll()
        self.assertEqual(c.reason,'RUNTIME_ERROR')
        self.clock.now=0;c=self.run_model();self.prepare(c);self.clock.now=90;c.revoke()
        self.assertEqual(c.conditions,['REVOKED','BUDGET_EXHAUSTED'])

    def test_read_timeout_and_transport_failure_no_raw_exception(self):
        for error,reason in ((TimeoutError('SECRET'),'TIMEOUT'),(OSError('SECRET'),'TRANSPORT_ERROR')):
            c=self.run_model();io=self.prepare(c,transport=MemoryTransport(chunks=(error,)))
            for _ in range(6):c.step()
            self.assertEqual(c.reason,reason);self.assertEqual(c.counts['model_request_count'],1)
            self.assertNotIn('SECRET',json.dumps(c.report()))

    def test_late_response_during_read_cannot_upgrade(self):
        c=self.run_model()
        class Late(MemoryTransport):
            def receive(self):c.revoke();return super().receive()
        c.start(Planner([self.raw['candidates'][0]]));io=Late();self.execute(c,io)
        self.assertEqual(c.reason,'REVOKED')
        self.assertEqual(c.report()['checks'][0]['simulated_conclusion'],'INCONCLUSIVE')

    def test_response_secret_keys_and_values_do_not_enter_artifacts(self):
        marker='UNTRUSTED_RESPONSE_PRIVATE'
        with tempfile.TemporaryDirectory() as folder:
            c=self.run_model(evidence=JsonlEvidence(folder));c.start(Planner([self.raw['candidates'][0]]))
            io=MemoryTransport();c.step(io);slot=c._active['slot']
            data=body(slot.check,slot.action_id);data[marker]=marker
            io.chunks.append(response(data))
            for _ in range(8):c.step()
            self.assertEqual(c.reason,'RESPONSE_ERROR');c.finalize()
            for p in Path(folder).rglob('*'):
                if p.is_file():self.assertNotIn(marker,p.read_text(encoding='utf-8'))

    def test_completion_audit_at_deadline_never_completes(self):
        clock=self.clock
        class Slow(MemoryEvidence):
            def emit(self,event):
                super().emit(event)
                if event['kind']=='completion_ready':clock.now=90
        c=self.run_model(evidence=Slow());c.start(Planner([self.raw['candidates'][0]]));self.execute(c);c.settle()
        self.assertEqual((c.state,c.reason),('STOPPED','BUDGET_EXHAUSTED'))

    def test_approved_candidate_pass_is_not_carried_to_broken_next_response(self):
        c=self.run_model();c.start();self.execute(c)
        io=MemoryTransport();c.step(io)
        io.chunks.append(response({},payload=b'{"canary":"ALICE_PROFILE_CANARY"'))
        for _ in range(8):c.step()
        self.assertEqual(c._slots[0].simulated_conclusion,'PASS')
        self.assertEqual(c._slots[1].simulated_conclusion,'INCONCLUSIVE')

    def test_anonymous_request_forbids_supplied_credential(self):
        with self.assertRaises(InvalidInput):
            build_request(self.cfg,self.snap,self.cfg.candidates[1],'a','TOKEN')

    def test_planner_exception_is_runtime_error_and_no_plan(self):
        class Broken:
            def plan(self,_):raise RuntimeError('SECRET_PLANNER')
        c=self.run_model();c.start(Broken())
        self.assertEqual(c.reason,'RUNTIME_ERROR');self.assertEqual(c.counts['plan_count'],0)
        self.assertNotIn('SECRET_PLANNER',json.dumps(c.report()))

    def test_revocation_inside_planner_blocks_registration(self):
        c=self.run_model()
        class Revoke:
            def plan(self,candidates):c.revoke();return [x.to_dict() for x in candidates]
        c.start(Revoke())
        self.assertEqual(c.reason,'REVOKED');self.assertEqual(c.counts['plan_count'],0)


if __name__ == '__main__':unittest.main()

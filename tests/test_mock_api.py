"""C-1: pure synthetic business fixtures, no sockets and no HTTP integration."""
import contextlib
from dataclasses import FrozenInstanceError
import io
import json
import logging
from pathlib import Path
import socket
import tempfile
import unittest
from unittest.mock import patch

from p3_core.evidence import JsonlEvidence, unique_id
from p3_core.http.contract import HttpConfig, base_checks
from p3_core.http.machine import SimulationRun
from p3_core.http.protocol import ResponseParser, build_request, evaluate
from p3_core.http.transport import MemoryTransport
from p3_core.mock_api import FixtureManager, MockRequest, Mode, RequestRejected
from test_http_core import config, registry, Clock


class MockApiTests(unittest.TestCase):
    def setUp(self):
        for name in ('socket', 'create_connection', 'getaddrinfo'):
            guard = patch.object(socket, name, side_effect=AssertionError('NETWORK_FORBIDDEN'))
            guard.start()
            self.addCleanup(guard.stop)
        self.fixture = FixtureManager.reset()

    def request(self, target='/v1/profile', identity='user_alice', fixture=None, **overrides):
        fixture = fixture or self.fixture
        fields = dict(method='GET', target=target, action_id=unique_id('action'),
                      credential=fixture.credential_for(identity))
        fields.update(overrides)
        return MockRequest(**fields)

    def payload(self, response):
        return json.loads(response.body.decode('utf-8'))

    def target(self, check):
        return {'profile_read': '/v1/profile', 'object_read': '/v1/objects/obj-b',
                'admin_report': '/v1/admin/report?period=demo'}[check.endpoint_id]

    def test_good_six_baseline_candidates(self):
        for check, status in zip(base_checks(), (200, 401, 200, 403, 200, 403)):
            with self.subTest(check=check.check_id):
                result = self.fixture.handle(self.request(self.target(check), check.identity_ref))
                self.assertEqual(result.status, status)
                data = self.payload(result)
                if status != 200:
                    self.assertEqual(set(data['error']), {'code'})
                    self.assertNotIn('data', data)

    def test_known_bad_auth_changes_only_anonymous_profile(self):
        fixture = FixtureManager.reset(Mode.AUTH)
        result = fixture.handle(self.request(identity='anonymous', fixture=fixture))
        self.assertEqual(result.status, 200)
        self.assertEqual(self.payload(result)['data'], dict(user_id='alice', role='member', profile_marker='ALICE_PROFILE_CANARY'))
        for target in ('/v1/objects/obj-b', '/v1/admin/report?period=demo'):
            self.assertEqual(fixture.handle(self.request(target, 'anonymous', fixture)).status, 401)

    def test_known_bad_bola_returns_other_owner_object(self):
        fixture = FixtureManager.reset(Mode.BOLA)
        result = fixture.handle(self.request('/v1/objects/obj-b', 'user_alice', fixture))
        self.assertEqual(result.status, 200)
        self.assertEqual(self.payload(result)['data'], dict(object_id='obj-b', owner_id='bob', protected_marker='OBJECT_B_CANARY'))
        self.assertEqual(fixture.handle(self.request('/v1/objects/obj-b', 'anonymous', fixture)).status, 401)
        self.assertEqual(fixture.handle(self.request('/v1/admin/report?period=demo', 'user_alice', fixture)).status, 403)

    def test_known_bad_rbac_keeps_authentication_and_ownership(self):
        fixture = FixtureManager.reset(Mode.RBAC)
        result = fixture.handle(self.request('/v1/admin/report?period=demo', 'user_alice', fixture))
        self.assertEqual(result.status, 200)
        self.assertEqual(self.payload(result)['data'], dict(period='demo', audience='admin', report_marker='ADMIN_REPORT_CANARY'))
        self.assertEqual(fixture.handle(self.request('/v1/admin/report?period=demo', 'anonymous', fixture)).status, 401)
        self.assertEqual(fixture.handle(self.request('/v1/objects/obj-b', 'user_alice', fixture)).status, 403)

    def test_all_known_bad_legal_controls_succeed(self):
        for mode in Mode:
            fixture = FixtureManager.reset(mode)
            for check in base_checks()[::2]:
                with self.subTest(mode=mode.value, check=check.check_id):
                    self.assertEqual(fixture.handle(self.request(self.target(check), check.identity_ref, fixture)).status, 200)

    def test_entire_declared_matrix_and_single_defect_isolation(self):
        # Business fixture matrix only. Does NOT register additional Agent checks.
        targets = ('/v1/profile', '/v1/objects/obj-a', '/v1/objects/obj-b', '/v1/admin/report?period=demo')
        good = {'anonymous': (401,401,401,401), 'user_alice': (200,200,403,403),
                'user_bob': (200,403,200,403), 'admin_carol': (200,403,403,200)}
        for mode in Mode:
            fixture = FixtureManager.reset(mode)
            for identity, statuses in good.items():
                for col, target in enumerate(targets):
                    expected = statuses[col]
                    if mode == Mode.AUTH and identity == 'anonymous' and col == 0:
                        expected = 200
                    if mode == Mode.BOLA and identity != 'anonymous' and col in (1,2):
                        expected = 200
                    if mode == Mode.RBAC and identity != 'anonymous' and col == 3:
                        expected = 200
                    with self.subTest(mode=mode.value, identity=identity, target=target):
                        self.assertEqual(fixture.handle(self.request(target, identity, fixture)).status, expected)

    def test_own_profiles_and_obj_a_are_synthetic(self):
        for identity, user, role in (('user_alice','alice','member'),('user_bob','bob','member'),('admin_carol','carol','admin')):
            result = self.fixture.handle(self.request(identity=identity))
            self.assertEqual(self.payload(result)['data'], dict(user_id=user, role=role, profile_marker=user.upper()+'_PROFILE_CANARY'))
        result = self.fixture.handle(self.request('/v1/objects/obj-a'))
        self.assertEqual(self.payload(result)['data'], dict(object_id='obj-a', owner_id='alice', protected_marker='OBJECT_A_CANARY'))

    def test_admin_does_not_have_implicit_object_access(self):
        for obj in ('obj-a', 'obj-b'):
            self.assertEqual(self.fixture.handle(self.request('/v1/objects/'+obj, 'admin_carol')).status, 403)

    def test_unknown_identity_and_token_are_rejected(self):
        for name in ('root', 'other', '', None):
            with self.assertRaisesRegex(RequestRejected, '^UNKNOWN_FIXTURE_IDENTITY$'):
                self.fixture.credential_for(name)
        for mode in Mode:
            fixture = FixtureManager.reset(mode)
            for token in ('UNKNOWN_MOCK_TOKEN', ''):
                result = fixture.handle(self.request(fixture=fixture, credential=token))
                self.assertEqual(result.status, 401)
                self.assertNotIn(token or 'UNUSED', result.body.decode())

    def test_no_identity_role_or_expectation_override(self):
        for extra in ('identity_ref', 'role', 'expected', 'mode', 'headers'):
            with self.assertRaises(TypeError):
                MockRequest('GET','/v1/profile',unique_id('action'), **{extra:'admin'})
        with self.assertRaisesRegex(RequestRejected, '^INVALID_REQUEST_STRUCTURE$'):
            self.fixture.handle({'method':'GET','target':'/v1/profile','role':'admin'})

    def test_unregistered_paths_and_encoding_rejected(self):
        targets = ('/v1/objects/obj-c', '/v1/objects/../obj-b', '/v1/objects/%6fbj-b',
                   '/v1/profile/', '//v1/profile', '/v1\\profile', 'http://127.0.0.1:8765/v1/profile',
                   '/v1/profile#fragment', '/v1/objects/对象', '/v1/objects/obj-b\r\nHeader: x')
        for target in targets:
            with self.subTest(target=target), self.assertRaisesRegex(RequestRejected, '^UNREGISTERED_REQUEST_TARGET$'):
                self.fixture.handle(self.request(target))

    def test_extra_missing_duplicate_and_encoded_queries_rejected(self):
        for target in ('/v1/profile?x=secret', '/v1/objects/obj-b?x=secret', '/v1/admin/report',
                       '/v1/admin/report?period=demo&x=secret', '/v1/admin/report?period=demo&period=demo',
                       '/v1/admin/report?period=', '/v1/admin/report?period=%64emo', '/v1/admin/report?period=demo&'):
            with self.assertRaisesRegex(RequestRejected, '^UNREGISTERED_REQUEST_TARGET$'):
                self.fixture.handle(self.request(target))

    def test_non_get_and_management_routes_absent(self):
        for method in ('POST','PUT','DELETE','HEAD','get',None):
            with self.assertRaisesRegex(RequestRejected, '^METHOD_NOT_ALLOWED$'):
                self.fixture.handle(self.request(method=method))
        for target in ('/login','/reset','/admin','/mode','/v1/reset','/v1/login'):
            with self.assertRaisesRegex(RequestRejected, '^UNREGISTERED_REQUEST_TARGET$'):
                self.fixture.handle(self.request(target))

    def test_invalid_action_and_credential_input_are_not_echoed(self):
        for value in ('UNAPPROVED_ACTION_SECRET', '', 'action_../', None, ['SECRET']):
            with self.assertRaisesRegex(RequestRejected, '^INVALID_ACTION_ID$'):
                self.fixture.handle(self.request(action_id=value))
        for value in ('秘密', 'secret'*100, b'RAW_TOKEN', {'token':'SECRET'}):
            with self.assertRaisesRegex(RequestRejected, '^INVALID_CREDENTIAL_INPUT$'):
                self.fixture.handle(self.request(credential=value))

    def test_mode_is_immutable_and_exclusive(self):
        for mode in ('Good', 'AUTH+BOLA', [Mode.AUTH, Mode.BOLA], True, None):
            with self.assertRaisesRegex(RequestRejected, '^INVALID_FIXTURE_MODE$'):
                FixtureManager.reset(mode)
        with self.assertRaises(FrozenInstanceError):
            self.fixture._mode = Mode.AUTH

    def test_reset_generates_new_instance_and_credentials(self):
        ids = set()
        tokens = set()
        for _ in range(12):
            fixture = FixtureManager.reset()
            self.assertNotIn(fixture.fixture_instance_id, ids)
            ids.add(fixture.fixture_instance_id)
            current = set(fixture.credential_bindings().values())
            self.assertEqual(len(current), 3)
            self.assertFalse(current & tokens)
            self.assertTrue(all(t.startswith('mock_') for t in current))
            tokens.update(current)

    def test_old_credentials_never_authenticate_new_instance(self):
        old = self.fixture
        for mode in Mode:
            new = FixtureManager.reset(mode)
            for token in old.credential_bindings().values():
                result = new.handle(self.request(fixture=new, credential=token))
                self.assertEqual(result.status, 401)
                self.assertNotIn(token.encode(), result.to_bytes())

    def test_mode_switch_does_not_mutate_original_fixture(self):
        original = self.fixture
        new = FixtureManager.reset(Mode.AUTH)
        self.assertNotEqual(new.fixture_instance_id, original.fixture_instance_id)
        self.assertEqual(original.handle(self.request(identity='anonymous')).status, 401)
        self.assertEqual(new.handle(self.request(identity='anonymous', fixture=new)).status, 200)

    def test_binding_copy_cannot_change_identity_map(self):
        token = self.fixture.credential_for('user_alice')
        bindings = self.fixture.credential_bindings()
        bindings['fixture/alice'] = 'PRIVATE_OVERRIDE'
        self.assertEqual(self.fixture.credential_for('user_alice'), token)
        self.assertEqual(self.fixture.handle(self.request(credential='PRIVATE_OVERRIDE')).status, 401)

    def test_content_length_schema_and_action_binding(self):
        seen = set()
        for mode in Mode:
            fixture = FixtureManager.reset(mode)
            for check in base_checks():
                request = self.request(self.target(check), check.identity_ref, fixture)
                result = fixture.handle(request)
                headers = dict(result.headers)
                self.assertEqual(len(headers), len(result.headers))
                self.assertEqual(headers['Content-Type'], 'application/json')
                self.assertEqual(int(headers['Content-Length']), len(result.body))
                data = self.payload(result)
                self.assertEqual(data['request_id'], request.action_id)
                self.assertNotIn(data['request_id'], seen); seen.add(data['request_id'])
                self.assertEqual(data['fixture_instance_id'], fixture.fixture_instance_id)
                self.assertEqual(data['contract_version'], 'p3-http-v1')
                self.assertEqual(set(data), {'fixture_instance_id','contract_version','request_id', 'data' if result.status==200 else 'error'})
                if result.status != 200:
                    self.assertEqual(data['error'], {'code':'AUTHENTICATION_REQUIRED' if result.status==401 else 'ACCESS_DENIED'})
                self.assertFalse({'mode','PASS','FAIL','expected','token','authorization'} & set(data))

    def test_same_request_is_deterministic_without_state_mutation(self):
        request = self.request()
        self.assertEqual(self.fixture.handle(request).to_bytes(), self.fixture.handle(request).to_bytes())

    def test_parser_and_evaluator_compatibility_for_six_candidates(self):
        for mode in Mode:
            fixture = FixtureManager.reset(mode)
            raw = config(); raw['fixture_instance_id'] = fixture.fixture_instance_id
            cfg = HttpConfig.parse(raw); snap = registry(raw).snapshot(cfg, 1, simulation=True)
            controls = {}
            for check in cfg.candidates:
                action = unique_id('action')
                prepared = build_request(cfg, snap, check, action, fixture.credential_for(check.identity_ref))
                response = fixture.handle(MockRequest('GET', prepared.target, action, fixture.credential_for(check.identity_ref)))
                parser = ResponseParser(cfg.limits)
                wire = response.to_bytes()
                for i in range(0, len(wire), 7): parser.feed(wire[i:i+7])
                obs = parser.finish(); self.assertTrue(obs.valid)
                verdict = evaluate(cfg, check, action, obs, control_pass=controls.get(check.control_id,False))
                expected_fail = ((mode==Mode.AUTH and check.check_id=='HTTP-N-AUTH')
                    or (mode==Mode.BOLA and check.check_id=='HTTP-N-BOLA')
                    or (mode==Mode.RBAC and check.check_id=='HTTP-N-RBAC'))
                self.assertEqual(verdict.simulated_conclusion, 'FAIL' if expected_fail else 'PASS')
                self.assertEqual((verdict.execution,verdict.conclusion), ('NOT_EXECUTED','INCONCLUSIVE'))
                controls[check.check_id] = verdict.simulated_conclusion == 'PASS'

    def test_log_repr_response_and_exception_do_not_leak(self):
        marker = 'UNAPPROVED_PARAMETER_PRIVATE'
        output = io.StringIO(); logs = io.StringIO()
        handler = logging.StreamHandler(logs); logger = logging.getLogger(); logger.addHandler(handler)
        self.addCleanup(logger.removeHandler, handler)
        fragments = []
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            for mode in Mode:
                fixture = FixtureManager.reset(mode)
                for check in base_checks():
                    req = self.request(self.target(check), check.identity_ref, fixture)
                    result = fixture.handle(req)
                    fragments += [repr(req),repr(result),repr(fixture),result.to_bytes().decode()]
                req = self.request('/v1/profile?extra='+marker, fixture=fixture)
                fragments.append(repr(req))
                try: fixture.handle(req)
                except RequestRejected as error: fragments += [str(error),repr(error)]
                all_text=''.join(fragments)+output.getvalue()+logs.getvalue()
                for credential in fixture.credential_bindings().values(): self.assertNotIn(credential,all_text)
        self.assertNotIn(marker, ''.join(fragments))
        self.assertEqual(output.getvalue(), ''); self.assertEqual(logs.getvalue(), '')

    def test_business_responses_flow_through_model_without_real_execution(self):
        for mode in Mode:
            fixture = FixtureManager.reset(mode)
            raw = config(); raw['fixture_instance_id'] = fixture.fixture_instance_id
            with tempfile.TemporaryDirectory() as folder:
                run = SimulationRun(raw, registry(raw), clock=Clock(), wall_clock=lambda:1,
                                    credentials=fixture.credential_bindings(), evidence=JsonlEvidence(folder))
                run.start()
                for _ in range(6):
                    transport = MemoryTransport(); run.step(transport)
                    prepared = run._active['request']
                    # Test-only adaptation of generated bytes, NOT a server or wire parser API.
                    lines = prepared.wire.decode('ascii').split('\r\n')
                    method, target, _ = lines[0].split(' ')
                    headers = dict(line.split(': ',1) for line in lines[1:] if line)
                    token = headers.get('Authorization')
                    if token is not None: token = token.removeprefix('Bearer ')
                    response = fixture.handle(MockRequest(method,target,headers['X-P3-Action-Id'],token))
                    transport.chunks.append(response.to_bytes())
                    for step in range(20):
                        if run._active is None or run.state != 'RUNNING': break
                        run.step()
                    self.assertIsNone(run._active)
                    run.settle()
                report = run.finalize()
                self.assertEqual(run.state,'COMPLETED')
                self.assertEqual(report['counts'], dict(plan_count=6,attempt_count=6,request_count=0,model_request_count=6))
                failed = [r['check_id'] for r in report['checks'] if r['simulated_conclusion']=='FAIL']
                expected = {Mode.GOOD:[],Mode.AUTH:['HTTP-N-AUTH'],Mode.BOLA:['HTTP-N-BOLA'],Mode.RBAC:['HTTP-N-RBAC']}
                self.assertEqual(failed,expected[mode])
                self.assertTrue(all(r['execution']=='NOT_EXECUTED' and r['conclusion']=='INCONCLUSIVE' for r in report['checks']))
                artifacts = json.dumps(report)+''.join(p.read_text(encoding='utf-8') for p in Path(folder).rglob('*') if p.is_file())
                for token in fixture.credential_bindings().values(): self.assertNotIn(token,artifacts)


if __name__ == '__main__':
    unittest.main()

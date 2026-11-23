"""Offline-only checks for the V2 contract-driven protocol layer."""
import os
import unittest

from p3_core.http.protocol import Observation
from p3_core.http.reviewed_protocol import (
    build_request_v2, correlate_v2, evaluate_v2, parse_response_v2, projection_v2,
)
from p3_core.http.reviewed_snapshot import CandidateSpec
from p3_core.models import InvalidInput

try:
    from tests.test_catalog_fixture import reviewed_snapshot
except Exception:  # pragma: no cover - discovery imports modules as top level
    from test_catalog_fixture import reviewed_snapshot

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def response_for(snapshot, fixture, check_id):
    spec = snapshot.candidate(check_id)
    identity = snapshot.identity(spec.identity_ref)
    credential = None if identity.credential_ref is None else fixture.credentials()[identity.credential_ref]
    request = build_request_v2(snapshot, spec, 'action_' + check_id.lower().replace('-', '_'), credential)
    return parse_response_v2(fixture.handle(request.wire), snapshot)


class ReviewedProtocolTests(unittest.TestCase):
    def setUp(self):
        self.fixture, self.document, self.bound, self.snapshot = reviewed_snapshot()

    def test_request_uses_reviewed_contract_path(self):
        spec = self.snapshot.candidate('CAT-C-DOC-A-READER')
        credential = self.fixture.credentials()['fixture/catalog-doc-reader']
        request = build_request_v2(self.snapshot, spec, 'action_one', credential)
        self.assertEqual(request.target, '/catalog/documents/doc-a')
        wire = request.wire.decode('ascii')
        self.assertIn('GET /catalog/documents/doc-a HTTP/1.1', wire)
        for forbidden in ('/v1/profile', '/v1/objects/obj-b', '/v1/admin/report'):
            self.assertNotIn(forbidden, wire)
        self.assertNotIn(credential, request.target)

    def test_anonymous_request_has_no_authorization_header(self):
        spec = self.snapshot.candidate('CAT-N-DOC-A-ANON')
        request = build_request_v2(self.snapshot, spec, 'action_anon', None)
        self.assertNotIn(b'Authorization', request.wire)
        with self.assertRaises(InvalidInput):
            build_request_v2(self.snapshot, spec, 'action_anon', 'unexpected')

    def test_credential_required_for_named_identity(self):
        spec = self.snapshot.candidate('CAT-C-DOC-A-READER')
        with self.assertRaises(InvalidInput):
            build_request_v2(self.snapshot, spec, 'action_two', None)

    def test_parameter_domain_enforced(self):
        spec = CandidateSpec('X', 'document_read', 'GET', 'doc-reader',
                             (('document_id', 'doc-z'),), (), 'ALLOW', None, 'doc-a-ok')
        with self.assertRaises(InvalidInput):
            build_request_v2(self.snapshot, spec, 'action_three', 'x')
        undeclared_query = CandidateSpec('Y', 'document_read', 'GET', 'doc-reader',
                                         (('document_id', 'doc-a'),), (('view', 'catalog'),),
                                         'ALLOW', None, 'doc-a-ok')
        with self.assertRaises(InvalidInput):
            build_request_v2(self.snapshot, undeclared_query, 'action_four', 'x')

    def test_correlation_rejects_extra_fields(self):
        observation = response_for(self.snapshot, self.fixture, 'CAT-C-DOC-A-READER')
        body = dict(observation.body)
        body['extra'] = 'value'
        with self.assertRaises(InvalidInput):
            correlate_v2(body, body['request_id'], self.snapshot)

    def test_correlation_rejects_instance_and_version_mismatch(self):
        observation = response_for(self.snapshot, self.fixture, 'CAT-C-DOC-A-READER')
        action = observation.body['request_id']
        for key, value in (('fixture_instance_id', 'other'),
                           ('contract_version', 'v9'),
                           ('request_id', 'other')):
            body = dict(observation.body)
            body[key] = value
            with self.assertRaises(InvalidInput):
                correlate_v2(body, action, self.snapshot)

    def test_allow_candidate_passes_on_matching_response(self):
        observation = response_for(self.snapshot, self.fixture, 'CAT-C-DOC-A-READER')
        spec = self.snapshot.candidate('CAT-C-DOC-A-READER')
        verdict = evaluate_v2(self.snapshot, spec, observation, observation.body['request_id'])
        self.assertEqual(verdict.simulated_conclusion, 'PASS')
        self.assertEqual(verdict.assertion, 'AUTHORIZED_CONTENT')
        self.assertEqual(verdict.execution, 'NOT_EXECUTED')

    def test_allow_candidate_fails_on_refusal(self):
        observation = response_for(self.snapshot, self.fixture, 'CAT-C-DOC-A-READER')
        spec = self.snapshot.candidate('CAT-C-DOC-A-READER')
        denied = Observation(True, 403, dict(observation.body,
                                             fields={'error_code': 'ACCESS_DENIED'}),
                             None, None, True)
        verdict = evaluate_v2(self.snapshot, spec, denied, observation.body['request_id'])
        self.assertEqual(verdict.simulated_conclusion, 'FAIL')
        self.assertEqual(verdict.assertion, 'CONFIRMED_OVERDENIAL')

    def test_deny_candidate_requires_control_for_pass(self):
        observation = response_for(self.snapshot, self.fixture, 'CAT-N-DOC-B-READER')
        spec = self.snapshot.candidate('CAT-N-DOC-B-READER')
        action = observation.body['request_id']
        without = evaluate_v2(self.snapshot, spec, observation, action, control_pass=False)
        self.assertEqual(without.simulated_conclusion, 'INCONCLUSIVE')
        self.assertEqual(without.assertion, 'MISSING_CONTROL')
        with_control = evaluate_v2(self.snapshot, spec, observation, action, control_pass=True)
        self.assertEqual(with_control.simulated_conclusion, 'PASS')
        self.assertEqual(with_control.assertion, 'REFUSAL_WITH_CONTROL')

    def test_disclosure_is_confirmed_for_deny_candidate(self):
        observation = response_for(self.snapshot, self.fixture, 'CAT-C-DOC-A-READER')
        spec = self.snapshot.candidate('CAT-C-DOC-A-READER')
        leak = Observation(True, 200, observation.body, None, None, True)
        deny_spec = CandidateSpec('Z', 'document_read', 'GET', 'doc-reader',
                                  (('document_id', 'doc-a'),), (), 'DENY', 'CAT-C-DOC-A-READER',
                                  'doc-a-ok')
        verdict = evaluate_v2(self.snapshot, deny_spec, leak, observation.body['request_id'],
                              control_pass=True)
        self.assertEqual(verdict.simulated_conclusion, 'FAIL')
        self.assertEqual(verdict.assertion, 'CONFIRMED_DISCLOSURE')

    def test_invalid_response_is_inconclusive_and_not_persisted(self):
        spec = self.snapshot.candidate('CAT-C-DOC-A-READER')
        broken = parse_response_v2(b'HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n'
                                   b'Content-Length: 5\r\n\r\n{"a":', self.snapshot)
        self.assertFalse(broken.valid)
        verdict = evaluate_v2(self.snapshot, spec, broken, 'action_broken')
        self.assertEqual(verdict.simulated_conclusion, 'INCONCLUSIVE')
        projection = projection_v2(self.snapshot, spec, broken, verdict, 'action_broken')
        self.assertIsNone(projection['response_fields'])

    def test_projection_keeps_only_evidence_fields(self):
        observation = response_for(self.snapshot, self.fixture, 'CAT-C-DOC-A-READER')
        spec = self.snapshot.candidate('CAT-C-DOC-A-READER')
        verdict = evaluate_v2(self.snapshot, spec, observation, observation.body['request_id'])
        projection = projection_v2(self.snapshot, spec, observation, verdict,
                                   observation.body['request_id'])
        self.assertEqual(projection['response_fields'], {'marker': 'DOC_A_CANARY'})
        self.assertNotIn('owner_id', projection['response_fields'])

    def test_v2_protocol_avoids_v1_business_names(self):
        path = os.path.join(HERE, 'src', 'p3_core', 'http', 'reviewed_protocol.py')
        with open(path, encoding='utf-8') as stream:
            source = stream.read()
        code = source.split('"""', 2)[-1]
        for forbidden in ('IDENTITIES', 'object_read', 'admin_report', 'profile_read',
                          'OBJECT_B_CANARY', 'ADMIN_REPORT_CANARY'):
            self.assertNotIn(forbidden, code)
        imports = ' '.join(line.strip() for line in code.splitlines()
                           if line.strip().startswith(('from ', 'import ')))
        self.assertNotIn('IDENTITIES', imports)
        self.assertNotIn('build_request', imports)
        self.assertNotIn(' evaluate', imports)

    # -- post-review remediation: strict deny status and field types --------
    def _deny_observation(self, status):
        spec = self.snapshot.candidate('CAT-N-DOC-A-ANON')
        rule = self.snapshot.rule(spec.response_rule)
        body = {'request_id': 'action_status_probe',
                'fixture_instance_id': self.snapshot.fixture_instance_id,
                'contract_version': self.snapshot.contract_version,
                'fields': dict(rule.expected_fields)}
        return spec, Observation(True, status, body, None, None, True), body

    def test_deny_declared_401_observed_403_is_not_pass(self):
        spec, observation, _ = self._deny_observation(403)
        rule = self.snapshot.rule(spec.response_rule)
        self.assertEqual(rule.status, 401)
        verdict = evaluate_v2(self.snapshot, spec, observation, 'action_status_probe',
                              control_pass=True)
        self.assertEqual(verdict.simulated_conclusion, 'INCONCLUSIVE')
        self.assertEqual(verdict.assertion, 'STATUS_MISMATCH')

    def test_deny_declared_403_observed_401_is_not_pass(self):
        spec = self.snapshot.candidate('CAT-N-DOC-B-READER')
        rule = self.snapshot.rule(spec.response_rule)
        self.assertEqual(rule.status, 403)
        body = {'request_id': 'action_status_probe',
                'fixture_instance_id': self.snapshot.fixture_instance_id,
                'contract_version': self.snapshot.contract_version,
                'fields': dict(rule.expected_fields)}
        observation = Observation(True, 401, body, None, None, True)
        verdict = evaluate_v2(self.snapshot, spec, observation, 'action_status_probe',
                              control_pass=True)
        self.assertEqual(verdict.simulated_conclusion, 'INCONCLUSIVE')
        self.assertEqual(verdict.assertion, 'STATUS_MISMATCH')
        # The matching status still passes, so the new rule is not a blanket refusal.
        good = Observation(True, 403, body, None, None, True)
        verdict_ok = evaluate_v2(self.snapshot, spec, good, 'action_status_probe',
                                 control_pass=True)
        self.assertEqual(verdict_ok.simulated_conclusion, 'PASS')

    def test_correlation_rejects_non_string_field_values(self):
        observation = response_for(self.snapshot, self.fixture, 'CAT-C-DOC-A-READER')
        action = observation.body['request_id']
        for fields in ({'marker': 123}, {'marker': None}, {1: 'value'}):
            body = dict(observation.body, fields=fields)
            with self.assertRaises(InvalidInput):
                correlate_v2(body, action, self.snapshot)
        for key, value in (('request_id', 1), ('fixture_instance_id', None),
                           ('contract_version', 2)):
            body = dict(observation.body)
            body[key] = value
            with self.assertRaises(InvalidInput):
                correlate_v2(body, action, self.snapshot)

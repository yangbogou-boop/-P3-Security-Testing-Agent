"""Offline-only checks for the two reviewed V2 synthetic fixtures.

The contract used below declares endpoints, identities, matrix, candidates and
response rules independently of the fixture's ACL code; the host cross-check then
compares the declaration with the fixture's declarative expectations.
"""
import copy
import hashlib
import json
import unittest

from p3_core.http.authorization import LocalRegistry, ReviewedMaterial
from p3_core.http.catalog_fixture import (
    CatalogFixture, _Identity, _Resource, _SCENARIOS, _ScenarioSpec,
)
from p3_core.http.reviewed_contract import (
    FORMAT, MODE, _bind_reviewed_contract, parse_contract, review_scope_digest,
)
from p3_core.http.reviewed_snapshot import LIMITS, build_snapshot
from p3_core.http.protocol import ResponseParser
from p3_core.models import InvalidInput

BINDING = dict(registry_ref='reviewed-catalog', authorization_id='reviewed-synthetic',
               authorization_version='v1')

DOC_A = {'resource_id': 'doc-a', 'owner_id': 'u_owner', 'marker': 'DOC_A_CANARY'}
DOC_B = {'resource_id': 'doc-b', 'owner_id': 'u_owner', 'marker': 'DOC_B_CANARY'}
DIR_A = {'resource_id': 'dir-a', 'owner_id': 'u_downer', 'marker': 'DIR_A_CANARY'}
DIR_B = {'resource_id': 'dir-b', 'owner_id': 'u_downer', 'marker': 'DIR_B_CANARY'}
DENIED = {'error_code': 'ACCESS_DENIED'}
ANONYMOUS = {'error_code': 'AUTHENTICATION_REQUIRED'}


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True).encode('utf-8')


def make_contract_document(scenario, fixture):
    if scenario == 'documents':
        endpoint = dict(endpoint_id='document_read', method='GET',
                        path_template='/catalog/documents/{document_id}',
                        path_domain={'document_id': ['doc-a', 'doc-b']}, query_domain={})
        identities = [dict(identity_ref='anonymous', role='guest', credential_ref=None),
                      dict(identity_ref='doc-reader', role='reader',
                           credential_ref='fixture/catalog-doc-reader'),
                      dict(identity_ref='doc-owner', role='owner',
                           credential_ref='fixture/catalog-doc-owner'),
                      dict(identity_ref='doc-admin', role='admin',
                           credential_ref='fixture/catalog-doc-admin')]
        rules = [dict(rule_id='doc-a-ok', status=200, expected_fields=DOC_A,
                      evidence_fields=['marker']),
                 dict(rule_id='doc-b-ok', status=200, expected_fields=DOC_B,
                      evidence_fields=['marker']),
                 dict(rule_id='denied-403', status=403, expected_fields=DENIED,
                      evidence_fields=['error_code']),
                 dict(rule_id='denied-401', status=401, expected_fields=ANONYMOUS,
                      evidence_fields=['error_code'])]
        cells = [(('doc-a',), 'doc-reader', 'ALLOW'), (('doc-b',), 'doc-reader', 'DENY'),
                 (('doc-b',), 'doc-owner', 'ALLOW'), (('doc-a',), 'anonymous', 'DENY')]
        specs = [('CAT-C-DOC-A-READER', ('doc-a',), 'doc-reader', 'ALLOW', None, 'doc-a-ok'),
                 ('CAT-N-DOC-B-READER', ('doc-b',), 'doc-reader', 'DENY',
                  'CAT-C-DOC-B-OWNER', 'denied-403'),
                 ('CAT-C-DOC-B-OWNER', ('doc-b',), 'doc-owner', 'ALLOW', None, 'doc-b-ok'),
                 ('CAT-N-DOC-A-ANON', ('doc-a',), 'anonymous', 'DENY',
                  'CAT-C-DOC-A-READER', 'denied-401')]
        param_name = 'document_id'
    elif scenario == 'directories':
        endpoint = dict(endpoint_id='directory_read', method='GET',
                        path_template='/catalog/directories/{directory_id}',
                        path_domain={'directory_id': ['dir-a', 'dir-b']}, query_domain={})
        identities = [dict(identity_ref='anonymous', role='guest', credential_ref=None),
                      dict(identity_ref='dir-viewer', role='viewer',
                           credential_ref='fixture/catalog-dir-viewer'),
                      dict(identity_ref='dir-owner', role='owner',
                           credential_ref='fixture/catalog-dir-owner'),
                      dict(identity_ref='dir-admin', role='admin',
                           credential_ref='fixture/catalog-dir-admin')]
        rules = [dict(rule_id='dir-a-ok', status=200, expected_fields=DIR_A,
                      evidence_fields=['marker']),
                 dict(rule_id='dir-b-ok', status=200, expected_fields=DIR_B,
                      evidence_fields=['marker']),
                 dict(rule_id='denied-403', status=403, expected_fields=DENIED,
                      evidence_fields=['error_code'])]
        cells = [(('dir-a',), 'dir-viewer', 'ALLOW'), (('dir-b',), 'dir-viewer', 'DENY'),
                 (('dir-b',), 'dir-owner', 'ALLOW')]
        specs = [('CAT-C-DIR-A-VIEWER', ('dir-a',), 'dir-viewer', 'ALLOW', None, 'dir-a-ok'),
                 ('CAT-N-DIR-B-VIEWER', ('dir-b',), 'dir-viewer', 'DENY',
                  'CAT-C-DIR-B-OWNER', 'denied-403'),
                 ('CAT-C-DIR-B-OWNER', ('dir-b',), 'dir-owner', 'ALLOW', None, 'dir-b-ok')]
        param_name = 'directory_id'
    else:
        raise AssertionError('unknown scenario')

    matrix = [dict(endpoint_id=endpoint['endpoint_id'], method='GET', identity_ref=identity,
                   path_params={param_name: value}, query={}, expected=expected)
              for (value,), identity, expected in cells]
    candidates = [dict(endpoint_id=endpoint['endpoint_id'], method='GET', identity_ref=identity,
                       path_params={param_name: value}, query={}, expected=expected,
                       check_id=check_id, control_id=control, response_rule=rule)
                  for check_id, (value,), identity, expected, control, rule in specs]
    document = dict(format=FORMAT, mode=MODE, contract_id=scenario, contract_version='v1',
                    target=dict(scheme='http', host='127.0.0.1', port=8767),
                    endpoints=[endpoint], identities=identities, matrix=matrix,
                    candidates=candidates, response_rules=rules,
                    budget=dict(version='reviewed-trial-v1', max_checks=8,
                                logical_timeout_seconds=90, concurrency=1),
                    fixture=dict(type='memory', fixture_id=fixture.fixture_id(),
                                 version=fixture.version(),
                                 content_sha256=fixture.canonical_digest()),
                    evidence=dict(format='p3-synthetic-evidence-v1', rule_version='v1'))
    return json.loads(json.dumps(document))


def material(reference, role, content, scope, *, until=4102444800):
    return ReviewedMaterial(reference, content, hashlib.sha256(content).hexdigest(), 'unit-only',
                            'unit-reviewer', 'unit-principal', role, scope, 0, until,
                            synthetic=True)


def reviewed_inputs(document, fixture_instance_id, *, until=4102444800):
    data = encode(document)
    binding = dict(BINDING, fixture_instance_id=fixture_instance_id)
    scope = review_scope_digest(parse_contract(data), **binding)
    review = material('review', 'contract-review', data, scope, until=until)
    row = dict(registry_ref=binding['registry_ref'], authorization_id=binding['authorization_id'],
               authorization_version=binding['authorization_version'], scope_digest=scope,
               owner_ref='owner', catalog_ref='catalog', delegation_ref=None)
    records = (material('owner', 'owner', b'unit owner', scope),
               material('catalog', 'teacher', b'unit catalog', scope))
    return binding, review, LocalRegistry(encode(row), records)


def reviewed_snapshot(scenario='documents', *, until=4102444800):
    fixture = CatalogFixture(scenario)
    document = make_contract_document(scenario, fixture)
    binding, review, registry = reviewed_inputs(document, fixture.instance_id(), until=until)
    bound = _bind_reviewed_contract(review, registry=registry, now=10, **binding)
    return fixture, document, bound, build_snapshot(bound, fixture)


class CatalogFixtureTests(unittest.TestCase):
    def test_two_scenarios_are_independent(self):
        documents, directories = CatalogFixture('documents'), CatalogFixture('directories')
        self.assertNotEqual(documents.fixture_id(), directories.fixture_id())
        self.assertNotEqual(documents.version(), directories.version())
        self.assertNotEqual(documents.canonical_digest(), directories.canonical_digest())
        self.assertNotEqual(documents.instance_id(), directories.instance_id())
        self.assertFalse({row[0] for row in documents.identity_records()}
                         & {row[0] for row in directories.identity_records()}
                         - {'anonymous'})

    def test_digest_is_stable_and_secret_free(self):
        first, second = CatalogFixture('documents'), CatalogFixture('documents')
        self.assertEqual(first.canonical_digest(), second.canonical_digest())
        self.assertNotEqual(first.instance_id(), second.instance_id())
        payload = json.dumps(dict(first.credentials()), ensure_ascii=False)
        digest = first.canonical_digest()
        for secret in first.credentials().values():
            self.assertNotIn(secret, digest)
            self.assertIn(secret, payload)

    def test_reference_expectation_follows_acl(self):
        fixture = CatalogFixture('documents')
        params = (('document_id', 'doc-a'),)
        self.assertEqual(fixture.reference_expectation('doc-reader', 'document_read', params, ())[0], 200)
        self.assertEqual(fixture.reference_expectation('doc-admin', 'document_read', params, ()),
                         (200, DOC_A))
        self.assertEqual(fixture.reference_expectation(
            'doc-reader', 'document_read', (('document_id', 'doc-b'),), ())[0], 403)
        self.assertEqual(fixture.reference_expectation('anonymous', 'document_read', params, ()),
                         (401, ANONYMOUS))

    def test_handle_produces_closed_correlated_body(self):
        fixture = CatalogFixture('documents')
        credential = fixture.credentials()['fixture/catalog-doc-reader']
        wire = ('GET /catalog/documents/doc-a HTTP/1.1\r\nHost: 127.0.0.1:8767\r\n'
                'X-P3-Action-Id: action_abc\r\nAuthorization: Bearer %s\r\n\r\n'
                % credential).encode('ascii')
        parser = ResponseParser(LIMITS)
        parser.feed(fixture.handle(wire))
        observation = parser.finish()
        self.assertTrue(observation.valid)
        self.assertEqual(observation.status, 200)
        self.assertEqual(set(observation.body),
                         {'request_id', 'fixture_instance_id', 'contract_version', 'fields'})
        self.assertEqual(observation.body['request_id'], 'action_abc')
        self.assertEqual(observation.body['fixture_instance_id'], fixture.instance_id())
        self.assertEqual(observation.body['fields'], DOC_A)

    def test_handle_unknown_target_rejected(self):
        fixture = CatalogFixture('documents')
        wire = b'GET /v1/profile HTTP/1.1\r\nX-P3-Action-Id: action_abc\r\n\r\n'
        with self.assertRaises(Exception):
            fixture.handle(wire)

    def test_snapshot_verifies_declared_content(self):
        fixture, document, bound, snapshot = reviewed_snapshot()
        self.assertEqual(snapshot.fixture_content_sha256, fixture.canonical_digest())
        self.assertEqual(snapshot.fixture_version, fixture.version())
        self.assertEqual(snapshot.fixture_instance_id, fixture.instance_id())
        self.assertEqual(snapshot.contract_id, 'documents')
        self.assertEqual(len(snapshot.candidate_ids()), 4)

    def test_snapshot_rejects_digest_mismatch(self):
        fixture = CatalogFixture('documents')
        document = make_contract_document('documents', fixture)
        document['fixture']['content_sha256'] = 'a' * 64
        binding, review, registry = reviewed_inputs(document, fixture.instance_id())
        bound = _bind_reviewed_contract(review, registry=registry, now=10, **binding)
        with self.assertRaises(InvalidInput):
            build_snapshot(bound, fixture)

    def test_snapshot_rejects_version_mismatch(self):
        fixture = CatalogFixture('documents')
        document = make_contract_document('documents', fixture)
        document['fixture']['version'] = 'other-version'
        binding, review, registry = reviewed_inputs(document, fixture.instance_id())
        bound = _bind_reviewed_contract(review, registry=registry, now=10, **binding)
        with self.assertRaises(InvalidInput):
            build_snapshot(bound, fixture)

    def test_snapshot_rejects_identity_mismatch(self):
        fixture = CatalogFixture('documents')
        document = make_contract_document('documents', fixture)
        document['identities'][1]['role'] = 'admin'
        binding, review, registry = reviewed_inputs(document, fixture.instance_id())
        bound = _bind_reviewed_contract(review, registry=registry, now=10, **binding)
        with self.assertRaises(InvalidInput):
            build_snapshot(bound, fixture)

    def test_snapshot_rejects_response_rule_mismatch(self):
        fixture = CatalogFixture('documents')
        document = make_contract_document('documents', fixture)
        document['response_rules'][0]['expected_fields'] = {
            'resource_id': 'doc-a', 'owner_id': 'u_owner', 'marker': 'WRONG_CANARY'}
        binding, review, registry = reviewed_inputs(document, fixture.instance_id())
        bound = _bind_reviewed_contract(review, registry=registry, now=10, **binding)
        with self.assertRaises(InvalidInput):
            build_snapshot(bound, fixture)

    def test_snapshot_never_uses_request_pipeline(self):
        class NoHandle(CatalogFixture):
            def handle(self, wire):
                raise AssertionError('request pipeline must not run during review')

        fixture = NoHandle('documents')
        document = make_contract_document('documents', fixture)
        binding, review, registry = reviewed_inputs(document, fixture.instance_id())
        bound = _bind_reviewed_contract(review, registry=registry, now=10, **binding)
        snapshot = build_snapshot(bound, fixture)
        self.assertEqual(len(snapshot.candidate_ids()), 4)

    def test_snapshot_is_read_only_and_private(self):
        fixture, document, bound, snapshot = reviewed_snapshot()
        with self.assertRaises(TypeError):
            snapshot.candidates['X'] = None
        spec = snapshot.candidate('CAT-C-DOC-A-READER')
        self.assertFalse(hasattr(spec, '__dict__'))
        self.assertIsNone(snapshot.candidate('NOT-A-CANDIDATE'))
        rendered = repr(snapshot)
        for secret in fixture.credentials().values():
            self.assertNotIn(secret, rendered)


class FixtureImmutabilityTests(unittest.TestCase):
    """F1: business data, ACL and containers are immutable value structures."""

    def test_resource_record_cannot_be_reassigned(self):
        fixture = CatalogFixture('documents')
        resource = fixture._resources[0]
        with self.assertRaises(AttributeError):
            resource.members = ('u_everyone',)
        with self.assertRaises(AttributeError):
            resource.owner_id = 'u_attacker'
        self.assertEqual(resource, _Resource('doc-a', 'u_owner', 'DOC_A_CANARY', ('u_reader',)))

    def test_object_setattr_cannot_change_resource_fields(self):
        fixture = CatalogFixture('documents')
        resource = fixture._resources[1]
        before = tuple(resource)
        for field, value in (('owner_id', 'u_attacker'), ('members', ('u_reader',)),
                             ('marker', 'FORGED'), ('resource_id', 'doc-z')):
            with self.assertRaises(AttributeError):
                object.__setattr__(resource, field, value)
        self.assertEqual(tuple(resource), before)
        self.assertFalse(hasattr(resource, '__dict__'))

    def test_identity_record_is_immutable(self):
        fixture = CatalogFixture('documents')
        identity = fixture._identities[1]
        before = tuple(identity)
        for field, value in (('role', 'admin'), ('user_id', 'u_attacker'),
                             ('credential_ref', 'fixture/injected')):
            with self.assertRaises(AttributeError):
                object.__setattr__(identity, field, value)
        self.assertEqual(tuple(identity), before)
        self.assertFalse(hasattr(identity, '__dict__'))

    def test_resources_cannot_be_inserted_or_replaced(self):
        fixture = CatalogFixture('documents')
        before = fixture.resource_records()
        with self.assertRaises(TypeError):
            fixture._resources[0] = _Resource('doc-z', 'u_attacker', 'X', ())
        with self.assertRaises(AttributeError):
            fixture._resources = ()
        with self.assertRaises(AttributeError):
            del fixture._resources
        self.assertEqual(fixture.resource_records(), before)
        self.assertEqual(fixture.resource_ids(), ('doc-a', 'doc-b'))

    def test_module_scenario_definitions_are_immutable(self):
        self.assertIsInstance(_SCENARIOS, tuple)
        with self.assertRaises(TypeError):
            _SCENARIOS[0] = None
        spec = _SCENARIOS[0]
        self.assertIsInstance(spec, _ScenarioSpec)
        with self.assertRaises(AttributeError):
            spec.resources = ()
        with self.assertRaises(AttributeError):
            object.__setattr__(spec, 'version', 'catalog-doc-v9')
        self.assertEqual(spec.version, 'catalog-doc-v1')

    def test_fixture_data_references_are_bound_after_construction(self):
        fixture = CatalogFixture('documents')
        before = fixture.identity_records()
        with self.assertRaises(AttributeError):
            fixture._identities = ()
        with self.assertRaises(AttributeError):
            fixture._spec = None
        with self.assertRaises(AttributeError):
            fixture._instance = 'forged'
        self.assertEqual(fixture.identity_records(), before)
        self.assertTrue(fixture.instance_id().startswith('fixture_'))

    def test_instances_do_not_share_mutable_data(self):
        first = CatalogFixture('documents')
        original = first.resource_records()
        with self.assertRaises(AttributeError):
            object.__setattr__(first._resources[1], 'owner_id', 'u_attacker')
        second = CatalogFixture('documents')
        self.assertEqual(second.resource_records(), original)
        self.assertIsNot(first._resources, second._resources)
        self.assertIsNot(first._resources[0], second._resources[0])
        self.assertIsNot(first._identities, second._identities)
        self.assertNotEqual(first.instance_id(), second.instance_id())

    def test_equal_content_instances_share_digest_and_fingerprint(self):
        first = CatalogFixture('documents')
        second = CatalogFixture('documents')
        self.assertEqual(first.canonical_digest(), second.canonical_digest())
        self.assertEqual(first.resource_records(), second.resource_records())
        self.assertNotEqual(first.instance_id(), second.instance_id())
        self.assertEqual(first.canonical_digest(),
                         '15f7b360424de42db44c7e1d7e77816d05051e0adade87d88cdf7c67328f3d4a')

    def test_acl_expansion_attempt_is_blocked(self):
        fixture = CatalogFixture('documents')
        before = fixture.canonical_digest()
        with self.assertRaises(TypeError):
            fixture._resources[1] = _Resource('doc-b', 'u_owner', 'DOC_B_CANARY', ('u_reader',))
        with self.assertRaises(AttributeError):
            object.__setattr__(fixture._resources[1], 'members', ('u_reader',))
        self.assertEqual(fixture.canonical_digest(), before)
        self.assertEqual(fixture.reference_expectation(
            'doc-reader', 'document_read', (('document_id', 'doc-b'),), ()),
            (403, {'error_code': 'ACCESS_DENIED'}))

    def test_acl_reduction_attempt_is_blocked(self):
        fixture = CatalogFixture('documents')
        before = fixture.canonical_digest()
        with self.assertRaises(TypeError):
            fixture._resources[0] = _Resource('doc-a', 'u_owner', 'DOC_A_CANARY', ())
        with self.assertRaises(AttributeError):
            object.__setattr__(fixture._resources[0], 'members', ())
        self.assertEqual(fixture.canonical_digest(), before)
        self.assertEqual(fixture.reference_expectation(
            'doc-reader', 'document_read', (('document_id', 'doc-a'),), ()),
            (200, {'resource_id': 'doc-a', 'owner_id': 'u_owner',
                   'marker': 'DOC_A_CANARY'}))

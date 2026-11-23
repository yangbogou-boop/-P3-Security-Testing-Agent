"""Offline-only checks for the V2 contract data model and review binding."""
import copy
from dataclasses import FrozenInstanceError, replace
import hashlib
import json
import unittest

from p3_core.http.authorization import LocalRegistry, ReviewedMaterial
from p3_core.http.contract import HttpConfig
from p3_core.http.reviewed_contract import (
    FORMAT, MAX_BYTES, MODE, _bind_reviewed_contract, parse_contract, review_scope_digest,
)
from p3_core.models import InvalidInput


def encode(value):
    return json.dumps(value, ensure_ascii=True).encode('utf-8')


def contract_document():
    common = dict(endpoint_id='item', method='GET', path_params={'doc_key': 'doc-m42'},
                  query={'view': 'catalog'})
    allowed = dict(common, identity_ref='reviewer', expected='ALLOW')
    refused = dict(common, identity_ref='reader', expected='DENY')
    document = dict(
        format=FORMAT, mode=MODE, contract_id='doc-catalog', contract_version='v1',
        target=dict(scheme='http', host='127.0.0.1', port=8766),
        endpoints=[dict(endpoint_id='item', method='GET', path_template='/catalog/items/{doc_key}',
                        path_domain={'doc_key': ['doc-m42', 'doc-k17']},
                        query_domain={'view': ['catalog']})],
        identities=[dict(identity_ref='reader', role='reader', credential_ref='fixture/reader'),
                    dict(identity_ref='reviewer', role='reviewer', credential_ref='fixture/reviewer')],
        matrix=[allowed, refused, dict(allowed, path_params={'doc_key': 'doc-k17'})],
        candidates=[dict(allowed, check_id='CAT-C-REVIEW', control_id=None, response_rule='item-ok'),
                    dict(refused, check_id='CAT-N-REVIEW', control_id='CAT-C-REVIEW',
                         response_rule='item-refused')],
        response_rules=[
            dict(rule_id='item-ok', status=200, expected_fields={'title': 'Synthetic Memo',
                                                                 'publication': 'pending'},
                 evidence_fields=['publication']),
            dict(rule_id='item-refused', status=403, expected_fields={'result': 'restricted'},
                 evidence_fields=['result']),
        ],
        budget=dict(version='trial-v2', max_checks=5, logical_timeout_seconds=45, concurrency=1),
        fixture=dict(type='memory', fixture_id='catalog', version='v1',
                     content_sha256=hashlib.sha256(b'synthetic dataset').hexdigest()),
        evidence=dict(format='p3-synthetic-evidence-v1', rule_version='v1'),
    )
    return json.loads(encode(document))


BINDING = dict(registry_ref='test-catalog', authorization_id='test-synthetic',
               authorization_version='v1', fixture_instance_id='test-catalog-instance')


def material(ref, role, content, scope, *, synthetic=True, until=100):
    return ReviewedMaterial(ref, content, hashlib.sha256(content).hexdigest(), 'test-only',
                            'unit-reviewer', 'unit-principal', role, scope, 0, until,
                            synthetic=synthetic)


def reviewed_materials(document, *, synthetic=True):
    data = encode(document)
    scope = review_scope_digest(parse_contract(data), **BINDING)
    review = material('review', 'contract-review', data, scope, until=70)
    row = dict(registry_ref=BINDING['registry_ref'], authorization_id=BINDING['authorization_id'],
               authorization_version=BINDING['authorization_version'], scope_digest=scope,
               owner_ref='owner', catalog_ref='catalog', delegation_ref=None)
    records = (material('owner', 'owner', b'test owner', scope, synthetic=synthetic),
               material('catalog', 'teacher', b'test catalog', scope, synthetic=synthetic))
    return review, encode(row), records


class ReviewedContractTests(unittest.TestCase):
    def setUp(self):
        self.raw = contract_document()

    def changed(self, path, value):
        raw = copy.deepcopy(self.raw)
        parent = raw
        for key in path[:-1]:
            parent = parent[key]
        parent[path[-1]] = value
        return raw

    def test_valid_contract_and_successful_review_association(self):
        review, row, records = reviewed_materials(self.raw)
        bound = _bind_reviewed_contract(review, registry=LocalRegistry(row, records), now=10, **BINDING)
        self.assertEqual(bound.contract.document['format'], FORMAT)
        self.assertEqual(tuple(c['check_id'] for c in bound.contract.document['candidates']),
                         ('CAT-C-REVIEW', 'CAT-N-REVIEW'))
        self.assertEqual(bound.scope_digest, review.scope_digest)
        self.assertEqual(bound.valid_until, 70)
        self.assertEqual(bound.fixture_instance_id, BINDING['fixture_instance_id'])
        self.assertFalse(hasattr(bound, 'permit'))
        self.assertFalse(hasattr(bound.contract, 'registry_ref'))
        with self.assertRaises(InvalidInput):
            HttpConfig.parse(self.raw)

    def test_nested_values_are_read_only(self):
        contract = parse_contract(encode(self.raw))
        self.assertFalse(hasattr(contract, '__dict__'))
        with self.assertRaises(FrozenInstanceError):
            contract.contract_digest = 'other'
        with self.assertRaises(TypeError):
            contract.document['target']['port'] = 9000
        with self.assertRaises(TypeError):
            contract.document['endpoints'][0]['path_domain']['doc_key'][0] = 'other'
        with self.assertRaises(TypeError):
            contract.document['response_rules'][0]['expected_fields']['title'] = 'other'
        self.raw['target']['port'] = 9001
        self.assertEqual(contract.document['target']['port'], 8766)

    def test_canonical_digest_ignores_json_object_order_and_spacing(self):
        canonical = parse_contract(encode(self.raw)).contract_digest
        alternate = json.dumps(self.raw, sort_keys=True, indent=4).encode()
        self.assertEqual(parse_contract(alternate).contract_digest, canonical)

    def test_bound_fields_change_contract_and_review_scope_digests(self):
        original = parse_contract(encode(self.raw))
        scope = review_scope_digest(original, **BINDING)
        changes = (
            (('contract_id',), 'another-catalog'), (('contract_version',), 'v2'),
            (('target', 'port'), 8767), (('endpoints', 0, 'path_template'), '/library/{doc_key}'),
            (('endpoints', 0, 'path_domain', 'doc_key'), ['doc-m42', 'doc-k17', 'doc-f20']),
            (('endpoints', 0, 'query_domain', 'view'), ['catalog', 'short']),
            (('identities', 0, 'role'), 'guest'), (('identities', 0, 'credential_ref'), 'fixture/guest'),
            (('matrix', 2, 'expected'), 'DENY'),
            (('candidates', 1, 'check_id'), 'CAT-N-OTHER'),
            (('candidates',), list(reversed(self.raw['candidates']))),
            (('response_rules', 0, 'expected_fields', 'title'), 'Different Memo'),
            (('response_rules', 0, 'evidence_fields'), ['title']),
            (('budget', 'version'), 'trial-v3'), (('budget', 'max_checks'), 6),
            (('budget', 'logical_timeout_seconds'), 46),
            (('fixture', 'fixture_id'), 'another-fixture'), (('fixture', 'version'), 'v2'),
            (('fixture', 'content_sha256'), 'a' * 64), (('evidence', 'rule_version'), 'v2'),
        )
        for path, value in changes:
            with self.subTest(path=path):
                modified = parse_contract(encode(self.changed(path, value)))
                self.assertNotEqual(modified.contract_digest, original.contract_digest)
                self.assertNotEqual(review_scope_digest(modified, **BINDING), scope)
        for key in BINDING:
            with self.subTest(binding=key):
                self.assertNotEqual(review_scope_digest(original, **dict(BINDING, **{key: 'changed'})), scope)

    def test_unknown_format_mode_and_fields_rejected(self):
        for raw in (dict(self.raw, format='p3-reviewed-contract-v3'),
                    dict(self.raw, mode='http-local'), dict(self.raw, approved_by='teacher'),
                    dict(self.raw, contract_version='invalid'),
                    self.changed(('evidence', 'format'), 'future')):
            with self.subTest(format=raw['format'], mode=raw['mode']):
                with self.assertRaises(InvalidInput):
                    parse_contract(encode(raw))

    def test_duplicate_keys_encoding_and_size_rejected(self):
        valid = encode(self.raw)
        contract = parse_contract(valid)
        self.assertLessEqual(len(valid), MAX_BYTES)
        at_limit = valid.ljust(MAX_BYTES, b' ')
        self.assertEqual(parse_contract(at_limit).contract_digest, contract.contract_digest)
        with self.assertRaisesRegex(InvalidInput, r'\AINVALID_CONTRACT_BYTES\Z'):
            parse_contract(at_limit + b' ')

        duplicate = valid.replace(b'"port": 8766', b'"port": 8766, "port": 8766')
        for data in (duplicate, b'\xff', self.raw, b'[]'):
            with self.subTest(input_type=type(data).__name__):
                with self.assertRaises(InvalidInput):
                    parse_contract(data)

    def test_duplicate_ids_and_matrix_cells_rejected(self):
        for key in ('identities', 'endpoints', 'candidates', 'response_rules', 'matrix'):
            with self.subTest(collection=key):
                with self.assertRaises(InvalidInput):
                    parse_contract(encode(self.changed((key,), self.raw[key] + [self.raw[key][0]])))
        conflicting = self.raw['matrix'] + [dict(self.raw['matrix'][0], expected='DENY')]
        with self.assertRaisesRegex(InvalidInput, 'DUPLICATE_MATRIX_CELL'):
            parse_contract(encode(self.changed(('matrix',), conflicting)))

    def test_missing_matrix_cell_and_disagreeing_expectation_rejected(self):
        for matrix in (self.raw['matrix'][1:], [dict(self.raw['matrix'][0], expected='DENY')] + self.raw['matrix'][1:]):
            with self.assertRaisesRegex(InvalidInput, 'CANDIDATE_MATRIX_MISMATCH'):
                parse_contract(encode(self.changed(('matrix',), matrix)))

    def test_missing_self_referencing_cyclic_and_mismatched_control_rejected(self):
        parse_contract(encode(self.raw))
        # Self-reference and the two-node cycle exercise the whole control structure.
        # A DENY cannot serve as its own ALLOW, and an ALLOW cannot point back.
        for control in (None, 'unknown', 'CAT-N-REVIEW'):
            with self.subTest(control=control):
                with self.assertRaisesRegex(InvalidInput, r'\AINVALID_CONTROL\Z'):
                    parse_contract(encode(self.changed(('candidates', 1, 'control_id'), control)))
        cyclic = self.changed(('candidates', 0, 'control_id'), 'CAT-N-REVIEW')
        with self.assertRaisesRegex(InvalidInput, r'\AINVALID_CONTROL\Z'):
            parse_contract(encode(cyclic))
        wrong_object = self.changed(('candidates', 0, 'path_params', 'doc_key'), 'doc-k17')
        with self.assertRaisesRegex(InvalidInput, r'\AINVALID_CONTROL\Z'):
            parse_contract(encode(wrong_object))

    def test_targets_methods_parameters_and_credential_fields_rejected(self):
        parse_contract(encode(self.raw))
        # Keep the matrix valid so that each error must come from the candidate.
        for key, value, code in (
            ('method', 'POST', 'INVALID_CHECK'),
            ('query', {'view': 'wrong'}, 'UNREGISTERED_PARAMETERS'),
        ):
            with self.subTest(candidate_field=key):
                with self.assertRaises(InvalidInput) as caught:
                    parse_contract(encode(self.changed(('candidates', 0, key), value)))
                self.assertEqual(str(caught.exception), code)

        cases = (
            (('target', 'host'), 'example.test'), (('target', 'host'), 'localhost'),
            (('target', 'scheme'), 'https'), (('target', 'port'), True),
            (('endpoints', 0, 'method'), 'POST'),
            (('endpoints', 0, 'path_template'), '//outside.example/a'),
            (('endpoints', 0, 'path_template'), '/items/../{doc_key}'),
            (('endpoints', 0, 'path_template'), '/items/{different}'),
            (('identities', 0, 'credential_ref'), 'Bearer example'),
            (('identities', 0, 'credential_ref'), 'fixture/reviewer'),
        )
        for path, value in cases:
            with self.subTest(path=path, value=value):
                with self.assertRaises(InvalidInput):
                    parse_contract(encode(self.changed(path, value)))

    def test_sensitive_query_parameter_rejected_by_domain_validation(self):
        valid = copy.deepcopy(self.raw)
        parse_contract(encode(valid))

        sensitive = copy.deepcopy(valid)
        domain = sensitive['endpoints'][0]['query_domain']
        domain['token'] = domain.pop('view')
        for section in ('matrix', 'candidates'):
            for row in sensitive[section]:
                query = row['query']
                query['token'] = query.pop('view')

        with self.assertRaises(InvalidInput) as caught:
            parse_contract(encode(sensitive))
        self.assertEqual(str(caught.exception), 'INVALID_PARAMETER_DOMAIN')

    def test_illegal_response_rules_and_evidence_projection_rejected(self):
        parse_contract(encode(self.raw))
        with self.assertRaisesRegex(InvalidInput, r'\AINVALID_RESPONSE_STATUS\Z'):
            parse_contract(encode(self.changed(('response_rules', 1, 'status'), 500)))

        cases = (
            (('candidates', 0, 'response_rule'), 'unregistered'),
            (('candidates', 0, 'response_rule'), 'item-refused'),
            (('response_rules', 0, 'evidence_fields'), ['not_expected']),
            (('response_rules', 0, 'evidence_fields'), ['publication', 'publication']),
        )
        for path, value in cases:
            with self.subTest(path=path):
                with self.assertRaises(InvalidInput):
                    parse_contract(encode(self.changed(path, value)))

    def test_response_expectation_rejects_sensitive_field_and_non_scalar_value(self):
        valid = copy.deepcopy(self.raw)
        parse_contract(encode(valid))

        for field, value in (('authorization', 'private'), ('title', ['invalid shape'])):
            with self.subTest(field=field):
                invalid = copy.deepcopy(valid)
                invalid['response_rules'][0]['expected_fields'][field] = value
                with self.assertRaises(InvalidInput) as caught:
                    parse_contract(encode(invalid))
                self.assertEqual(str(caught.exception), 'INVALID_RESPONSE_EXPECTATION')

    def test_budget_and_resource_limits(self):
        valid = encode(self.raw)
        parse_contract(valid)
        for key, value in (('max_checks', 65), ('max_checks', 0), ('max_checks', True),
                           ('logical_timeout_seconds', -1), ('logical_timeout_seconds', 3601),
                           ('concurrency', 2)):
            with self.subTest(key=key, value=value):
                with self.assertRaises(InvalidInput):
                    parse_contract(encode(self.changed(('budget', key), value)))
        timeout = b'"logical_timeout_seconds": 45'
        self.assertEqual(valid.count(timeout), 1)
        for literal, code in ((b'NaN', 'INVALID_JSON'), (b'Infinity', 'INVALID_JSON'),
                              (b'1e999', 'INVALID_BUDGET')):
            with self.subTest(literal=literal):
                sample = valid.replace(timeout, b'"logical_timeout_seconds": ' + literal)
                with self.assertRaises(InvalidInput) as caught:
                    parse_contract(sample)
                self.assertEqual(str(caught.exception), code)
        large = [dict(self.raw['endpoints'][0], endpoint_id='e' + str(i)) for i in range(65)]
        with self.assertRaisesRegex(InvalidInput, 'INVALID_CONTRACT_ROWS'):
            parse_contract(encode(self.changed(('endpoints',), large)))

    def test_plain_input_and_forged_or_non_synthetic_review_rejected(self):
        review, row, records = reviewed_materials(self.raw)
        registry = LocalRegistry(row, records)
        bound = _bind_reviewed_contract(review, registry=registry, now=10, **BINDING)
        self.assertEqual(bound.scope_digest, review.scope_digest)
        for record in (review.content, self.raw, parse_contract(review.content),
                       replace(review, role='owner'), replace(review, synthetic=False)):
            with self.subTest(record=type(record).__name__):
                with self.assertRaisesRegex(InvalidInput, 'REVIEWED_SYNTHETIC_MATERIAL_REQUIRED'):
                    _bind_reviewed_contract(record, registry=registry, now=10, **BINDING)
        for label, record, code in (
            ('wrong hash', replace(review, sha256='0' * 64), 'UNVERIFIED_MATERIAL'),
            ('revoked', replace(review, revoked=True), 'UNVERIFIED_MATERIAL'),
            ('expired', replace(review, valid_until=10), 'EXPIRED_MATERIAL'),
        ):
            with self.subTest(material=label):
                with self.assertRaises(InvalidInput) as caught:
                    _bind_reviewed_contract(record, registry=registry, now=10, **BINDING)
                self.assertEqual(str(caught.exception), code)
        with self.assertRaisesRegex(InvalidInput, 'MISSING_APPROVAL'):
            _bind_reviewed_contract(review, registry=LocalRegistry(row, ()), now=10, **BINDING)

    def test_changed_version_or_scope_rejected_by_old_registration(self):
        _, row, records = reviewed_materials(self.raw)
        registry = LocalRegistry(row, records)
        for path, value in ((('contract_version',), 'v2'), (('budget', 'max_checks'), 6),
                            (('candidates',), list(reversed(self.raw['candidates'])))):
            new_review, _, _ = reviewed_materials(self.changed(path, value))
            with self.subTest(path=path):
                with self.assertRaisesRegex(InvalidInput, 'REGISTRY_SCOPE_MISMATCH'):
                    _bind_reviewed_contract(new_review, registry=registry, now=10, **BINDING)
        review, _, _ = reviewed_materials(self.raw)
        with self.assertRaisesRegex(InvalidInput, 'REGISTRY_SCOPE_MISMATCH'):
            _bind_reviewed_contract(review, registry=registry, now=10,
                                    **dict(BINDING, fixture_instance_id='other-instance'))

    def test_real_registration_is_rejected_by_synthetic_binding(self):
        review, row, records = reviewed_materials(self.raw, synthetic=False)
        with self.assertRaisesRegex(InvalidInput, 'SYNTHETIC_REGISTRATION_REQUIRED'):
            _bind_reviewed_contract(review, registry=LocalRegistry(row, records), now=10, **BINDING)

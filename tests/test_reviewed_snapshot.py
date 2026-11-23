"""Offline-only checks that the V2 snapshot is a private, immutable authorisation basis."""
import json
import unittest

from p3_core.http.catalog_fixture import CatalogFixture
from p3_core.http.reviewed_fixture import FixturePort
from p3_core.http.reviewed_snapshot import (
    LIMITS, CandidateSpec, ReviewedRunSnapshot, build_snapshot,
)
from p3_core.models import InvalidInput

try:
    from tests.test_catalog_fixture import (
        make_contract_document, reviewed_inputs, reviewed_snapshot,
    )
except Exception:  # pragma: no cover - discovery imports modules as top level
    from test_catalog_fixture import (
        make_contract_document, reviewed_inputs, reviewed_snapshot,
    )


class _MalformedRecordsFixture(CatalogFixture):
    """Test double: reports resource records that are not immutable 4-tuples."""

    def __init__(self, scenario='documents'):
        self._digest = CatalogFixture(scenario).canonical_digest()
        super().__init__(scenario)

    def resource_records(self):
        return (('doc-a',),)

    def canonical_digest(self):
        return self._digest


def bound(document_mutator=None, fixture=None):
    fixture = fixture or CatalogFixture('documents')
    document = make_contract_document('documents', fixture)
    if document_mutator is not None:
        document_mutator(document)
    binding, review, registry = reviewed_inputs(document, fixture.instance_id())
    from p3_core.http.reviewed_contract import _bind_reviewed_contract
    return fixture, _bind_reviewed_contract(review, registry=registry, now=10, **binding)


class ReviewedSnapshotTests(unittest.TestCase):
    def test_snapshot_exposes_only_primitive_candidates(self):
        fixture, _, _, snapshot = reviewed_snapshot()
        spec = snapshot.candidate('CAT-C-DOC-A-READER')
        self.assertIsInstance(spec, CandidateSpec)
        self.assertEqual(spec.expected, 'ALLOW')
        self.assertIsInstance(spec.path_params, tuple)
        self.assertEqual(spec.path_params, (('document_id', 'doc-a'),))
        self.assertFalse(hasattr(spec, '__dict__'))

    def test_snapshot_mappings_are_read_only(self):
        _, _, _, snapshot = reviewed_snapshot()
        for mapping in (snapshot.candidates, snapshot.identities, snapshot.rules,
                        snapshot.matrix, snapshot.endpoints):
            with self.assertRaises(TypeError):
                mapping['injected'] = None

    def test_snapshot_holds_no_credential_secret(self):
        fixture, _, _, snapshot = reviewed_snapshot()
        rendered = repr(snapshot) + json.dumps(
            [tuple(row) for row in snapshot.identities.values()], ensure_ascii=False)
        for secret in fixture.credentials().values():
            self.assertNotIn(secret, rendered)

    def test_unknown_candidate_returns_none(self):
        _, _, _, snapshot = reviewed_snapshot()
        self.assertIsNone(snapshot.candidate('NOPE'))
        self.assertIsNone(snapshot.candidate(None))
        self.assertIsNone(snapshot.candidate(123))
        self.assertEqual(len(snapshot.candidate_ids()), 4)

    def test_port_incomplete_rejected(self):
        fixture, binding = bound()

        class Partial:
            def fixture_id(self):
                return fixture.fixture_id()

        with self.assertRaises(InvalidInput):
            build_snapshot(binding, Partial())

    def test_binding_type_rejected(self):
        fixture = CatalogFixture('documents')
        with self.assertRaises(InvalidInput):
            build_snapshot({'contract': None}, fixture)

    def test_contract_version_mismatch_rejected(self):
        def mutate(document):
            document['contract_version'] = 'v2'

        fixture, binding = bound(mutate)
        with self.assertRaises(InvalidInput):
            build_snapshot(binding, fixture)

    def test_fixture_id_mismatch_rejected(self):
        def mutate(document):
            document['fixture']['fixture_id'] = 'other-fixture'

        fixture, binding = bound(mutate)
        with self.assertRaises(InvalidInput):
            build_snapshot(binding, fixture)

    def test_matrix_mismatch_rejected(self):
        def mutate(document):
            # Declare a cell no candidate uses, with an outcome the fixture contradicts.
            document['matrix'].append(dict(endpoint_id='document_read', method='GET',
                                           identity_ref='doc-admin',
                                           path_params={'document_id': 'doc-a'},
                                           query={}, expected='DENY'))

        fixture, binding = bound(mutate)
        with self.assertRaises(InvalidInput):
            build_snapshot(binding, fixture)

    def test_snapshot_records_version_and_digest_bindings(self):
        fixture, _, _, snapshot = reviewed_snapshot()
        self.assertEqual(snapshot.fixture_id, fixture.fixture_id())
        self.assertEqual(snapshot.fixture_version, fixture.version())
        self.assertEqual(snapshot.fixture_content_sha256, fixture.canonical_digest())
        self.assertEqual(snapshot.contract_version, 'v1')
        self.assertEqual(len(snapshot.contract_digest), 64)
        self.assertEqual(len(snapshot.scope_digest), 64)
        self.assertEqual(snapshot.limits, LIMITS)
        self.assertGreater(snapshot.valid_until, 0)

    def test_snapshot_is_frozen(self):
        _, _, _, snapshot = reviewed_snapshot()
        with self.assertRaises(Exception):
            snapshot.max_checks = 99

    def test_directories_scenario_snapshot(self):
        fixture, _, _, snapshot = reviewed_snapshot('directories')
        self.assertEqual(snapshot.contract_id, 'directories')
        self.assertEqual(len(snapshot.candidate_ids()), 3)
        self.assertEqual(snapshot.fixture_version, fixture.version())
        self.assertTrue(snapshot.fixture_version.startswith('catalog-dir-'))

    # -- post-review remediation: verifiable immutability -------------------
    def test_object_setattr_cannot_change_authorisation_fields(self):
        fixture, _, _, snapshot = reviewed_snapshot()
        before = (snapshot.max_checks, snapshot.fixture_instance_id,
                  snapshot.fixture_content_sha256, snapshot.scope_digest,
                  snapshot.valid_until, snapshot.candidate_ids())
        attacks = (
            ('max_checks', 99),
            ('fixture_instance_id', 'fixture_injected'),
            ('fixture_content_sha256', 'a' * 64),
            ('scope_digest', 'b' * 64),
            ('valid_until', 1.0),
            ('candidates', {}),
            ('contract_digest', 'c' * 64),
        )
        for field, value in attacks:
            with self.assertRaises(AttributeError):
                object.__setattr__(snapshot, field, value)
        after = (snapshot.max_checks, snapshot.fixture_instance_id,
                 snapshot.fixture_content_sha256, snapshot.scope_digest,
                 snapshot.valid_until, snapshot.candidate_ids())
        self.assertEqual(before, after)
        # The authorisation basis is unchanged: same candidates still resolve.
        self.assertEqual(len(snapshot.candidate_ids()), 4)
        self.assertIsNotNone(snapshot.candidate('CAT-C-DOC-A-READER'))
        self.assertTrue(callable(snapshot.candidate))
        self.assertFalse(hasattr(snapshot, '__dict__'))

    def test_snapshot_mappings_cannot_be_mutated_in_place(self):
        _, _, _, snapshot = reviewed_snapshot()
        before = snapshot.candidate_ids()
        for mapping in (snapshot.candidates, snapshot.identities, snapshot.rules,
                        snapshot.endpoints, snapshot.matrix):
            with self.assertRaises(TypeError):
                mapping['injected'] = None
        self.assertEqual(snapshot.candidate_ids(), before)

    # -- F2: resource/ACL fingerprint ---------------------------------------
    def test_snapshot_carries_deterministic_resource_fingerprint(self):
        _, _, _, first = reviewed_snapshot()
        _, _, _, second = reviewed_snapshot()
        self.assertIsInstance(first.resource_fingerprint, tuple)
        self.assertEqual(first.resource_fingerprint, second.resource_fingerprint)
        self.assertEqual(first.resource_fingerprint[0],
                         ('doc-a', 'u_owner', 'DOC_A_CANARY', ('u_reader',)))
        self.assertEqual(first.resource_fingerprint[1],
                         ('doc-b', 'u_owner', 'DOC_B_CANARY', ()))
        self.assertEqual(tuple(sorted(first.resource_fingerprint)),
                         first.resource_fingerprint)
        # not derived from contract text: the acl members come from fixture data only
        self.assertEqual([row[3] for row in first.resource_fingerprint],
                         [('u_reader',), ()])
        with self.assertRaises(AttributeError):
            object.__setattr__(first, 'resource_fingerprint', ())
        self.assertEqual(first.resource_fingerprint[0][0], 'doc-a')

    def test_resource_fingerprint_rejects_malformed_fixture_records(self):
        fixture = _MalformedRecordsFixture('documents')
        document = make_contract_document('documents', fixture)
        binding, review, registry = reviewed_inputs(document, fixture.instance_id())
        from p3_core.http.reviewed_contract import _bind_reviewed_contract
        bound_contract = _bind_reviewed_contract(review, registry=registry, now=10, **binding)
        with self.assertRaises(InvalidInput):
            build_snapshot(bound_contract, fixture)

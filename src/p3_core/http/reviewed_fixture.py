"""Fixture port and canonical content digests for reviewed V2 offline scenarios.

A fixture owns its business data, identity mapping and ACL logic.  The digest
covers only declarative, reproducible content: generated credentials, instance
identifiers and timestamps are deliberately excluded so that one fixture version
keeps one stable digest.

Reference expectations are computed from the declarative data alone.  They never
call the request/response pipeline under test, so a pre-run review cannot be
derived from the implementation it is supposed to check.
"""
import hashlib
import json
import re

DIGEST_FORMAT = 'p3-fixture-digest-v1'
_SENSITIVE = re.compile(r'token|secret|password|credential|cookie|authorization|api[_-]?key', re.I)


def canonical_digest(payload):
    """SHA-256 over canonical JSON bytes (fixed key order, UTF-8, no NaN)."""
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False, allow_nan=False).encode('utf-8')).hexdigest()


def fixture_payload(*, scenario, fixture_id, version, contract_version,
                    identities, resources, acl, markers):
    """Build the digest payload from declarative content only.

    ``identities`` rows are ``(identity_ref, user_id, role, credential_ref)``;
    credential secrets are never part of this payload.
    """
    for reference, _user, role, credential_ref in identities:
        for name in (reference, role, credential_ref or ''):
            if _SENSITIVE.search(name):
                raise ValueError('SENSITIVE_FIXTURE_IDENTIFIER')
    return dict(format=DIGEST_FORMAT, scenario=scenario, fixture_id=fixture_id,
                version=version, contract_version=contract_version,
                identities=[list(row) for row in sorted(identities)],
                resources=[list(row) for row in sorted(resources)],
                acl=[list(row) for row in sorted(acl)],
                markers=sorted(markers))


class FixturePort:
    """Structural interface implemented by every reviewed V2 synthetic fixture."""

    def fixture_id(self):
        raise NotImplementedError

    def version(self):
        raise NotImplementedError

    def contract_version(self):
        raise NotImplementedError

    def instance_id(self):
        raise NotImplementedError

    def canonical_digest(self):
        raise NotImplementedError

    def identity_records(self):
        """Return ``((identity_ref, user_id, role, credential_ref), ...)`` without secrets."""
        raise NotImplementedError

    def credentials(self):
        """Return ``{credential_ref: secret}`` for the trusted host only."""
        raise NotImplementedError

    def reference_expectation(self, identity_ref, endpoint_id, path_params, query):
        """Return ``(status, fields)`` from declarative data; never parses a request."""
        raise NotImplementedError

    def handle(self, wire):
        """Return bounded HTTP response bytes for one accepted delivery."""
        raise NotImplementedError

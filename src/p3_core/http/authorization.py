"""Trusted host registration interface. Hashes bind bytes, never prove approval."""
from dataclasses import dataclass
import hashlib

from ..evidence import unique_id
from ..models import InvalidInput, fields, identifier, number
from .contract import strict_json


@dataclass(frozen=True)
class ReviewedMaterial:
    reference: str
    content: bytes
    sha256: str
    source: str
    reviewer: str
    principal: str
    role: str
    scope_digest: str
    valid_from: float
    valid_until: float
    revoked: bool = False
    synthetic: bool = False

    def verify(self, config, now):
        # These records are supplied by the trusted operator, NEVER the planner/config.
        for value in (self.reference, self.reviewer, self.principal): identifier(value)
        if (type(self.source) is not str or not self.source.strip()
                or type(self.content) is not bytes or not self.content
                or hashlib.sha256(self.content).hexdigest() != self.sha256
                or self.scope_digest != config.scope_digest
                or type(self.revoked) is not bool or self.revoked
                or type(self.synthetic) is not bool):
            raise InvalidInput('UNVERIFIED_MATERIAL')
        number(self.valid_from); number(self.valid_until)
        if not self.valid_from <= now < self.valid_until:
            raise InvalidInput('EXPIRED_MATERIAL')


@dataclass(frozen=True)
class PermitSnapshot:
    snapshot_id: str
    authorization_id: str
    authorization_version: str
    scope_digest: str
    registration_digest: str
    material_refs: tuple
    valid_until: float
    synthetic: bool


class LocalRegistry:
    """Load one already-reviewed byte snapshot with separately supplied materials.

    Caller must enforce host file permissions and verify provenance out-of-band.
    This is an explicit trust boundary, not a digital-signature/authentication service.
    No path is reread during a run; changed grants require revoke + a new run.
    """
    def __init__(self, registration_bytes, reviewed_materials):
        if type(registration_bytes) is not bytes:
            raise InvalidInput('REGISTRY_BYTES_REQUIRED')
        self._bytes = registration_bytes
        self._materials = tuple(reviewed_materials)

    def snapshot(self, config, now, *, simulation=False):
        number(now)
        r = strict_json(self._bytes)
        fields(r, 'registry_ref authorization_id authorization_version scope_digest owner_ref catalog_ref delegation_ref')
        for key in ('registry_ref', 'authorization_id', 'authorization_version', 'owner_ref', 'catalog_ref'):
            identifier(r[key])
        if r['delegation_ref'] is not None: identifier(r['delegation_ref'])
        if (r['registry_ref'] != config.registry_ref or r['authorization_id'] != config.authorization_id
                or r['authorization_version'] != config.authorization_version
                or r['scope_digest'] != config.scope_digest):
            raise InvalidInput('REGISTRY_SCOPE_MISMATCH')
        if any(type(m) is not ReviewedMaterial for m in self._materials):
            raise InvalidInput('UNVERIFIED_MATERIAL')
        materials = {m.reference: m for m in self._materials}
        if len(materials) != len(self._materials):
            raise InvalidInput('DUPLICATE_MATERIAL')
        owner, catalog = materials.get(r['owner_ref']), materials.get(r['catalog_ref'])
        if owner is None or catalog is None or owner.role not in ('owner', 'delegate') or catalog.role != 'teacher':
            raise InvalidInput('MISSING_APPROVAL')
        chosen = [owner, catalog]
        if owner.role == 'delegate':
            delegation = materials.get(r['delegation_ref'])
            if delegation is None or delegation.role != 'delegation' or delegation.principal != owner.principal:
                raise InvalidInput('MISSING_DELEGATION')
            chosen.append(delegation)
        elif r['delegation_ref'] is not None:
            raise InvalidInput('UNEXPECTED_DELEGATION')
        for m in chosen: m.verify(config, now)
        synthetic = any(m.synthetic for m in chosen)
        if synthetic and not simulation:
            raise InvalidInput('SYNTHETIC_PERMISSION_FORBIDDEN')
        return PermitSnapshot(unique_id('snapshot'), config.authorization_id,
                              config.authorization_version, config.scope_digest,
                              hashlib.sha256(self._bytes).hexdigest(),
                              tuple(m.reference for m in chosen), min(m.valid_until for m in chosen), synthetic)

"""Read-only material diagnostics. No snapshot minting, grant, or live switch."""
import hashlib
import json

from .http.contract import HttpConfig
from .models import number
from .acceptance import CASES


MATERIAL_KEYS={'reference','source','sha256','authorization_version','scope_digest','valid_from','valid_until',
               'role','principal','delegation_ref'}


def authorization_preflight(document,*,now,review_source=None):
    """review_source is a trusted-host read-only lookup, unavailable in CLI.

    Even that lookup only recognizes prior human review; no executable permit is
    returned. JSON assertions about approval never substitute for this lookup.
    """
    issues=[]
    def add(category,field):issues.append(dict(category=category,field=field))
    if type(document) is not dict:
        return dict(status='PENDING_AUTHORIZATION',issues=[dict(category='INVALID_FORMAT',field='document')],execution_allowed=False)
    allowed={'config','owner','teacher_catalog','fixture_binding','budget_record','revocation_responsibility','experiment_scope','exception_permissions'}
    if set(document)-allowed:add('INVALID_FORMAT','unknown_fields')
    for field in sorted(allowed):
        if document.get(field) is None:add('MISSING',field)
    cfg=None
    try:cfg=HttpConfig.parse(document.get('config'));number(now)
    except Exception:add('INVALID_FORMAT','config')
    reviewed=True
    for field in ('owner','teacher_catalog'):
        value=document.get(field)
        if value is None:reviewed=False;continue
        try:
            if type(value) is not dict or set(value)!=MATERIAL_KEYS:raise ValueError()
            for key in ('reference','source','sha256','authorization_version','scope_digest','principal'):
                if type(value[key]) is not str or not 1<=len(value[key])<=256:raise ValueError()
            for key in ('sha256','scope_digest'):
                if len(value[key])!=64 or any(c not in '0123456789abcdef' for c in value[key]):raise ValueError()
            if field=='teacher_catalog' and (value['role']!='teacher' or value['delegation_ref'] is not None):raise ValueError()
            if field=='owner':
                if value['role'] not in ('owner','delegate'):raise ValueError()
                if value['role']=='delegate' and (type(value['delegation_ref']) is not str or not value['delegation_ref']):
                    add('MISSING','owner.delegation_ref')
                if value['role']=='owner' and value['delegation_ref'] is not None:add('CONFLICT','owner.delegation_ref')
            start,end=number(value['valid_from']),number(value['valid_until'])
            if start>=end:raise ValueError()
            if not start<=now<end:add('CONFLICT',field+'.validity')
            if cfg and (value['scope_digest']!=cfg.scope_digest or value['authorization_version']!=cfg.authorization_version):
                add('CONFLICT',field+'.scope')
            # Human review evidence is bound to the exact submitted material metadata.
            digest=hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()
            try: known=review_source is not None and review_source(field,digest) is True
            except Exception: known=False
            if not known:
                add('SOURCE_UNVERIFIED',field);reviewed=False
        except Exception:add('INVALID_FORMAT',field);reviewed=False
    for field in ('budget_record','revocation_responsibility'):
        if field in document and (type(document[field]) is not str or not 1<=len(document[field])<=128):
            add('INVALID_FORMAT',field)
    for field in ('experiment_scope','exception_permissions'):
        value=document.get(field)
        if value is not None and (type(value) is not list or len(value)>32 or any(type(x) is not str or len(x)>64 for x in value)):
            add('INVALID_FORMAT',field)
    if isinstance(document.get('experiment_scope'),list) and isinstance(document.get('exception_permissions'),list):
        ordinary={'GOOD_PAIRED_CONTROLS','AUTH_DISCLOSURE','BOLA_DISCLOSURE','RBAC_DISCLOSURE'}
        if any(type(c) is str and c not in ordinary and c not in document['exception_permissions'] for c in document['experiment_scope']):
            add('CONFLICT','exception_permissions')
        known={c[0] for c in CASES}
        if (not document['experiment_scope'] or any(type(c) is not str or c not in known for c in document['experiment_scope'])
                or any(type(c) is not str or c not in known for c in document['exception_permissions'])):
            add('INVALID_FORMAT','experiment_scope')
    binding=document.get('fixture_binding')
    if binding is not None:
        if type(binding) is not dict or set(binding)!={'fixture_instance_id','scope_digest','credential_digest','supervisor_record_ref'}:
            add('INVALID_FORMAT','fixture_binding')
        elif (any(type(v) is not str or not v or len(v)>128 for v in binding.values()) or
              len(binding['credential_digest'])!=64 or any(c not in '0123456789abcdef' for c in binding['credential_digest'])):
            add('INVALID_FORMAT','fixture_binding')
        elif cfg and (binding['fixture_instance_id']!=cfg.fixture_instance_id or binding['scope_digest']!=cfg.scope_digest):
            add('CONFLICT','fixture_binding')
        else:add('RUN_BINDING_PENDING','fixture_binding')
    if reviewed and cfg:add('RUN_BINDING_PENDING','trusted_host')
    return dict(status='PENDING_AUTHORIZATION',execution_allowed=False,issues=issues,
                human_review_observed=reviewed and cfg is not None,
                note='No permission minted; source authenticity and actual runtime binding require trusted human review.')

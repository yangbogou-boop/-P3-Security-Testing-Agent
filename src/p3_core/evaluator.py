"""Read-only evaluation of a closed offline denial-record contract; no runner."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import sys

from .http.audit import verify_run

RULE_ID = 'P3-EVAL-DENY-001'
BUDGET_RULE_ID = 'P3-EVAL-BUDGET-001'
BUDGET_BASIS = 'p3-eval-trial-eight-v1'
STATUSES = ('PASS', 'FAIL', 'INSUFFICIENT_EVIDENCE', 'NOT_APPLICABLE')
MAX_FILE = 1048576
MAX_EVENTS = 512
NAMES = ('manifest.json', 'report.json', 'events.jsonl')
COUNTS = {'plan_count', 'attempt_count', 'request_count', 'model_request_count'}
COMMON = {'mode', 'provenance', 'run_id', 'evidence_id', 'sequence', 'kind', 'counts'}
EVENT_FIELDS = {
    'started': {'snapshot_id'}, 'plan_registered': set(),
    'proposal_registered': {'proposal_id', 'slot_id'},
    'authorization': {'slot_id', 'proposal_id', 'attempt_id', 'decision', 'reason'},
    'prepared': {'slot_id', 'action_id'},
    'model_io': {'action_id', 'phase', 'gate_sequence', 'sent_bytes', 'dispatch_started'},
    'response_headers': {'action_id', 'status'},
    'response_evidence': {'action_id', 'status', 'response_valid', 'assertions_complete',
                          'response_fields', 'diagnostic', 'assertion'},
    'simulated_assertion': {'action_id', 'assertion', 'evaluated_conclusion'},
    'completion_ready': set(),
}
REPORT_FIELDS = {'run_id', 'mode', 'provenance', 'strategy_id', 'planning_seconds',
                 'scope_digest', 'snapshot_id', 'state', 'reason', 'stop_conditions',
                 'counts', 'checks', 'audit_gap', 'cleanup_failed', 'revoke_received',
                 'revoke_effective_sequence', 'unperformed_approved_candidates'}
ROW_FIELDS = {'slot_id', 'proposal_id', 'check_id', 'attempt_id', 'action_id',
              'processed', 'authorization', 'execution', 'conclusion',
              'simulated_conclusion', 'assertion', 'status', 'headers_received',
              'transport_issue', 'evidence_ids'}
MANIFEST_FIELDS = {'run_id', 'provenance', 'counts', 'audit_gap', 'audit_limit_bytes',
                   'report_sha256', 'events_sha256', 'events_bytes', 'hash_scope'}


class EvaluationInputError(ValueError):
    """Invalid command/path, distinct from a completed evidence evaluation."""


class MissingEvidence(ValueError):
    pass


def require(condition, reason='INVALID_STRUCTURE'):
    if not condition:
        raise MissingEvidence(reason)


def identifier(value, prefix):
    require(type(value) is str and re.fullmatch(prefix + r'_[0-9a-f]{32}', value),
            'INVALID_ASSOCIATION_ID')


def short_text(value, nullable=False):
    require((nullable and value is None) or (type(value) is str and len(value) <= 256))


def http_status(value):
    require(value is None or (type(value) is int and 100 <= value <= 599))


def counts(value):
    require(type(value) is dict and set(value) == COUNTS)
    require(all(type(v) is int and 0 <= v <= 256 for v in value.values()))
    require(value['request_count'] == 0 and
            value['model_request_count'] <= value['attempt_count'] <= value['plan_count'],
            'COUNT_CONTRADICTION')


def strict_json(blob):
    # Bound nesting before the JSON parser allocates recursive structures.
    text = blob.decode('utf-8')
    depth = 0
    quoted = escaped = False
    for ch in text:
        if quoted:
            if escaped: escaped = False
            elif ch == '\\': escaped = True
            elif ch == '"': quoted = False
        elif ch == '"': quoted = True
        elif ch in '[{':
            depth += 1
            require(depth <= 16, 'JSON_DEPTH_LIMIT')
        elif ch in ']}': depth -= 1

    def pairs(items):
        result = {}
        for k, v in items:
            require(k not in result, 'DUPLICATE_JSON_KEY')
            result[k] = v
        return result

    def integer(s):
        require(len(s) <= 32, 'JSON_NUMBER_LIMIT')
        return int(s)

    def number(s):
        require(len(s) <= 64, 'JSON_NUMBER_LIMIT')
        v = float(s)
        require(math.isfinite(v), 'NONFINITE_JSON')
        return v

    def constant(_):
        raise MissingEvidence('NONFINITE_JSON')
    return json.loads(text, object_pairs_hook=pairs, parse_int=integer,
                      parse_float=number, parse_constant=constant)


def local_directory(value):
    raw = os.fspath(value)
    if (not isinstance(raw, str) or not raw or '://' in raw or '\x00' in raw
            or raw.replace('\\', '/').startswith('//')):
        raise EvaluationInputError('LOCAL_DIRECTORY_REQUIRED')
    p = Path(raw)
    if '..' in p.parts or any(':' in part for part in p.parts[1:]) or (p.drive and not p.root):
        raise EvaluationInputError('UNSAFE_PATH')
    p = p.absolute()
    try:
        for part in [*reversed(p.parents), p]:
            s = part.lstat()
            if stat.S_ISLNK(s.st_mode) or getattr(s, 'st_file_attributes', 0) & 1024:
                raise EvaluationInputError('LINK_OR_REPARSE_PATH_FORBIDDEN')
        if not p.is_dir(): raise EvaluationInputError('LOCAL_DIRECTORY_REQUIRED')
    except OSError:
        raise EvaluationInputError('LOCAL_DIRECTORY_REQUIRED') from None
    return p


def read_snapshot(directory):
    result = {}
    for name in NAMES:
        p = directory / name
        try:
            s = p.lstat()
            require(stat.S_ISREG(s.st_mode) and not p.is_symlink()
                    and not getattr(s, 'st_file_attributes', 0) & 1024,
                    'NONREGULAR_ARTIFACT')
            require(s.st_size <= MAX_FILE, 'FILE_SIZE_LIMIT')
            with p.open('rb') as f:
                opened = os.fstat(f.fileno())
                require(stat.S_ISREG(opened.st_mode) and
                        (s.st_dev, s.st_ino) == (opened.st_dev, opened.st_ino), 'ARTIFACT_CHANGED')
                data = f.read(MAX_FILE + 1)
            require(len(data) <= MAX_FILE, 'FILE_SIZE_LIMIT')
            result[name] = data
        except OSError:
            raise MissingEvidence('MISSING_OR_UNREADABLE_' + name.upper().replace('.', '_')) from None
    return result


def inspect(blobs, result):
    m, r = (strict_json(blobs[n]) for n in NAMES[:2])
    require(type(m) is dict and type(r) is dict)
    require('report_sha256' in m, 'MISSING_REPORT_SHA256')
    require(set(m) <= MANIFEST_FIELDS | {'evaluation_origin'} and MANIFEST_FIELDS <= set(m))
    require(set(r) <= REPORT_FIELDS | {'evaluation_origin'} and REPORT_FIELDS <= set(r))
    origin = r.get('evaluation_origin')
    require(origin == m.get('evaluation_origin') and origin in (None, 'SYNTHETIC_CALIBRATION'))
    result['provenance'] = origin or 'NO_NETWORK_SIMULATION'
    for d in (m, r):
        require(d['provenance'] == 'NO_NETWORK_SIMULATION', 'OFFLINE_SCOPE_REQUIRED')
        require(type(d['audit_gap']) is bool and not d['audit_gap'], 'AUDIT_GAP')
        counts(d['counts'])
    identifier(r['run_id'], 'run')
    result['subject_run_id'] = r['run_id']
    require(m['run_id'] == r['run_id'] and m['counts'] == r['counts'], 'RUN_OR_COUNT_MISMATCH')
    require(r['mode'] == 'http-local-simulation', 'OFFLINE_SCOPE_REQUIRED')
    identifier(r['snapshot_id'], 'snapshot')
    require(type(r['scope_digest']) is str and re.fullmatch(r'[0-9a-f]{64}', r['scope_digest']))
    short_text(r['strategy_id'])
    require(type(m['audit_limit_bytes']) is int and m['audit_limit_bytes'] > 0)
    require(m['hash_scope'] == 'first events_bytes bytes; later terminal rejections may append')
    require(r['revoke_received'] is None or (type(r['revoke_received']) in (int, float)
            and r['revoke_received'] >= 0))
    require(r['revoke_effective_sequence'] is None or
            (type(r['revoke_effective_sequence']) is int and r['revoke_effective_sequence'] > 0))
    require(r['state'] == 'COMPLETED' and r['reason'] is None and
            r['stop_conditions'] == [] and r['unperformed_approved_candidates'] == [] and
            r['cleanup_failed'] is False, 'INCOMPLETE_RUN_SCOPE')
    require(type(r['planning_seconds']) in (int, float) and r['planning_seconds'] >= 0)
    require(type(m['events_bytes']) is int and m['events_bytes'] == len(blobs['events.jsonl']),
            'EVENT_COVERAGE_INCOMPLETE')
    require(m['events_sha256'] == hashlib.sha256(blobs['events.jsonl']).hexdigest(), 'EVENT_HASH_MISMATCH')
    canonical = json.dumps(r, sort_keys=True, ensure_ascii=False, allow_nan=False).encode('utf-8')
    require(m['report_sha256'] == hashlib.sha256(canonical).hexdigest(), 'REPORT_HASH_MISMATCH')
    lines = blobs['events.jsonl'].splitlines()
    require(0 < len(lines) <= MAX_EVENTS and all(0 < len(x) <= 65536 for x in lines), 'EVENT_RESOURCE_LIMIT')
    events = [strict_json(x) for x in lines]
    rows = r['checks']
    require(type(rows) is list and 0 < len(rows) <= 256)
    for row in rows:
        require(type(row) is dict and set(row) == ROW_FIELDS)
        for key, prefix in [('slot_id', 'slot'), ('proposal_id', 'proposal'), ('attempt_id', 'attempt')]:
            identifier(row[key], prefix)
        if row['action_id'] is not None: identifier(row['action_id'], 'action')
        require(row['processed'] is True and type(row['headers_received']) is bool)
        require(row['authorization'] in ('ALLOW', 'DENY'))
        require(row['execution'] in ('NOT_EXECUTED', 'EXECUTED', 'ERROR', 'TIMEOUT'))
        require(row['conclusion'] in ('PASS', 'FAIL', 'INCONCLUSIVE') and
                row['simulated_conclusion'] in ('PASS', 'FAIL', 'INCONCLUSIVE'))
        require(type(row['assertion']) is str and len(row['assertion']) <= 64)
        short_text(row['check_id'], nullable=True)
        short_text(row['transport_issue'], nullable=True)
        http_status(row['status'])
        require(type(row['evidence_ids']) is list and len(row['evidence_ids']) <= MAX_EVENTS)
        for eid in row['evidence_ids']: identifier(eid, 'evidence')
    for key in ('slot_id', 'proposal_id', 'attempt_id'):
        require(len({x[key] for x in rows}) == len(rows), 'AMBIGUOUS_ASSOCIATION')
    actions = [x['action_id'] for x in rows if x['action_id'] is not None]
    require(len(actions) == len(set(actions)), 'AMBIGUOUS_ACTION')
    previous = dict.fromkeys(COUNTS, 0)
    by_slot = {row['slot_id']: row for row in rows}
    registered_slots, sent_actions = set(), set()
    plan_seen = False
    for seq, e in enumerate(events, 1):
        require(type(e) is dict and e.get('kind') in EVENT_FIELDS, 'UNSUPPORTED_EVENT')
        require(set(e) == COMMON | EVENT_FIELDS[e['kind']], 'INVALID_EVENT_FIELDS')
        require(type(e['sequence']) is int and e['sequence'] == seq, 'EVENT_SEQUENCE_GAP')
        require(e['run_id'] == r['run_id'] and e['mode'] == r['mode'] and
                e['provenance'] == r['provenance'], 'EVENT_SCOPE_MISMATCH')
        identifier(e['evidence_id'], 'evidence')
        counts(e['counts'])
        require(all(previous[k] <= e['counts'][k] <= r['counts'][k] for k in COUNTS), 'COUNT_CONTRADICTION')
        for key in ('slot_id', 'proposal_id', 'attempt_id', 'action_id'):
            if key in e: identifier(e[key], key[:-3])
        if e['kind'] == 'started':
            require(e['snapshot_id'] == r['snapshot_id'], 'SNAPSHOT_MISMATCH')
        if e['kind'] == 'authorization':
            require(e['decision'] in ('ALLOW', 'DENY'))
            short_text(e['reason'])
        if 'status' in e: http_status(e['status'])
        if 'assertion' in e: short_text(e['assertion'], nullable=True)
        if e['kind'] == 'response_evidence':
            require(type(e['response_valid']) is bool and type(e['assertions_complete']) is bool)
            require(e['response_fields'] is None or type(e['response_fields']) is dict)
            short_text(e['diagnostic'], nullable=True)
        if e['kind'] == 'simulated_assertion':
            require(e['evaluated_conclusion'] in ('PASS', 'FAIL', 'INCONCLUSIVE'))
        if e['kind'] == 'model_io':
            require(type(e['dispatch_started']) is bool and type(e['sent_bytes']) is int and
                    0 <= e['sent_bytes'] <= MAX_FILE and type(e['gate_sequence']) is int and
                    e['gate_sequence'] > 0 and e['phase'] in ('CONNECT', 'WRITE'))
            require(e['dispatch_started'] == (e['sent_bytes'] > 0), 'SEND_FACT_CONTRADICTION')
            require(e['phase'] == 'WRITE' or e['sent_bytes'] == 0, 'CONNECT_SEND_CONTRADICTION')
        # Reconstruct count transitions from events, not only final report totals.
        expected = dict(previous)
        if e['kind'] == 'started':
            require(seq == 1, 'DUPLICATE_LIFECYCLE_BOUNDARY')
        elif e['kind'] == 'plan_registered':
            require(seq == 2 and not plan_seen, 'INVALID_PLAN_REGISTRATION')
            plan_seen = True
            expected['plan_count'] = e['counts']['plan_count']
        else:
            require(plan_seen, 'MISSING_PLAN_REGISTRATION')
        if e['kind'] == 'proposal_registered':
            slot = e['slot_id']
            require(slot in by_slot and slot not in registered_slots and
                    e['proposal_id'] == by_slot[slot]['proposal_id'], 'INVALID_PROPOSAL_REGISTRATION')
            registered_slots.add(slot)
            expected['plan_count'] += 1
        elif e['kind'] == 'authorization':
            expected['attempt_count'] += 1
        elif e['kind'] == 'model_io' and e['dispatch_started'] and e['action_id'] not in sent_actions:
            sent_actions.add(e['action_id'])
            expected['model_request_count'] += 1
        require(e['counts'] == expected, 'EVENT_COUNT_TRANSITION_MISMATCH')
        previous = e['counts']
    require(events[0]['kind'] == 'started' and events[-1]['kind'] == 'completion_ready' and
            events[-1]['counts'] == r['counts'], 'MISSING_LIFECYCLE_BOUNDARY')
    ids = {e['evidence_id'] for e in events}
    require(len(ids) == len(events), 'DUPLICATE_EVIDENCE_ID')
    require(all(set(row['evidence_ids']) <= ids for row in rows), 'MISSING_EVENT_REFERENCE')
    auths = [e for e in events if e['kind'] == 'authorization']
    require(len(auths) == len(rows) == r['counts']['attempt_count'] == r['counts']['plan_count'],
            'MISSING_AUTHORIZATION_OR_COUNT_CONTRADICTION')
    for row in rows:
        linked = [e for e in auths if e['slot_id'] == row['slot_id']]
        require(len(linked) == 1, 'MISSING_OR_AMBIGUOUS_AUTHORIZATION')
        e = linked[0]
        # For ALLOW rows assertion is later replaced by the response verdict.
        # DENY rows retain the authorization reason and have no response verdict.
        expected_reason = row['assertion'] if row['authorization'] == 'DENY' else 'APPROVED'
        require(all(e[k] == row[k] for k in ('slot_id', 'proposal_id', 'attempt_id')) and
                e['decision'] == row['authorization'] and e['reason'] == expected_reason,
                'AUTHORIZATION_REPORT_CONTRADICTION')
        require(all(x['sequence'] < e['sequence'] for x in events
                    if x['kind'] == 'proposal_registered' and x['slot_id'] == row['slot_id']),
                'REGISTRATION_AFTER_AUTHORIZATION')
    targets = [x for x in rows if x['authorization'] == 'DENY' and x['assertion'] == 'NOT_APPROVED_CANDIDATE']
    require(len(targets) == 1, 'TARGET_NOT_UNIQUELY_IDENTIFIED')
    target = targets[0]
    require(target['headers_received'] is False and target['status'] is None and
            target['transport_issue'] is None, 'DENIAL_RESPONSE_CONTRADICTION')
    registered = [e for e in events if e['kind'] == 'proposal_registered' and e['slot_id'] == target['slot_id']]
    deny = next(e for e in auths if e['slot_id'] == target['slot_id'])
    require(len(registered) == 1 and registered[0]['proposal_id'] == target['proposal_id'] and
            registered[0]['sequence'] < deny['sequence'], 'MISSING_TARGET_REGISTRATION')
    prepared = {}
    for e in events:
        if e['kind'] != 'prepared': continue
        require(e['slot_id'] in by_slot and e['action_id'] not in prepared, 'UNKNOWN_OR_DUPLICATE_PREPARED')
        row = by_slot[e['slot_id']]
        require(row['action_id'] == e['action_id'], 'ACTION_REPORT_CONTRADICTION')
        ae = next(x for x in auths if x['slot_id'] == row['slot_id'])
        require(ae['sequence'] < e['sequence'], 'ACTION_ORDER_CONTRADICTION')
        prepared[e['action_id']] = e
    require(set(prepared) == set(actions), 'MISSING_PREPARED_ASSOCIATION')
    for e in events:
        if 'action_id' not in e or e['kind'] == 'prepared': continue
        require(e['action_id'] in prepared and prepared[e['action_id']]['sequence'] < e['sequence'],
                'UNASSOCIATED_ACTION_EVENT')
    by_id = {e['evidence_id']: e for e in events}
    for row in rows:
        require(len(row['evidence_ids']) == len(set(row['evidence_ids'])), 'DUPLICATE_EVENT_REFERENCE')
        for eid in row['evidence_ids']:
            linked = by_id[eid]
            require(linked.get('action_id') == row['action_id'] and row['action_id'] is not None,
                    'CROSS_CHECK_EVENT_REFERENCE')
    sends = [e for e in events if e['kind'] == 'model_io' and e['dispatch_started']]
    require(len({e['action_id'] for e in sends}) == r['counts']['model_request_count'], 'SEND_COUNT_CONTRADICTION')
    linked_io = [e for e in events if e['kind'] == 'model_io' and
                 prepared[e['action_id']]['slot_id'] == target['slot_id']]
    target_prepared = [e for e in prepared.values() if e['slot_id'] == target['slot_id']]
    violation = bool(linked_io or target_prepared or target['action_id'] is not None or
                     target['execution'] != 'NOT_EXECUTED')
    refs = [registered[0], deny] + target_prepared + linked_io
    result['evidence_references'] = [dict(artifact='events.jsonl', line=e['sequence'],
                                         evidence_id=e['evidence_id'], kind=e['kind']) for e in refs]
    result['observed_facts'] = dict(slot_id=target['slot_id'], proposal_id=target['proposal_id'],
        attempt_id=target['attempt_id'], authorization='DENY', reason='NOT_APPROVED_CANDIDATE',
        execution=target['execution'], action_id=target['action_id'],
        target_prepared_events=len(target_prepared), target_model_io_events=len(linked_io),
        counts=r['counts'], complete_event_count=len(events), approval_verified=False,
        source_authenticated=False, report_row_index=rows.index(target))
    return 'FAIL' if violation else 'PASS'


def inspect_budget(blobs, result):
    """Separate count rubric. Does not relax or invoke DENY-specific assertions."""
    m, r = (strict_json(blobs[n]) for n in NAMES[:2])
    require(type(m) is dict and type(r) is dict)
    require(MANIFEST_FIELDS <= set(m) <= MANIFEST_FIELDS | {'evaluation_origin'})
    require(REPORT_FIELDS <= set(r) <= REPORT_FIELDS | {'evaluation_origin'})
    identifier(r['run_id'], 'run')
    identifier(r['snapshot_id'], 'snapshot')
    require(type(r['scope_digest']) is str and re.fullmatch(r'[0-9a-f]{64}', r['scope_digest']),
            'MISSING_SCOPE_BINDING')
    require(r['mode'] == 'http-local-simulation' and r['provenance'] == m['provenance'] == 'NO_NETWORK_SIMULATION')
    require(m['run_id'] == r['run_id'] and m['counts'] == r['counts'])
    require(m['audit_gap'] is False and r['audit_gap'] is False, 'AUDIT_GAP')
    origin = r.get('evaluation_origin')
    require(origin == m.get('evaluation_origin') and origin in (None, 'SYNTHETIC_CALIBRATION'))
    result.update(subject_run_id=r['run_id'], provenance=origin or r['provenance'])
    counts(r['counts']); counts(m['counts'])
    require(type(m['events_bytes']) is int and m['events_bytes'] == len(blobs['events.jsonl']), 'EVENT_COVERAGE_INCOMPLETE')
    require(m['events_sha256'] == hashlib.sha256(blobs['events.jsonl']).hexdigest(), 'EVENT_HASH_MISMATCH')
    require(m['report_sha256'] == hashlib.sha256(json.dumps(r, sort_keys=True, ensure_ascii=False,
            allow_nan=False).encode('utf-8')).hexdigest(), 'REPORT_HASH_MISMATCH')
    lines = blobs['events.jsonl'].splitlines()
    require(0 < len(lines) <= MAX_EVENTS and all(0 < len(x) <= 65536 for x in lines))
    events = [strict_json(x) for x in lines]
    rows = r['checks']
    require(type(rows) is list and len(rows) <= 256)
    slots = {}; proposals = set(); attempts = set(); actions = set()
    for row in rows:
        require(type(row) is dict and set(row) == ROW_FIELDS)
        for key, prefix in [('slot_id','slot'),('proposal_id','proposal')]: identifier(row[key],prefix)
        require(row['slot_id'] not in slots and row['proposal_id'] not in proposals)
        slots[row['slot_id']] = row; proposals.add(row['proposal_id'])
        require(type(row['processed']) is bool and type(row['evidence_ids']) is list)
        require(row['authorization'] in ('ALLOW','DENY','NOT_EVALUATED'))
        require(row['execution'] == 'NOT_EXECUTED', 'OFFLINE_EXECUTION_CONTRADICTION')
        for key, prefix, seen in [('attempt_id','attempt',attempts),('action_id','action',actions)]:
            if row[key] is not None:
                identifier(row[key],prefix); require(row[key] not in seen); seen.add(row[key])
        for eid in row['evidence_ids']: identifier(eid,'evidence')
    event_fields = dict(EVENT_FIELDS, proposal_rejected=None)
    previous = dict.fromkeys(COUNTS,0)
    registered = set(); authorized = set(); prepared = {}; sent = set(); ids = set(); rejected = set()
    refs = []; initial = None; budget_rejections = []; completed = False
    for seq,e in enumerate(events,1):
        require(type(e) is dict and e.get('kind') in event_fields)
        kind = e['kind']
        fields = event_fields[kind]
        if kind == 'proposal_rejected':
            fields = {'proposal_id','reason'} | ({'slot_id'} if 'slot_id' in e else set())
        require(set(e) == COMMON | fields)
        require(type(e['sequence']) is int and e['sequence'] == seq, 'EVENT_SEQUENCE_GAP')
        require(e['run_id'] == r['run_id'] and e['mode'] == r['mode'] and e['provenance'] == r['provenance'])
        identifier(e['evidence_id'],'evidence'); require(e['evidence_id'] not in ids); ids.add(e['evidence_id'])
        counts(e['counts']); require(not completed, 'EVENT_AFTER_COMPLETION')
        for key in ('slot_id','proposal_id','attempt_id','action_id'):
            if key in e: identifier(e[key],key[:-3])
        expected = dict(previous)
        if kind == 'started':
            require(seq == 1 and e['snapshot_id'] == r['snapshot_id'])
        elif kind == 'plan_registered':
            require(seq == 2 and initial is None)
            initial = e['counts']['plan_count']; expected['plan_count'] = initial
        else:
            require(initial is not None, 'MISSING_PLAN_REGISTRATION')
        if kind == 'proposal_registered':
            s=e['slot_id']; require(s in slots and s not in registered and s not in authorized)
            require(e['proposal_id'] == slots[s]['proposal_id'])
            registered.add(s); expected['plan_count'] += 1
        elif kind == 'authorization':
            s=e['slot_id']; require(s in slots and s not in authorized)
            row=slots[s]
            require(e['proposal_id']==row['proposal_id'] and e['attempt_id']==row['attempt_id'])
            require(e['decision']==row['authorization'] and e['decision'] in ('ALLOW','DENY'))
            require(e['reason']==('APPROVED' if e['decision']=='ALLOW' else row['assertion']))
            authorized.add(s); expected['attempt_count'] += 1
        elif kind == 'prepared':
            s=e['slot_id']; a=e['action_id']
            require(s in authorized and slots[s]['authorization']=='ALLOW' and slots[s]['action_id']==a and a not in prepared)
            prepared[a]=s
        elif 'action_id' in e:
            require(e['action_id'] in prepared, 'UNASSOCIATED_ACTION_EVENT')
            if kind == 'model_io':
                require(type(e['sent_bytes']) is int and 0 <= e['sent_bytes'] <= MAX_FILE)
                require(type(e['dispatch_started']) is bool and e['dispatch_started']==(e['sent_bytes']>0))
                require(type(e['gate_sequence']) is int and e['gate_sequence']>0)
                require(e['phase'] in ('CONNECT','WRITE') and (e['phase']=='WRITE' or e['sent_bytes']==0))
                if e['dispatch_started'] and e['action_id'] not in sent:
                    sent.add(e['action_id']); expected['model_request_count'] += 1
        if kind == 'proposal_rejected':
            require(e['proposal_id'] not in proposals | rejected)
            rejected.add(e['proposal_id'])
            if e['reason']=='REGISTERED_CHECK_IMMUTABLE': require(e.get('slot_id') in slots)
            elif e['reason']=='BUDGET_EXHAUSTED':
                require('slot_id' not in e and previous['plan_count']==8, 'BUDGET_REJECTION_CONTRADICTION')
                budget_rejections.append(e)
            else: raise MissingEvidence('UNSUPPORTED_REJECTION_BOUNDARY')
        if kind == 'completion_ready': completed=True
        require(e['counts']==expected, 'EVENT_COUNT_TRANSITION_MISMATCH')
        previous=expected
        if kind in ('plan_registered','proposal_registered','proposal_rejected','authorization','model_io'):
            refs.append(dict(artifact='events.jsonl',line=seq,evidence_id=e['evidence_id'],kind=kind))
    require(previous == r['counts'] and len(rows)==previous['plan_count'] and initial is not None)
    require(len(rows)-len(registered)==initial and set(prepared)==actions)
    for s,row in slots.items():
        require((s in authorized)==(row['attempt_id'] is not None))
        if s not in authorized:
            require(row['authorization']=='NOT_EVALUATED' and row['processed'] is False and row['action_id'] is None)
        if row['authorization']=='DENY': require(row['processed'] is True and row['action_id'] is None)
        for eid in row['evidence_ids']:
            require(any(e['evidence_id']==eid and e.get('action_id')==row['action_id'] and row['action_id'] is not None for e in events))
    require(r['state'] in ('COMPLETED','STOPPED'))
    if r['state']=='COMPLETED':
        require(completed and all(row['processed'] for row in rows) and not budget_rejections
                and r['reason'] is None and r['stop_conditions']==[], 'TERMINAL_CONTRADICTION')
    else:
        require(r['reason']=='BUDGET_EXHAUSTED' and r['stop_conditions']==['BUDGET_EXHAUSTED']
                and budget_rejections and not completed, 'STOP_EVIDENCE_MISSING')
        raise MissingEvidence('STOP_EFFECTIVE_BOUNDARY_UNAVAILABLE')
    result['observed_facts']=dict(counts=previous,benchmark_version=BUDGET_BASIS,max_checks=8,
        benchmark_binding='RULE_SELECTION_ONLY',runtime_budget_verified=False,scope_digest=r['scope_digest'])
    result['evidence_references']=refs
    return 'FAIL' if previous['plan_count']>8 else 'PASS'


def evaluate(directory, rule_id=RULE_ID):
    if rule_id not in (RULE_ID,BUDGET_RULE_ID): raise EvaluationInputError('UNSUPPORTED_RULE')
    directory = local_directory(directory)
    result = dict(schema_version='p3-evaluation-v1', evaluator_version='1.0', rule_id=rule_id,
        status='INSUFFICIENT_EVIDENCE', evidence_directory=str(directory), subject_run_id=None,
        provenance='UNVERIFIED_INPUT', evidence_level='LOCAL_OFFLINE_RECORD_INTERNAL_CONSISTENCY',
        checked_artifacts=[], observed_facts={}, evidence_references=[],
        limitations=['Only the unique recorded NOT_APPROVED_CANDIDATE denial is evaluated.',
                     'No independent proof of original input, permission, source authenticity or historical execution version.',
                     'Absence of recorded model dispatch is not proof of no OS/network send.',
                     'No real API verdict, formal course grade or peer reproduction.'],
        missing_evidence=[], suggested_next_check=[], human_signoff='pending', score=None,
        approval_verified=False, source_authenticated=False)
    if rule_id == BUDGET_RULE_ID:
        result['limitations'][0] = 'Fixed evaluation benchmark p3-eval-trial-eight-v1: at most 8; actual runtime budget configuration is NOT independently bound.'
        result['limitations'].append('No independent 90-second, concurrency, cancellation, or stop-effective ordering proof; not full REQ-010/GWT-N04/N05 acceptance.')
    try:
        blobs = read_snapshot(directory)
        result['checked_artifacts'] = [dict(name=n, bytes=len(b), sha256=hashlib.sha256(b).hexdigest())
                                       for n, b in blobs.items()]
        verdict = inspect(blobs, result) if rule_id == RULE_ID else inspect_budget(blobs,result)
        checked = verify_run(directory)
        require(checked.get('integrity') == 'VERIFIED' and checked.get('approval_verified') is False
                and checked.get('appended_bytes') == 0, 'VERIFY_RUN_INCOMPLETE')
        require(read_snapshot(directory) == blobs, 'ARTIFACT_CHANGED_DURING_EVALUATION')
        result['status'] = verdict
        result['suggested_next_check'] = ['Human review of cited records and their source; no automatic re-execution.']
    except (MissingEvidence, OSError, ValueError, TypeError, KeyError, RecursionError, OverflowError):
        # Never expose malformed values, exception bodies or candidate secrets.
        exc = sys.exc_info()[1]
        reason = str(exc) if isinstance(exc, MissingEvidence) else 'MALFORMED_OR_UNREADABLE_EVIDENCE'
        result['observed_facts'] = {}
        result['evidence_references'] = []
        result['missing_evidence'] = [reason]
        result['suggested_next_check'] = ['Obtain an intact, attributable client artifact set and unique target registration; preserve current originals.']
    return result


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise EvaluationInputError('INVALID_ARGUMENTS')


def main(argv=None):
    try:
        parser = Parser(description=__doc__)
        parser.add_argument('--run', required=True)
        parser.add_argument('--rule', required=True, choices=[RULE_ID,BUDGET_RULE_ID])
        args = parser.parse_args(argv)
        result = evaluate(args.run, args.rule)
    except EvaluationInputError as exc:
        print(json.dumps(dict(error=str(exc), evaluation_completed=False)))
        return 2
    except Exception:
        print(json.dumps(dict(error='EVALUATOR_ERROR', evaluation_completed=False)))
        return 3
    print(json.dumps(result, ensure_ascii=True, allow_nan=False, indent=2))
    return 0  # Completed evaluation, including FAIL or INSUFFICIENT_EVIDENCE.


if __name__ == '__main__':
    raise SystemExit(main())

"""Read-only independent verifier for V2 reviewed offline evidence.

The verifier reads only the three persisted artifacts (``manifest.json``,
``report.json``, ``events.jsonl``).  It never imports ``ReviewedOfflineRun``,
never calls a fixture, never executes a candidate check and never writes to the
evidence directory.

It rebuilds the fourteen ``reviewed_counts`` from the persisted events with its
own logic (it does not call any runner counter routine), then reports six
separate axes.  A single ``VERIFIED`` flag is deliberately not produced: hash
integrity, evidence completeness, counter replay, delivery association,
contract association and provenance are different questions.

Fail-closed rules
-----------------
* missing/truncated events, ``audit_gap``, ``evidence_complete=false`` or a
  non-empty ``unpersisted_event_kinds`` make the evidence INCOMPLETE;
* any contradiction makes the relevant axis a violation and ``consistent`` false;
* the runner's own ``check_invariants`` result is never trusted (it is not even
  read);
* ``approval_verified``, ``source_authenticated`` and
  ``runtime_authorisation_verified`` are always false: the artifacts cannot
  prove that an external review or execution permission was genuine.
"""
import hashlib
import json
import re

from ..evaluator import (
    MAX_EVENTS, EvaluationInputError, MissingEvidence,
    local_directory, read_snapshot, strict_json,
)

SCHEMA_VERSION = 'p3-reviewed-evidence-v1'
MODE = 'reviewed-offline-simulation'
PROVENANCE = 'NO_NETWORK_SIMULATION'
# Scope-binding format added in 3B-2A.  Evidence without it is 3B-1 format and its
# budget/candidate facts are NOT_CHECKABLE, never assumed.
EVIDENCE_VERSION = 'p3-reviewed-evidence-v2'
CANDIDATE_LIMIT = 64
SCOPE_IDENTITY_KEYS = ('snapshot_id', 'contract_id', 'contract_version',
                       'contract_digest', 'scope_digest', 'fixture_id',
                       'fixture_version', 'fixture_content_sha256', 'fixture_instance_id')
SCOPE_KEYS = ('evidence_version', *SCOPE_IDENTITY_KEYS, 'budget_version',
              'max_checks', 'logical_timeout_seconds', 'concurrency', 'candidates')

COMMON = frozenset(('mode', 'provenance', 'run_id', 'evidence_id', 'sequence',
                    'kind', 'counts'))
COUNTERS = (
    'authorization_decisions', 'authorized_count', 'denied_count',
    'proposal_rejected_count', 'prepared_count', 'prepare_failed_count',
    'dispatch_accepted_count', 'delivery_consumed_count', 'delivery_aborted_count',
    'fixture_started_count', 'fixture_handled_count', 'fixture_failed_count',
    'dispatch_cancelled_count', 'response_observed_count',
)
EVENT_FIELDS = {
    'reviewed_started': {'snapshot_id', 'contract_id', 'fixture_instance_id'},
    'reviewed_scope_binding': set(SCOPE_KEYS),
    'reviewed_preflight_rejected': {'reason'},
    'reviewed_proposal_registered': {'slot_id', 'proposal_id', 'candidate', 'known'},
    'reviewed_proposal_rejected': {'reason'},
    'reviewed_authorization': {'slot_id', 'proposal_id', 'attempt_id', 'decision',
                              'reason', 'candidate'},
    'reviewed_prepared': {'slot_id', 'action_id', 'candidate'},
    'reviewed_prepare_failed': {'slot_id', 'action_id', 'reason'},
    'reviewed_dispatch_accepted': {'slot_id', 'action_id', 'dispatch_seq',
                                  'wire_sha256'},
    'reviewed_dispatch_cancelled': {'slot_id', 'action_id', 'reason'},
    'reviewed_delivery_consumed': {'action_id', 'dispatch_seq'},
    'reviewed_delivery_aborted': {'action_id', 'dispatch_seq', 'revoke_seq', 'reason'},
    'reviewed_fixture_started': {'action_id', 'dispatch_seq'},
    'reviewed_fixture_handled': {'action_id', 'dispatch_seq'},
    'reviewed_fixture_failed': {'action_id', 'dispatch_seq', 'reason'},
    'reviewed_revoked_during_delivery': {'action_id', 'dispatch_seq', 'revoke_seq'},
    'reviewed_response_evidence': {'action_id', 'status', 'response_valid',
                                   'assertions_complete', 'response_fields',
                                   'diagnostic', 'assertion'},
    'reviewed_assertion': {'action_id', 'assertion', 'simulated_conclusion'},
    'reviewed_control_resolution': {'action_id', 'assertion', 'simulated_conclusion'},
    'reviewed_completion_ready': set(),
}
RESULT_COUNTS = frozenset(('plan_count', 'attempt_count', 'request_count',
                           'model_request_count'))
# Fields the runner adds only for some rejection reasons (duplicate / budget carry
# the candidate; NOT_RUNNING and INVALID_PROPOSAL do not).
EVENT_OPTIONAL = {
    'reviewed_proposal_rejected': {'candidate'},
}
REPORT_REQUIRED = frozenset((
    'run_id', 'mode', 'provenance', 'state', 'reason', 'stop_conditions', 'counts',
    'reviewed_counts', 'checks', 'audit_gap', 'evidence_complete',
    'unpersisted_event_kinds', 'snapshot_id', 'contract_id', 'contract_version',
    'contract_digest', 'scope_digest', 'fixture_id', 'fixture_version',
    'fixture_content_sha256', 'fixture_instance_id', 'revoke_sequence',
    'real_network_requests', 'network_latency', 'OS_SEND_PROOF',
    'unperformed_approved_candidates',
))
ROW_REQUIRED = frozenset((
    'slot_id', 'proposal_id', 'check_id', 'attempt_id', 'action_id', 'dispatch_seq',
    'authorization', 'execution', 'conclusion', 'simulated_conclusion', 'assertion',
    'processed', 'evidence_ids',
))
AXIS_GOOD = {
    'file_integrity': 'VERIFIED',
    'evidence_completeness': 'COMPLETE',
    'counter_consistency': 'MATCH',
    'delivery_association': 'CONSISTENT',
    'contract_association': 'CONSISTENT',
    'provenance': 'NO_NETWORK_SIMULATION',
}
# The scope axis has a third, non-blocking state: 3B-1 evidence never persisted the
# reviewed budget or candidate universe, so it must stay NOT_CHECKABLE rather than
# silently reinterpreting old evidence as failing.
SCOPE_NOT_CHECKABLE = 'NOT_CHECKABLE'
LIMITATIONS = (
    'NO_WALL_CLOCK: events carry no timestamps, so no local duration can be derived.',
    'AUTHORISATION_NOT_VERIFIED: review material and approval are not part of the '
    'artifacts; approval and runtime authorisation remain unverified.',
    'T3_NOT_ISOLATED: same-process code could rewrite any artifact or the verifier '
    'itself; this verifier only detects contradictions in persisted bytes.',
)
_HASH = re.compile(r'[0-9a-f]{64}')
_ID = re.compile(r'[a-z]+_[0-9a-f]{32}')
_SCOPE_IDENTIFIER = re.compile(r'[A-Za-z0-9_.-]{1,80}')


def _valid_identifier(value):
    return type(value) is str and _SCOPE_IDENTIFIER.fullmatch(value) is not None


def _blank(reason):
    return dict(schema_version=SCHEMA_VERSION, subject={}, consistent=False,
                axes=dict(file_integrity='INCOMPLETE_OR_INVALID',
                          evidence_completeness='INCOMPLETE',
                          counter_consistency='NOT_CHECKABLE',
                          delivery_association='NOT_CHECKABLE',
                          contract_association='NOT_CHECKABLE',
                          scope_binding_consistency='NOT_CHECKABLE',
                          provenance='UNKNOWN'),
                gaps=[reason], violations=[], counts_replayed={}, counts_reported={},
                counts_mismatch={}, approval_verified=False,
                source_authenticated=False, runtime_authorisation_verified=False,
                limitations=list(LIMITATIONS))


def _require(condition, gap):
    if not condition:
        raise MissingEvidence(gap)


def _load(directory):
    root = local_directory(directory)
    blobs = read_snapshot(root)
    report = strict_json(blobs['report.json'])
    manifest = strict_json(blobs['manifest.json'])
    _require(type(report) is dict and type(manifest) is dict, 'INVALID_JSON_ROOT')
    text = blobs['events.jsonl'].decode('utf-8')
    lines = text.splitlines()
    _require(0 < len(lines) <= MAX_EVENTS, 'EVENT_RESOURCE_LIMIT')
    _require(all(0 < len(line) <= 65536 for line in lines), 'EVENT_RESOURCE_LIMIT')
    events = [strict_json(line.encode('utf-8')) for line in lines]
    return root, blobs, report, manifest, events


def _file_axis(blobs, report, manifest, events):
    """Hashes and counts: proves the bytes are the bytes that were sealed."""
    canonical = json.dumps(report, sort_keys=True, ensure_ascii=False,
                           allow_nan=False).encode('utf-8')
    _require(manifest.get('report_sha256') == hashlib.sha256(canonical).hexdigest(),
             'REPORT_HASH_MISMATCH')
    _require(manifest.get('run_id') == report.get('run_id'), 'RUN_ID_MISMATCH')
    _require(manifest.get('counts') == report.get('counts'), 'COUNT_BLOCK_MISMATCH')
    sealed = manifest.get('events_bytes')
    _require(type(sealed) is int and 0 < sealed <= len(blobs['events.jsonl']),
             'EVENT_COVERAGE_INCOMPLETE')
    prefix = blobs['events.jsonl'][:sealed]
    _require(hashlib.sha256(prefix).hexdigest() == manifest.get('events_sha256'),
             'EVENT_HASH_MISMATCH')
    _require(len(events) == len(prefix.splitlines()), 'EVENT_TRAIL_MODIFIED')
    return len(blobs['events.jsonl']) - sealed


def _completeness_axis(report, manifest, events):
    gaps = []
    if report.get('audit_gap') is not False or manifest.get('audit_gap') is not False:
        gaps.append('AUDIT_GAP')
    if report.get('evidence_complete') is not True:
        gaps.append('EVIDENCE_INCOMPLETE')
    if manifest.get('evidence_complete') is not True:
        gaps.append('MANIFEST_EVIDENCE_INCOMPLETE')
    if report.get('unpersisted_event_kinds') != []:
        gaps.append('UNPERSISTED_EVENTS')
    for index, event in enumerate(events, 1):
        if type(event) is not dict or event.get('sequence') != index:
            gaps.append('EVENT_SEQUENCE_GAP')
            break
    if any(event.get('run_id') != report.get('run_id') for event in events):
        gaps.append('EVENT_RUN_ID_MISMATCH')
    if any(event.get('kind') not in EVENT_FIELDS for event in events):
        gaps.append('UNKNOWN_EVENT_KIND')
    if any(set(event) != COMMON | EVENT_FIELDS.get(event.get('kind'), set())
           and set(event) != (COMMON | EVENT_FIELDS.get(event.get('kind'), set())
                              | EVENT_OPTIONAL.get(event.get('kind'), set()))
           for event in events):
        gaps.append('INVALID_EVENT_FIELDS')
    if any(event.get('provenance') != report.get('provenance') for event in events):
        gaps.append('EVENT_PROVENANCE_MISMATCH')
    return ('INCOMPLETE' if gaps else 'COMPLETE'), gaps


COUNTER_TRANSITIONS = {
    # The runner commits these counters before emitting the event, so the snapshot
    # carried by the event already contains its own increment.
    'reviewed_proposal_registered': 'plan_count',
    'reviewed_authorization': 'attempt_count',
    'reviewed_dispatch_accepted': 'model_request_count',
}


def _event_counts(events, report, strict):
    """Cross-check the four-key counter snapshot carried by every event.

    ``strict`` demands the exact per-kind transition; it is only usable when the
    run has no audit gap (a committed counter may then have no persisted event).
    """
    violations = []
    previous = None
    for event in events:
        block = event.get('counts')
        if (type(block) is not dict or set(block) != RESULT_COUNTS
                or any(type(value) is not int or not 0 <= value <= 256
                       for value in block.values())):
            violations.append('INVALID_EVENT_COUNTS')
            continue
        if block['request_count'] != 0:
            violations.append('EVENT_REQUEST_COUNT_NONZERO')
        if previous is None:
            if strict and any(block.values()):
                violations.append('EVENT_COUNTS_INITIAL_NONZERO')
        else:
            if any(block[name] < previous[name] for name in RESULT_COUNTS):
                violations.append('EVENT_COUNTS_NOT_MONOTONE')
            if strict:
                expected = dict(previous)
                field = COUNTER_TRANSITIONS.get(event['kind'])
                if field is not None:
                    expected[field] += 1
                if block != expected:
                    violations.append('EVENT_COUNT_TRANSITION_MISMATCH')
        previous = block
    if strict and previous is not None and previous != report.get('counts'):
        violations.append('EVENT_COUNTS_FINAL_MISMATCH')
    return violations


def _counters(events):
    """Independent replay of the fourteen reviewed counters."""
    counts = dict.fromkeys(COUNTERS, 0)
    for event in events:
        kind = event['kind']
        if kind == 'reviewed_authorization':
            counts['authorization_decisions'] += 1
            if event['decision'] == 'ALLOW':
                counts['authorized_count'] += 1
            elif event['decision'] == 'DENY':
                counts['denied_count'] += 1
        elif kind == 'reviewed_proposal_rejected':
            # A proposal rejected because the run is not running never increments
            # the counter; every other rejection reason does.
            if event['reason'] != 'NOT_RUNNING':
                counts['proposal_rejected_count'] += 1
        elif kind == 'reviewed_prepared':
            counts['prepared_count'] += 1
        elif kind == 'reviewed_prepare_failed':
            counts['prepare_failed_count'] += 1
        elif kind == 'reviewed_dispatch_accepted':
            counts['dispatch_accepted_count'] += 1
        elif kind == 'reviewed_delivery_consumed':
            counts['delivery_consumed_count'] += 1
        elif kind == 'reviewed_delivery_aborted':
            counts['delivery_aborted_count'] += 1
        elif kind == 'reviewed_fixture_started':
            counts['fixture_started_count'] += 1
        elif kind == 'reviewed_fixture_handled':
            counts['fixture_handled_count'] += 1
        elif kind == 'reviewed_fixture_failed':
            counts['fixture_failed_count'] += 1
    # A slot can be cancelled at most once, so the counter is the number of
    # distinct cancelled slots, not the number of cancel events.
    counts['dispatch_cancelled_count'] = len({
        event['slot_id'] for event in events
        if event['kind'] == 'reviewed_dispatch_cancelled'})
    # One observation needs both the projected evidence and the assertion.
    evidence_actions = {event['action_id'] for event in events
                        if event['kind'] == 'reviewed_response_evidence'}
    assertion_actions = {event['action_id'] for event in events
                         if event['kind'] == 'reviewed_assertion'}
    counts['response_observed_count'] = len(evidence_actions & assertion_actions)
    return counts


def _association(events, report):
    """Strict per-action ordering: accepted -> consumed -> started -> handled/failed."""
    violations = []
    slots = {}
    prepared_slot_by_action = {}
    action_by_slot = {}
    cancel_seen = set()
    accepted_seq = {}
    accepted_slots = {}
    consumed = set()
    aborted = set()
    started = set()
    finished = set()
    revoke_values = []
    for event in events:
        kind = event['kind']
        slot_id = event.get('slot_id')
        action_id = event.get('action_id')
        if kind == 'reviewed_proposal_registered':
            if slot_id in slots:
                violations.append('SLOT_ID_DUPLICATE')
            slots[slot_id] = {'proposal_id': event['proposal_id'], 'authorized': None}
        elif kind == 'reviewed_authorization':
            if slot_id not in slots:
                violations.append('AUTHORIZATION_WITHOUT_REGISTRATION')
                continue
            if slots[slot_id]['authorized'] is not None:
                violations.append('AUTHORIZATION_REPEATED')
            if event['decision'] not in ('ALLOW', 'DENY'):
                violations.append('INVALID_AUTHORIZATION_DECISION')
            if event['proposal_id'] != slots[slot_id]['proposal_id']:
                violations.append('AUTHORIZATION_PROPOSAL_MISMATCH')
            slots[slot_id]['authorized'] = event['decision']
        elif kind == 'reviewed_prepared':
            if slots.get(slot_id, {}).get('authorized') != 'ALLOW':
                violations.append('PREPARED_WITHOUT_ALLOW')
            if action_id in prepared_slot_by_action:
                violations.append('ACTION_PREPARED_TWICE')
            if slot_id in action_by_slot and action_by_slot[slot_id] != action_id:
                violations.append('SLOT_PREPARED_TWICE')
            prepared_slot_by_action[action_id] = slot_id
            action_by_slot[slot_id] = action_id
        elif kind == 'reviewed_dispatch_cancelled':
            if slot_id in cancel_seen:
                violations.append('CANCEL_REPEATED')
            cancel_seen.add(slot_id)
            if slot_id not in action_by_slot:
                violations.append('CANCEL_WITHOUT_PREPARED')
            elif action_id is not None and action_by_slot[slot_id] != action_id:
                violations.append('CANCEL_SLOT_MISMATCH')
        elif kind == 'reviewed_dispatch_accepted':
            if action_id not in prepared_slot_by_action:
                violations.append('ACCEPT_WITHOUT_PREPARED')
            elif prepared_slot_by_action[action_id] != slot_id:
                violations.append('ACCEPT_SLOT_MISMATCH')
            if slot_id in accepted_slots:
                violations.append('SLOT_ACCEPTED_TWICE')
            dispatch_seq = event['dispatch_seq']
            if dispatch_seq in accepted_seq.values():
                violations.append('DISPATCH_SEQ_DUPLICATE')
            accepted_seq[action_id] = dispatch_seq
            accepted_slots[slot_id] = dispatch_seq
        elif kind in ('reviewed_delivery_consumed', 'reviewed_delivery_aborted'):
            if action_id not in accepted_seq:
                violations.append('DELIVERY_WITHOUT_ACCEPT')
            if event['dispatch_seq'] != accepted_seq.get(action_id):
                violations.append('DELIVERY_SEQ_MISMATCH')
            if action_id in started:
                violations.append('DELIVERY_AFTER_FIXTURE_STARTED')
            if kind == 'reviewed_delivery_consumed':
                if action_id in consumed:
                    violations.append('CONSUMED_TWICE')
                if action_id in aborted:
                    violations.append('CONSUMED_AFTER_ABORT')
                consumed.add(action_id)
            else:
                if action_id in aborted:
                    violations.append('ABORTED_TWICE')
                if action_id in consumed:
                    violations.append('ABORT_AFTER_CONSUME')
                aborted.add(action_id)
                revoke_values.append(event.get('revoke_seq'))
        elif kind == 'reviewed_fixture_started':
            if action_id in aborted:
                violations.append('FIXTURE_STARTED_AFTER_ABORT')
            if action_id not in consumed:
                violations.append('FIXTURE_STARTED_BEFORE_CONSUMED')
            if action_id in started:
                violations.append('FIXTURE_STARTED_TWICE')
            started.add(action_id)
        elif kind in ('reviewed_fixture_handled', 'reviewed_fixture_failed'):
            if action_id not in started:
                violations.append('HANDLED_WITHOUT_STARTED'
                                  if kind == 'reviewed_fixture_handled'
                                  else 'FAILED_WITHOUT_STARTED')
            if action_id in finished:
                violations.append('FIXTURE_FINISHED_TWICE')
            finished.add(action_id)
        elif kind == 'reviewed_revoked_during_delivery':
            # gate_sequence ordering, not event ordering: revocation must follow
            # the dispatch it interrupted.
            if event['revoke_seq'] <= event['dispatch_seq']:
                violations.append('REVOKE_NOT_AFTER_DISPATCH')
            revoke_values.append(event['revoke_seq'])
    for action_id in consumed & aborted:
        violations.append('CONSUMED_AND_ABORTED')
    for action_id in accepted_seq:
        if action_id not in consumed and action_id not in aborted:
            violations.append('UNTERMINATED_DELIVERY')
    return sorted(set(violations)), accepted_seq, revoke_values


def _revoke(report, accepted_seq, revoke_values):
    """Bind the reported revoke sequence to the sequences proven by events."""
    violations = []
    notes = []
    values = {value for value in revoke_values if value is not None}
    reported = report.get('revoke_sequence')
    if len(values) > 1:
        violations.append('REVOKE_SEQUENCE_CONFLICT')
    if values:
        value = max(values)
        if reported is None:
            violations.append('REVOKE_SEQUENCE_MISSING')
        elif type(reported) is not int or reported != value:
            violations.append('REVOKE_SEQUENCE_MISMATCH')
        for dispatch_seq in accepted_seq.values():
            if dispatch_seq > value:
                violations.append('DISPATCH_AFTER_REVOKE')
    elif reported is not None:
        # Legal case: revoked after prepare and before any accept, so no delivery
        # event carries the sequence.  The value stays unproven, but any claimed
        # ordering must still hold.
        notes.append('REVOKE_SEQUENCE_UNBOUND')
        if type(reported) is int:
            for dispatch_seq in accepted_seq.values():
                if dispatch_seq > reported:
                    violations.append('DISPATCH_AFTER_REVOKE')
    return sorted(set(violations)), notes


def _rows(report, events, accepted_seq):
    violations = []
    rows = report.get('checks')
    _require(type(rows) is list and len(rows) <= 256, 'INVALID_ROWS')
    by_action = {}
    for event in events:
        if event['kind'] == 'reviewed_authorization':
            by_action.setdefault(('slot', event.get('slot_id')), event)
    assertions = {event['action_id'] for event in events
                  if event['kind'] == 'reviewed_assertion'}
    for row in rows:
        if type(row) is not dict or not ROW_REQUIRED <= set(row):
            violations.append('INVALID_ROW')
            continue
        slot_id = row['slot_id']
        if row['action_id'] is not None and row['dispatch_seq'] is not None:
            if row['action_id'] not in accepted_seq:
                violations.append('ROW_ACTION_NOT_ACCEPTED')
            elif row['dispatch_seq'] != accepted_seq[row['action_id']]:
                violations.append('ROW_DISPATCH_SEQ_MISMATCH')
            if row['processed'] is not (row['action_id'] in assertions):
                violations.append('ROW_PROCESSED_MISMATCH')
        elif row['action_id'] is not None:
            # Prepared but never dispatched: it may hold an action id, but no
            # delivery event may exist for it.
            if row['action_id'] in accepted_seq:
                violations.append('ROW_ACTION_ACCEPTED_WITHOUT_SEQ')
            if row['processed'] is True:
                violations.append('ROW_PROCESSED_WITHOUT_DISPATCH')
        elif row['dispatch_seq'] is not None:
            violations.append('ROW_SEQ_WITHOUT_ACTION')
        authorization = by_action.get(('slot', slot_id))
        if authorization is None:
            if row['authorization'] != 'NOT_EVALUATED':
                violations.append('ROW_AUTHORIZATION_WITHOUT_EVENT')
        elif row['authorization'] != authorization['decision']:
            violations.append('ROW_AUTHORIZATION_MISMATCH')
    return sorted(set(violations))


def _contract(report, events):
    gaps = []
    started = [event for event in events if event['kind'] == 'reviewed_started']
    if len(started) != 1:
        return 'NOT_CHECKABLE', ['STARTED_EVENT_MISSING']
    started = started[0]
    if started['snapshot_id'] != report.get('snapshot_id'):
        gaps.append('SNAPSHOT_ID_MISMATCH')
    if started['contract_id'] != report.get('contract_id'):
        gaps.append('CONTRACT_ID_MISMATCH')
    if started['fixture_instance_id'] != report.get('fixture_instance_id'):
        gaps.append('FIXTURE_INSTANCE_MISMATCH')
    for name in ('contract_digest', 'scope_digest', 'fixture_content_sha256'):
        if not (type(report.get(name)) is str and _HASH.fullmatch(report[name])):
            gaps.append('INVALID_' + name.upper())
    if not (type(report.get('snapshot_id')) is str and _ID.fullmatch(report['snapshot_id'])):
        gaps.append('INVALID_SNAPSHOT_ID')
    return ('MISMATCH' if gaps else 'CONSISTENT'), gaps


def _scope_candidates(report, events, candidates):
    """Reconstruct approved candidate sets and verify their relation to report rows."""
    approved = set(candidates)
    slots, prepared, accepted, decisions = {}, {}, {}, {}
    submitted, authorized, processed = set(), set(), set()
    violations = set()
    for event in events:
        kind = event['kind']
        slot_id, action_id = event.get('slot_id'), event.get('action_id')
        candidate = event.get('candidate')
        if kind == 'reviewed_proposal_registered':
            known = type(candidate) is str and candidate in approved
            if event['known'] is not known:
                violations.add('CANDIDATE_KNOWN_MISMATCH')
            slots[slot_id] = (event['proposal_id'], candidate if known else None)
            if known:
                if candidate in submitted:
                    violations.add('CANDIDATE_SUBMITTED_TWICE')
                submitted.add(candidate)
        elif kind == 'reviewed_authorization':
            registered = slots.get(slot_id, (None, None))[1]
            if (event['decision'] == 'ALLOW') != (registered is not None):
                violations.add('CANDIDATE_AUTHORIZATION_MISMATCH')
            if registered is not None:
                if candidate != registered:
                    violations.add('CANDIDATE_EVENT_MISMATCH')
                if event['decision'] == 'ALLOW':
                    authorized.add(registered)
        elif kind in ('reviewed_prepared', 'reviewed_dispatch_accepted'):
            registered = slots.get(slot_id, (None, None))[1]
            if registered is None or registered not in authorized:
                violations.add('CANDIDATE_NOT_AUTHORIZED')
                continue
            if kind == 'reviewed_prepared':
                if candidate != registered:
                    violations.add('CANDIDATE_EVENT_MISMATCH')
                prepared[action_id] = registered
            elif prepared.get(action_id) == registered:
                accepted[action_id] = registered
        elif kind in ('reviewed_assertion', 'reviewed_control_resolution'):
            if action_id not in accepted:
                violations.add('CANDIDATE_ASSERTION_WITHOUT_DISPATCH')
                continue
            registered = accepted[action_id]
            conclusion = event['simulated_conclusion']
            if conclusion not in ('PASS', 'FAIL', 'INCONCLUSIVE'):
                violations.add('CANDIDATE_CONCLUSION_INVALID')
            if kind == 'reviewed_assertion':
                if registered in processed:
                    violations.add('CANDIDATE_ASSERTION_REPEATED')
                processed.add(registered)
            elif registered not in processed:
                violations.add('CANDIDATE_CONTROL_WITHOUT_ASSERTION')
            decisions[registered] = (event['assertion'], conclusion)

    seen_slots = set()
    for row in report['checks']:
        slot_id = row['slot_id']
        if slot_id in seen_slots or slot_id not in slots:
            violations.add('CANDIDATE_ROW_SLOT_MISMATCH')
        seen_slots.add(slot_id)
        proposal_id, registered = slots.get(slot_id, (None, None))
        check_id = row['check_id']
        if check_id is not None and (type(check_id) is not str or check_id not in approved):
            violations.add('CANDIDATE_NOT_REVIEWED')
        if (row['proposal_id'], check_id) != (proposal_id, registered):
            violations.add('CANDIDATE_ROW_MISMATCH')
        if registered is not None:
            if row['processed'] is not (registered in processed):
                violations.add('CANDIDATE_PROCESSED_MISMATCH')
            if registered in decisions:
                if ((row['assertion'], row['simulated_conclusion']) != decisions[registered]
                        or accepted.get(row['action_id']) != registered):
                    violations.add('CANDIDATE_CONCLUSION_MISMATCH')
            elif row['simulated_conclusion'] != 'INCONCLUSIVE':
                violations.add('CANDIDATE_CONCLUSION_WITHOUT_ASSERTION')
        elif row['simulated_conclusion'] != 'INCONCLUSIVE':
            violations.add('UNREVIEWED_CANDIDATE_CONCLUSION')
    if seen_slots != set(slots):
        violations.add('CANDIDATE_ROW_SLOT_MISMATCH')
    unperformed = approved - processed
    reported = report['unperformed_approved_candidates']
    if (type(reported) is not list or any(type(value) is not str for value in reported)
            or len(set(reported)) != len(reported) or set(reported) != unperformed):
        violations.add('CANDIDATE_UNPERFORMED_MISMATCH')
    phases = dict(reviewed=approved, submitted=submitted, authorized=authorized,
                  prepared=set(prepared.values()),
                  dispatch_accepted=set(accepted.values()), processed=processed, unperformed=unperformed,
                  decided={candidate for candidate in processed
                           if decisions[candidate][1] in ('PASS', 'FAIL')})
    return violations, {name: sorted(values) for name, values in phases.items()}


def _scope(report, manifest, events, complete):
    """Cross-check the scope block, startup event and manifest's local seal."""
    violations = []
    block = report.get('reviewed_scope')
    scope_events = [(index, event) for index, event in enumerate(events)
                    if event['kind'] == 'reviewed_scope_binding']
    marked = ('evidence_version' in report or 'reviewed_scope' in report
              or 'evidence_version' in manifest or 'reviewed_scope_sha256' in manifest
              or scope_events)
    if not marked:
        return SCOPE_NOT_CHECKABLE, violations, ['SCOPE_BINDING_ABSENT'], {}
    if (report.get('evidence_version') != EVIDENCE_VERSION
            or manifest.get('evidence_version') != EVIDENCE_VERSION):
        violations.append('EVIDENCE_VERSION_MISMATCH')
    if type(block) is not dict:
        return 'MISMATCH', violations + ['SCOPE_BLOCK_MISSING'], [], {}
    if len(scope_events) != 1:
        code = 'SCOPE_BINDING_REPEATED' if scope_events else 'SCOPE_BINDING_MISSING'
        return 'MISMATCH', violations + [code], [], {}
    index, event = scope_events[0]
    if (index == 0 or events[index - 1]['kind'] != 'reviewed_started'
            or any(e['kind'] != 'reviewed_proposal_rejected' or e['reason'] != 'NOT_RUNNING'
                   for e in events[:index - 1])):
        violations.append('SCOPE_BINDING_ORDER')
    if set(block) != set(SCOPE_KEYS):
        violations.append('SCOPE_FIELDS_INVALID')
    if block.get('evidence_version') != EVIDENCE_VERSION or event.get('evidence_version') != EVIDENCE_VERSION:
        violations.append('EVIDENCE_VERSION_MISMATCH')
    if any(type(event.get(key)) is not type(block.get(key)) or event.get(key) != block.get(key)
           for key in SCOPE_KEYS):
        violations.append('SCOPE_FIELD_MISMATCH')
    for key in SCOPE_IDENTITY_KEYS:
        if block.get(key) != report.get(key) or event.get(key) != report.get(key):
            violations.append('SCOPE_' + key.upper() + '_MISMATCH')
    for key in ('contract_id', 'contract_version', 'fixture_id', 'fixture_version',
                'fixture_instance_id'):
        if not _valid_identifier(block.get(key)):
            violations.append('SCOPE_IDENTITY_INVALID')
    canonical = json.dumps(block, sort_keys=True, separators=(',', ':'),
                           allow_nan=False).encode('utf-8')
    if manifest.get('reviewed_scope_sha256') != hashlib.sha256(canonical).hexdigest():
        violations.append('SCOPE_MANIFEST_HASH_MISMATCH')
    for key in ('snapshot_id', 'contract_digest', 'fixture_content_sha256'):
        if manifest.get(key) != report[key]:
            violations.append('SCOPE_MANIFEST_IDENTITY_MISMATCH')

    max_checks = block.get('max_checks')
    timeout = block.get('logical_timeout_seconds')
    concurrency = block.get('concurrency')
    if (not _valid_identifier(block.get('budget_version'))
            or type(max_checks) is not int or not 1 <= max_checks <= CANDIDATE_LIMIT
            or type(timeout) not in (int, float) or not 0 < timeout <= 3600
            or type(concurrency) is not int or concurrency != 1):
        violations.append('BUDGET_INVALID')
    registrations = sum(event['kind'] == 'reviewed_proposal_registered' for event in events)
    if type(max_checks) is int and max(len(report['checks']), registrations) > max_checks:
        violations.append('BUDGET_EXCEEDED')

    candidates = block.get('candidates')
    phases = {}
    if type(candidates) is not list or not 0 < len(candidates) <= CANDIDATE_LIMIT:
        violations.append('CANDIDATE_UNIVERSE_INVALID')
    elif any(not _valid_identifier(value) for value in candidates):
        violations.append('CANDIDATE_INVALID')
    else:
        if len(set(candidates)) != len(candidates):
            violations.append('CANDIDATE_DUPLICATE')
        if candidates != sorted(candidates):
            violations.append('CANDIDATE_ORDER')
        if complete:
            candidate_violations, phases = _scope_candidates(report, events, candidates)
            violations.extend(candidate_violations)
    return ('MISMATCH' if violations else 'CONSISTENT'), sorted(set(violations)), [], phases


def _provenance(report, manifest, events):
    gaps = []
    if report.get('provenance') != PROVENANCE or manifest.get('provenance') != PROVENANCE:
        gaps.append('PROVENANCE_NOT_OFFLINE')
    if report.get('real_network_requests') != 'NOT_MEASURED':
        gaps.append('REAL_NETWORK_CLAIM')
    if report.get('network_latency') != 'NOT_MEASURED':
        gaps.append('LATENCY_CLAIM')
    if report.get('OS_SEND_PROOF') != 'UNAVAILABLE':
        gaps.append('OS_SEND_PROOF_CLAIM')
    if any(event.get('mode') != MODE for event in events):
        gaps.append('EVENT_MODE_MISMATCH')
    return ('UNKNOWN' if gaps else PROVENANCE), gaps


# Decisive assertion pairs from reviewed_protocol.evaluate_v2. The persisted
# projection proves status and response shape, but contains no control candidate ID.
_DECISIVE_ASSERTIONS = {
    'AUTHORIZED_CONTENT': ('PASS', (200,)),
    'REFUSAL_WITH_CONTROL': ('PASS', (401, 403)),
    'CONFIRMED_DISCLOSURE': ('FAIL', (200,)),
    'CONFIRMED_OVERDENIAL': ('FAIL', (401, 403)),
}
_STOP_REASONS = (
    'REVOKED', 'AUTHORIZATION_INVALID', 'RUNTIME_ERROR', 'AUDIT_ERROR',
    'PREPARE_ERROR', 'FIXTURE_BINDING_MISMATCH', 'DISPATCH_OVERLAP_REJECTED',
    'FIXTURE_ERROR', 'BUDGET_EXHAUSTED', 'TIMEOUT',
)


_CONCLUSION_ISSUE_PRIORITY = (
    'ASSERTION_CONCLUSION_CONFLICT',
    'FINAL_CONCLUSIONS_UNVERIFIED',
    'CONTROL_EVIDENCE_UNVERIFIED',
)


def _valid_conclusion_projection(response):
    # ResponseParser emits a three-digit integer or no status for an invalid response.
    status = response['status']
    valid = response['response_valid']
    complete = response['assertions_complete']
    fields = response['response_fields']
    if type(valid) is not bool or type(complete) is not bool:
        return False
    if not (status is None and not valid) and not (type(status) is int and 100 <= status <= 599):
        return False
    if not complete:
        return fields is None
    return valid and type(fields) is dict and all(
        type(key) is str and type(value) is str for key, value in fields.items())


def _assertion_issue(response, assertion, conclusion):
    if response is None or type(assertion) is not str or response['assertion'] != assertion:
        return 'FINAL_CONCLUSIONS_UNVERIFIED'
    decisive = _DECISIVE_ASSERTIONS.get(assertion)
    expected = decisive[0] if decisive is not None else 'INCONCLUSIVE'
    if conclusion != expected:
        return 'ASSERTION_CONCLUSION_CONFLICT'
    if not _valid_conclusion_projection(response):
        return 'FINAL_CONCLUSIONS_UNVERIFIED'
    if decisive is None:
        return None
    status = response['status']
    # The protocol also recognizes a correlated disclosure in a server error.
    server_disclosure = (assertion == 'CONFIRMED_DISCLOSURE'
                         and type(status) is int and 500 <= status <= 599)
    if response['response_valid'] is not True or (status not in decisive[1] and not server_disclosure):
        return 'FINAL_CONCLUSIONS_UNVERIFIED'
    if assertion != 'CONFIRMED_OVERDENIAL' and response['assertions_complete'] is not True:
        return 'FINAL_CONCLUSIONS_UNVERIFIED'
    return None


def _stop_reason_issue(report, event):
    reason = event['reason']
    if reason not in _STOP_REASONS or report['state'] != 'STOPPED':
        return 'STOP_REASON_UNVERIFIED'
    conditions = report['stop_conditions']
    if type(conditions) is not list or not conditions or reason != conditions[0]:
        return 'STOP_REASON_CONFLICT' if conditions else 'STOP_REASON_UNVERIFIED'
    revoke = report['revoke_sequence']
    if event['kind'] == 'reviewed_delivery_aborted':
        revoke = event['revoke_seq']
        if type(revoke) is int and (
                type(event['dispatch_seq']) is not int or revoke <= event['dispatch_seq']):
            return 'STOP_REASON_CONFLICT'
    if revoke is not None:
        if type(revoke) is not int or revoke <= 0:
            return 'STOP_REASON_UNVERIFIED'
        # A present, associated revocation outranks other stop conditions.
        return None if reason == 'REVOKED' else 'STOP_REASON_CONFLICT'
    if reason == 'REVOKED':
        return 'STOP_REASON_UNVERIFIED'
    if report['reason'] != reason:
        return 'STOP_REASON_CONFLICT' if report['reason'] in _STOP_REASONS else 'STOP_REASON_UNVERIFIED'
    return None


def _verified_metric_facts(report, events, accepted, lifecycle):
    """Project facts from the already validated snapshot; never open another file."""
    slots = 0
    actions, action_slots, started, handled = {}, {}, set(), {}
    responses, final, pending, stop_events = {}, {}, {}, {}
    last_positive = 0
    conclusion_issues = set()
    handling_bound = True
    for position, event in enumerate(events, 1):
        kind = event['kind']
        action = event.get('action_id')
        if kind == 'reviewed_proposal_registered':
            slots += 1
        elif kind == 'reviewed_prepared':
            actions[action] = event['candidate']
            action_slots[action] = event['slot_id']
        elif kind in ('reviewed_fixture_started', 'reviewed_fixture_handled'):
            if action not in accepted or event['dispatch_seq'] != accepted[action]:
                handling_bound = False
            if kind == 'reviewed_fixture_started':
                started.add(action)
            elif action in started and action in actions:
                handled[action] = actions[action]
            else:
                handling_bound = False
        elif kind == 'reviewed_response_evidence':
            if action not in handled or action in responses:
                conclusion_issues.add('FINAL_CONCLUSIONS_UNVERIFIED')
            responses[action] = event
        elif kind == 'reviewed_assertion':
            assertion = event['assertion']
            conclusion = event['simulated_conclusion']
            issue = _assertion_issue(responses.get(action), assertion, conclusion)
            if assertion == 'REFUSAL_WITH_CONTROL' and not last_positive:
                issue = issue or 'CONTROL_EVIDENCE_UNVERIFIED'
            if issue is not None:
                conclusion_issues.add(issue)
            elif assertion == 'AUTHORIZED_CONTENT':
                last_positive = position
            elif assertion == 'MISSING_CONTROL':
                response = responses[action]
                if response['status'] in (401, 403) and response['assertions_complete'] is True:
                    pending[action] = position
            final[action] = conclusion
        elif kind == 'reviewed_control_resolution':
            # The runtime only re-evaluates a pending denial after its positive
            # control passes. Exact control identity is not persisted in V2.
            if (action not in pending or event['assertion'] != 'REFUSAL_WITH_CONTROL'
                    or event['simulated_conclusion'] != 'PASS'
                    or last_positive <= pending[action]):
                conclusion_issues.add('CONTROL_EVIDENCE_UNVERIFIED')
            pending.pop(action, None)
            final[action] = event['simulated_conclusion']
        elif kind in ('reviewed_dispatch_cancelled', 'reviewed_delivery_aborted'):
            slot = event.get('slot_id', action_slots.get(action))
            stop_events.setdefault(slot, []).append(event)

    reasons, unlinked, stop_issue = {}, 0, None
    for transitions in stop_events.values():
        event = transitions[0]
        issue = (_stop_reason_issue(report, event) if len(transitions) == 1
                 else 'STOP_REASON_CONFLICT')
        if issue:
            unlinked += 1
            if stop_issue != 'STOP_REASON_CONFLICT':
                stop_issue = issue
        else:
            reason = event['reason']
            reasons[reason] = reasons.get(reason, 0) + 1
    facts = dict(registered_slots=slots, stop_reasons=reasons,
                 unverified_reason_events=unlinked,
                 unverified_report_reason=(report['reason'] is not None
                                           and report['reason'] not in tuple(reasons)))
    if stop_issue:
        facts['stop_reason_issue'] = stop_issue
    if handling_bound:
        facts['handled_actions'] = len(handled)
    if not lifecycle:
        return facts

    facts['max_checks'] = report['reviewed_scope']['max_checks']
    if handling_bound:
        facts['handled_candidates'] = sorted(set(handled.values()))
    processed = set(lifecycle['processed'])
    if (not handling_bound or not final.keys() <= handled.keys() or len(final) != len(processed)
            or {handled[action] for action in final} != processed):
        conclusion_issues.add('FINAL_CONCLUSIONS_UNVERIFIED')
    if conclusion_issues:
        ordered = [issue for issue in _CONCLUSION_ISSUE_PRIORITY if issue in conclusion_issues]
        facts['final_conclusion_issue'] = ordered[0]
        facts['final_conclusion_issues'] = ordered
    else:
        facts['final_conclusions'] = {
            label: sum(outcome == label for outcome in final.values())
            for label in ('PASS', 'FAIL', 'INCONCLUSIVE')}
    return facts


def verify(directory, *, include_facts=False):
    """Verify one V2 evidence directory. Returns a multi-axis result; never raises."""
    try:
        _, blobs, report, manifest, events = _load(directory)
    except (MissingEvidence, EvaluationInputError, OSError, ValueError, TypeError,
            KeyError, AttributeError, RecursionError) as error:
        return _blank(str(error) or 'UNREADABLE_EVIDENCE')
    try:
        result = _blank('NONE')
        result['gaps'] = []
        result['violations'] = []
        result['subject'] = dict(run_id=report.get('run_id'),
                                 contract_id=report.get('contract_id'),
                                 fixture_id=report.get('fixture_id'))
        if report.get('mode') != MODE:
            result['gaps'].append('NOT_A_REVIEWED_V2_RUN')
            return result
        if not REPORT_REQUIRED <= set(report):
            result['gaps'].append('REPORT_FIELDS_MISSING')
            return result
        appended = _file_axis(blobs, report, manifest, events)
        result['axes']['file_integrity'] = 'VERIFIED'
        result['appended_bytes'] = appended
        completeness, gaps = _completeness_axis(report, manifest, events)
        result['axes']['evidence_completeness'] = completeness
        result['gaps'].extend(gaps)
        if include_facts:
            result['audit_gap'] = 'AUDIT_GAP' in gaps
        strict = (report.get('audit_gap') is False
                  and manifest.get('audit_gap') is False
                  and report.get('evidence_complete') is True
                  and manifest.get('evidence_complete') is True
                  and report.get('unpersisted_event_kinds') == [])
        violations, accepted_seq, revoke_values = _association(events, report)
        result['violations'].extend(violations)
        result['violations'].extend(_event_counts(events, report, strict))
        revoke_violations, revoke_notes = _revoke(report, accepted_seq, revoke_values)
        result['violations'].extend(revoke_violations)
        result['axes']['delivery_association'] = (
            'VIOLATION' if result['violations'] else 'CONSISTENT')
        result['violations'].extend(_rows(report, events, accepted_seq))
        if result['violations']:
            result['axes']['delivery_association'] = 'VIOLATION'
        replay = _counters(events)
        reported = report.get('reviewed_counts')
        result['counts_replayed'] = replay
        result['counts_reported'] = dict(reported) if type(reported) is dict else {}
        if type(reported) is not dict or set(reported) != set(COUNTERS):
            result['axes']['counter_consistency'] = 'MISMATCH'
            result['gaps'].append('REVIEWED_COUNTS_FIELDS')
        else:
            mismatch = {name: {'replayed': replay[name], 'reported': reported[name]}
                        for name in COUNTERS if replay[name] != reported[name]}
            result['counts_mismatch'] = mismatch
            result['axes']['counter_consistency'] = (
                'MISMATCH' if mismatch else 'MATCH')
        counts = report.get('counts')
        if (type(counts) is not dict or set(counts) != RESULT_COUNTS
                or counts.get('request_count') != 0
                or counts.get('model_request_count') != replay['dispatch_accepted_count']
                or counts.get('attempt_count') != replay['authorization_decisions']
                or counts.get('plan_count') != len(report.get('checks') or [])):
            result['axes']['counter_consistency'] = 'MISMATCH'
            result['gaps'].append('RESULT_COUNTS_INCONSISTENT')
        contract, contract_gaps = _contract(report, events)
        result['axes']['contract_association'] = contract
        result['gaps'].extend(contract_gaps)
        scope_state, scope_violations, scope_notes, phases = _scope(
            report, manifest, events, completeness == 'COMPLETE')
        result['axes']['scope_binding_consistency'] = scope_state
        result['violations'].extend(scope_violations)
        result['scope_notes'] = scope_notes
        provenance, provenance_gaps = _provenance(report, manifest, events)
        result['axes']['provenance'] = provenance
        result['gaps'].extend(provenance_gaps)
        result['consistent'] = (
            all(result['axes'][name] == good for name, good in AXIS_GOOD.items())
            and scope_state in ('CONSISTENT', SCOPE_NOT_CHECKABLE))
        if result['consistent'] and phases:
            result['candidate_lifecycle'] = phases
        if include_facts and result['consistent'] and appended == 0:
            result['verified_facts'] = _verified_metric_facts(report, events, accepted_seq, phases)
        result['unverifiable'] = [
            dict(item='contract_digest / scope_digest authenticity',
                 missing='no independent review material; only internal consistency '
                         'between report, scope block and scope event is proven'),
            dict(item='fixture_content_sha256 authenticity',
                 missing='bound internally to the scope event, but no external '
                         'authority attests the digest'),
            dict(item='external review and execution permission',
                 missing='approval material is not part of the artifacts'),
            dict(item='wall-clock duration',
                 missing='events carry no timestamps'),
        ]
        if scope_state == SCOPE_NOT_CHECKABLE:
            result['unverifiable'].append(
                dict(item='authorised budget',
                     missing='3B-1 evidence has no reviewed_scope; budget_version, '
                             'max_checks, logical_timeout_seconds and concurrency '
                             'cannot be reconstructed'))
            result['unverifiable'].append(
                dict(item='reviewed candidate universe',
                     missing='3B-1 evidence lists no reviewed candidates; coverage '
                             'must not be computed from report rows alone'))
        if not strict:
            result['unverifiable'].append(
                dict(item='event counter transitions',
                     missing='run has an audit gap; a committed counter may have no '
                             'persisted event, so exact transitions are unprovable'))
        if 'REVOKE_SEQUENCE_UNBOUND' in revoke_notes:
            result['unverifiable'].append(
                dict(item='revoke sequence binding',
                     missing='no delivery event carries revoke_seq in this run'))
        return result
    except (MissingEvidence, EvaluationInputError, OSError, ValueError, TypeError,
            KeyError, AttributeError, RecursionError) as error:
        result = _blank(str(error) or 'UNVERIFIABLE_EVIDENCE')
        return result


def is_consistent(result):
    """Apply the consistency result, including the legacy scope exception."""
    return bool(result.get('consistent')) and not result.get('gaps')

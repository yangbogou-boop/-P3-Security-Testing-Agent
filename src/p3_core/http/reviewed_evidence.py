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
LIMITATIONS = (
    'UNPERSISTED_BUDGET: the report does not carry max_checks/budget_version, so '
    '"stayed within the reviewed budget" cannot be proven from evidence alone.',
    'NO_WALL_CLOCK: events carry no timestamps, so no local duration can be derived.',
    'AUTHORISATION_NOT_VERIFIED: review material and approval are not part of the '
    'artifacts; approval and runtime authorisation remain unverified.',
    'T3_NOT_ISOLATED: same-process code could rewrite any artifact or the verifier '
    'itself; this verifier only detects contradictions in persisted bytes.',
)
_HASH = re.compile(r'[0-9a-f]{64}')
_ID = re.compile(r'[a-z]+_[0-9a-f]{32}')


def _blank(reason):
    return dict(schema_version=SCHEMA_VERSION, subject={}, consistent=False,
                axes=dict(file_integrity='INCOMPLETE_OR_INVALID',
                          evidence_completeness='INCOMPLETE',
                          counter_consistency='NOT_CHECKABLE',
                          delivery_association='NOT_CHECKABLE',
                          contract_association='NOT_CHECKABLE',
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


def verify(directory):
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
        provenance, provenance_gaps = _provenance(report, manifest, events)
        result['axes']['provenance'] = provenance
        result['gaps'].extend(provenance_gaps)
        result['consistent'] = all(result['axes'][name] == good
                                   for name, good in AXIS_GOOD.items())
        result['unverifiable'] = [
            dict(item='contract_digest / scope_digest authenticity',
                 missing='no persisted event binds these digests; only the report '
                         'hash protects them from tampering'),
            dict(item='fixture_content_sha256 authenticity',
                 missing='no persisted event binds the fixture digest'),
            dict(item='authorised budget',
                 missing='report lacks max_checks and budget_version'),
            dict(item='reviewed candidate universe',
                 missing='report lists only unperformed candidates; the reviewed '
                         'set is reconstructed from rows + that list'),
            dict(item='wall-clock duration',
                 missing='events carry no timestamps'),
        ]
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
    """True only when every axis is in its good state."""
    return bool(result.get('consistent')) and not result.get('gaps')

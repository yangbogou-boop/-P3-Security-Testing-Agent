"""Read-only metrics over one independently verified V2 evidence snapshot."""
from .reviewed_evidence import AXIS_GOOD, verify

DEFINITION_VERSION = 'p3-reviewed-metrics-v1'
_NAMES = (
    'coverage', 'submission_ratio', 'fixture_handling_ratio',
    'decidable_processed_ratio', 'authorization_distribution',
    'simulated_conclusion_distribution', 'control_completion', 'dispatch_funnel',
    'budget_utilization', 'audit_completeness', 'stop_reasons', 'local_elapsed',
    'detection_and_false_positive_rates',
)
_OFFLINE = 'NO_NETWORK_SIMULATION'


def _metric(status, source, reason=None, *, numerator=None, denominator=None,
            value=None, unit='ratio', **details):
    return dict(status=status, evidence_source=source, reason=reason,
                numerator=numerator, denominator=denominator, value=value, unit=unit,
                limitations=[_OFFLINE], details=details)


def _ratio(numerator, denominator, source):
    if numerator is None or denominator is None:
        return _metric('NOT_CHECKABLE', source, 'REQUIRED_VERIFIED_FACTS_MISSING',
                       numerator=numerator, denominator=denominator)
    if denominator == 0:
        return _metric('NOT_APPLICABLE', source, 'ZERO_DENOMINATOR',
                       numerator=numerator, denominator=denominator)
    return _metric('OK', source, numerator=numerator, denominator=denominator,
                   value=numerator / denominator)


def _calculated(checked, facts):
    life = {key: len(value) for key, value in checked.get('candidate_lifecycle', {}).items()}
    counts = checked['counts_replayed']
    scope_size = life.get('reviewed')
    total = facts['registered_slots']
    bins = facts.get('final_conclusions')
    decided = life.get('decided') if bins is not None else None
    processed = life.get('processed')
    conclusion_issue = facts.get('final_conclusion_issue')
    conclusion_details = {'conclusion_issues': facts['final_conclusion_issues']} if conclusion_issue else {}
    conclusion_status = ('EVIDENCE_INCONSISTENT' if conclusion_issue == 'ASSERTION_CONCLUSION_CONFLICT'
                         else 'NOT_CHECKABLE')
    handled = facts.get('handled_candidates')
    handled_actions = facts.get('handled_actions')
    submitted = life.get('submitted')
    authorization = counts['authorization_decisions']
    prepared = counts['prepared_count']
    accepted = counts['dispatch_accepted_count']
    consumed = counts['delivery_consumed_count']
    def conclusion_ratio(denominator, source):
        if conclusion_issue is not None:
            return _metric(conclusion_status, source, conclusion_issue,
                           denominator=denominator, **conclusion_details)
        return _ratio(decided, denominator, source)

    return {
        1: conclusion_ratio(scope_size, 'final assertions and reviewed scope'),
        2: dict(_ratio(submitted, scope_size, 'reviewed proposal registration'),
                details={'unknown_slots': total - submitted if submitted is not None else None}),
        3: dict(_ratio(len(handled) if handled is not None else None, scope_size,
                       'associated in-memory fixture handling'),
                details={'handled_actions': handled_actions}),
        4: conclusion_ratio(processed, 'associated final assertions'),
        5: _metric('OK', 'replayed authorization events', unit='distribution',
                   ALLOW=_ratio(counts['authorized_count'], authorization, 'replayed authorization'),
                   DENY=_ratio(counts['denied_count'], authorization, 'replayed authorization'),
                   not_evaluated=total - authorization),
        6: (_metric(conclusion_status, 'associated final assertions',
                    conclusion_issue or 'FINAL_CONCLUSIONS_UNVERIFIED',
                    denominator=processed, unit='distribution', **conclusion_details) if bins is None else
            _metric('OK', 'associated final assertions', unit='distribution',
                    **{label: _ratio(amount, processed, 'associated final assertions')
                       for label, amount in bins.items()})),
        8: _metric('OK' if scope_size is not None and handled_actions is not None else 'PARTIAL',
                   'replayed and associated events', unit='funnel', registered_slots=total,
                   counts=counts,
                   prepared_per_reviewed=_ratio(prepared, scope_size, 'replay and reviewed scope'),
                   accepted_per_prepared=_ratio(accepted, prepared, 'dispatch replay'),
                   consumed_per_accepted=_ratio(consumed, accepted, 'dispatch replay'),
                   handled_per_consumed=_ratio(handled_actions, consumed, 'associated handling')),
        9: _ratio(total, facts.get('max_checks'), 'replayed slots and verified budget'),
        11: _metric('PARTIAL' if facts['unverified_reason_events'] or facts['unverified_report_reason']
                    else 'OK', 'associated cancellation and abort events', facts.get('stop_reason_issue'), unit='counts',
                    value=facts['stop_reasons'], unverified_reason_events=facts['unverified_reason_events'],
                    unverified_report_reason=facts['unverified_report_reason']),
    }


def evaluate(directory):
    """Evaluate one local directory without running a fixture or writing evidence."""
    checked = verify(directory, include_facts=True)
    axes = checked['axes']
    conflict = (axes['scope_binding_consistency'] == 'MISMATCH'
                or axes['counter_consistency'] == 'MISMATCH'
                or axes['contract_association'] == 'MISMATCH'
                or axes['delivery_association'] == 'VIOLATION')
    unavailable = 'EVIDENCE_INCONSISTENT' if conflict else 'INSUFFICIENT_EVIDENCE'
    facts = checked.get('verified_facts')
    metrics = {}
    if (facts is not None and all(axes.get(key) == value for key, value in AXIS_GOOD.items())
            and axes['scope_binding_consistency'] in ('CONSISTENT', 'NOT_CHECKABLE')):
        metrics = _calculated(checked, facts)

    audit_state = 'NOT_CHECKABLE'
    gaps = list(checked['gaps'])
    if axes['file_integrity'] == 'VERIFIED':
        audit_state = axes['evidence_completeness']
        if checked['appended_bytes']:
            audit_state = 'INCOMPLETE'
            gaps.append('UNSEALED_TRAILING_BYTES')
    metrics.update({
        7: _metric('NOT_CHECKABLE', 'reviewed scope', 'CONTROL_UNIVERSE_UNVERIFIED'),
        10: _metric('NOT_CHECKABLE', 'evidence verification', 'EXPECTED_EVENT_COUNT_UNVERIFIED',
                    completeness=audit_state, audit_gap=checked.get('audit_gap'), gaps=gaps),
        12: _metric('NOT_MEASURED', None, 'NO_REPLAYABLE_TIMESTAMPS', unit='seconds'),
        13: _metric('NOT_APPLICABLE', None, 'INDEPENDENT_GROUND_TRUTH_MISSING'),
    })
    items = []
    for index, name in enumerate(_NAMES, 1):
        item = metrics.get(index)
        if item is None:
            item = _metric(unavailable, 'reviewed_evidence.verify', 'VERIFICATION_GATE')
        items.append(dict(item, metric_id=f'M{index}', name=name,
                          definition_version=DEFINITION_VERSION))
    return dict(definition_version=DEFINITION_VERSION, axes=axes, gaps=gaps,
                violations=checked['violations'], provenance=axes['provenance'],
                approval_verified=False, source_authenticated=False,
                runtime_authorisation_verified=False, metrics=items)


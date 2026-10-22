"""Offline acceptance-management format; no runner and no automatic VERIFIED."""
from .models import InvalidInput

STATUSES=('PENDING_AUTHORIZATION','READY_FOR_HUMAN_REVIEW','NOT_EXECUTED',
          'EXECUTED_PENDING_VERIFICATION','VERIFIED','FAILED')
CASES=(
 ('GOOD_PAIRED_CONTROLS','Good: six paired checks','test_good_all_six_fixed'),
 ('AUTH_DISCLOSURE','AUTH: anonymous profile plus legal control','test_three_defects_both_strategies'),
 ('BOLA_DISCLOSURE','BOLA: obj-b owner control','test_three_defects_both_strategies'),
 ('RBAC_DISCLOSURE','RBAC: admin report control','test_three_defects_both_strategies'),
 ('CONNECTION_FAILURE','Authorized connection fault','test_read_timeout_and_transport_failure_no_raw_exception'),
 ('UNEXPECTED_STATUS','404/5xx/redirect; no following redirect','test_404_and_5xx_no_leak_are_inconclusive'),
 ('INVALID_JSON','Malformed JSON/UTF8/duplicates','test_t34_canary_cannot_rescue_malformed_framing_or_json'),
 ('TRUNCATION','Incomplete or oversized response','test_header_fact_survives_incomplete_body_without_verdict'),
 ('TIMEOUT','Read/write deadline fault','test_service_timeout_read_and_partial_write_close'),
 ('REVOKE_CONNECT','Revoke before/after connect','test_t27_connect_then_revoke_before_first_send'),
 ('REVOKE_FIRST_SEND','Both gate orderings','test_service_send_and_revoke_have_total_gate_order'),
 ('REVOKE_PARTIAL_SEND','Revoke after partial positive send','test_service_partial_send_then_effective_revoke'),
 ('LATE_RESPONSE','Terminal late response and stale instance','test_late_response_during_read_cannot_upgrade'),
 ('AUDIT_FAILURE','Before/after send evidence failure','test_audit_failure_cannot_confirm_response'))

CRITERIA={
 'GOOD_PAIRED_CONTROLS':'Three successful legal controls and complete 401/403 denial assertions; status alone is insufficient.',
 'AUTH_DISCLOSURE':'Paired profile control plus complete, instance-bound protected anonymous response; fragment alone is inconclusive.',
 'BOLA_DISCLOSURE':'Paired bob control plus complete obj-b/owner=bob assertion for alice; wrong instance/object is inconclusive.',
 'RBAC_DISCLOSURE':'Paired admin control plus complete period=demo/admin audience assertion for member.',
 'CONNECTION_FAILURE':'ERROR/INCONCLUSIVE; zero requests before positive send, one after partial send; no retry.',
 'UNEXPECTED_STATUS':'INCONCLUSIVE/RESPONSE_ERROR unless independently complete protected disclosure meets existing contract; never follow redirect.',
 'INVALID_JSON':'INCONCLUSIVE/RESPONSE_ERROR for invalid UTF8, duplicate keys, unknown fields or conflicting lengths; no canary override.',
 'TRUNCATION':'Preserve recognized header fact but no confirmed conclusion for incomplete body; bounded storage and explicit gap.',
 'TIMEOUT':'Stop at applicable deadline; no late upgrade; retain sent count and observe cleanup latency.',
 'REVOKE_CONNECT':'No positive send after effective revoke; connect alone counts zero; cleanup without reconnect.',
 'REVOKE_FIRST_SEND':'Exercise both gate orders; first positive send counts once, revoke winning prevents send; bytes cannot be recalled.',
 'REVOKE_PARTIAL_SEND':'No continued write after effective revoke; retain one send count, unknown unfinished result and explicit close failure.',
 'LATE_RESPONSE':'No terminal resurrection or stale instance/credential confirmation.',
 'AUDIT_FAILURE':'Stop new dispatch; no confirmation from unpersisted evidence; recover unknown prefix without replay.'}


def acceptance_plan():
    common=['owner_material','teacher_catalog','source_review','scope_version_match',
            'fixture_credential_binding','budget_record','revocation_responsibility']
    return dict(schema_version='p3-c3-management-v1',network_status='PENDING_AUTHORIZATION',
        allowed_statuses=list(STATUSES),execution_entrypoint=None,cases=[dict(
            case=name,status='PENDING_AUTHORIZATION',scope=scope,
            required_permissions=dict(owner='original permission/delegation chain and source review',
                teacher='approved target/endpoint/identity/check catalog',
                binding='exact HttpConfig scope digest, versions, fixture and credentials',
                exception_scope=name if i>=4 else None),
            criteria=CRITERIA[name],
            observations=['both revoke-request/effective timestamps and gate sequences',
                          'first/last positive send and byte counts',
                          'owner close completion/failure and OS resource observation'],
            preconditions=common+(['explicit_exception_permission'] if i>=4 else []),
            offline_tests=[test],evidence_required=['client_events_manifest_report','server_connection_summary',
                'run_fixture_action_connection_binding','revocation_gate_sequences','cleanup_observation'],
            cannot_prove_offline=['real_permission_authenticity','OS_send_and_close','cancellation_latency',
                                 'actual_target_identity','durable_dual_source_capture'],
            result=dict(executed_at=None,execution_proof=None,reviewer_record=None,verdict=None))
            for i,(name,scope,test) in enumerate(CASES)])


def validate_management_record(row):
    """Validate external review records; does not authenticate them or run tests."""
    if type(row) is not dict or row.get('case') not in {c[0] for c in CASES} or row.get('status') not in STATUSES:
        raise InvalidInput('INVALID_MANAGEMENT_RECORD')
    status=row['status'];result=row.get('result')
    if type(result) is not dict or set(result)!={'executed_at','execution_proof','reviewer_record','verdict'}:
        raise InvalidInput('INVALID_MANAGEMENT_RECORD')
    if status in ('EXECUTED_PENDING_VERIFICATION','VERIFIED') and not result['execution_proof']:
        raise InvalidInput('EXECUTION_PROOF_REQUIRED')
    if status in ('VERIFIED','FAILED') and not result['reviewer_record']:
        raise InvalidInput('HUMAN_REVIEW_REQUIRED')
    return dict(format='VALID',source_verified=False,execution_allowed=False,status='PENDING_AUTHORIZATION')


def offline_status(plan=None):
    # Offline checks never consume supplied statuses as authority for promotion.
    return acceptance_plan()

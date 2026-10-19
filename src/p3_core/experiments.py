"""Reproducible synthetic scenarios and deterministic strategy experiments.

All approvals here are explicitly synthetic and usable only with SimulationRun.
No network listener/Executor is imported or activated by this module.
"""
import hashlib
import json
from pathlib import Path
import time

from .evidence import JsonlEvidence, MemoryEvidence
from .http.authorization import LocalRegistry, ReviewedMaterial
from .http.audit import BoundedEvidence, verify_run
from .http.contract import HttpConfig, base_checks
from .http.machine import SimulationRun
from .http.strategies import FixedSelection, EvidenceSelection
from .http.transport import MemoryTransport
from .mock_api import FixtureManager, Mode
from .mock_api.adapter import ServiceAdapter

STRATEGIES={'fixed':FixedSelection,'dynamic':EvidenceSelection}
MODES={'good':Mode.GOOD,'auth':Mode.AUTH,'bola':Mode.BOLA,'rbac':Mode.RBAC}
FAULTS=(None,'malformed','truncated','redirect','timeout','transport','audit','empty','server_error','duplicate_length')


def configuration(fixture):
    return dict(mode='http-local',schema_version='http-core-v1',
        target=dict(scheme='http',host='127.0.0.1',port=8765),
        budget=dict(max_checks=8,logical_timeout_seconds=90,concurrency=1),
        limits=dict(header_bytes=4096,body_bytes=65536,response_bytes=69632),
        authorization=dict(authorization_id='simulation-only',authorization_version='v1',registry_ref='synthetic-local'),
        fixture_instance_id=fixture.fixture_instance_id,contract_version='p3-http-v1',matrix_version='p3-matrix-v1',
        candidate_version='six-v1',fixture_version='synthetic-v1',budget_version='trial-v1',
        candidates=[c.to_dict() for c in base_checks()])


def synthetic_registry(raw):
    cfg=HttpConfig.parse(raw)
    data=b'SYNTHETIC UNIT EXPERIMENT ONLY - NO REAL PERMISSION'
    mats=[ReviewedMaterial(ref,data,hashlib.sha256(data).hexdigest(),'synthetic-experiment',
        'test-reviewer','test-principal',role,cfg.scope_digest,0,4102444800,False,True)
        for ref,role in (('synthetic-owner','owner'),('synthetic-catalog','teacher'))]
    record=dict(registry_ref=cfg.registry_ref,authorization_id=cfg.authorization_id,
        authorization_version=cfg.authorization_version,scope_digest=cfg.scope_digest,
        owner_ref='synthetic-owner',catalog_ref='synthetic-catalog',delegation_ref=None)
    return LocalRegistry(json.dumps(record).encode(),mats)


def run_scenario(mode='good',strategy='fixed',*,output=None,fault=None):
    if mode not in MODES or strategy not in STRATEGIES or fault not in FAULTS:
        raise ValueError('INVALID_SCENARIO')
    fixture=FixtureManager.reset(MODES[mode])
    raw=configuration(fixture)
    adapter=ServiceAdapter(fixture,raw['target']['port'])
    sink=JsonlEvidence(output) if output is not None else MemoryEvidence()
    class AuditFault:
        def open(self,*args): sink.open(*args)
        def emit(self,event):
            if event['kind']=='prepared': raise OSError('SIMULATED_AUDIT_FAILURE')
            sink.emit(event)
        def finish(self,*args): sink.finish(*args)
    evidence=BoundedEvidence(AuditFault() if fault=='audit' else sink)
    run=SimulationRun(raw,synthetic_registry(raw),credentials=fixture.credential_bindings(),
                      evidence=evidence,selection=STRATEGIES[strategy]())
    start=time.perf_counter()
    run.start()
    order=[]
    dispatched=set()
    unauthorized=set()
    while run.state=='RUNNING':
        if run._active is None:
            transport=MemoryTransport()
            run.step(transport)
            if run.state=='RUNNING' and run._active is not None:
                active=run._active
                order.append(active['slot'].check.check_id)
                response=adapter.handle_bytes(active['request'].wire)
                if fault=='malformed': response=response.replace(b'{',b'!',1)
                elif fault=='truncated': response=response[:-4]
                elif fault=='redirect': response=b'HTTP/1.1 302 Found'+response[response.index(b'\r\n'):]
                elif fault=='empty': response=b'HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: 0\r\n\r\n'
                elif fault=='server_error': response=b'HTTP/1.1 500 Error'+response[response.index(b'\r\n'):]
                elif fault=='duplicate_length': response=response.replace(b'\r\n\r\n',b'\r\nContent-Length: 1\r\n\r\n',1)
                if fault=='timeout': transport.chunks.append(TimeoutError('TEST_ONLY'))
                elif fault=='transport': transport.chunks.append(OSError('TEST_ONLY'))
                else: transport.chunks.append(response)
        else: run.step()
        if run._active and run._active['sent']:
            slot=run._active['slot']
            dispatched.add(slot.action_id)
            if slot.authorization!='ALLOW' or slot.check not in run.config.candidates:
                unauthorized.add(slot.action_id)
        run.settle()
    report=run.finalize()
    elapsed=time.perf_counter()-start
    true_failure={'auth':'HTTP-N-AUTH','bola':'HTTP-N-BOLA','rbac':'HTTP-N-RBAC'}.get(mode)
    confirmed=[r for r in report['checks'] if r['simulated_conclusion'] in ('PASS','FAIL')]
    failures=[r['check_id'] for r in report['checks'] if r['simulated_conclusion']=='FAIL']
    metrics=dict(coverage=dict(numerator=len(confirmed),denominator=6),
        detected=dict(numerator=int(true_failure in failures) if true_failure else 0,denominator=int(true_failure is not None),
                      applicable=true_failure is not None),
        false_confirmations=sum(x!=true_failure for x in failures),
        inconclusive=sum(r['simulated_conclusion']=='INCONCLUSIVE' for r in report['checks']),
        tool_failures=int(report['reason'] in ('RESPONSE_ERROR','TRANSPORT_ERROR','TIMEOUT','AUDIT_ERROR','RUNTIME_ERROR')),
        unauthorized_dispatches=len(unauthorized),
        actual_unauthorized_dispatches=0, # This harness cannot create a socket.
        blocked_intents=sum(r['authorization']=='DENY' for r in report['checks']),
        observed_model_dispatches=len(dispatched),
        cost=dict(actual_requests=report['counts']['request_count'],model_requests=report['counts']['model_request_count'],
                  local_elapsed_seconds=elapsed,planning_seconds=report['planning_seconds'],llm_calls=0,
                  preparation_and_review_seconds=None))
    return dict(provenance='NO_NETWORK_SIMULATION',network_status='PENDING_AUTHORIZATION',
        mode=mode,strategy=strategy,fault=fault,order=order,metrics=metrics,report=report,
        integrity=verify_run(Path(output)/run.run_id) if output is not None else None,
        experiment_contract=dict(candidates='six-v1',matrix='p3-matrix-v1',fixture='synthetic-v1',
                                 budget=raw['budget'],objective='all six checks with controls',
                                 reset='fresh isolated equivalent fixture and synthetic approval per run'))


def compare_strategies(output, repeats=3):
    if type(repeats) is not int or not 1<=repeats<=20: raise ValueError('INVALID_REPEATS')
    rows=[]
    cases=[('good',None),('auth',None),('bola',None),('rbac',None),('good','malformed'),('good','timeout')]
    for mode,fault in cases:
        for trial in range(repeats):
            for strategy in STRATEGIES:
                row=run_scenario(mode,strategy,output=output,fault=fault)
                row['trial']=trial+1
                rows.append(row)
    return dict(provenance='NO_NETWORK_SIMULATION',network_status='PENDING_AUTHORIZATION',
        repeats=repeats,runs=rows,decision='KEEP_FIXED_PENDING_REAL_EVIDENCE',
        limitations=['No actual HTTP measurements','Timing is local test-harness time, not network latency',
                     'Small sample, no statistical superiority claim','Preparation/human-review costs not measured'])

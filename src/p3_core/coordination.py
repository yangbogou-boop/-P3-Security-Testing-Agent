"""Bounded sidecar evidence. Correlation is not an API verdict or permission."""
import copy
import re
import json
import hashlib
from pathlib import Path
from threading import Lock

from .evidence import MemoryEvidence, JsonlEvidence, Redactor, unique_id
from .models import InvalidInput, number
from .http.contract import strict_json


REASONS={'RESPONSE_SENT','REVOKED','TIMEOUT','AUTHORIZATION_INVALID','PENDING_AUTHORIZATION',
         'FIXTURE_BINDING_INVALID','CREDENTIAL_BINDING_INVALID','RUNTIME_ERROR','TRUNCATED_REQUEST',
         'REQUEST_TOO_LARGE','TRANSPORT_ERROR','INVALID_REQUEST','AUDIT_ERROR'}
FIELDS={'connection_id','action_id','sent_bytes','received_bytes','first_send_sequence','last_send_sequence',
        'reason','cleanup_failed','revoke_requested_at','revoke_effective_sequence','revoke_effective_at','summary_sequence'}


class EvidenceCoordinator:
    """Only synthetic/offline sidecars in this round; no live-evidence toggle.

    expect() declares correlation expectations only. Verification additionally
    requires capture_controller() from the actual offline Controller. Records
    from another binding are rejected without echoing data.
    """
    def __init__(self,binding,*,sink=None,limit=32,on_failure=None):
        if type(limit) is not int or not 1<=limit<=256:raise InvalidInput('INVALID_CAPACITY')
        self.binding,self.limit,self.on_failure=binding,limit,on_failure
        self.sink=sink if sink is not None else MemoryEvidence()
        self._lock=Lock();self._actions=set();self._records={};self._seen_actions=set()
        self._sequence=0;self._bad=False;self._audit_gap=False;self._finished=False
        self._completion='PENDING';self._finished_report=None
        self._controller=None;self._registered=();self._verified=False
        self.sidecar_id=unique_id('coordination')
        try:self.sink.open(self.sidecar_id,Redactor())
        except Exception:self._fail(audit=True)

    def _fail(self,*,audit=False):
        self._bad=True;self._audit_gap=self._audit_gap or audit
        if self.on_failure is not None:
            try:self.on_failure()
            except Exception:self._audit_gap=True

    def expect(self,action_id,binding):
        if binding!=self.binding or type(action_id) is not str or not re.fullmatch(r'action_[0-9a-f]{32}',action_id):
            raise InvalidInput('INVALID_ACTION_BINDING')
        with self._lock:
            if self._finished or self._bad:raise InvalidInput('COORDINATION_CLOSED')
            if len(self._actions)>=self.limit and action_id not in self._actions:raise InvalidInput('CAPACITY')
            self._actions.add(action_id)

    def capture_controller(self,controller):
        """Trusted host binds the actual offline Controller, not a claimed list.

        This process-local root is never reconstructed from JSON or a digest.
        Python host code is trusted; this is not a sandbox against host mutation.
        Synthetic Controller approval proves only offline action registration.
        """
        from .http.machine import SimulationRun
        if type(controller) is not SimulationRun:
            raise InvalidInput('OFFLINE_CONTROLLER_REQUIRED')
        if not controller._lock.acquire(blocking=False):raise InvalidInput('OWNER_BUSY')
        try:
            cfg=controller.config
            if (cfg is None or controller.run_id!=self.binding.run_id
                    or cfg.fixture_instance_id!=self.binding.fixture_instance_id
                    or cfg.scope_digest!=self.binding.scope_digest
                    or cfg.authorization_version!=self.binding.authorization_version
                    or controller._audit_gap or not controller.simulation):
                raise InvalidInput('CONTROLLER_BINDING_INVALID')
            registered=tuple(sorted((s.action_id,s.check.check_id,s.attempt_id)
                for s in controller._slots if s.action_id and s.authorization=='ALLOW'
                and s.check in cfg.candidates and s.attempt_id))
        finally:controller._lock.release()
        with self._lock:
            if self._finished or self._bad or (self._controller is not None and self._controller is not controller):
                raise InvalidInput('COORDINATION_CLOSED')
            if not registered or len(registered)>self.limit or not set(self._registered)<=set(registered):
                raise InvalidInput('INVALID_REGISTRATION')
            self._controller=controller;self._registered=registered
            self._actions.update(row[0] for row in registered)

    @staticmethod
    def _validate(row):
        if type(row) is not dict or set(row)!=FIELDS:raise ValueError()
        if not re.fullmatch(r'connection_[0-9a-f]{32}',row['connection_id']):raise ValueError()
        if row['action_id'] is not None and not re.fullmatch(r'action_[0-9a-f]{32}',row['action_id']):raise ValueError()
        if row['reason'] not in REASONS or type(row['cleanup_failed']) is not bool:raise ValueError()
        for key in ('sent_bytes','received_bytes','summary_sequence'):
            if type(row[key]) is not int or not 0<=row[key]<=1048576:raise ValueError()
        if row['summary_sequence']<1:raise ValueError()
        for key in ('first_send_sequence','last_send_sequence','revoke_effective_sequence'):
            if row[key] is not None and (type(row[key]) is not int or not 1<=row[key]<=1000000):raise ValueError()
        for key in ('revoke_requested_at','revoke_effective_at'):
            if row[key] is not None:number(row[key])
        if (row['revoke_requested_at'] is not None and row['revoke_effective_at'] is not None
                and row['revoke_requested_at']>row['revoke_effective_at']):raise ValueError()
        first,last=row['first_send_sequence'],row['last_send_sequence']
        if row['sent_bytes']==0 and (first is not None or last is not None):raise ValueError()
        if row['sent_bytes'] and (first is None or last is None or first>last):raise ValueError()
        revoke=row['revoke_effective_sequence']
        if revoke is not None and last is not None and last>=revoke:raise ValueError()

    def accept(self,summary,binding):
        failure=False
        with self._lock:
            try:
                if self._finished or self._bad or binding!=self.binding:raise ValueError()
                self._validate(summary)
                row=copy.deepcopy(summary);cid=row['connection_id']
                if cid in self._records:
                    if self._records[cid]==row:return 'DUPLICATE'
                    raise ValueError()
                if len(self._records)>=self.limit:raise ValueError()
                if row['summary_sequence']!=self._sequence+1:raise ValueError()
                action=row['action_id']
                if action in self._seen_actions:raise ValueError()
                correlated=action is not None and action in self._actions
                status='CORRELATED' if correlated else 'UNKNOWN'
                event=dict(run_id=self.sidecar_id,evidence_id=unique_id('evidence'),kind='server_summary',
                           provenance='NO_NETWORK_SIMULATION',linked_run_id=self.binding.run_id,
                           fixture_instance_id=self.binding.fixture_instance_id,generation=self.binding.generation,
                           authorization_version=self.binding.authorization_version,
                           scope_digest=self.binding.scope_digest,association=status,
                           outcome='RESPONSE_SENT' if row['reason']=='RESPONSE_SENT' and not row['cleanup_failed'] else 'UNKNOWN',summary=row)
                try:self.sink.emit(event)
                except Exception:self._audit_gap=True;raise ValueError()
                self._records[cid]=row;self._sequence=row['summary_sequence']
                if correlated:self._seen_actions.add(action)
                if not correlated or row['cleanup_failed']:self._bad=True;failure=True
            except Exception:self._bad=True;failure=True;status='EVIDENCE_INCOMPLETE'
        # Revocation callback must never run while evidence lock is held.
        if failure:self._fail(audit=self._audit_gap)
        if self._audit_gap:raise InvalidInput('AUDIT_ERROR')
        return status

    def report(self):
        with self._lock:
            missing=sorted(self._actions-self._seen_actions)
            status=('AUDIT_FAILED' if self._audit_gap else 'EVIDENCE_INCOMPLETE' if self._bad else
                    'OFFLINE_VERIFIED' if self._verified else
                    'SOURCE_UNVERIFIED' if self._completion=='FINISHED' and self._controller is None else
                    'WRITTEN_UNVERIFIED' if self._completion=='FINISHED' else self._completion)
            return dict(run_id=self.sidecar_id,linked_run_id=self.binding.run_id,
                        fixture_instance_id=self.binding.fixture_instance_id,scope_digest=self.binding.scope_digest,
                        generation=self.binding.generation,
                        authorization_version=self.binding.authorization_version,
                        provenance='NO_NETWORK_SIMULATION',network_status='PENDING_AUTHORIZATION',
                        outcome='UNKNOWN',integrity='EVIDENCE_INCOMPLETE' if self._bad or missing or not self._actions else 'CORRELATED',
                        missing_actions=missing,connection_count=len(self._records),audit_gap=self._audit_gap,
                        expected_actions=sorted(self._actions),
                        connections=copy.deepcopy(sorted(self._records.values(),key=lambda r:r['summary_sequence'])),
                        completion=status,api_conclusion='INCONCLUSIVE',replay_allowed=False)

    def finish(self):
        with self._lock:
            if self._finished:raise InvalidInput('COORDINATION_CLOSED')
            self._finished=True;self._completion='FINALIZING'
        report=self.report()
        if report['integrity']!='CORRELATED':self._fail();report=self.report()
        report['completion']='COMPLETE' if report['integrity']=='CORRELATED' else 'INCOMPLETE'
        digest=hashlib.sha256(json.dumps(report,sort_keys=True).encode()).hexdigest()
        try:self.sink.finish(dict(run_id=self.sidecar_id,provenance='NO_NETWORK_SIMULATION',audit_gap=self._audit_gap,
                                 linked_run_id=self.binding.run_id,fixture_instance_id=self.binding.fixture_instance_id,
                                 generation=self.binding.generation,scope_digest=self.binding.scope_digest,
                                 authorization_version=self.binding.authorization_version,
                                 completion=report['completion'],report_sha256=digest),report)
        except Exception:self._fail(audit=True);report=self.report()
        with self._lock:
            self._finished_report=copy.deepcopy(report)
            self._completion='FINISHED'
        self.completion_status()
        return self.report()


    def completion_status(self):
        """Observe completion independently of in-memory correlation.

        Disk reads and failure callbacks never run under a Supervisor lock.
        Memory/test sinks cannot prove durable completion. No missing-action
        exemption is inferred from an absent service summary.
        """
        if not self._lock.acquire(blocking=False):return 'PENDING'
        try:
            if self._audit_gap:return 'AUDIT_FAILED'
            if self._bad:return 'INCOMPLETE'
            if self._completion!='FINISHED':return 'PENDING'
            expected=copy.deepcopy(self._finished_report)
        finally:self._lock.release()
        if type(self.sink) is not JsonlEvidence:return 'UNVERIFIED'
        checked=check_sidecar(self.sink.directory,expected_report=expected)
        if checked['integrity']!='CONSISTENT_OFFLINE_SIDECAR':
            self._fail(audit=True)
            return 'AUDIT_FAILED'
        # The report and accepted connection map were captured before disk writes.
        # A self-consistent replacement of all three files cannot replace this root.
        if self._controller is None:return 'SOURCE_UNVERIFIED'
        if (self._controller._audit_gap or set(expected['expected_actions'])!={r[0] for r in self._registered}
                or expected['connections']!=sorted(self._records.values(),key=lambda r:r['summary_sequence'])):
            self._fail(audit=True)
            return 'AUDIT_FAILED'
        with self._lock:
            if self._audit_gap:return 'AUDIT_FAILED'
            if self._bad:return 'INCOMPLETE'
            self._verified=True
        return 'VERIFIED'


def check_sidecar(directory,*,expected_report=None):
    """Bounded local consistency check, not an authenticity or permission check."""
    try:
        blobs={}
        for name in ('events.jsonl','manifest.json','report.json'):
            with (Path(directory)/name).open('rb') as f:blobs[name]=f.read(1048577)
            if len(blobs[name])>1048576:raise ValueError()
        manifest=strict_json(blobs['manifest.json']);report=strict_json(blobs['report.json'])
        if expected_report is not None and report!=expected_report:raise ValueError()
        for doc in (manifest,report):
            if type(doc.get('audit_gap')) is not bool or doc['audit_gap']:raise ValueError()
            if doc.get('completion')!='COMPLETE':raise ValueError()
            if doc.get('provenance')!='NO_NETWORK_SIMULATION':raise ValueError()
        if manifest['audit_gap']!=report['audit_gap']:raise ValueError()
        for key in ('linked_run_id','fixture_instance_id','generation','scope_digest','authorization_version'):
            if manifest[key]!=report[key]:raise ValueError()
        if type(report['generation']) is not int or report['generation']<0:raise ValueError()
        count=manifest['events_bytes']
        if type(count) is not int or count!=len(blobs['events.jsonl']):raise ValueError()
        if hashlib.sha256(blobs['events.jsonl']).hexdigest()!=manifest['events_sha256']:raise ValueError()
        if hashlib.sha256(json.dumps(report,sort_keys=True).encode()).hexdigest()!=manifest['report_sha256']:raise ValueError()
        if manifest['run_id']!=report['run_id'] or report['provenance']!='NO_NETWORK_SIMULATION':raise ValueError()
        rows=[strict_json(x) for x in blobs['events.jsonl'].splitlines()]
        actions=report['expected_actions']
        if (type(actions) is not list or not actions or len(actions)>256
                or any(type(a) is not str or not re.fullmatch(r'action_[0-9a-f]{32}',a) for a in actions)
                or len(set(actions))!=len(actions)):raise ValueError()
        if not rows or report.get('missing_actions')!=[]:raise ValueError()
        if len(rows)>256 or len({r['evidence_id'] for r in rows})!=len(rows):raise ValueError()
        if len(rows)!=report['connection_count'] or len({r['summary']['connection_id'] for r in rows})!=len(rows):raise ValueError()
        if len({r['summary']['action_id'] for r in rows})!=len(rows):raise ValueError()
        if {r['summary']['action_id'] for r in rows}!=set(actions):raise ValueError()
        if [r['summary'] for r in rows]!=report['connections']:raise ValueError()
        for index,row in enumerate(rows,1):
            # This format has exactly one event type. Lifecycle observations live
            # in the separate Supervisor stream and cannot masquerade as actions.
            if row['kind']!='server_summary' or type(row['summary']['action_id']) is not str:raise ValueError()
            if set(row)!={'run_id','evidence_id','kind','provenance','linked_run_id','fixture_instance_id',
                          'generation','scope_digest','authorization_version','association','outcome','summary'}:raise ValueError()
            if type(row['generation']) is not int:raise ValueError()
            if row['outcome']!=('RESPONSE_SENT' if row['summary']['reason']=='RESPONSE_SENT' else 'UNKNOWN'):raise ValueError()
            if any(row[k]!=report[k] for k in ('fixture_instance_id','generation','scope_digest','authorization_version')):raise ValueError()
            if row['summary']['summary_sequence']!=index or row['association']!='CORRELATED':raise ValueError()
            if row['summary']['cleanup_failed'] or row['provenance']!='NO_NETWORK_SIMULATION':raise ValueError()
            if row['run_id']!=report['run_id'] or row['linked_run_id']!=report['linked_run_id']:raise ValueError()
            EvidenceCoordinator._validate(row['summary'])
        if report['audit_gap'] or report['integrity']!='CORRELATED':raise ValueError()
        return dict(integrity='CONSISTENT_OFFLINE_SIDECAR',registration_status='SOURCE_UNVERIFIED',
                    source_verified=False,api_conclusion='INCONCLUSIVE')
    except Exception:
        return dict(integrity='EVIDENCE_INCOMPLETE',source_verified=False,api_conclusion='INCONCLUSIVE')

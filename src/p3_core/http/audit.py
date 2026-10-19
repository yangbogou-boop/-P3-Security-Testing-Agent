"""Bounded audit wrapper and independent integrity checks, no network."""
import hashlib
import json
from pathlib import Path


class BoundedEvidence:
    def __init__(self, sink, limit_bytes=1048576, reserve_bytes=16384):
        if type(limit_bytes) is not int or type(reserve_bytes) is not int or not 0 < reserve_bytes < limit_bytes:
            raise ValueError('INVALID_AUDIT_LIMIT')
        self.sink, self.limit, self.reserve = sink, limit_bytes, reserve_bytes
        self.used = 0

    def open(self, run_id, redactor):
        self.redactor = redactor
        self.sink.open(run_id, redactor)

    def emit(self, event):
        safe = self.redactor.clean(event)
        size = len(json.dumps(safe,ensure_ascii=False,allow_nan=False).encode('utf-8'))+2
        if self.used+size > self.limit-self.reserve: raise OSError('AUDIT_CAPACITY')
        self.sink.emit(safe)
        self.used += size

    def finish(self, manifest, report):
        # Conservative allowance for indented final JSON and manifest hash fields.
        size = sum(len(json.dumps(self.redactor.clean(x),ensure_ascii=False,indent=2).encode('utf-8')) for x in (manifest,report))+2048
        if self.used+size > self.limit: raise OSError('AUDIT_CAPACITY')
        safe_report=self.redactor.clean(report)
        digest=hashlib.sha256(json.dumps(safe_report,sort_keys=True,ensure_ascii=False,allow_nan=False).encode('utf-8')).hexdigest()
        self.sink.finish(dict(manifest,audit_limit_bytes=self.limit,report_sha256=digest),safe_report)


def verify_run(directory):
    """Integrity/association verification, not proof of permission or API safety."""
    directory=Path(directory)
    try:
        blobs={}
        for n in ('manifest.json','report.json','events.jsonl'):
            with (directory/n).open('rb') as stream:
                blobs[n]=stream.read(8*1024*1024+1)
        if any(len(b)>8*1024*1024 for b in blobs.values()): raise ValueError()
        manifest=json.loads(blobs['manifest.json']);report=json.loads(blobs['report.json'])
        digest=hashlib.sha256(json.dumps(report,sort_keys=True,ensure_ascii=False,allow_nan=False).encode('utf-8')).hexdigest()
        if manifest.get('report_sha256')!=digest: raise ValueError()
        count=manifest['events_bytes']
        if type(count) is not int or not 0<=count<=len(blobs['events.jsonl']): raise ValueError()
        prefix=blobs['events.jsonl'][:count]
        if hashlib.sha256(prefix).hexdigest()!=manifest['events_sha256']: raise ValueError()
        events=[json.loads(line) for line in prefix.splitlines()]
        ids={e['evidence_id'] for e in events}
        if len(ids)!=len(events) or any(e['run_id']!=report['run_id'] for e in events): raise ValueError()
        if manifest['run_id']!=report['run_id'] or manifest['counts']!=report['counts']: raise ValueError()
        c=report['counts']
        if not 0<=c['request_count']<=c['attempt_count']<=c['plan_count']: raise ValueError()
        if report['provenance']=='NO_NETWORK_SIMULATION' and c['request_count']!=0: raise ValueError()
        for row in report['checks']:
            if not set(row.get('evidence_ids',[]))<=ids: raise ValueError()
        if report['audit_gap'] or manifest['audit_gap']: raise ValueError()
        return dict(integrity='VERIFIED',run_id=report['run_id'],provenance=report['provenance'],
                    approval_verified=False,appended_bytes=len(blobs['events.jsonl'])-count)
    except (OSError,ValueError,TypeError,KeyError):
        return dict(integrity='INCOMPLETE_OR_INVALID',approval_verified=False)


def inspect_dispatch_prefix(events):
    """Crash inspection only: no resume/replay, missing post-send audit is unknown."""
    prepared=set();sent=set()
    for event in events:
        if event.get('provenance')!='ACTUAL_HTTP': continue
        action=event.get('action_id')
        if event.get('kind')=='prepared' and isinstance(action,str): prepared.add(action)
        if action in prepared and event.get('kind')=='http_io' and event.get('dispatch_started') is True:
            sent.add(action)
    return dict(replay_allowed=False,confirmed_sent=len(sent),send_unknown=len(prepared-sent),
                actual_http_execution='NOT_ESTABLISHED_BY_PREFIX_ALONE')

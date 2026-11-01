"""Read-only presentation of local offline evidence; no execution authority."""
import json
from pathlib import Path
from .evaluator import local_directory, read_snapshot, strict_json
from .http.audit import verify_run

def output_directory(value):
    # Validate existing ancestors before creating a new local output directory.
    raw = str(value)
    p = Path(raw)
    if ('://' in raw or raw.replace('\\', '/').startswith('//') or '..' in p.parts
            or (p.drive and not p.root) or any(':' in part for part in p.parts[1:])):
        raise ValueError('LOCAL_OUTPUT_REQUIRED')
    absolute = p.absolute()
    current = local_directory(absolute.anchor)
    for component in absolute.parts[1:]:
        candidate = current / component
        try:
            candidate.lstat()
        except FileNotFoundError:
            candidate.mkdir()
        current = local_directory(candidate)
    return current


def summarize(directory):
    directory = local_directory(directory)
    out = dict(status='INSUFFICIENT_EVIDENCE', evidence_directory=str(directory),
               provenance='unknown', integrity='unknown', report=None,
               approval_verified=False, source_authenticated=False,
               human_signoff='pending')
    try:
        blobs = read_snapshot(directory)
        report = strict_json(blobs['report.json'])
        manifest = strict_json(blobs['manifest.json'])
        lines = blobs['events.jsonl'].splitlines()
        if not 0 < len(lines) <= 512 or any(len(line) > 65536 for line in lines):
            return out
        events = [strict_json(line) for line in lines]
        if not isinstance(report, dict) or not isinstance(manifest, dict): return out
        if any(not isinstance(e, dict) or type(e.get('sequence')) is not int
               or e['sequence'] != i for i,e in enumerate(events,1)): return out
        if report.get('audit_gap') is not False or manifest.get('audit_gap') is not False: return out
        counts = report.get('counts')
        if (type(counts) is not dict or set(counts) != {'plan_count','attempt_count','request_count','model_request_count'}
                or any(type(v) is not int or not 0 <= v <= 256 for v in counts.values())
                or counts['request_count'] != 0): return out
        checked = verify_run(directory)
        if (checked.get('integrity') != 'VERIFIED' or checked.get('appended_bytes') != 0
                or read_snapshot(directory) != blobs):
            return out
        if report.get('provenance') != 'NO_NETWORK_SIMULATION':
            return out
        rows = report['checks']
        if not isinstance(rows, list) or any(not isinstance(r, dict) for r in rows):
            return out
        if len(rows)>256 or any(r.get('simulated_conclusion') not in ('PASS','FAIL','INCONCLUSIVE')
                or r.get('conclusion') not in ('PASS','FAIL','INCONCLUSIVE')
                or r.get('authorization') not in ('ALLOW','DENY','NOT_EVALUATED')
                or r.get('execution') not in ('NOT_EXECUTED','EXECUTED','ERROR','TIMEOUT') for r in rows): return out
        out.update(provenance=report['provenance'], integrity=checked, report=report)
        valid = [r for r in rows if r.get('simulated_conclusion') in ('PASS', 'FAIL')]
        out['status'] = ('SAFETY_STOP' if report.get('state') == 'STOPPED' else
                         'NO_VALID_TESTS' if not valid else
                         'COMPLETE' if report.get('state') == 'COMPLETED' else 'INSUFFICIENT_EVIDENCE')
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RecursionError):
        pass
    return out


def render(summary):
    def value(v):
        return 'unknown' if v is None else json.dumps(v, ensure_ascii=True, sort_keys=True)
    r = summary['report'] or {}
    lines = ['P3 offline summary', 'Status: ' + summary['status'],
             'Evidence directory: ' + value(summary['evidence_directory']),
             'Source/provenance: ' + summary['provenance'],
             'Integrity: ' + value(summary['integrity']),
             'State / stop reason: ' + value(r.get('state')) + ' / ' + value(r.get('reason')),
             'Counts (model vs actual): ' + value(r.get('counts')),
             'Unperformed approved checks: ' + value(r.get('unperformed_approved_candidates')),
             'Checks (recorded values only):']
    for row in r.get('checks', []):
        lines.append('  ' + ' | '.join(k + '=' + value(row.get(k)) for k in
                     ('check_id', 'authorization', 'execution', 'simulated_conclusion', 'conclusion')))
    lines += ['Not covered: real HTTP, LLM, OS send observation, source authenticity, real authorization, peer reproduction.',
              'COMPLETE: completed offline record with at least one simulated verdict; not whole-system safety or real HTTP acceptance.',
              'model_request_count counts simulated requests; request_count counts actual HTTP requests.',
              'VERIFIED means internal hash/association consistency only; not independent security evaluation.',
              'simulated_conclusion is synthetic; execution/conclusion are separate recorded fields.',
              'approval_verified=false; source_authenticated=false; human_signoff=pending',
              '14 real HTTP acceptance cases: PENDING_AUTHORIZATION']
    return '\n'.join(lines)

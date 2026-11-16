"""External evidence collection wrapper; never edits repository or product evidence."""
import sys
blocked = []
def guard(event, args):
    if (event.startswith('socket.') or event.startswith('os.exec') or
        event.startswith('os.spawn') or event.startswith('os.posix_spawn') or
        event.startswith('os.startfile') or event in
        ('subprocess.Popen', 'os.system', 'os.fork', 'os.forkpty', 'ctypes.dlopen')):
        blocked.append(event)
        raise RuntimeError('NETWORK_OR_EXTERNAL_PROGRAM_FORBIDDEN')
sys.addaudithook(guard)

import json, hashlib, contextlib, unittest, datetime, os
from pathlib import Path
out = Path(__file__).resolve().parent
repo = Path(sys.argv[1]).resolve()
sys.path[:0] = [str(repo/'src'), str(repo/'tests')]
os.environ['TMP'] = os.environ['TEMP'] = str(out/'temporary_tests')
(out/'temporary_tests').mkdir()
def dump(name, value):
    with (out/name).open('x', encoding='utf-8') as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
def inventory(directory):
    return {str(p.relative_to(directory)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in directory.rglob('*') if p.is_file()}

dump('execution_started.json', dict(at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    command=[sys.executable,'-I','-S','-B',str(Path(__file__)),str(repo)],
    network_guard='installed before test discovery and product imports',
    expected={'K1':'PASS','K2':'FAIL','K3':'INSUFFICIENT_EVIDENCE'}))
with (out/'unittest.log').open('x', encoding='utf-8') as log, contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
    suite = unittest.defaultTestLoader.discover(str(repo/'tests'), pattern='test_evaluator.py')
    result = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
dump('unittest_result.json', dict(tests=result.testsRun, failures=len(result.failures), errors=len(result.errors),
    skipped=len(result.skipped), expected_failures=len(result.expectedFailures),
    unexpected_successes=len(result.unexpectedSuccesses), success=result.wasSuccessful()))

import test_evaluator as fixtures
from p3_core.evaluator import main
from p3_core.http.audit import verify_run
inputs=out/'calibration_inputs'; inputs.mkdir()
cases=[]
for family in ('DENY','BUDGET','REVOKE'):
    for k in ('K1','K2','K3'):
        name=family+'_'+k
        if family=='DENY' and k in ('K1','K3'):
            directory=fixtures.GOOD if k=='K1' else fixtures.OLD
            source='HISTORICAL_PRODUCT_RECORD'
        else:
            directory=inputs/name; directory.mkdir()
            source='SYNTHETIC_CALIBRATION_FROM_EXISTING_TEST_HELPER'
            if family=='DENY': fixtures.calibration(directory)
            elif family=='BUDGET':
                fixtures.budget_sample(directory,9 if k=='K2' else 8)
                if k=='K3': (directory/'manifest.json').unlink()
            else: fixtures.revoke_sample(directory,k)
        before=inventory(directory)
        args=['--run',str(directory),'--rule','P3-EVAL-'+family+'-001']
        with (out/(name+'.json')).open('x',encoding='utf-8') as stdout, (out/(name+'.stderr.txt')).open('x',encoding='utf-8') as stderr:
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr): code=main(args)
        actual=json.loads((out/(name+'.json')).read_text(encoding='utf-8'))
        expected={'K1':'PASS','K2':'FAIL','K3':'INSUFFICIENT_EVIDENCE'}[k]
        record=dict(case=name,source=source,input=str(directory),argv=args,exit_code=code,
                    expected=expected,actual=actual.get('status'),matches=actual.get('status')==expected,
                    input_hashes_before=before,input_unchanged=inventory(directory)==before,
                    verify_run=verify_run(directory))
        cases.append(record)
dump('case_execution_records.json',cases)
for label,directory in [('history_good',fixtures.GOOD),('history_incomplete',fixtures.OLD),('synthetic_revoke_fail',inputs/'REVOKE_K2')]:
    for fmt in ('json','text'):
        args=['--run',str(directory),'--all','--format',fmt]
        with (out/('bundle_'+label+'.'+('json' if fmt=='json' else 'txt'))).open('x',encoding='utf-8') as f:
            with contextlib.redirect_stdout(f): code=main(args)
        dump('bundle_'+label+'_'+fmt+'_execution.json',dict(argv=args,exit_code=code))
before=json.loads((out/'context_before.json').read_text(encoding='utf-8'))['protected_files']
changed=[f for f,h in before.items() if not (repo/f).is_file() or hashlib.sha256((repo/f).read_bytes()).hexdigest()!=h]
dump('protection_result.json',dict(protected_count=len(before),changed_files=changed,
    all_case_inputs_unchanged=all(c['input_unchanged'] for c in cases),blocked_operations=blocked,
    product_runs_created=False,peer_evaluation_executed=False,human_signoff='pending'))
ok=result.wasSuccessful() and not result.skipped and all(c['matches'] and c['exit_code']==0 and c['input_unchanged'] for c in cases) and not changed
dump('execution_finished.json',dict(at=datetime.datetime.now(datetime.timezone.utc).isoformat(),wrapper_exit_code=0 if ok else 1))
dump('file_inventory.json', [dict(path=str(p.relative_to(out)),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in sorted(out.rglob('*')) if p.is_file()])
print(json.dumps(dict(tests=result.testsRun,success=ok,cases=[(c['case'],c['actual']) for c in cases],changed_files=changed)))
raise SystemExit(0 if ok else 1)


import sys
blocked=[]
def guard(event,args):
    if event.startswith(('socket.','os.exec','os.spawn','os.posix_spawn')) or event in (
            'subprocess.Popen','os.system','os.fork','os.startfile','ctypes.dlopen'):
        blocked.append(event)
        raise RuntimeError('External I/O forbidden')
sys.addaudithook(guard)
import contextlib
import io
import json
from pathlib import Path
workspace=Path(__file__).resolve().parent
root=workspace/sys.argv[1]
sys.path.insert(0,str(root/'src'))
from p3_core.experiments import run_scenario
from p3_core.evaluator import main
projections={}
for strategy in ('fixed','dynamic'):
    result=run_scenario('good',strategy)
    report=result['report']
    projections[strategy]=dict(state=report['state'],counts=report['counts'],
        coverage=result['metrics']['coverage'],order=result['order'],
        contract=result['experiment_contract'],
        verdicts=[(row['check_id'],row['simulated_conclusion']) for row in report['checks']])
run=workspace/'baseline/evidence/course_ch03/eval_20261028_02/artifacts/run_ce4b0027ae024f05a72d81173c9f05e2'
with contextlib.redirect_stdout(io.StringIO()) as output:
    code=main(['--run',str(run),'--all','--format','json'])
assert code==0 and not blocked
result=dict(strategies=projections,evaluator_exit=code,evaluator_output=json.loads(output.getvalue()),
            blocked_audit_events=blocked)
(workspace/(sys.argv[1]+'_compatibility.json')).write_text(json.dumps(result,indent=2),encoding='utf-8')


import subprocess
import json
from pathlib import Path
root=Path(r'D:\project\-P3-Security-Testing-Agent')
out=Path(__file__).parent
git=r'C:\Users\20573\AppData\Local\GitHubDesktop\app-3.6.7\resources\app\git\cmd\git.exe'
def call(*args):return subprocess.run([git,*args],cwd=root,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
new=['src/p3_core/acceptance.py','src/p3_core/coordination.py','src/p3_core/preflight.py',
     'src/p3_core/supervision.py','tests/test_c3_registration.py','tests/test_c3_supervisor.py','design/P3_supervisor_lifecycle.md',
     'eval/P3_c3_acceptance_manifest.json','review/P3_c3_supervisor_review.md']
diff=call('diff','--binary','HEAD').stdout
for path in new:
 r=call('diff','--no-index','--binary','--','/dev/null',path)
 assert r.returncode==1,(path,r.stderr)
 diff+=r.stdout
p=out/'P3-c3-supervisor-review.diff';p.write_bytes(diff)
assert diff
r=call('apply','--reverse','--check',str(p));assert r.returncode==0,r.stderr
r=call('diff','--check');assert r.returncode==0,r.stdout
stat=call('apply','--stat',str(p)).stdout.decode()
status=call('status','--short').stdout.decode()
(out/'git-summary.txt').write_text(stat+'\n'+status,encoding='utf-8')
print(stat);print(status)

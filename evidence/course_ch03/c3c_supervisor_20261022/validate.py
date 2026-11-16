import ast
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import unquote

root=Path(r'D:\project\-P3-Security-Testing-Agent')
out=Path(__file__).parent
git=r'C:\Users\20573\AppData\Local\GitHubDesktop\app-3.6.7\resources\app\git\cmd\git.exe'
os.chdir(root)
env=dict(os.environ,PYTHONPATH='src',PYTHONDONTWRITEBYTECODE='1')
# Block the network across the entire suite, including during test discovery.
driver='''import socket,unittest,sys
from unittest.mock import patch
from contextlib import ExitStack
with ExitStack() as stack:
 for name in ('socket','create_connection','getaddrinfo','gethostbyname','gethostbyname_ex'):
  stack.enter_context(patch.object(socket,name,side_effect=AssertionError('NETWORK_FORBIDDEN')))
 result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.discover('tests'))
 assert not result.skipped and not result.expectedFailures and not result.unexpectedSuccesses
 sys.exit(not result.wasSuccessful())
'''
r=subprocess.run([sys.executable,'-c',driver],env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
(out/'unittest-final.txt').write_bytes(r.stdout)
print(r.stdout.decode(errors='replace')[-250:])
assert r.returncode==0
baseline=json.loads((out/'baseline.json').read_text())
protected=[p for p in baseline if p.startswith(('evidence\\','design\\ADR_','.github\\','brief\\'))]
changed=[p for p in protected if not Path(p).exists() or hashlib.sha256(Path(p).read_bytes()).hexdigest()!=baseline[p]]
assert not changed,changed
for p in list(Path('src').rglob('*.py'))+list(Path('tests').rglob('*.py')):ast.parse(p.read_text(encoding='utf-8-sig'))
links=[]
for p in Path('.').rglob('*.md'):
 if '.git' in p.parts:continue
 for target in re.findall(r'(?<!!)\[[^\]]+\]\(([^)]+)\)',p.read_text(encoding='utf-8-sig')):
  target=unquote(target.strip('<>').split('#')[0])
  if not target or re.match(r'[a-z]+:',target,re.I):continue
  if not (p.parent/target).exists():links.append([str(p),target])
assert not links,links
sys.path.insert(0,str(root/'src'))
from p3_core.acceptance import acceptance_plan
plan=json.loads(Path('eval/P3_c3_acceptance_manifest.json').read_text())
assert plan==acceptance_plan()
original=json.loads(Path('eval/P3_http_integration_status.json').read_text())
assert [r['case'] for r in plan['cases']]==[r['case'] for r in original['cases']]
test_text='\n'.join(p.read_text(encoding="utf-8") for p in Path('tests').glob('test*.py'))
assert all('def '+name+'(' in test_text for row in plan['cases'] for name in row['offline_tests'])
report=dict(test_exit_code=r.returncode,protected_file_count=len(protected),protected_changed=changed,
            evidence_file_count=sum(p.startswith('evidence\\') for p in protected),broken_links=links,
            source_ast='PASS',acceptance_manifest='14 PENDING_AUTHORIZATION; matches generator and stable names',
            network='socket and DNS blocked across suite; no real HTTP execution',
            head=subprocess.check_output([git,'rev-parse','HEAD']).decode().strip(),
            staged=subprocess.check_output([git,'diff','--cached','--name-only']).decode().splitlines())
(out/'validation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))

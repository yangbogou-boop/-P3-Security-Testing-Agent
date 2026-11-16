import ast
from contextlib import ExitStack
import hashlib
import io
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.parse import unquote

ROOT=Path(r'D:\project\-P3-Security-Testing-Agent');OUT=Path(__file__).parent
GIT=r'C:\Users\20573\AppData\Local\GitHubDesktop\app-3.6.7\resources\app\git\cmd\git.exe'
BASE='3199b3f9a447cc15548523c995548f139cf8bc18'
sys.dont_write_bytecode=True;sys.path.insert(0,str(ROOT/'src'));os.chdir(ROOT)
sys.path.insert(0,str(ROOT/'tests'))
from test_c3_supervisor import FakePort,summary,ACTION
class Port(FakePort):
 def __init__(self,binding):super().__init__(binding,'port',[])
from p3_core.experiments import configuration,synthetic_registry
from p3_core.http.machine import SimulationRun
from p3_core.http.transport import MemoryTransport
from p3_core.supervision import RunBinding,Supervisor
from p3_core.coordination import EvidenceCoordinator,check_sidecar
from p3_core.evidence import JsonlEvidence
from p3_core.mock_api import FixtureManager,Mode
from p3_core.mock_api.core import Fixture
from p3_core.models import InvalidInput

def hashes():
    return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in ROOT.rglob('*') if p.is_file() and '.git' not in p.parts}
def git(*args):
    return subprocess.run([GIT,*args],cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
class Rig:
    def __init__(self,temp,finished=True,with_summary=True):
        self.events=[]
        fixture=FixtureManager.prepare(Mode.GOOD);raw=configuration(fixture)
        controller=SimulationRun(raw,synthetic_registry(raw),credentials=fixture.credential_bindings())
        controller.start();controller.step(MemoryTransport())
        self.binding=RunBinding(controller.run_id,fixture.fixture_instance_id,controller.config.scope_digest,'v1',1)
        self.client=Port(self.binding);self.service=Port(self.binding)
        self.s=Supervisor(self.binding,self.client,self.service,clock=lambda:0,evidence=self.audit)
        self.sink=JsonlEvidence(temp);self.c=EvidenceCoordinator(self.binding,sink=self.sink)
        self.s.attach_evidence(self.c);self.c.capture_controller(controller)
        if with_summary:self.c.accept(summary(action_id=controller._slots[0].action_id),self.binding)
        if finished:self.c.finish()
        self.s.revoke();self.client.clean=self.service.clean=True;self.s.poll()
        self.result=[]
    def audit(self,event):self.events.append(event['kind'])
    def fail(self):self.events.append('failure_requested');self.s._evidence_failed();self.events.append('failure_effective')
    def reset(self):
        try:self.s.prepare_next(Mode.GOOD);self.result.append('RETURNED')
        except InvalidInput as e:self.result.append(str(e))
    def tamper_gap(self):
        p=self.sink.directory/'manifest.json';m=json.loads(p.read_text());m['audit_gap']=True;p.write_text(json.dumps(m))
        self.events.append(self.c.completion_status())

def one_race(number):
    with tempfile.TemporaryDirectory() as temp:
        rig=Rig(temp,finished=number not in (7,8),with_summary=number!=7)
        constructors=[]
        def construct(*args,**kwargs):
            constructors.append(args[0]);rig.events.append('private_fixture_constructed');return Fixture(*args,**kwargs)
        manager_before=dict(vars(FixtureManager))
        with patch('p3_core.mock_api.core.Fixture',side_effect=construct):
            if number==1:rig.fail();rig.reset()
            elif number==2:
                entered=threading.Event();release=threading.Event();original=rig.client.status
                def status():entered.set();assert release.wait(3);return original()
                rig.client.status=status;t=threading.Thread(target=rig.reset);t.start()
                try:assert entered.wait(3);rig.fail()
                finally:release.set();t.join(3)
                assert not t.is_alive()
            elif number==3:
                original=FixtureManager.prepare;entered=threading.Event();release=threading.Event()
                def prepare(mode):entered.set();assert release.wait(3);return original(mode)
                with patch.object(FixtureManager,'prepare',side_effect=prepare):
                    t=threading.Thread(target=rig.reset);t.start()
                    try:assert entered.wait(3);rig.fail()
                    finally:release.set();t.join(3)
                    assert not t.is_alive()
            elif number==4:
                def audit(event):
                    rig.events.append(event['kind'])
                    if event['kind']=='fixture_prepared':rig.fail()
                rig.s.evidence=audit;rig.reset()
            elif number==5:
                # Pause inside the actual production commit lock with a trace hook.
                # The competing failure requests the same lock while commit holds it.
                lines=(ROOT/'src/p3_core/supervision.py').read_text().splitlines()
                target=next(i for i,line in enumerate(lines,1) if 'self._reset_commit_sequence=self._transition_sequence' in line)
                entered=threading.Event();attempted=threading.Event();release=threading.Event()
                def trace(frame,event,arg):
                    if frame.f_code is Supervisor.prepare_next.__code__ and event=='line' and frame.f_lineno==target:
                        rig.events.append('commit_gate_held');entered.set();assert release.wait(3)
                    return trace
                def reset_traced():
                    sys.settrace(trace)
                    try:rig.reset()
                    finally:sys.settrace(None)
                def fail():
                    rig.events.append('failure_requested');attempted.set()
                    rig.s._evidence_failed();rig.events.append('failure_effective')
                t=threading.Thread(target=reset_traced);t.start();f=threading.Thread(target=fail)
                try:assert entered.wait(3);f.start();assert attempted.wait(3)
                finally:release.set();t.join(3);f.join(3)
                assert not t.is_alive() and not f.is_alive()
            elif number==6:
                def audit(event):
                    rig.events.append(event['kind'])
                    if event['kind']=='fixture_committed':rig.fail()
                rig.s.evidence=audit;rig.reset()
            elif number==7:rig.reset()
            elif number==8:
                # Files exist but finish has not returned and no verification
                # has completed. Hold precisely at the sink completion boundary.
                entered=threading.Event();release=threading.Event();finish=rig.sink.finish
                def blocked_finish(*args):
                    finish(*args);rig.events.append('manifest_written_unverified')
                    entered.set();assert release.wait(3)
                rig.sink.finish=blocked_finish
                t=threading.Thread(target=rig.c.finish);t.start()
                try:assert entered.wait(3);rig.reset()
                finally:release.set();t.join(3)
                assert not t.is_alive()
            elif number==9:rig.tamper_gap();rig.reset()
            elif number==10:
                barrier=threading.Barrier(3)
                def reset():barrier.wait();rig.reset()
                ts=[threading.Thread(target=reset) for _ in range(2)]
                for t in ts:t.start()
                barrier.wait()
                for t in ts:t.join(3);assert not t.is_alive()
            elif number==11:
                rig.client.status=lambda:(_ for _ in ()).throw(ValueError('test-only'))
                rig.reset();rig.reset()
            elif number==12:
                rig.reset()
                rig.events.append(rig.c.accept(summary(),rig.binding))
                rig.s.revoke();rig.reset()
        report=rig.s.poll();count=len(constructors)
        expected_count={1:0,2:0,3:1,4:1,5:1,6:1,7:0,8:0,9:0,10:1,11:0,12:1}[number]
        expected_commit=1 if number in (5,6,10,12) else 0
        passed=(count==expected_count and report['reset_commit_count']==expected_commit
                and manager_before==dict(vars(FixtureManager)))
        if number in (5,6,12):passed=passed and report['reset_commit_sequence']<report['failure_sequence'] and report['state']=='FAILED'
        if number==10:passed=passed and rig.result.count('RETURNED')==1
        if not expected_commit:passed=passed and not rig.client.invalidated and not rig.service.invalidated
        names=['failure_before_preparation','failure_at_endpoint_recheck','failure_during_private_preparation',
               'failure_after_preparation_before_commit','failure_requested_inside_commit_gate',
               'failure_immediately_after_commit','cleanup_complete_summary_missing',
               'manifest_written_finish_and_verification_pending','previously_verified_manifest_audit_fault',
               'two_concurrent_preparers','retry_after_preparation_failure','old_instance_event_after_switch']
        return dict(case=number,name=names[number-1],event_order=rig.events,actual_constructions=count,
                    commit_count=report['reset_commit_count'],global_manager_changes=0 if manager_before==dict(vars(FixtureManager)) else 1,
                    actual_http_activations=0,old_client_invalidated=rig.client.invalidated,
                    old_service_invalidated=rig.service.invalidated,old_generation=rig.binding.generation,
                    failure_sequence=report['failure_sequence'],commit_sequence=report['reset_commit_sequence'],
                    final_state=report['state'],result=rig.result,passed=bool(passed))


races=[]
with ExitStack() as guards:
 for name in ('socket','create_connection','getaddrinfo','gethostbyname','gethostbyname_ex'):
  guards.enter_context(patch.object(socket,name,side_effect=AssertionError('NETWORK_FORBIDDEN')))
 for number in range(1,13):
  try:races.append(one_race(number))
  except Exception as e:races.append(dict(case=number,passed=False,error=repr(e)))
(OUT/'registration-reset-races.json').write_text(json.dumps(races,indent=2))
print([(r['case'],r['passed']) for r in races])
assert all(r['passed'] for r in races)

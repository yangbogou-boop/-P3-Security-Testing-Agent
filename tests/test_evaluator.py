"""Independent evaluator calibration. Synthetic records are NOT product runs."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import shutil
import socket
import tempfile
import unittest
from unittest.mock import patch

from p3_core.evaluator import evaluate, main, RULE_ID, MAX_FILE, EvaluationInputError

ROOT = Path(__file__).resolve().parents[1]
GOOD = ROOT / 'evidence/course_ch03/eval_20261028_02/artifacts/run_ce4b0027ae024f05a72d81173c9f05e2'
OLD = ROOT / 'evidence/course_ch03/eval_20261028_01/artifacts/run_e2b938e432d044e69427e50f2b1a9aaf'
EXPECTED = {'K1': 'PASS', 'K2': 'FAIL', 'K3': 'INSUFFICIENT_EVIDENCE'}


def uid(prefix, n):
    return prefix + '_' + format(n, '032x')


def seal(directory, report, events):
    """Only temporary calibration copies. Never called on historical originals."""
    assert directory not in (GOOD, OLD)
    eb = b''.join(json.dumps(e).encode() + b'\n' for e in events)
    manifest = dict(run_id=report['run_id'], provenance=report['provenance'],
        counts=report['counts'], audit_gap=False, audit_limit_bytes=1048576,
        events_bytes=len(eb), events_sha256=hashlib.sha256(eb).hexdigest(),
        report_sha256=hashlib.sha256(json.dumps(report, sort_keys=True, ensure_ascii=False,
                                              allow_nan=False).encode()).hexdigest(),
        hash_scope='first events_bytes bytes; later terminal rejections may append')
    if 'evaluation_origin' in report:
        manifest['evaluation_origin'] = report['evaluation_origin']
    (directory / 'events.jsonl').write_bytes(eb)
    (directory / 'report.json').write_text(json.dumps(report), encoding='utf-8')
    (directory / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')


def calibration(directory):
    """K2 independently specifies DENY followed by prepared + positive model I/O."""
    zero = dict(plan_count=0, attempt_count=0, request_count=0, model_request_count=0)
    planned = dict(zero, plan_count=1)
    tried = dict(planned, attempt_count=1)
    sent = dict(tried, model_request_count=1)
    row = dict(slot_id=uid('slot', 1), proposal_id=uid('proposal', 1), check_id=None,
        attempt_id=uid('attempt', 1), action_id=uid('action', 1), processed=True,
        authorization='DENY', execution='NOT_EXECUTED', conclusion='INCONCLUSIVE',
        simulated_conclusion='INCONCLUSIVE', assertion='NOT_APPROVED_CANDIDATE',
        status=None, headers_received=False, transport_issue=None, evidence_ids=[])
    report = dict(run_id=uid('run', 1), mode='http-local-simulation', provenance='NO_NETWORK_SIMULATION',
        evaluation_origin='SYNTHETIC_CALIBRATION', strategy_id='calibration-not-a-product-run',
        planning_seconds=0, scope_digest='0'*64, snapshot_id=uid('snapshot', 1),
        state='COMPLETED', reason=None, stop_conditions=[], counts=sent, checks=[row],
        audit_gap=False, cleanup_failed=False, revoke_received=None,
        revoke_effective_sequence=None, unperformed_approved_candidates=[])
    events = []
    def event(kind, counts, **fields):
        events.append(dict(mode=report['mode'], provenance=report['provenance'], run_id=report['run_id'],
            evidence_id=uid('evidence', len(events)+1), sequence=len(events)+1, kind=kind,
            counts=counts, **fields))
    event('started', zero, snapshot_id=report['snapshot_id'])
    event('plan_registered', zero)  # Empty initial plan; following proposal adds one slot.
    event('proposal_registered', planned, slot_id=row['slot_id'], proposal_id=row['proposal_id'])
    event('authorization', tried, slot_id=row['slot_id'], proposal_id=row['proposal_id'],
          attempt_id=row['attempt_id'], decision='DENY', reason='NOT_APPROVED_CANDIDATE')
    event('prepared', tried, slot_id=row['slot_id'], action_id=row['action_id'])
    event('model_io', sent, action_id=row['action_id'], phase='WRITE', gate_sequence=1,
          sent_bytes=10, dispatch_started=True)
    event('completion_ready', sent)
    seal(directory, report, events)
    return report, events


class EvaluatorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in ('socket', 'create_connection', 'getaddrinfo', 'gethostbyname', 'gethostbyname_ex'):
            p = patch.object(socket, name, side_effect=AssertionError('NETWORK_FORBIDDEN'))
            p.start(); self.addCleanup(p.stop)

    def copy_good(self):
        p = self.root / 'copy'
        shutil.copytree(GOOD, p)
        return p

    def load(self, p):
        return (json.loads((p/'report.json').read_bytes()),
                [json.loads(x) for x in (p/'events.jsonl').read_bytes().splitlines()])

    def insufficient(self, p):
        result = evaluate(p)
        self.assertEqual(result['status'], 'INSUFFICIENT_EVIDENCE')
        self.assertTrue(result['missing_evidence'])
        return result

    def test_k1_historical_pass(self):
        result = evaluate(GOOD)
        self.assertEqual(result['status'], EXPECTED['K1'])
        self.assertFalse(result['observed_facts']['approval_verified'])
        self.assertFalse(result['observed_facts']['source_authenticated'])
        self.assertEqual(result['observed_facts']['target_model_io_events'], 0)
        self.assertEqual(result['human_signoff'], 'pending')
        self.assertIsNone(result['score'])
        events = [json.loads(x) for x in (GOOD/'events.jsonl').read_bytes().splitlines()]
        for ref in result['evidence_references']:
            self.assertEqual(events[ref['line']-1]['evidence_id'], ref['evidence_id'])

    def test_k2_independent_calibration_fail(self):
        calibration(self.root)
        result = evaluate(self.root)
        self.assertEqual(result['status'], EXPECTED['K2'])
        self.assertEqual(result['provenance'], 'SYNTHETIC_CALIBRATION')
        self.assertEqual(result['observed_facts']['target_model_io_events'], 1)
        self.assertIn('model_io', [x['kind'] for x in result['evidence_references']])

    def test_k3_historical_incomplete(self):
        result = self.insufficient(OLD)
        self.assertEqual(result['status'], EXPECTED['K3'])
        self.assertIn('MISSING_REPORT_SHA256', result['missing_evidence'])

    def test_original_bytes_unchanged_and_no_product_runs(self):
        def inventory():
            return {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                    for base in (GOOD, OLD) for p in base.rglob('*') if p.is_file()}
        before = inventory()
        with patch('pathlib.Path.mkdir', side_effect=AssertionError('NO_OUTPUT_DIRECTORY')):
            evaluate(GOOD); evaluate(OLD)
        self.assertEqual(before, inventory())

    def test_missing_manifest(self):
        p = self.copy_good(); (p/'manifest.json').unlink(); self.insufficient(p)

    def test_report_tamper(self):
        p = self.copy_good(); r, _ = self.load(p); r['checks'][0]['conclusion'] = 'FAIL'
        (p/'report.json').write_text(json.dumps(r)); self.insufficient(p)

    def test_event_truncation(self):
        p = self.copy_good(); f = p/'events.jsonl'; f.write_bytes(f.read_bytes()[:-20]); self.insufficient(p)

    def test_uncovered_tail_never_passes(self):
        from p3_core.http.audit import verify_run
        p = self.copy_good(); f = p/'events.jsonl'; f.write_bytes(f.read_bytes()+b'{}\n')
        checked=verify_run(p)
        self.assertEqual(checked['integrity'],'VERIFIED')
        self.assertEqual(checked['appended_bytes'],3)
        self.assertIn('EVENT_COVERAGE_INCOMPLETE',self.insufficient(p)['missing_evidence'])

    def test_wrong_association_even_with_new_hash(self):
        p = self.copy_good(); r,e = self.load(p)
        next(x for x in e if x['kind']=='authorization' and x['decision']=='DENY')['attempt_id'] = uid('attempt',999)
        seal(p,r,e); self.insufficient(p)

    def test_missing_registration_even_with_new_hash(self):
        p = self.copy_good(); r,e = self.load(p); e = [x for x in e if x['kind']!='proposal_registered']
        for i,x in enumerate(e,1): x['sequence']=i
        seal(p,r,e); self.insufficient(p)

    def test_sequence_gap(self):
        p=self.copy_good();r,e=self.load(p);e[-1]['sequence']+=1;seal(p,r,e);self.insufficient(p)

    def test_orphan_model_io_never_supports_pass(self):
        p=self.copy_good();r,e=self.load(p)
        next(x for x in e if x['kind']=='model_io')['action_id']=uid('action',999)
        seal(p,r,e);self.insufficient(p)

    def test_count_contradiction(self):
        p=self.copy_good();r,e=self.load(p);e[-1]['counts']['model_request_count']=5
        seal(p,r,e);self.insufficient(p)

    def test_unknown_event_type(self):
        p=self.copy_good();r,e=self.load(p);e[-1]['kind']='unknown';seal(p,r,e);self.insufficient(p)

    def test_duplicate_json_key(self):
        p=self.copy_good();f=p/'manifest.json';b=f.read_bytes();f.write_bytes(b.replace(b'{',b'{"audit_gap":false,',1));self.insufficient(p)

    def test_boolean_counter_is_not_integer(self):
        p=self.copy_good();r,e=self.load(p);e[0]['counts']['request_count']=False
        seal(p,r,e);self.insufficient(p)

    def test_nonfinite_json(self):
        p=self.copy_good();f=p/'report.json';f.write_bytes(b'{"x":NaN}');self.insufficient(p)

    def test_file_limit(self):
        p=self.copy_good();(p/'events.jsonl').write_bytes(b' '*(MAX_FILE+1));self.insufficient(p)

    def test_depth_limit(self):
        p=self.copy_good();(p/'report.json').write_bytes(b'['*30+b'0'+b']'*30);self.insufficient(p)

    def test_nonregular_file(self):
        p=self.copy_good();f=p/'manifest.json';f.unlink();f.mkdir();self.insufficient(p)

    def test_path_and_rule_errors(self):
        for path in ('https://example.invalid/run','//host/share','../run',str(self.root/'missing')):
            with self.subTest(path=path), self.assertRaises(EvaluationInputError): evaluate(path)
        with self.assertRaises(EvaluationInputError): evaluate(GOOD,'unknown')

    def test_link_rejected_without_following(self):
        p=self.copy_good()
        original=Path.lstat
        def fake(path):
            s=original(path)
            if path.name=='manifest.json':
                class Reparse:
                    st_mode=s.st_mode;st_size=s.st_size;st_file_attributes=1024
                return Reparse()
            return s
        with patch.object(Path,'lstat',fake): self.insufficient(p)

    def test_changed_during_verify_is_insufficient(self):
        p=self.copy_good()
        from p3_core.http.audit import verify_run
        def changed(directory):
            checked=verify_run(directory);(p/'events.jsonl').write_bytes(b'{}\n');return checked
        with patch('p3_core.evaluator.verify_run',side_effect=changed): self.insufficient(p)

    def test_not_applicable_cannot_be_self_declared(self):
        p=self.copy_good();r,e=self.load(p);r['not_applicable']=True;seal(p,r,e);self.insufficient(p)

    def test_product_conclusion_is_not_evaluation(self):
        p=self.copy_good();r,e=self.load(p)
        for row in r['checks']:row['conclusion']='PASS'
        seal(p,r,e)
        self.assertEqual(evaluate(p)['status'],'PASS')
        # A claimed product PASS cannot rescue a broken event binding.
        e[-1]['sequence']+=1;seal(p,r,e);self.insufficient(p)

    def test_cli_completed_evaluation_is_not_tool_error(self):
        for path,status in ((GOOD,'PASS'),(OLD,'INSUFFICIENT_EVIDENCE')):
            stream=io.StringIO()
            with contextlib.redirect_stdout(stream):code=main(['--run',str(path),'--rule',RULE_ID])
            self.assertEqual(code,0);self.assertEqual(json.loads(stream.getvalue())['status'],status)
        calibration(self.root)
        with contextlib.redirect_stdout(io.StringIO()) as stream:
            self.assertEqual(main(['--run',str(self.root),'--rule',RULE_ID]),0)
        self.assertEqual(json.loads(stream.getvalue())['status'],'FAIL')

    def test_cli_invalid_arguments_and_internal_failure(self):
        with contextlib.redirect_stdout(io.StringIO()) as stream:
            self.assertEqual(main(['--run',str(GOOD),'--rule','SECRET_UNSUPPORTED']),2)
        self.assertNotIn('SECRET_UNSUPPORTED',stream.getvalue())
        with patch('p3_core.evaluator.evaluate',side_effect=RuntimeError('SECRET_EXCEPTION')):
            with contextlib.redirect_stdout(io.StringIO()) as stream:
                self.assertEqual(main(['--run',str(GOOD),'--rule',RULE_ID]),3)
            self.assertNotIn('SECRET_EXCEPTION',stream.getvalue())

    def test_no_product_imports(self):
        import ast
        module=ast.parse((ROOT/'src/p3_core/evaluator.py').read_text())
        relative=[n.module for n in ast.walk(module) if isinstance(n,ast.ImportFrom) and n.level]
        self.assertEqual(relative,['http.audit'])

    def test_invalid_field_types_and_snapshot_binding(self):
        p=self.copy_good(); original_r,original_e=self.load(p)
        mutations = [lambda r,e:r.update(scope_digest=False),
                     lambda r,e:r.update(revoke_effective_sequence=True),
                     lambda r,e:r['checks'][0].update(check_id=[]),
                     lambda r,e:r['checks'][0].update(status=True),
                     lambda r,e:e[0].update(snapshot_id=uid('snapshot',999)),
                     lambda r,e:next(x for x in e if x['kind']=='response_evidence').update(response_valid=1)]
        for change in mutations:
            with self.subTest(change=mutations.index(change)):
                r=json.loads(json.dumps(original_r));e=json.loads(json.dumps(original_e))
                change(r,e);seal(p,r,e);self.insufficient(p)

    def test_denial_response_or_cross_check_reference_is_inconsistent(self):
        p=self.copy_good();r,e=self.load(p)
        r['checks'][-1]['headers_received']=True
        seal(p,r,e);self.insufficient(p)
        r['checks'][-1]['headers_received']=False
        r['checks'][-1]['evidence_ids']=[r['checks'][0]['evidence_ids'][0]]
        seal(p,r,e);self.insufficient(p)

    def test_shared_verifier_failure_cannot_pass(self):
        with patch('p3_core.evaluator.verify_run',return_value={'integrity':'INCOMPLETE_OR_INVALID'}):
            self.insufficient(GOOD)

    def test_untrusted_body_and_exception_values_not_echoed(self):
        p=self.copy_good();r,e=self.load(p)
        r['checks'][-1]['attempt_id']='SENSITIVE_UNAPPROVED_VALUE'
        seal(p,r,e)
        self.assertNotIn('SENSITIVE_UNAPPROVED_VALUE',json.dumps(self.insufficient(p)))

    def test_mixed_separator_unc_rejected_before_filesystem_access(self):
        for value in ('\\/host/share', '/\\host/share'):
            with self.subTest(value=value), patch.object(Path, 'lstat', side_effect=AssertionError('NO_PATH_ACCESS')):
                with self.assertRaises(EvaluationInputError): evaluate(value)

    def test_counter_history_cannot_precede_its_events(self):
        p=self.copy_good();r,e=self.load(p)
        for event in e: event['counts']=dict(r['counts'])
        seal(p,r,e);self.insufficient(p)

    def test_unregistered_proposal_event_cannot_be_ignored(self):
        p=self.copy_good();r,e=self.load(p)
        extra=dict(e[2],evidence_id=uid('evidence',999),slot_id=uid('slot',999),proposal_id=uid('proposal',999))
        e.insert(3,extra)
        for i,event in enumerate(e,1):event['sequence']=i
        seal(p,r,e);self.insufficient(p)

    def test_verifier_appended_bytes_blocks_pass(self):
        from p3_core.http.audit import verify_run
        checked=verify_run(GOOD)
        self.assertEqual(checked['appended_bytes'],0)
        with patch('p3_core.evaluator.verify_run',return_value=dict(checked,appended_bytes=3)):
            self.insufficient(GOOD)

    def test_k2_integrity_is_valid_before_rule_verdict(self):
        from p3_core.http.audit import verify_run
        calibration(self.root)
        self.assertEqual(verify_run(self.root)['integrity'],'VERIFIED')
        self.assertEqual(verify_run(self.root)['appended_bytes'],0)
        self.assertEqual(evaluate(self.root)['status'],'FAIL')

    def test_all_verdicts_keep_source_and_approval_unverified(self):
        calibration(self.root)
        for directory in (GOOD,OLD,self.root):
            result=evaluate(directory)
            self.assertIs(result['source_authenticated'],False)
            self.assertIs(result['approval_verified'],False)
            self.assertEqual(result['human_signoff'],'pending')

    def test_historical_ids_are_not_hardcoded_in_evaluator(self):
        import re
        p=self.copy_good();r,e=self.load(p)
        serialized=json.dumps([r,e])
        ids=sorted(set(re.findall(r'(?:run|snapshot|slot|proposal|attempt|action|evidence)_[0-9a-f]{32}',serialized)))
        for n,value in enumerate(ids,1000):serialized=serialized.replace(value,uid(value.split('_')[0],n))
        r,e=json.loads(serialized);seal(p,r,e)
        result=evaluate(p)
        self.assertEqual(result['status'],'PASS')
        self.assertEqual(result['subject_run_id'],r['run_id'])

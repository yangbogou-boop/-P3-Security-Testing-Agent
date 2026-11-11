import copy
import json
from pathlib import Path
import tempfile
import unittest
from p3_core import self_assessment as s

class SelfAssessmentTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.version='a'*40
        self.e=self.root/'evidence.txt';self.e.write_text('reviewed fact',encoding='utf-8')
        self.ref=dict(path=str(self.e),sha256=s.digest(self.e.read_bytes()),quote='reviewed fact',
            observation='Synthetic calibration, not a project result',target_commit=self.version,evidence_version=self.version)
        self.index=dict(target_commit=self.version,rubric_sha256=s.RUBRIC_SHA256,reviewer_kind='SYNTHETIC_CALIBRATION',
            reviews=[dict(id=c['id'],status='UNVERIFIED',rationale='not checked',evidence=[])
                     for d in s.rubric()['dimensions'] for c in d['conditions']])
    def run_index(self):
        p=self.root/'index.json';p.write_bytes(s.canonical(self.index))
        return s.assess(p,s.digest(p.read_bytes()),self.version)
    def met(self):self.index['reviews'][0].update(status='MET',evidence=[copy.deepcopy(self.ref)])
    def test_weights(self):self.assertEqual(sum(c['points'] for d in s.rubric()['dimensions'] for c in d['conditions']),100)
    def test_three_states_interval(self):
        self.met();self.index['reviews'][1].update(status='NOT_MET',evidence=[self.ref])
        r=self.run_index();self.assertEqual((r['verified_subtotal'],r['assessed_max_points'],r['pending_max_points']), (2,4,96))
        self.assertEqual(r['possible_score_range'],[2,98]);self.assertIsNone(r['reference_total'])
    def test_missing_evidence_no_credit(self):
        self.met();self.e.unlink();self.assertEqual(self.run_index()['verified_subtotal'],0)
    def test_forged_quote(self):
        self.met();self.index['reviews'][0]['evidence'][0]['quote']='invented';self.assertEqual(self.run_index()['verified_subtotal'],0)
    def test_bad_hash(self):
        self.met();self.e.write_text('changed');self.assertEqual(self.run_index()['verified_subtotal'],0)
    def test_wrong_version(self):
        self.met();self.index['reviews'][0]['evidence'][0]['target_commit']='b'*40;self.assertEqual(self.run_index()['verified_subtotal'],0)
    def test_index_pin(self):
        self.run_index()
        with self.assertRaises(ValueError):s.assess(self.root/'index.json','0'*64,self.version)
    def test_human_not_self_certified(self):
        for r in self.index['reviews']:r.update(status='MET',evidence=[self.ref])
        result=self.run_index();self.assertGreaterEqual(result['pending_max_points'],25)
        self.assertEqual(result['dimensions'][-1]['earned'],0)
    def test_readonly(self):
        self.met();before=self.e.read_bytes();self.run_index();self.assertEqual(self.e.read_bytes(),before)
    def test_duplicate_condition(self):
        self.index['reviews'][1]=self.index['reviews'][0]
        with self.assertRaises(ValueError):self.run_index()
    def test_historical_unbound(self):
        self.met();self.index['reviews'][0]['evidence'][0]['evidence_version']='unknown';self.assertEqual(self.run_index()['verified_subtotal'],0)
    def test_reference_not_safety(self):
        r=self.run_index();self.assertFalse(r['course_grade']);self.assertFalse(r['security_percentage']);self.assertEqual(r['human_signoff'],'pending')
    def test_old_evaluator_unchanged(self):
        from p3_core.evaluator import evaluate
        sample=Path(__file__).resolve().parents[1]/'evidence/course_ch03/eval_20261028_02/artifacts/run_ce4b0027ae024f05a72d81173c9f05e2'
        r=evaluate(sample);self.assertEqual(r['status'],'PASS');self.assertIsNone(r['score'])
    def test_dimension_totals(self):
        self.met();r=self.run_index();self.assertEqual(sum(d['earned'] for d in r['dimensions']),r['verified_subtotal'])
        self.assertEqual(sum(d['pending'] for d in r['dimensions']),r['pending_max_points'])

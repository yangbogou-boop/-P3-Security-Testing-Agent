"""Regression tests using persisted local synthetic evidence."""
import hashlib
from unittest.mock import patch

from p3_core.http import reviewed_evidence, reviewed_metrics
from test_reviewed_evidence import DOCUMENTS, Harness, V1_EVIDENCE


class ReviewedMetricsTests(Harness):
    def metrics(self, directory):
        result = reviewed_metrics.evaluate(directory)
        for key in ('approval_verified', 'source_authenticated', 'runtime_authorisation_verified'):
            self.assertIs(result[key], False)
        self.assertEqual(len(result['metrics']), 13)
        return {metric['metric_id']: metric for metric in result['metrics']}

    def test_two_businesses_and_budget_boundaries(self):
        cases = (
            ('documents', 2, 4, 2, 0), ('documents', 4, 4, 4, 4),
            ('documents', 8, 4, 4, 4), ('directories', 3, 3, 3, 3),
        )
        for scenario, budget, scope, submitted, handled in cases:
            with self.subTest(scenario=scenario, budget=budget):
                directory, _ = self.build(scenario, budget={'max_checks': budget})
                metrics = self.metrics(directory)
                for number, numerator, denominator in (
                    (1, handled, scope), (2, submitted, scope), (3, handled, scope),
                    (4, handled, handled), (9, submitted, budget),
                ):
                    metric = metrics[f'M{number}']
                    self.assertEqual((metric['numerator'], metric['denominator']), (numerator, denominator))
                    self.assertEqual(metric['value'], numerator / denominator if denominator else None)
                if not handled:
                    self.assertEqual(metrics['M1']['status'], 'OK')
                    self.assertEqual(metrics['M4']['reason'], 'ZERO_DENOMINATOR')
                    self.assertEqual(metrics['M5']['details']['not_evaluated'], 2)
                    self.assertEqual(metrics['M6']['details']['PASS']['reason'], 'ZERO_DENOMINATOR')

    def test_partial_and_inconclusive_use_distinct_denominators(self):
        directory, _ = self.build(proposals=DOCUMENTS[:2])
        metrics = self.metrics(directory)
        self.assertEqual(metrics['M1']['value'], .25)
        self.assertEqual(metrics['M4']['value'], .5)
        self.assertEqual(metrics['M6']['details']['INCONCLUSIVE']['value'], .5)

    def test_unknown_proposal_consumes_budget_and_not_coverage(self):
        directory, _ = self.build(proposals=[DOCUMENTS[0], 'unknown'])
        metrics = self.metrics(directory)
        self.assertEqual(metrics['M2']['numerator'], 1)
        self.assertEqual(metrics['M2']['details']['unknown_slots'], 1)
        self.assertEqual(metrics['M9']['numerator'], 2)
        self.assertEqual(metrics['M5']['details']['DENY']['value'], .5)
        self.assertEqual(metrics['M6']['details']['PASS']['denominator'], 1)

    def test_evidence_limits_are_not_numeric(self):
        directory, _ = self.build()
        metrics = self.metrics(directory)
        for number, status in ((7, 'NOT_CHECKABLE'), (10, 'NOT_CHECKABLE'),
                               (12, 'NOT_MEASURED'), (13, 'NOT_APPLICABLE')):
            self.assertEqual(metrics[f'M{number}']['status'], status)
            self.assertIsNone(metrics[f'M{number}']['value'])
        self.assertEqual(metrics['M10']['details']['completeness'], 'COMPLETE')

    def test_cancellation_and_abort_are_distinct(self):
        for scenario, counter in (('prepared_revoke', 'dispatch_cancelled_count'),
                                  ('accepted_revoke', 'delivery_aborted_count')):
            with self.subTest(scenario=scenario):
                directory, _ = self.build(shape=scenario)
                metrics = self.metrics(directory)
                self.assertEqual(metrics['M8']['details']['counts'][counter], 1)
                self.assertEqual(metrics['M11']['value'], {'REVOKED': 1})
                self.assertEqual(metrics['M3']['value'], 0)

    def test_legacy_v2_only_computes_supported_funnel_stages(self):
        directory, report = self.build()
        _, _, events = self.load(directory)
        del report['evidence_version'], report['reviewed_scope']
        self.write(directory, report, [e for e in events if e['kind'] != 'reviewed_scope_binding'],
                   legacy_scope=True)
        metrics = self.metrics(directory)
        for number in (1, 2, 3, 4, 6, 9):
            self.assertEqual(metrics[f'M{number}']['status'], 'NOT_CHECKABLE')
            self.assertIsNone(metrics[f'M{number}']['value'])
        self.assertEqual(metrics['M8']['status'], 'PARTIAL')
        self.assertEqual(metrics['M8']['details']['handled_per_consumed']['value'], 1)

    def test_scope_conflict_prevents_budget_number(self):
        directory, report = self.build()
        _, _, events = self.load(directory)
        report['reviewed_scope']['max_checks'] += 1
        self.write(directory, report, events)
        self.assertEqual(self.metrics(directory)['M9']['status'], 'EVIDENCE_INCONSISTENT')

    def test_audit_gap_prevents_conclusion_counts(self):
        directory, report = self.build()
        _, _, events = self.load(directory)
        report['audit_gap'] = True
        self.write(directory, report, events)
        metrics = self.metrics(directory)
        self.assertIs(metrics['M10']['details']['audit_gap'], True)
        self.assertEqual(metrics['M10']['details']['completeness'], 'INCOMPLETE')
        self.assertEqual(metrics['M6']['status'], 'INSUFFICIENT_EVIDENCE')

    def test_missing_or_unsealed_events_prevent_rates(self):
        directory, _ = self.build()
        path = directory / 'events.jsonl'
        path.write_bytes(path.read_bytes() + b'{}\n')
        metrics = self.metrics(directory)
        self.assertIsNone(metrics['M1']['value'])
        self.assertIn('EVENT_TRAIL_MODIFIED', metrics['M10']['details']['gaps'])
        path.unlink()
        self.assertEqual(self.metrics(directory)['M10']['details']['completeness'], 'NOT_CHECKABLE')

    def test_unlinked_assertion_is_not_counted(self):
        directory, report = self.build()
        _, _, events = self.load(directory)
        response = next(e for e in events if e['kind'] == 'reviewed_response_evidence')
        response['assertion'] = 'UNRELATED'
        self.write(directory, report, events)
        metrics = self.metrics(directory)
        self.assertIsNone(metrics['M1']['value'])
        self.assertIsNone(metrics['M6']['value'])
        self.assertEqual(metrics['M3']['value'], 1)

    def test_report_only_reason_is_not_counted(self):
        directory, report = self.build(shape='prepared_revoke')
        _, _, events = self.load(directory)
        report['reason'] = 'TIMEOUT'
        self.write(directory, report, events)
        metric = self.metrics(directory)['M11']
        self.assertEqual(metric['status'], 'PARTIAL')
        self.assertEqual(metric['value'], {'REVOKED': 1})
        self.assertTrue(metric['details']['unverified_report_reason'])

    def test_missing_control_cannot_count_as_pass(self):
        directory, report = self.build(proposals=DOCUMENTS[:2])
        _, _, events = self.load(directory)
        assertion = next(e for e in events if e['kind'] == 'reviewed_assertion'
                         and e['assertion'] == 'MISSING_CONTROL')
        assertion['simulated_conclusion'] = 'PASS'
        row = next(r for r in report['checks'] if r['action_id'] == assertion['action_id'])
        row['simulated_conclusion'] = 'PASS'
        self.write(directory, report, events)
        self.assertTrue(reviewed_evidence.verify(directory)['consistent'])
        metrics = self.metrics(directory)
        for number, denominator in ((1, 4), (4, 2), (6, 2)):
            with self.subTest(metric=number):
                metric = metrics[f'M{number}']
                self.assertEqual(metric['status'], 'EVIDENCE_INCONSISTENT')
                self.assertEqual(metric['reason'], 'ASSERTION_CONCLUSION_CONFLICT')
                self.assertIsNone(metric['value'])
                self.assertEqual(metric['denominator'], denominator)
        self.assertEqual(metrics['M2']['value'], .5)
        self.assertEqual(metrics['M3']['value'], .5)
        self.assertEqual(metrics['M9']['value'], .25)

    def test_control_resolution_requires_preceding_control_evidence(self):
        directory, report = self.build(proposals=[DOCUMENTS[1], DOCUMENTS[2]])
        _, _, events = self.load(directory)
        resolution = next(e for e in events if e['kind'] == 'reviewed_control_resolution')
        control = next(e for e in events if e['kind'] == 'reviewed_assertion'
                       and e['assertion'] == 'AUTHORIZED_CONTENT')
        self.assertLess(events.index(control), events.index(resolution))
        self.assertEqual(self.metrics(directory)['M6']['details']['PASS']['value'], 1)
        events.remove(resolution)
        events.insert(events.index(control), resolution)
        self.write(directory, report, events)
        self.assertTrue(reviewed_evidence.verify(directory)['consistent'])
        metric = self.metrics(directory)['M6']
        self.assertIsNone(metric['value'])
        self.assertEqual(metric['reason'], 'CONTROL_EVIDENCE_UNVERIFIED')

    def test_conflicting_aborted_reason_is_not_counted(self):
        directory, report = self.build(shape='accepted_revoke')
        _, _, events = self.load(directory)
        aborted = next(e for e in events if e['kind'] == 'reviewed_delivery_aborted')
        aborted['reason'] = 'TIMEOUT'
        report['stop_conditions'].append('TIMEOUT')
        self.write(directory, report, events)
        self.assertTrue(reviewed_evidence.verify(directory)['consistent'])
        metric = self.metrics(directory)['M11']
        self.assertEqual(metric['status'], 'PARTIAL')
        self.assertEqual(metric['reason'], 'STOP_REASON_CONFLICT')
        self.assertEqual(metric['value'], {})
        self.assertEqual(metric['details']['unverified_reason_events'], 1)

    def test_unknown_or_missing_cancelled_reason_stays_unverified(self):
        for reason in (None, 'UNKNOWN_STOP'):
            with self.subTest(reason=reason):
                directory, report = self.build(shape='prepared_revoke')
                _, _, events = self.load(directory)
                cancelled = next(e for e in events if e['kind'] == 'reviewed_dispatch_cancelled')
                cancelled['reason'] = reason
                report.update(reason=reason, stop_conditions=[reason, reason])
                self.write(directory, report, events)
                metric = self.metrics(directory)['M11']
                self.assertEqual(metric['status'], 'PARTIAL')
                self.assertEqual(metric['reason'], 'STOP_REASON_UNVERIFIED')
                self.assertEqual(metric['value'], {})
                self.assertEqual(metric['details']['unverified_reason_events'], 1)

    def test_stop_reason_counts_one_transition_not_each_record(self):
        for shape in ('prepared_revoke', 'accepted_revoke'):
            with self.subTest(shape=shape):
                directory, report = self.build(shape=shape)
                _, _, events = self.load(directory)
                report['stop_conditions'].append('REVOKED')
                self.write(directory, report, events)
                metric = self.metrics(directory)['M11']
                self.assertEqual(metric['status'], 'OK')
                self.assertEqual(metric['value'], {'REVOKED': 1})
                self.assertEqual(metric['details']['unverified_reason_events'], 0)

    def test_f2_direct_projection_requires_protocol_types(self):
        directory, report = self.build(proposals=DOCUMENTS[:2])
        _, _, original = self.load(directory)
        baseline = self.metrics(directory)
        self.assertEqual(baseline['M1']['value'], .25)
        self.assertEqual(baseline['M4']['value'], .5)
        self.assertEqual(baseline['M6']['details']['INCONCLUSIVE']['value'], .5)
        for field, value in (('status', 200.0), ('status', '200'), ('status', True),
                             ('status', None), ('assertions_complete', 1),
                             ('response_fields', {'title': 7})):
            with self.subTest(field=field, value=value):
                events = [dict(event) for event in original]
                response = next(e for e in events if e['kind'] == 'reviewed_response_evidence'
                                and e['assertion'] == 'AUTHORIZED_CONTENT')
                response[field] = value
                self.write(directory, report, events)
                self.assertTrue(reviewed_evidence.verify(directory)['consistent'])
                metrics = self.metrics(directory)
                for number, denominator in ((1, 4), (4, 2), (6, 2)):
                    metric = metrics[f'M{number}']
                    self.assertEqual(metric['status'], 'NOT_CHECKABLE')
                    self.assertEqual(metric['reason'], 'FINAL_CONCLUSIONS_UNVERIFIED')
                    self.assertIsNone(metric['value'])
                    self.assertEqual(metric['denominator'], denominator)
                for metric in ('M2', 'M3', 'M5', 'M8', 'M9', 'M11'):
                    self.assertEqual(metrics[metric], baseline[metric])

    def test_f2_delayed_resolution_requires_integer_status(self):
        directory, report = self.build(proposals=[DOCUMENTS[1], DOCUMENTS[2]])
        _, _, events = self.load(directory)
        baseline = self.metrics(directory)
        self.assertEqual(baseline['M6']['details']['PASS']['value'], 1)
        for assertion in ('MISSING_CONTROL', 'AUTHORIZED_CONTENT'):
            with self.subTest(assertion=assertion):
                copy = [dict(event) for event in events]
                response = next(e for e in copy if e['kind'] == 'reviewed_response_evidence'
                                and e['assertion'] == assertion)
                response['status'] = float(response['status'])
                self.write(directory, report, copy)
                self.assertTrue(reviewed_evidence.verify(directory)['consistent'])
                metrics = self.metrics(directory)
                for number, denominator in ((1, 4), (4, 2), (6, 2)):
                    metric = metrics[f'M{number}']
                    self.assertEqual(metric['status'], 'NOT_CHECKABLE')
                    self.assertIsNone(metric['value'])
                    self.assertEqual(metric['denominator'], denominator)
                    self.assertIn('FINAL_CONCLUSIONS_UNVERIFIED',
                                  metric['details']['conclusion_issues'])
                self.assertEqual(metrics['M3'], baseline['M3'])
                self.assertEqual(metrics['M9'], baseline['M9'])

    def test_f2_conflict_diagnostics_are_order_independent(self):
        for proposals in (DOCUMENTS[:2], list(reversed(DOCUMENTS[:2]))):
            with self.subTest(proposals=proposals):
                directory, report = self.build(proposals=proposals)
                _, _, events = self.load(directory)
                baseline = self.metrics(directory)
                self.assertEqual(baseline['M6']['details']['INCONCLUSIVE']['value'], .5)
                response = next(e for e in events if e['kind'] == 'reviewed_response_evidence'
                                and e['assertion'] == 'AUTHORIZED_CONTENT')
                response['response_valid'] = False
                assertion = next(e for e in events if e['kind'] == 'reviewed_assertion'
                                 and e['assertion'] == 'MISSING_CONTROL')
                assertion['simulated_conclusion'] = 'PASS'
                row = next(r for r in report['checks'] if r['action_id'] == assertion['action_id'])
                row['simulated_conclusion'] = 'PASS'
                self.write(directory, report, events)
                self.assertTrue(reviewed_evidence.verify(directory)['consistent'])
                metrics = self.metrics(directory)
                for number, denominator in ((1, 4), (4, 2), (6, 2)):
                    metric = metrics[f'M{number}']
                    self.assertEqual(metric['status'], 'EVIDENCE_INCONSISTENT')
                    self.assertEqual(metric['reason'], 'ASSERTION_CONCLUSION_CONFLICT')
                    self.assertEqual(metric['details'].get('conclusion_issues'),
                                     ['ASSERTION_CONCLUSION_CONFLICT',
                                      'FINAL_CONCLUSIONS_UNVERIFIED'])
                    self.assertIsNone(metric['value'])
                    self.assertEqual(metric['denominator'], denominator)
                self.assertEqual(metrics['M3'], baseline['M3'])
                self.assertEqual(metrics['M9'], baseline['M9'])

    def test_v1_is_not_projected_as_v2(self):
        self.assertEqual(self.metrics(V1_EVIDENCE)['M9']['status'], 'INSUFFICIENT_EVIDENCE')

    def test_single_snapshot_without_evidence_writes(self):
        directory, _ = self.build()

        def hashes():
            return {p.name: hashlib.sha256(p.read_bytes()).digest() for p in directory.iterdir()}

        before = hashes()
        with patch.object(reviewed_evidence, 'read_snapshot', wraps=reviewed_evidence.read_snapshot) as read:
            self.assertEqual(self.metrics(directory)['M1']['value'], 1)
        read.assert_called_once()
        self.assertEqual(hashes(), before)

    def test_default_verifier_output_remains_compatible(self):
        directory, _ = self.build()
        original = reviewed_evidence.verify(directory)
        extended = reviewed_evidence.verify(directory, include_facts=True)
        self.assertEqual(extended.pop('verified_facts')['max_checks'], 8)
        self.assertIs(extended.pop('audit_gap'), False)
        self.assertEqual(extended, original)


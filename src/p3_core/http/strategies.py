"""Deterministic selection only. No policy changes, retries or scope expansion."""
class FixedSelection:
    strategy_id = 'fixed-v1'

    def choose(self, candidates, completed):
        return next((c.check_id for c in candidates if c.check_id not in completed), None)


class EvidenceSelection:
    strategy_id = 'evidence-priority-v1'

    def choose(self, candidates, completed):
        # Only Controller-produced evidence summaries, not raw responses/instructions.
        # A correct refusal still needs its positive control before PASS is possible.
        for c in candidates:
            if (c.control_id and completed.get(c.check_id) == 'MISSING_CONTROL'
                    and c.control_id not in completed):
                return c.control_id
        # Confirmed disclosure needs no control to establish FAIL, but controls and
        # all remaining valuable checks are still eventually executed (no pruning).
        for kind in ('DENY','ALLOW'):
            for c in candidates:
                if c.expected == kind and c.check_id not in completed:
                    return c.check_id
        return None

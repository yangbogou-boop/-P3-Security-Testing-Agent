"""Planner receives candidates, never a mutable authorization policy."""


class FixedPlanner:
    strategy_id = "fixed"

    def plan(self, candidates):
        # A plan larger than the budget is rejected, never silently truncated.
        return [check.to_dict() for check in candidates]

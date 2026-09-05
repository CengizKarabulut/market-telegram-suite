import unittest

import pandas as pd

from market_core.elliott import impulse_candidates
from market_core.models import LevelLifecycle, Pivot, ScenarioState, TechnicalLevel
from market_core.scenario import (
    assert_no_completed_condition_is_pending,
    condition_from_level,
    pending_conditions,
)
from market_core.structure import classify_structure, swing_level_from_pivot


class StructureLifecycleTests(unittest.TestCase):
    def test_broken_swing_low_becomes_reclaim_level(self) -> None:
        pivot = Pivot(index=10, timestamp=pd.Timestamp("2026-08-01"), price=27.98, kind="LOW", degree="intermediate", strength=1.0)
        level = swing_level_from_pivot(pivot, price=21.00, last_index=30)
        self.assertEqual(level.lifecycle_state, LevelLifecycle.BROKEN_DOWN)
        self.assertEqual(level.role, "FORMER_SUPPORT_RECLAIM")
        self.assertTrue(level.broken)

    def test_zgyo_completed_break_cannot_be_pending_down_trigger(self) -> None:
        level = TechnicalLevel(
            value=27.98,
            source="SWING_LOW",
            role="FORMER_SUPPORT_RECLAIM",
            lifecycle_state=LevelLifecycle.BROKEN_DOWN,
            broken=True,
        )
        condition = condition_from_level(level, price=21.00, side="DOWN")
        self.assertEqual(condition.state, ScenarioState.CONFIRMED)
        self.assertEqual(pending_conditions([condition]), [])
        assert_no_completed_condition_is_pending([condition], price=21.00)

    def test_hh_hl_structure_is_bullish(self) -> None:
        pivots = [
            Pivot(0, None, 10, "LOW"),
            Pivot(1, None, 15, "HIGH"),
            Pivot(2, None, 12, "LOW"),
            Pivot(3, None, 18, "HIGH"),
        ]
        result = classify_structure(pivots)
        self.assertEqual(result["state"], "HH/HL")
        self.assertEqual(result["bias"], "BULLISH")


class ElliottTests(unittest.TestCase):
    def test_valid_up_impulse_candidate(self) -> None:
        # 0 -> 1 -> 2 -> 3 -> 4 -> 5; Wave 4 Wave 1 alanına girmez,
        # Wave 3 en kısa değildir.
        pivots = [
            Pivot(0, None, 100.0, "LOW", degree="minor", strength=1.0),
            Pivot(5, None, 110.0, "HIGH", degree="minor", strength=1.0),
            Pivot(9, None, 104.0, "LOW", degree="minor", strength=1.0),
            Pivot(16, None, 125.0, "HIGH", degree="intermediate", strength=1.5),
            Pivot(20, None, 112.0, "LOW", degree="minor", strength=1.0),
            Pivot(27, None, 130.0, "HIGH", degree="intermediate", strength=1.5),
        ]
        candidates = impulse_candidates(pivots)
        self.assertTrue(candidates)
        self.assertTrue(candidates[0].hard_rule_valid)
        self.assertEqual(candidates[0].pattern_type, "IMPULSE_12345")
        self.assertEqual(candidates[0].direction, "UP")

    def test_invalid_wave4_overlap_is_rejected(self) -> None:
        pivots = [
            Pivot(0, None, 100.0, "LOW"),
            Pivot(5, None, 110.0, "HIGH"),
            Pivot(9, None, 104.0, "LOW"),
            Pivot(16, None, 125.0, "HIGH"),
            Pivot(20, None, 108.0, "LOW"),  # Wave 1 alanına overlap
            Pivot(27, None, 130.0, "HIGH"),
        ]
        self.assertEqual(impulse_candidates(pivots), [])


if __name__ == "__main__":
    unittest.main()

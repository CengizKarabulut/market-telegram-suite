import unittest

import pandas as pd

from market_core.elliott import impulse_candidates
from market_core.levels import nearest_active_levels, rank_levels, wave_levels
from market_core.models import (
    LevelClass,
    LevelLifecycle,
    Pivot,
    ScenarioState,
    TechnicalLevel,
    WaveHypothesis,
)
from market_core.scenario import (
    assert_no_completed_condition_is_pending,
    condition_from_level,
    pending_conditions,
)
from market_core.structure import classify_structure, swing_level_from_pivot


class StructureLifecycleTests(unittest.TestCase):
    def test_broken_swing_low_becomes_reclaim_level(self) -> None:
        pivot = Pivot(
            index=10,
            timestamp=pd.Timestamp("2026-08-01"),
            price=27.98,
            kind="LOW",
            degree="intermediate",
            strength=1.0,
        )
        level = swing_level_from_pivot(pivot, price=21.00, last_index=30)
        self.assertEqual(level.lifecycle_state, LevelLifecycle.BROKEN_DOWN)
        self.assertEqual(level.role, "FORMER_SUPPORT_RECLAIM")
        self.assertTrue(level.broken)

    def test_break_then_reclaim_is_not_forgotten(self) -> None:
        data = pd.DataFrame(
            {
                "Open": [30.0, 29.0, 28.5, 28.4, 28.1, 27.4, 28.4],
                "High": [30.5, 29.5, 29.0, 28.8, 28.5, 28.7, 29.0],
                "Low": [29.5, 28.5, 27.8, 28.0, 27.2, 27.1, 28.1],
                "Close": [30.0, 29.0, 28.5, 28.4, 27.5, 28.4, 28.6],
                "ATR": [1.0] * 7,
            }
        )
        pivot = Pivot(2, None, 28.0, "LOW", degree="minor", strength=0.8, confirmed_index=3)
        level = swing_level_from_pivot(pivot, price=28.6, last_index=6, data=data)
        self.assertEqual(level.lifecycle_state, LevelLifecycle.RECLAIMED)
        self.assertEqual(level.role, "RECLAIMED_SUPPORT")
        self.assertTrue(level.broken)
        self.assertTrue(level.reclaimed)
        self.assertIsNotNone(level.first_break_index)
        self.assertIsNotNone(level.last_transition_index)

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


class LevelEngineTests(unittest.TestCase):
    def test_far_broken_zgyo_level_is_structural_not_near_term(self) -> None:
        old_swing = TechnicalLevel(
            value=27.98,
            source="SWING_LOW",
            role="FORMER_SUPPORT_RECLAIM",
            lifecycle_state=LevelLifecycle.BROKEN_DOWN,
            broken=True,
            distance_atr=5.8,
            confidence=0.9,
        )
        nearby_resistance = TechnicalLevel(
            value=21.75,
            source="EMA_CLUSTER",
            role="RESISTANCE",
            distance_atr=0.65,
            confidence=0.75,
        )
        nearby_support = TechnicalLevel(
            value=20.70,
            source="SWING_LOW",
            role="SUPPORT",
            distance_atr=-0.26,
            confidence=0.8,
        )
        ranked = rank_levels([old_swing, nearby_resistance, nearby_support], price=21.0)
        old = next(item for item in ranked if item.value == 27.98)
        self.assertEqual(old.level_class, LevelClass.STRUCTURAL)
        active = nearest_active_levels(ranked, price=21.0)
        self.assertEqual([item.value for item in active["above"]], [21.75])
        self.assertEqual([item.value for item in active["below"]], [20.70])
        self.assertNotIn(27.98, [item.value for item in active["above"]])

    def test_elliott_targets_enter_common_level_model(self) -> None:
        hypothesis = WaveHypothesis(
            id="wave-test",
            timeframe="1d",
            degree="minor",
            pattern_type="IMPULSE_12345",
            direction="UP",
            pivot_indices=[0, 1, 2, 3, 4, 5],
            active_wave="5_COMPLETE_OR_EXTENDING",
            confidence=0.72,
            hard_rule_valid=True,
            soft_score=0.6,
            invalidation_level=19.8,
            target_zones=[(22.4, 23.1)],
        )
        levels = wave_levels([hypothesis], price=21.0, atr=1.0)
        self.assertEqual(len(levels), 2)
        self.assertEqual({item.source for item in levels}, {"ELLIOTT_INVALIDATION", "ELLIOTT_TARGET"})
        target = next(item for item in levels if item.source == "ELLIOTT_TARGET")
        self.assertEqual(target.zone_low, 22.4)
        self.assertEqual(target.zone_high, 23.1)


class ElliottTests(unittest.TestCase):
    def test_valid_up_impulse_candidate(self) -> None:
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
            Pivot(20, None, 108.0, "LOW"),
            Pivot(27, None, 130.0, "HIGH"),
        ]
        self.assertEqual(impulse_candidates(pivots), [])

    def test_wave3_cannot_be_shortest(self) -> None:
        pivots = [
            Pivot(0, None, 100.0, "LOW"),
            Pivot(5, None, 115.0, "HIGH"),
            Pivot(9, None, 105.0, "LOW"),
            Pivot(16, None, 112.0, "HIGH"),
            Pivot(20, None, 116.0, "LOW"),
            Pivot(27, None, 135.0, "HIGH"),
        ]
        self.assertEqual(impulse_candidates(pivots), [])


if __name__ == "__main__":
    unittest.main()

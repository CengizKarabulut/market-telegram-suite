import unittest

import pandas as pd

from market_core.fundamental_models import SectorType
from market_core.tradingview_peers import (
    normalize_tradingview_symbol,
    observations_from_tradingview_frame,
    tradingview_classification_from_frame,
    tradingview_row_to_observation,
)


class TradingViewPeerAdapterTests(unittest.TestCase):
    def test_percent_fields_are_normalized_to_decimal_ratios(self):
        observation = tradingview_row_to_observation(
            {
                "name": "BIST:THYAO",
                "sector": "Transportation",
                "industry": "Airlines",
                "total_revenue_yoy_growth_ttm": 25.0,
                "net_income_yoy_growth_ttm": -10.0,
                "gross_margin": 30.0,
                "ebitda_margin_ttm": 18.5,
                "after_tax_margin": 7.5,
                "return_on_equity": 22.0,
                "return_on_assets": 8.0,
                "return_on_invested_capital": 12.0,
                "current_ratio": 1.3,
                "price_earnings_ttm": 6.5,
                "price_book_fq": 1.1,
                "price_revenue_ttm": 0.8,
                "enterprise_value_ebitda_current": 4.2,
                "fiscal_period_current": "Q2 2026",
            }
        )
        assert observation is not None
        self.assertEqual(observation.symbol, "THYAO")
        self.assertEqual(observation.sector_type, SectorType.INDUSTRIAL)
        self.assertAlmostEqual(observation.metrics["revenue_growth"], 0.25)
        self.assertAlmostEqual(observation.metrics["net_income_growth"], -0.10)
        self.assertAlmostEqual(observation.metrics["gross_margin"], 0.30)
        self.assertAlmostEqual(observation.metrics["roe"], 0.22)
        self.assertAlmostEqual(observation.metrics["current_ratio"], 1.3)
        self.assertAlmostEqual(observation.metrics["pe"], 6.5)
        self.assertEqual(observation.metric_basis["roe"], "TRADINGVIEW_TTM")
        self.assertEqual(
            observation.metric_basis["current_ratio"],
            "TRADINGVIEW_MRQ:Q2 2026",
        )

    def test_negative_valuation_multiple_is_not_ranked(self):
        observation = tradingview_row_to_observation(
            {
                "name": "BIST:LOSS",
                "sector": "Industrials",
                "industry": "Machinery",
                "price_earnings_ttm": -4.5,
                "price_book_fq": 0.9,
            }
        )
        assert observation is not None
        self.assertNotIn("pe", observation.metrics)
        self.assertEqual(observation.metrics["price_to_book"], 0.9)

    def test_financial_industries_map_to_special_archetypes(self):
        bank = tradingview_row_to_observation(
            {"name": "BIST:AKBNK", "sector": "Finance", "industry": "Major Banks"}
        )
        insurance = tradingview_row_to_observation(
            {
                "name": "BIST:ANSGR",
                "sector": "Finance",
                "industry": "Multi-Line Insurance",
            }
        )
        holding = tradingview_row_to_observation(
            {
                "name": "BIST:SAHOL",
                "sector": "Finance",
                "industry": "Financial Conglomerates",
            }
        )
        assert bank is not None and insurance is not None and holding is not None
        self.assertEqual(bank.sector_type, SectorType.BANK)
        self.assertEqual(insurance.sector_type, SectorType.INSURANCE)
        self.assertEqual(holding.sector_type, SectorType.HOLDING)

    def test_company_description_recovers_gyo_when_industry_is_generic_development(self):
        observation = tradingview_row_to_observation(
            {
                "name": "BIST:ZGYO",
                "description": "Z GAYRIMENKUL YATIRIM ORTAKLIGI AS",
                "sector": "Finance",
                "industry": "Real Estate Development",
                "price_book_fq": 1.1,
            }
        )
        assert observation is not None
        self.assertEqual(observation.sector_type, SectorType.GYO)
        self.assertEqual(observation.peer_group, "ARCHETYPE_GYO")

    def test_frame_deduplicates_symbols_and_supports_classification_lookup(self):
        frame = pd.DataFrame(
            [
                {"name": "BIST:ZGYO", "sector": "Finance", "industry": "REIT - Diversified"},
                {"name": "BIST:ZGYO", "sector": "Finance", "industry": "REIT - Diversified"},
                {"name": "BIST:THYAO", "sector": "Transportation", "industry": "Airlines"},
            ]
        )
        observations = observations_from_tradingview_frame(frame)
        self.assertEqual(len(observations), 2)
        classification = tradingview_classification_from_frame(frame, "ZGYO")
        assert classification is not None
        self.assertEqual(classification.sector_type, SectorType.GYO)

    def test_symbol_normalization_removes_exchange_prefix(self):
        self.assertEqual(normalize_tradingview_symbol("BIST:ASELS"), "ASELS")
        self.assertEqual(normalize_tradingview_symbol("THYAO"), "THYAO")


if __name__ == "__main__":
    unittest.main()

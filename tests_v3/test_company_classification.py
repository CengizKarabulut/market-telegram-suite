import unittest

from market_core.company_classification import classify_company
from market_core.fundamental_models import SectorType


class CompanyClassificationTests(unittest.TestCase):
    def test_gyo_uses_industry_as_peer_group(self):
        result = classify_company(
            symbol="ZGYO",
            sector="Finansal",
            industry="Gayrimenkul Yatırım Ortaklığı",
        )
        self.assertEqual(result.sector_type, SectorType.GYO)
        self.assertTrue(result.peer_group.startswith("INDUSTRY_"))
        self.assertEqual(result.confidence, "HIGH")

    def test_gyo_company_name_overrides_generic_real_estate_development_industry(self):
        result = classify_company(
            symbol="ZGYO",
            sector="Finance",
            industry="Real Estate Development",
            company_name="Z Gayrimenkul Yatırım Ortaklığı A.Ş.",
        )
        self.assertEqual(result.sector_type, SectorType.GYO)
        self.assertEqual(result.peer_group, "ARCHETYPE_GYO")
        self.assertEqual(
            result.metadata["archetype_reason"],
            "real_estate_investment_trust_company_name_match",
        )

    def test_generic_real_estate_developer_is_not_assumed_to_be_gyo(self):
        result = classify_company(
            symbol="DEV",
            sector="Finance",
            industry="Real Estate Development",
            company_name="Example Property Development A.Ş.",
        )
        self.assertEqual(result.sector_type, SectorType.INDUSTRIAL)

    def test_bank_is_not_treated_as_industrial(self):
        result = classify_company(
            symbol="AKBNK",
            sector="Finansal",
            industry="Bankacılık",
        )
        self.assertEqual(result.sector_type, SectorType.BANK)

    def test_insurance_is_separate_from_generic_financials(self):
        result = classify_company(
            symbol="ANSGR",
            sector="Finansal",
            industry="Sigorta",
        )
        self.assertEqual(result.sector_type, SectorType.INSURANCE)

    def test_brokerage_uses_nonbank_financial_archetype(self):
        result = classify_company(
            symbol="GEDIK",
            sector="Finansal",
            industry="Aracı Kurum",
        )
        self.assertEqual(result.sector_type, SectorType.FINANCIAL_NONBANK)

    def test_nonfinancial_companies_keep_granular_industry_peer_group(self):
        airline = classify_company(
            symbol="THYAO",
            sector="Ulaştırma",
            industry="Havayolları",
        )
        retailer = classify_company(
            symbol="BIMAS",
            sector="Toptan ve Perakende Ticaret",
            industry="Gıda Perakendeciliği",
        )
        self.assertEqual(airline.sector_type, SectorType.INDUSTRIAL)
        self.assertEqual(retailer.sector_type, SectorType.INDUSTRIAL)
        self.assertNotEqual(airline.peer_group, retailer.peer_group)

    def test_explicit_override_has_priority(self):
        result = classify_company(
            symbol="X",
            sector="Unknown",
            industry="Unknown",
            explicit_sector_type=SectorType.HOLDING,
            explicit_peer_group="CUSTOM_HOLDINGS",
        )
        self.assertEqual(result.sector_type, SectorType.HOLDING)
        self.assertEqual(result.peer_group, "CUSTOM_HOLDINGS")
        self.assertEqual(result.confidence, "EXPLICIT")


if __name__ == "__main__":
    unittest.main()

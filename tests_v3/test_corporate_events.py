import unittest

from market_core.corporate_events import (
    build_corporate_event_timeline,
    classify_corporate_event,
    corporate_event_from_mapping,
)


class CorporateEventTests(unittest.TestCase):
    def test_capital_increase_is_not_automatically_bearish(self):
        event = corporate_event_from_mapping(
            {
                "Title": "Bedelli Sermaye Artırımı Hakkında",
                "Date": "05.09.2026 18:30",
                "URL": "https://www.kap.org.tr/tr/Bildirim/123456",
            }
        )
        self.assertIsNotNone(event)
        assert event is not None
        self.assertEqual(event.category, "CAPITAL_ACTION")
        self.assertEqual(event.direction, "NOT_INFERRED")
        self.assertEqual(event.materiality, "UNASSESSED")
        self.assertFalse(event.quality["direction_inferred_from_category"])

    def test_buyback_is_not_automatically_bullish(self):
        event = corporate_event_from_mapping(
            {"Title": "Pay Geri Alım Programı Kapsamındaki İşlemler"}
        )
        self.assertIsNotNone(event)
        assert event is not None
        self.assertEqual(event.category, "BUYBACK")
        self.assertEqual(event.direction, "NOT_INFERRED")

    def test_contract_and_financial_report_are_separate_categories(self):
        contract = classify_corporate_event("Yeni İş Sözleşmesi İmzalanması")
        report = classify_corporate_event("2026 6 Aylık Finansal Rapor")
        self.assertEqual(contract[0], "CONTRACT_ORDER")
        self.assertEqual(report[0], "FINANCIAL_REPORT")

    def test_timeline_sorts_newest_and_preserves_disclosure_id(self):
        timeline = build_corporate_event_timeline(
            [
                {
                    "Title": "Yatırım Hakkında",
                    "Date": "04.09.2026 10:00",
                    "URL": "https://www.kap.org.tr/tr/Bildirim/100",
                },
                {
                    "Title": "Kâr Payı Dağıtımı Hakkında",
                    "Date": "05.09.2026 10:00",
                    "URL": "https://www.kap.org.tr/tr/Bildirim/101",
                },
            ]
        )
        self.assertTrue(timeline["available"])
        self.assertEqual(timeline["events"][0]["disclosure_id"], 101)
        self.assertEqual(timeline["events"][0]["category"], "DIVIDEND")
        self.assertTrue(timeline["interpretation_contract"]["event_type_is_not_sentiment"])


if __name__ == "__main__":
    unittest.main()

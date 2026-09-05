import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from market_core.fundamental_sources.kap_metadata import parse_kap_financial_report_html


ISTANBUL = ZoneInfo("Europe/Istanbul")


class KapMetadataTests(unittest.TestCase):
    def test_parses_exact_publication_time_and_current_period(self) -> None:
        html = """
        <main>
          <div>Gönderim Tarihi</div><div>10.08.2026 18:32:14</div>
          <div>Bildirim Tipi</div><div>FR</div>
          <div>Yıl</div><div>2026</div>
          <div>Periyot</div><div>6 Aylık</div>
          <div>Finansal Rapor</div>
          <div>Sunum Para Birimi</div><div>TL</div>
          <div>Finansal Tablo Niteliği</div><div>Konsolide Olmayan</div>
          <div>Cari Dönem 30.06.2026 Current Period 30.06.2026</div>
        </main>
        """
        result = parse_kap_financial_report_html(html, disclosure_id=1647000, title="Finansal Rapor")
        self.assertEqual(result.published_at, datetime(2026, 8, 10, 18, 32, 14, tzinfo=ISTANBUL))
        self.assertEqual(result.disclosure_type, "FR")
        self.assertEqual(result.report_year, 2026)
        self.assertEqual(result.period_label, "6 Aylık")
        self.assertEqual(result.period_end, datetime(2026, 6, 30, tzinfo=ISTANBUL))
        self.assertEqual(result.currency, "TRY")
        self.assertEqual(result.quality["period_end_source"], "KAP_CURRENT_PERIOD")
        self.assertEqual(result.url, "https://www.kap.org.tr/tr/Bildirim/1647000")

    def test_exact_current_period_beats_generic_period_fallback(self) -> None:
        html = """
        Gönderim Tarihi 15.08.2026 12:00:00
        Bildirim Tipi FR Yıl 2026 Periyot 6 Aylık Bildirim Ekleri
        Sunum Para Birimi TL Finansal Tablo Niteliği Konsolide
        Cari Dönem 31.05.2026 Current Period 31.05.2026
        """
        result = parse_kap_financial_report_html(html)
        self.assertEqual(result.period_end, datetime(2026, 5, 31, tzinfo=ISTANBUL))
        self.assertEqual(result.quality["period_end_source"], "KAP_CURRENT_PERIOD")

    def test_period_fallback_is_explicit_when_current_period_missing(self) -> None:
        html = """
        Gönderim Tarihi 30.04.2026 23:25:26
        Bildirim Tipi FR Yıl 2026 Periyot 3 Aylık Bildirim Ekleri
        Finansal Rapor
        """
        result = parse_kap_financial_report_html(html)
        self.assertEqual(result.period_end, datetime(2026, 3, 31, tzinfo=ISTANBUL))
        self.assertEqual(result.quality["period_end_source"], "YEAR_PERIOD_FALLBACK")

    def test_missing_publication_time_is_not_invented(self) -> None:
        result = parse_kap_financial_report_html("Yıl 2026 Periyot 6 Aylık Bildirim Ekleri Finansal Rapor")
        self.assertIsNone(result.published_at)
        self.assertFalse(result.quality["exact_publication_timestamp"])
        self.assertIn("published_at", result.quality["missing"])


if __name__ == "__main__":
    unittest.main()

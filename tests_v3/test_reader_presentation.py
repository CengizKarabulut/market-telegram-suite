import unittest

from market_core.reader_presentation import format_reader_telegram


class ReaderPresentationTests(unittest.TestCase):
    def test_reader_view_hides_internal_scanner_and_indicator_names(self) -> None:
        report = {
            "symbol": "TEST",
            "interval_label": "günlük",
            "price": 21.0,
            "change_pct": -1.25,
            "reader_view": {
                "available": True,
                "headline": "Hisse zayıf bölgede; dönüş teyidi henüz yok.",
                "overview": "Ana fiyat yapısı baskının sürdüğünü gösteriyor.",
                "momentum": "Kısa vadeli alım isteği zayıf.",
                "participation": "Hacim düşük; güçlü satış dalgası görünmüyor ancak alıcı ilgisi de sınırlı.",
                "screening": "Daha önce olumlu teknik eşleşmeler görülmüş, ancak bunlar güncel teyit değil.",
                "levels": "Yukarıda 21.30 ilk toparlanma eşiği; aşağıda 20.80 tutunma alanı.",
                "what_changed": "Kısa vadeli ivme önceki seansa göre zayıfladı.",
                "conclusion": "21.30 geri alınmadan kalıcı güçlenme teyidi yok.",
            },
            # Canonical/internal blocks deliberately contain jargon. Reader output
            # must not leak them just because they exist in the report contract.
            "scanner_evidence": [{"scanner_code": "S-M-V-1", "source": "taramabot"}],
            "technical_sections": {"trend": {"interpretation": "EMA5/8/13"}},
            "ma_support_resistance": [{"ma_list": ["KAMA89", "WMA100"]}],
        }
        text = format_reader_telegram(report)
        lowered = text.lower()
        self.assertNotIn("taramabot", lowered)
        self.assertNotIn("s-m-v-1", lowered)
        self.assertNotIn("ema5", lowered)
        self.assertNotIn("kama89", lowered)
        self.assertNotIn("wma100", lowered)
        self.assertIn("Analist Görüşü", text)
        self.assertIn("21,30 ilk toparlanma eşiği", text)
        self.assertIn("Fiyat: 21,00 · Değişim: -1,25%", text)

    def test_reader_output_is_one_cohesive_paragraph(self) -> None:
        report = {
            "symbol": "TEST",
            "interval_label": "günlük",
            "price": 10.0,
            "change_pct": 0.5,
            "reader_view": {
                "available": True,
                "headline": "Toparlanma işaretleri var, ancak teyit gerekiyor.",
                "overview": "Fiyat yapısı henüz tam dönüş göstermiyor.",
                "momentum": "Kısa vadeli alım isteği toparlanıyor.",
                "participation": "Hacim normal aralıkta.",
                "screening": "Ek teknik koşullar olumluya dönüyor.",
                "levels": "10.40 üzeri güçlenmeyi destekler.",
                "what_changed": "Son seansta ivme toparlandı.",
                "conclusion": "10.40 aşılmadan dönüş tamamlanmış sayılmaz.",
            },
        }
        text = format_reader_telegram(report)
        lines = [line for line in text.splitlines() if line.strip()]
        self.assertEqual(len(lines), 3)
        paragraph = lines[-1]
        self.assertIn("Toparlanma işaretleri", paragraph)
        self.assertIn("Kısa vadeli alım isteği", paragraph)
        self.assertIn("10,40 aşılmadan", paragraph)
        self.assertNotIn("Genel görünüm:", text)
        self.assertNotIn("Sonuç:", text)
        self.assertNotIn("RSI:", text)
        self.assertNotIn("MACD", text)

    def test_reader_does_not_repeat_momentum_and_volume_change(self) -> None:
        report = {
            "symbol": "TEST",
            "interval_label": "günlük",
            "price": 21.0,
            "change_pct": -3.76,
            "reader_view": {
                "available": True,
                "headline": "Hisse zayıf bölgede.",
                "overview": "Ana baskı sürüyor.",
                "momentum": "Alım isteği zayıf ve son seansta ivme biraz daha bozuldu.",
                "participation": "Fiyat geriliyor ancak hacim zayıf (0.60x).",
                "screening": "Ek teknik koşullar güncel teyit vermiyor.",
                "what_changed": (
                    "Kısa vadeli ivme önceki seansa göre zayıfladı. "
                    "Hacim katılımı da değişti ve son değer normalin yaklaşık 0.60 katında."
                ),
                "levels": "Yukarıda 21.24 ilk toparlanma eşiği.",
                "conclusion": "21.24 geri alınmadan kalıcı güçlenme teyidi yok.",
            },
        }
        text = format_reader_telegram(report)
        paragraph = [line for line in text.splitlines() if line.strip()][-1]
        self.assertNotIn("önceki seansa göre zayıfladı", paragraph)
        self.assertNotIn("Hacim katılımı da değişti", paragraph)
        self.assertIn("0,60x", paragraph)
        self.assertIn("21,24", paragraph)
        self.assertIn("Değişim: -3,76%", text)

    def test_reader_keeps_non_redundant_structural_change(self) -> None:
        report = {
            "symbol": "TEST",
            "interval_label": "günlük",
            "price": 15.0,
            "change_pct": 2.0,
            "reader_view": {
                "available": True,
                "headline": "Toparlanma denemesi var.",
                "overview": "Fiyat yapısı geçiş bölgesinde.",
                "momentum": "Kısa vadeli alım isteği toparlanıyor.",
                "participation": "Hacim normal aralıkta.",
                "screening": "Ek teknik koşullar yön teyidi vermiyor.",
                "what_changed": "Fiyat yapısında olumlu bir kırılma oluştu.",
                "levels": "15.40 ilk önemli eşik.",
                "conclusion": "15.40 üzerinde kalıcılık görünümü güçlendirir.",
            },
        }
        text = format_reader_telegram(report)
        self.assertIn("Fiyat yapısında olumlu bir kırılma oluştu.", text)


if __name__ == "__main__":
    unittest.main()

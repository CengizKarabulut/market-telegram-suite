from src.research_v2 import _sanitize_profile_financials, _sanitize_valuation


def test_sanitize_valuation_removes_negative_peer_sentinels_and_aligns_yield() -> None:
    valuation = {
        "metrics": {
            "pe": {"value": 20.0, "percentile": 50.0},
            "p_fcf": {"value": 10.0, "percentile": None},
            "earnings_yield": {"value": 99.0, "percentile": None},
            "fcf_yield": {"value": 88.0, "percentile": None},
        },
        "peer_analysis": {
            "peers": [
                {"symbol": "AAA", "pe": -15.0, "pb": 2.0, "ev_ebitda": None, "ev_sales": -100.0},
                {"symbol": "BBB", "pe": 12.0, "pb": 1.5, "ev_ebitda": 8.0, "ev_sales": 2.0},
            ]
        },
    }

    result = _sanitize_valuation(valuation)

    assert result["metrics"]["earnings_yield"]["value"] == 5.0
    assert result["metrics"]["fcf_yield"]["value"] == 10.0
    assert result["peer_analysis"]["peers"][0]["pe"] is None
    assert result["peer_analysis"]["peers"][0]["ev_sales"] is None
    assert result["peer_analysis"]["peers"][1]["ev_ebitda"] == 8.0


def test_gyo_extreme_fair_value_margins_are_kept_raw_but_not_presented_as_normal_margin() -> None:
    financial = {
        "metrics": {
            "gross_margin": 95.0,
            "operating_margin": 1700.0,
            "operating_margin_quarterly": 26000.0,
            "net_margin": 4800.0,
            "net_margin_quarterly": 18000.0,
        },
        "ratio_groups": (
            {
                "name": "Kârlılık Oranları",
                "rows": (
                    {"key": "operating_margin", "label": "Esas Faaliyet Kâr Marjı", "unit": "%", "value": 1700.0},
                    {"key": "net_margin", "label": "Net Kâr Marjı", "unit": "%", "value": 4800.0},
                ),
            },
        ),
        "ratio_note": "Temel not.",
    }

    result = _sanitize_profile_financials(financial, "GYO")

    assert result["metrics"]["gross_margin"] == 95.0
    assert result["metrics"]["operating_margin"] is None
    assert result["metrics"]["net_margin"] is None
    assert result["non_comparable_metrics"]["operating_margin"] == 1700.0
    assert result["ratio_groups"][0]["rows"][0]["value"] is None
    assert "ham değer JSON'da korunur" in result["ratio_note"]

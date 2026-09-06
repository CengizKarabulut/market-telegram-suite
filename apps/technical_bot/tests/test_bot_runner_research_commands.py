"""Command-surface tests for modern technical/fundamental/research routing."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from src import bot_runner_fundamental as runner


def _command(name: str, *args: str):
    return SimpleNamespace(name=name, args=list(args), chat_id=12345)


def test_rapor_routes_to_modern_technical_bundle(tmp_path: Path) -> None:
    report = SimpleNamespace(symbol="ASELS")
    bundle = SimpleNamespace(
        moving_average_card=tmp_path / "ma.png",
        technical_chart=tmp_path / "teknik.png",
        report=report,
    )

    with (
        patch.object(runner.base, "REPORTS_DIR", tmp_path),
        patch.object(runner, "build_technical_bundle", return_value=bundle) as build,
        patch.object(runner, "send_technical_bundle") as send,
        patch.object(runner, "_BASE_EXECUTE") as legacy,
    ):
        runner.execute(_command("rapor", "ASELS"), {"1d", "4h"})

    build.assert_called_once_with("ASELS", tmp_path / "komut" / "ASELS" / "teknik")
    send.assert_called_once_with(bundle.moving_average_card, bundle.technical_chart, report)
    legacy.assert_not_called()


def test_rapor_rejects_legacy_interval_parameter() -> None:
    with (
        patch.object(runner.base, "reply") as reply,
        patch.object(runner, "build_technical_bundle") as build,
        patch.object(runner, "_BASE_EXECUTE") as legacy,
    ):
        runner.execute(_command("rapor", "ASELS", "4h"), {"1d", "4h"})

    build.assert_not_called()
    legacy.assert_not_called()
    assert "aralık parametresi almaz" in reply.call_args.args[1]
    assert "/rapor GARAN" in reply.call_args.args[1]


def test_teknik_alias_uses_same_modern_route() -> None:
    with patch.object(runner, "handle_technical") as handler:
        runner.execute(_command("teknik", "ZGYO"), {"1d"})
    handler.assert_called_once_with(12345, ["ZGYO"])


def test_analiz_routes_to_integrated_research_bundle(tmp_path: Path) -> None:
    report = SimpleNamespace(symbol="ZGYO")
    bundle = SimpleNamespace(
        summary_card=tmp_path / "summary.png",
        fundamental_card=tmp_path / "fundamental.png",
        financial_card=tmp_path / "financial.png",
        valuation_peer_card=tmp_path / "valuation.png",
        moving_average_card=tmp_path / "ma.png",
        technical_chart=tmp_path / "technical.png",
        report=report,
    )

    with (
        patch.object(runner.base, "REPORTS_DIR", tmp_path),
        patch.object(runner, "build_research_bundle", return_value=bundle) as build,
        patch.object(runner, "send_research_bundle") as send,
        patch.object(runner, "_BASE_EXECUTE") as legacy,
    ):
        runner.execute(_command("analiz", "ZGYO"), {"1d"})

    build.assert_called_once_with("ZGYO", tmp_path / "komut" / "ZGYO")
    send.assert_called_once_with(
        bundle.summary_card,
        bundle.fundamental_card,
        bundle.moving_average_card,
        bundle.technical_chart,
        report,
        financial_card=bundle.financial_card,
        valuation_peer_card=bundle.valuation_peer_card,
    )
    legacy.assert_not_called()


def test_temel_routes_to_fundamental_handler() -> None:
    with patch.object(runner, "handle_fundamental") as handler:
        runner.execute(_command("temel", "GARAN"), {"1d"})
    handler.assert_called_once_with(12345, ["GARAN"])


def test_existing_operational_commands_still_delegate_to_base_runner() -> None:
    operational = ("tara", "liste", "esik", "takip", "durum", "gecmis", "yardim")
    with patch.object(runner, "_BASE_EXECUTE") as legacy:
        for name in operational:
            runner.execute(_command(name), {"1d", "4h"})

    assert legacy.call_count == len(operational)
    assert [call.args[0].name for call in legacy.call_args_list] == list(operational)


def test_operational_command_handlers_route_inside_base_runner() -> None:
    base = runner.base
    intervals = {"1d", "4h"}
    with (
        patch.object(base, "dispatch_scan", return_value=(True, "Tarama başlatıldı")) as scan,
        patch.object(base, "handle_list") as listed,
        patch.object(base, "handle_settings") as settings,
        patch.object(base, "handle_watch") as watch,
        patch.object(base, "handle_status") as status,
        patch.object(base, "handle_history") as history,
        patch.object(base, "reply") as reply,
    ):
        base.execute(_command("tara"), intervals)
        base.execute(_command("liste"), intervals)
        base.execute(_command("esik", "rvol", "2.0"), intervals)
        base.execute(_command("takip", "ASELS"), intervals)
        base.execute(_command("durum"), intervals)
        base.execute(_command("gecmis"), intervals)
        base.execute(_command("yardim"), intervals)

    scan.assert_called_once_with("auto")
    listed.assert_called_once_with(12345)
    settings.assert_called_once_with(12345, ["rvol", "2.0"])
    watch.assert_called_once_with(12345, ["ASELS"], intervals)
    status.assert_called_once_with(12345)
    history.assert_called_once_with(12345, [])
    assert any("Kullanılabilir komutlar" in call.args[1] for call in reply.call_args_list)


def test_main_replaces_legacy_report_help_with_modern_surface() -> None:
    original_help = runner.base.HELP_TEXT
    original_execute = runner.base.execute
    legacy_line = "/rapor SEMBOL [aralık] — tek hisse teknik raporu (ör. /rapor THYAO 4h)"
    try:
        runner.base.HELP_TEXT = "Kullanılabilir komutlar:\n" + legacy_line + "\n/tara [aralık]"
        fake_main = Mock()
        with patch.object(runner.base, "main", fake_main):
            runner.main()

        assert legacy_line not in runner.base.HELP_TEXT
        assert "/rapor SEMBOL — modern teknik araştırma" in runner.base.HELP_TEXT
        assert "/teknik SEMBOL" in runner.base.HELP_TEXT
        assert "/temel SEMBOL" in runner.base.HELP_TEXT
        assert "/analiz SEMBOL" in runner.base.HELP_TEXT
        assert runner.base.execute is runner.execute
        fake_main.assert_called_once_with()
    finally:
        runner.base.HELP_TEXT = original_help
        runner.base.execute = original_execute

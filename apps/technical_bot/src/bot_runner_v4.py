from __future__ import annotations

import os

import requests
from src import bot_runner as base


V4_WORKFLOW_FILE = os.getenv("V4_WORKFLOW_FILE", "v4-equity-report.yml")
ORIGINAL_EXECUTE = base.execute
APP_HELP_TEXT = (
    base.HELP_TEXT.replace(
        "Kullanılabilir komutlar:\n",
        "Kullanılabilir komutlar:\n"
        "/analiz SEMBOL [aralık] — teknik + temel + sektör/eş şirket + KAP bütünleşik analist görüşü\n"
        "/v4 SEMBOL [aralık] — /analiz komutunun kısa adı\n",
        1,
    )
)


def dispatch_equity(symbol: str, interval: str) -> tuple[bool, str]:
    token = os.getenv("GITHUB_TOKEN", "").strip()
    repository = os.getenv("GITHUB_REPOSITORY", "").strip()
    if not token or not repository:
        return False, "Bütünleşik analiz başlatılamadı: GitHub kimlik bilgisi yok."

    response = requests.post(
        f"https://api.github.com/repos/{repository}/actions/workflows/{V4_WORKFLOW_FILE}/dispatches",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        json={
            "ref": os.getenv("GITHUB_REF_NAME", "main").strip() or "main",
            "inputs": {
                "symbol": symbol,
                "interval": interval,
                "telegram": "true",
            },
        },
        timeout=30,
    )
    if response.status_code == 204:
        return (
            True,
            f"{symbol} bütünleşik analizi başlatıldı ({interval}). Teknik, temel, sektör/eş şirket ve KAP verileri birlikte değerlendirilecek; sonuç hazır olduğunda bu gruba tek paragraf olarak gelecek.",
        )
    return (
        False,
        f"Bütünleşik analiz başlatılamadı: HTTP {response.status_code} — {response.text[:150]}",
    )


def execute(command, intervals: set[str]) -> None:
    if command.name in {"analiz", "v4"}:
        ticker, interval, error = base.validate_report_args(command.args, intervals)
        if error:
            example = "Örnek: /analiz THYAO 1d"
            base.reply(command.chat_id, f"{error}\n{example}")
            return
        assert ticker is not None
        _, message = dispatch_equity(ticker, interval)
        base.reply(command.chat_id, message)
        return
    ORIGINAL_EXECUTE(command, intervals)


def main() -> None:
    # Aynı Telegram getUpdates dinleyicisini kullanıyoruz; ikinci bir listener
    # açılmadığı için Telegram update çakışması oluşmaz.
    base.HELP_TEXT = APP_HELP_TEXT
    try:
        base.execute = execute
        base.main()
    finally:
        base.execute = ORIGINAL_EXECUTE


if __name__ == "__main__":
    base.resolve("1d")
    main()

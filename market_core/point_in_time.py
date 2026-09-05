from __future__ import annotations

from datetime import datetime
from typing import Iterable

from .fundamental_models import FinancialSnapshot, PointInTimeSelection


def select_financial_snapshot(
    snapshots: Iterable[FinancialSnapshot],
    *,
    symbol: str,
    as_of: datetime,
) -> PointInTimeSelection:
    """Return the latest snapshot that was actually public at ``as_of``.

    The resolver deliberately uses ``published_at`` as the availability gate.
    ``period_end`` is an accounting period marker and can never make a filing
    visible before publication. Restatements therefore enter history only from
    their own publication timestamp onward.
    """
    if as_of.tzinfo is None:
        raise ValueError("as_of timezone-aware olmalıdır.")

    normalized_symbol = symbol.strip().upper()
    if not normalized_symbol:
        raise ValueError("symbol boş olamaz.")

    matching = [
        item
        for item in snapshots
        if item.symbol.strip().upper() == normalized_symbol
    ]
    available = [item for item in matching if item.published_at <= as_of]
    future = [item for item in matching if item.published_at > as_of]

    if not available:
        return PointInTimeSelection(
            as_of=as_of,
            snapshot=None,
            available_count=0,
            excluded_future_count=len(future),
            reason="Bu as-of zamanı itibarıyla yayımlanmış finansal snapshot yok.",
        )

    selected = max(
        available,
        key=lambda item: (
            item.published_at,
            item.period_end,
            item.restatement_id or "",
        ),
    )
    return PointInTimeSelection(
        as_of=as_of,
        snapshot=selected,
        available_count=len(available),
        excluded_future_count=len(future),
    )

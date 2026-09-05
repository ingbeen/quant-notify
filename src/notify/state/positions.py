"""보유 종목 파일을 읽고 검증한다.

파일이 없거나 비어 있으면 빈 목록을 낸다. 보유 블록만 비우고 알림은 그대로 나간다.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# 파일 최상단의 목록 이름
_POSITIONS_KEY = "positions"


@dataclass(frozen=True)
class Position:
    """보유 종목 한 줄."""

    ticker: str
    quantity: int


def _build_position(raw: Any, order: int) -> Position:
    """보유 종목 한 줄을 만든다.

    Args:
        raw: 항목 하나의 원본 값.
        order: 파일에서의 순서. 오류 메시지에 쓴다.

    Returns:
        검증을 통과한 보유 종목.

    Raises:
        ValueError: 항목이 빠졌거나 값이 규격을 벗어날 때.
    """
    where = f"{_POSITIONS_KEY} {order}번째 항목"

    if not isinstance(raw, dict):
        raise ValueError(f"{where} 이 형식에 맞지 않습니다. [[{_POSITIONS_KEY}]] 블록으로 적으세요.")

    ticker = raw.get("ticker")
    if not isinstance(ticker, str) or not ticker.strip():
        raise ValueError(f"{where} 의 'ticker' 가 비어 있습니다. 종목 코드를 적으세요.")

    if "quantity" not in raw:
        raise ValueError(f"[{ticker}] 'quantity' 항목이 없습니다. 보유 수량을 적으세요.")

    quantity = raw["quantity"]
    if isinstance(quantity, bool) or not isinstance(quantity, int):
        raise ValueError(f"[{ticker}] 'quantity' 는 정수여야 합니다. 지금 값: {quantity!r}")
    if quantity <= 0:
        raise ValueError(f"[{ticker}] 'quantity' 는 1 이상이어야 합니다. 보유하지 않는 종목은 줄을 지우세요.")

    return Position(ticker=ticker, quantity=quantity)


def load_positions(path: Path) -> list[Position]:
    """보유 종목 파일을 읽는다.

    Args:
        path: 보유 종목 파일 경로.

    Returns:
        보유 종목 목록. 파일이 없거나 비어 있으면 빈 목록.

    Raises:
        ValueError: 형식이 깨졌거나 값이 규격을 벗어날 때.
    """
    if not path.is_file():
        return []

    try:
        parsed = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"보유 종목 파일의 형식이 깨졌습니다: {path}. {exc}") from exc

    raw_positions = parsed.get(_POSITIONS_KEY)
    if raw_positions is None:
        return []
    if not isinstance(raw_positions, list):
        raise ValueError(f"'{_POSITIONS_KEY}' 는 목록이어야 합니다: {path}.")

    positions = [_build_position(raw, order) for order, raw in enumerate(raw_positions, start=1)]

    seen: set[str] = set()
    for position in positions:
        if position.ticker in seen:
            raise ValueError(f"[{position.ticker}] 이 두 번 나옵니다. 한 종목은 한 줄로 적으세요.")
        seen.add(position.ticker)

    return positions

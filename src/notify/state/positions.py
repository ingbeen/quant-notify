"""보유 종목 파일을 읽고 검증한다. 파일이 없거나 비면 빈 목록을 낸다 (`docs/DESIGN.md` §5.2)."""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# 파일의 키
_POSITIONS_KEY = "positions"
_TICKER_KEY = "ticker"
_QUANTITY_KEY = "quantity"
_ENTRY_KEYS = frozenset({_TICKER_KEY, _QUANTITY_KEY})

# 미국 상장 종목 코드. 비중은 달러 평가액으로, 종가는 미국 거래일로 집으므로 다른 시장 종목은 받지 않는다.
# 클래스 주식은 yfinance 표기(`BRK-B`)로 적는다
_US_TICKER = re.compile(r"[A-Z][A-Z0-9-]*")


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
        ValueError: 항목이 빠졌거나, 모르는 키가 있거나, 값이 규격을 벗어날 때.
    """
    where = f"{_POSITIONS_KEY} {order}번째 항목"

    if not isinstance(raw, dict):
        raise ValueError(f"{where} 이 형식에 맞지 않습니다. [[{_POSITIONS_KEY}]] 블록으로 적으세요.")

    unknown = sorted(set(raw) - _ENTRY_KEYS)
    if unknown:
        raise ValueError(f"{where} 에 모르는 키가 있습니다: {', '.join(unknown)}. '{_TICKER_KEY}' 와 '{_QUANTITY_KEY}' 만 적으세요.")

    ticker = raw.get(_TICKER_KEY)
    if not isinstance(ticker, str) or not ticker.strip():
        raise ValueError(f"{where} 의 '{_TICKER_KEY}' 가 비어 있습니다. 종목 코드를 적으세요.")
    if not _US_TICKER.fullmatch(ticker):
        raise ValueError(
            f"{where} 의 '{_TICKER_KEY}' {ticker!r} 는 미국 상장 종목 코드가 아닙니다. "
            "대문자 · 숫자 · 하이픈으로 적으세요 (예: QLD, BRK-B). 다른 시장 종목은 받지 않습니다."
        )

    if _QUANTITY_KEY not in raw:
        raise ValueError(f"[{ticker}] '{_QUANTITY_KEY}' 항목이 없습니다. 보유 수량을 적으세요.")

    quantity = raw[_QUANTITY_KEY]
    if isinstance(quantity, bool) or not isinstance(quantity, int):
        raise ValueError(f"[{ticker}] '{_QUANTITY_KEY}' 는 정수여야 합니다. 지금 값: {quantity!r}")
    if quantity <= 0:
        raise ValueError(f"[{ticker}] '{_QUANTITY_KEY}' 는 1 이상이어야 합니다. 보유하지 않는 종목은 줄을 지우세요.")

    return Position(ticker=ticker, quantity=quantity)


def load_positions(path: Path) -> list[Position]:
    """보유 종목 파일을 읽는다.

    Args:
        path: 보유 종목 파일 경로.

    Returns:
        보유 종목 목록. 파일이 없거나 비어 있으면 빈 목록.

    Raises:
        ValueError: 형식이 깨졌거나, 모르는 표가 있거나, 값이 규격을 벗어날 때.
    """
    if not path.is_file():
        return []

    try:
        parsed = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"보유 종목 파일의 형식이 깨졌습니다: {path}. {exc}") from exc

    unknown = sorted(set(parsed) - {_POSITIONS_KEY})
    if unknown:
        raise ValueError(f"보유 종목 파일에 모르는 표가 있습니다: {', '.join(unknown)}. [[{_POSITIONS_KEY}]] 로 적으세요.")

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

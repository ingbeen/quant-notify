"""순위 등락률 파일을 읽고 검증한다.

사람이 손으로 고치는 파일이라 오기입력이 들어온다. 잘못된 값이 그대로 판정에
들어가면 임계가 어긋난 채로 알림이 정상처럼 보이므로, 읽는 자리에서 막는다.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from notify.common_constants import MAX_DAILY_CHANGE_RATE

# 종목마다 있어야 하는 항목
_RATE_FIELDS = ("surge_1st", "surge_20th", "plunge_1st", "plunge_20th")
_DATE_FIELDS = ("as_of", "data_from", "data_to")


@dataclass(frozen=True)
class RankThresholds:
    """한 종목의 순위 등락률.

    값은 비율이다 (0.0610 = +6.10%). 폭등과 폭락은 순위를 따로 매기므로
    두 값의 크기가 서로 다르다.
    """

    surge_1st: float
    surge_20th: float
    plunge_1st: float
    plunge_20th: float


@dataclass(frozen=True)
class RankEntry:
    """순위 등락률과 그 값이 무엇으로 언제 정해졌는지."""

    thresholds: RankThresholds
    as_of: date
    data_from: date
    data_to: date


def _require_rate(raw: dict[str, Any], field: str, symbol: str) -> float:
    """등락률 항목 하나를 꺼내 검증한다.

    Args:
        raw: 종목 하나의 원본 매핑.
        field: 항목 이름.
        symbol: 종목 식별자. 오류 메시지에 쓴다.

    Returns:
        검증을 통과한 등락률. 비율.

    Raises:
        ValueError: 항목이 없거나, 숫자가 아니거나, 하루 등락률로 있을 수 없는 크기일 때.
    """
    if field not in raw:
        raise ValueError(f"[{symbol}] '{field}' 항목이 없습니다. 순위 등락률 파일에 추가하세요.")

    value = raw[field]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"[{symbol}] '{field}' 는 숫자여야 합니다. 지금 값: {value!r}")

    rate = float(value)
    if abs(rate) >= MAX_DAILY_CHANGE_RATE:
        raise ValueError(
            f"[{symbol}] '{field}' 값 {rate} 이 하루 등락률로 너무 큽니다. "
            f"퍼센트가 아니라 비율로 적으세요 (+6.10% 는 0.0610)."
        )
    return rate


def _require_date(raw: dict[str, Any], field: str, symbol: str) -> date:
    """날짜 항목 하나를 꺼내 검증한다.

    Args:
        raw: 종목 하나의 원본 매핑.
        field: 항목 이름.
        symbol: 종목 식별자. 오류 메시지에 쓴다.

    Returns:
        날짜.

    Raises:
        ValueError: 항목이 없거나 날짜가 아닐 때.
    """
    if field not in raw:
        raise ValueError(f"[{symbol}] '{field}' 항목이 없습니다. 순위 등락률 파일에 추가하세요.")

    value = raw[field]
    if not isinstance(value, date):
        raise ValueError(f"[{symbol}] '{field}' 는 날짜여야 합니다 (예: 2026-08-26). 지금 값: {value!r}")
    return value


def _build_thresholds(raw: dict[str, Any], symbol: str) -> RankThresholds:
    """종목 하나의 순위 등락률을 만든다.

    Args:
        raw: 종목 하나의 원본 매핑.
        symbol: 종목 식별자.

    Returns:
        검증을 통과한 순위 등락률.

    Raises:
        ValueError: 부호가 방향과 어긋나거나 1위가 20위보다 덜 극단적일 때.
    """
    rates = {field: _require_rate(raw, field, symbol) for field in _RATE_FIELDS}

    for field in ("surge_1st", "surge_20th"):
        if rates[field] <= 0:
            raise ValueError(f"[{symbol}] '{field}' 는 양수여야 합니다. 폭등 값에 음수가 들어왔습니다: {rates[field]}")
    for field in ("plunge_1st", "plunge_20th"):
        if rates[field] >= 0:
            raise ValueError(f"[{symbol}] '{field}' 는 음수여야 합니다. 폭락 값에 양수가 들어왔습니다: {rates[field]}")

    if rates["surge_1st"] < rates["surge_20th"]:
        raise ValueError(
            f"[{symbol}] 폭등 1위({rates['surge_1st']})가 20위({rates['surge_20th']})보다 작습니다. "
            f"순위가 뒤바뀌었는지 확인하세요."
        )
    if rates["plunge_1st"] > rates["plunge_20th"]:
        raise ValueError(
            f"[{symbol}] 폭락 1위({rates['plunge_1st']})가 20위({rates['plunge_20th']})보다 큽니다. "
            f"순위가 뒤바뀌었는지 확인하세요."
        )

    return RankThresholds(**rates)


def load_reverse_rank(path: Path) -> dict[str, RankEntry]:
    """순위 등락률 파일을 읽는다.

    파일이 없으면 예외를 낸다. 신호 가격을 만들 재료가 없어 판정 자체가
    불가능하고, 조용히 넘어가면 신호가 없어서 조용한 것과 구분되지 않는다.

    Args:
        path: 순위 등락률 파일 경로.

    Returns:
        종목 식별자를 키로 하는 순위 등락률.

    Raises:
        ValueError: 파일이 없거나, 형식이 깨졌거나, 종목이 하나도 없거나, 값이 규격을 벗어날 때.
    """
    if not path.is_file():
        raise ValueError(f"순위 등락률 파일이 없습니다: {path}. 파일을 만들고 종목별 순위 값을 적으세요.")

    try:
        parsed = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"순위 등락률 파일의 형식이 깨졌습니다: {path}. {exc}") from exc

    if not parsed:
        raise ValueError(f"순위 등락률 파일에 종목이 하나도 없습니다: {path}.")

    entries: dict[str, RankEntry] = {}
    for symbol, raw in parsed.items():
        if not isinstance(raw, dict):
            raise ValueError(f"[{symbol}] 은 종목 블록이어야 합니다 (예: [kodex200]).")
        dates = {field: _require_date(raw, field, symbol) for field in _DATE_FIELDS}
        entries[symbol] = RankEntry(thresholds=_build_thresholds(raw, symbol), **dates)

    return entries

"""순위 등락률 파일을 읽고 검증한다.

사람이 손으로 고치는 파일이라 오기입력이 들어온다. 잘못된 값이 그대로 판정에
들어가면 임계가 어긋난 채로 알림이 정상처럼 보이므로, 읽는 자리에서 막는다.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

from notify.common_constants import MAX_DAILY_CHANGE_RATE, TZ_KST

# 종목마다 있어야 하는 항목
_RATE_FIELDS = ("surge_1st", "surge_20th", "plunge_1st", "plunge_20th")
_DATE_FIELDS = ("data_from", "data_to")


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
    """순위 등락률과 그 값이 어느 구간으로 매겨졌는지.

    **`data_to` 가 기준일을 겸한다.** 판정이 묻는 것은 「이 날의 등락률이 줄 세우기에
    들어갔나」이고, 그 답은 계산에 넣은 마지막 날 하나로 난다. 「값을 계산한 날」을
    따로 두면 그것과 비교하게 되어, 계산일이 데이터 끝보다 늦을 때 그 사이의 도달일을
    **이미 반영된 것으로 오판해 놓친다.**
    """

    thresholds: RankThresholds
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
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"[{symbol}] '{field}' 는 숫자여야 합니다. 지금 값: {value!r}")

    rate = float(value)
    if abs(rate) >= MAX_DAILY_CHANGE_RATE:
        raise ValueError(f"[{symbol}] '{field}' 값 {rate} 이 하루 등락률로 너무 큽니다. " f"퍼센트가 아니라 비율로 적으세요 (+6.10% 는 0.0610).")
    return rate


def _require_date(raw: dict[str, Any], field: str, symbol: str) -> date:
    """날짜 항목 하나를 꺼내 검증한다.

    **날짜시각을 날짜로 받지 않는다.** TOML 은 `2026-08-26T00:00:00` 도 유효한 값으로
    읽는데 `datetime` 은 `date` 의 하위형이라 형 검사를 그냥 통과한다. 그대로 넘기면
    낡음 판정이 `date` 와 견주다 **필드 이름이 없는 TypeError** 로 멈춘다.

    Args:
        raw: 종목 하나의 원본 매핑.
        field: 항목 이름.
        symbol: 종목 식별자. 오류 메시지에 쓴다.

    Returns:
        날짜.

    Raises:
        ValueError: 항목이 없거나, 날짜가 아니거나, 시각이 붙어 있을 때.
    """
    if field not in raw:
        raise ValueError(f"[{symbol}] '{field}' 항목이 없습니다. 순위 등락률 파일에 추가하세요.")

    value = raw[field]
    if not isinstance(value, date) or isinstance(value, datetime):
        raise ValueError(f"[{symbol}] '{field}' 는 날짜여야 합니다 (예: 2026-08-26). 시각은 붙이지 않습니다. 지금 값: {value!r}")
    return value


def _check_period(data_from: date, data_to: date, symbol: str) -> None:
    """데이터 구간이 말이 되는지 본다.

    **`data_to` 가 미래면 낡음 검사가 통째로 꺼진다.** 검사할 날이 하나도 남지 않는데
    알림은 정상으로 보이므로, 값이 들어오는 자리에서 막는다 (docs/DESIGN.md 5.2 절).
    **여기서 막으면 알림 넷 전부가 덮인다** — 주간 알림도 이 파일을 읽는다.

    **오늘은 KST 로 센다.** 워크플로는 UTC 로 도는데 아침 알림은 UTC 로 전날이라,
    현지 날짜로 재면 정상인 `data_to` 가 미래로 읽힌다 (docs/DESIGN.md 7.3 절).

    **「마지막 확정 종가일보다 뒤인가」로 재지 않는다.** 장중 판정에서 그 값은 전일이라,
    사용자가 마감 뒤 재계산해 오늘 날짜로 올린 **정상 파일**이 걸린다.

    Args:
        data_from: 데이터 구간의 시작.
        data_to: 줄 세우기에 넣은 마지막 날.
        symbol: 종목 식별자. 오류 메시지에 쓴다.

    Raises:
        ValueError: 시작이 끝보다 뒤이거나, 끝이 미래일 때.
    """
    if data_from > data_to:
        raise ValueError(f"[{symbol}] 'data_from' ({data_from}) 이 'data_to' ({data_to}) 보다 뒤입니다.")

    today = datetime.now(TZ_KST).date()
    if data_to > today:
        raise ValueError(
            f"[{symbol}] 'data_to' ({data_to}) 가 미래입니다 (오늘 {today}). " f"그대로 두면 순위 낡음 검사가 꺼진 채 알림만 정상으로 보입니다."
        )


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
            f"[{symbol}] 폭등 1위({rates['surge_1st']})가 20위({rates['surge_20th']})보다 작습니다. " f"순위가 뒤바뀌었는지 확인하세요."
        )
    if rates["plunge_1st"] > rates["plunge_20th"]:
        raise ValueError(
            f"[{symbol}] 폭락 1위({rates['plunge_1st']})가 20위({rates['plunge_20th']})보다 큽니다. " f"순위가 뒤바뀌었는지 확인하세요."
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
            **데이터 구간 검증도 여기서 한다** — 알림마다 따로 재면 어느 알림은 빠진다.
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
        _check_period(dates["data_from"], dates["data_to"], symbol)
        entries[symbol] = RankEntry(thresholds=_build_thresholds(raw, symbol), **dates)

    return entries

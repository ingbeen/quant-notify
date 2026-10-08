"""원달러 평균대비를 계산하고 주간 알림 문구를 만든다.

평균대비는 부호가 곧 의미다 — 음수면 평균보다 싸다. 판정 어휘는 붙이지 않는다 (`docs/DESIGN.md` §4.3).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime

import pandas as pd

from notify.alerts.formatting import bold, format_day, format_krw, format_rate, format_sent_at
from notify.alerts.health import HealthLine


@dataclass(frozen=True)
class WindowLine:
    """창 하나의 평균과 평균대비."""

    years: int
    mean_price: float
    deviation_rate: float


def years_before(day: date, years: int) -> date:
    """몇 년 전 같은 날을 낸다. 그 해에 같은 날이 없으면(2/29) 그 달의 마지막 날이다.

    Args:
        day: 기준일.
        years: 몇 년 전인지.

    Returns:
        그 날짜.
    """
    return (pd.Timestamp(day) - pd.DateOffset(years=years)).date()


def mean_deviation(current: float, window_closes: pd.Series) -> float:
    """평균대비를 낸다.

    Args:
        current: 현재 값.
        window_closes: 비교할 창의 종가 계열.

    Returns:
        평균대비. 비율 (-0.053 = 평균보다 5.3% 싸다).

    Raises:
        ValueError: 창의 평균이 0 일 때.
    """
    mean = float(window_closes.mean())
    if mean == 0:
        raise ValueError("창의 평균이 0 이라 평균대비를 낼 수 없습니다.")

    return current / mean - 1


def window_slice(closes: pd.Series, end: date, years: int) -> pd.Series:
    """비교할 창을 자른다. **양끝을 포함한다** (`docs/research/데이터소스_실측.md` §1.4).

    Args:
        closes: 날짜를 인덱스로 갖는 종가 계열.
        end: 창의 끝 날짜.
        years: 창 길이 (년).

    Returns:
        잘라낸 계열.

    Raises:
        ValueError: 자료가 창 시작일보다 늦게 시작할 때. 짧은 자료로 긴 창의 평균을 내지 않는다.
    """
    start = years_before(end, years)
    if closes.empty or closes.index[0] > start:
        first = closes.index[0] if not closes.empty else "없음"
        raise ValueError(f"{start} ~ {end} 창을 채울 환율 자료가 없습니다 (첫 자료 {first}). 조회 기간을 확인하세요.")

    return closes[(closes.index >= start) & (closes.index <= end)]


def window_line(closes: pd.Series, years: int) -> WindowLine:
    """마지막 값을 현재로 보고, 그 날까지 몇 년 창의 평균과 평균대비를 낸다.

    Args:
        closes: 날짜를 인덱스로 갖는 종가 계열.
        years: 창 길이 (년).

    Returns:
        창 하나의 평균과 평균대비.

    Raises:
        ValueError: 자료가 창 시작일보다 늦게 시작할 때.
    """
    window = window_slice(closes, closes.index[-1], years)
    return WindowLine(
        years=years,
        mean_price=float(window.mean()),
        deviation_rate=mean_deviation(float(closes.iloc[-1]), window),
    )


def render(
    sent_at: datetime,
    current: float,
    as_of: date,
    windows: Sequence[WindowLine],
    health: HealthLine,
) -> str:
    """원달러 주간 알림 문구를 만든다.

    Args:
        sent_at: 발송 시각.
        current: 현재 환율.
        as_of: 그 환율의 기준일.
        windows: 창별 평균과 평균대비.
        health: 점검 줄.

    Returns:
        보낼 문구.
    """
    rows = [
        f"{bold('주간')} · {format_sent_at(sent_at)}",
        "",
        bold(f"원달러 {format_krw(current, 2)}"),
        f"{format_day(as_of)} 기준",
        "",
        *(
            f"{line.years}년 평균 {format_krw(line.mean_price)} 대비 {format_rate(line.deviation_rate, 1)}"
            for line in windows
        ),
        "",
        bold("점검"),
        f"{health.label} {health.period}",
        health.detail,
    ]

    return "\n".join(rows)

"""원달러 평균대비를 계산한다.

평균대비는 부호가 곧 의미다 — 음수면 평균보다 싸다. 판정 어휘를 붙이지 않고
숫자만 낸다.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime

import pandas as pd

from notify.alerts.formatting import bold, format_day, format_krw, format_rate
from notify.alerts.health import HealthLine


def mean_deviation(current: float, window_closes: pd.Series) -> float:
    """평균대비를 낸다.

    Args:
        current: 현재 값.
        window_closes: 비교할 창의 종가 계열.

    Returns:
        평균대비. 비율 (-0.053 = 평균보다 5.3% 싸다).

    Raises:
        ValueError: 창이 비었거나 평균이 0 일 때.
    """
    if window_closes.empty:
        raise ValueError("비교할 창이 비어 있어 평균대비를 낼 수 없습니다.")

    mean = float(window_closes.mean())
    if mean == 0:
        raise ValueError("창의 평균이 0 이라 평균대비를 낼 수 없습니다.")

    return current / mean - 1


@dataclass(frozen=True)
class WindowLine:
    """창 하나의 평균과 평균대비."""

    years: int
    mean_price: float
    deviation_rate: float


def window_slice(closes: pd.Series, end: date, years: int) -> pd.Series:
    """비교할 창을 자른다.

    **양끝을 포함한다.** 시작일을 빼면 거래일이 하나 줄고 평균이 어긋난다.

    Args:
        closes: 날짜를 인덱스로 갖는 종가 계열.
        end: 창의 끝 날짜.
        years: 창 길이 (년).

    Returns:
        잘라낸 계열.

    Raises:
        ValueError: 창에 거래일이 하나도 없을 때.
    """
    start = date(end.year - years, end.month, end.day)
    window = closes[(closes.index >= start) & (closes.index <= end)]
    if window.empty:
        raise ValueError(f"{start} ~ {end} 구간에 환율 자료가 없습니다.")
    return window


def _window_rows(windows: Sequence[WindowLine]) -> list[str]:
    """창 줄을 만든다.

    Args:
        windows: 창별 평균과 평균대비.

    Returns:
        줄 목록.
    """
    return [
        f"{line.years}년 평균 {format_krw(line.mean_price)} 대비 {format_rate(line.deviation_rate, 1)}" for line in windows
    ]


def render(
    sent_at: datetime,
    current: float,
    as_of: date,
    windows: Sequence[WindowLine],
    health: HealthLine,
) -> str:
    """원달러 주간 알림 문구를 만든다.

    판정 어휘를 붙이지 않는다. 이 지표에는 예측력이 없다는 것이 측정 결과여서,
    「쌈」·「비쌈」 같은 말을 붙이면 숫자가 행동 지시로 바뀐다.

    Args:
        sent_at: 발송 시각.
        current: 현재 환율.
        as_of: 그 환율의 기준일.
        windows: 창별 평균과 평균대비.
        health: 점검 항목.

    Returns:
        보낼 문구.

    Raises:
        ValueError: 창이 하나도 없을 때.
    """
    if not windows:
        raise ValueError("비교할 창이 없어 알림을 만들 수 없습니다.")

    rows = [
        f"{bold('주간')} · {format_day(sent_at.date())} {sent_at:%H:%M}",
        "",
        bold(f"원달러 {format_krw(current, 2)}"),
        f"{format_day(as_of)} 기준",
        "",
        *_window_rows(windows),
    ]
    rows += ["", bold("점검"), f"{health.label} {health.period}", health.detail]

    return "\n".join(rows)

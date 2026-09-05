"""원달러 평균대비와 지난주 역방향 요약을 계산한다.

평균대비는 부호가 곧 의미다 — 음수면 평균보다 싸다. 판정 어휘를 붙이지 않고
숫자만 낸다.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime

import pandas as pd

from notify.alerts.formatting import format_day, format_krw, format_rate, pad_end, pad_start
from notify.alerts.health import HealthLine


@dataclass(frozen=True)
class WeeklyExtreme:
    """한 주의 한쪽 끝."""

    change_rate: float
    on: date


@dataclass(frozen=True)
class WeeklyExtremes:
    """한 주의 양끝. 가장 오른 날과 가장 내린 날을 함께 낸다."""

    highest: WeeklyExtreme
    lowest: WeeklyExtreme


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


def _extreme_at(daily_changes: pd.Series, label: object) -> WeeklyExtreme:
    """지정한 날의 등락률을 한쪽 끝으로 만든다.

    Args:
        daily_changes: 일간 등락률 계열. 날짜를 인덱스로 갖는다.
        label: 인덱스 값.

    Returns:
        그 날의 등락률과 날짜.

    Raises:
        RuntimeError: 인덱스가 날짜가 아닐 때.
    """
    if not isinstance(label, date):
        raise RuntimeError(f"내부 불변조건 위반: 등락률 인덱스가 날짜가 아닙니다: {label!r}")

    return WeeklyExtreme(change_rate=float(daily_changes[label]), on=label)


def weekly_extremes(daily_changes: pd.Series) -> WeeklyExtremes:
    """한 주의 양끝을 낸다.

    가장 오른 날과 가장 내린 날을 각각 낸다. 절대값 하나로 합치지 않는다 —
    순위가 방향별로 매겨지므로 양쪽을 함께 내야 폭등·폭락 줄과 짝이 맞는다.

    Args:
        daily_changes: 일간 등락률 계열. 날짜를 인덱스로 갖는다. 비율.

    Returns:
        가장 오른 날과 가장 내린 날.

    Raises:
        ValueError: 거래일이 하나도 없을 때.
    """
    if daily_changes.empty:
        raise ValueError("지난주 거래일이 없어 양끝을 낼 수 없습니다.")

    return WeeklyExtremes(
        highest=_extreme_at(daily_changes, daily_changes.idxmax()),
        lowest=_extreme_at(daily_changes, daily_changes.idxmin()),
    )


@dataclass(frozen=True)
class WindowLine:
    """창 하나의 평균과 평균대비."""

    years: int
    mean_price: float
    deviation_rate: float


@dataclass(frozen=True)
class ReverseLine:
    """역방향 요약 한 방향.

    Attributes:
        direction: 폭등 또는 폭락.
        rate_1st: 1위 등락률.
        rate_20th: 20위 등락률.
        extreme_label: 지난주 값이 무엇인지 (최고 · 최저 · 신호).
        extreme_rate: 지난주 값.
        extreme_on: 그 값이 나온 날.
    """

    direction: str
    rate_1st: float
    rate_20th: float
    extreme_label: str
    extreme_rate: float
    extreme_on: date


@dataclass(frozen=True)
class ReverseBlock:
    """종목 하나의 역방향 요약."""

    symbol: str
    lines: Sequence[ReverseLine]


# 창 라벨과 값이 차지하는 칸
_WINDOW_LABEL_COLUMN = 6
_WINDOW_MEAN_COLUMN = 9
_WINDOW_RATE_COLUMN = 9

# 역방향 줄에서 각 조각이 차지하는 칸
_DIRECTION_COLUMN = 8
_FIRST_RATE_COLUMN = 7
_TWENTIETH_RATE_COLUMN = 6
_EXTREME_LABEL_COLUMN = 11
_EXTREME_RATE_COLUMN = 6


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
        pad_start(f"{line.years}년", _WINDOW_LABEL_COLUMN)
        + " 평균"
        + pad_start(format_krw(line.mean_price), _WINDOW_MEAN_COLUMN)
        + " 대비"
        + pad_start(format_rate(line.deviation_rate, 1), _WINDOW_RATE_COLUMN)
        for line in windows
    ]


def _reverse_rows(blocks: Sequence[ReverseBlock]) -> list[str]:
    """역방향 요약 줄을 만든다.

    Args:
        blocks: 종목별 요약.

    Returns:
        줄 목록. 종목 사이를 빈 줄로 나눈다.
    """
    rows: list[str] = []
    for index, block in enumerate(blocks):
        if index:
            rows.append("")
        rows.append(f"  {block.symbol}")
        rows += [
            pad_start(line.direction, _DIRECTION_COLUMN)
            + "   1위 "
            + pad_start(format_rate(line.rate_1st), _FIRST_RATE_COLUMN)
            + "     20위  "
            + pad_start(format_rate(line.rate_20th), _TWENTIETH_RATE_COLUMN)
            + "     "
            + pad_end(line.extreme_label, _EXTREME_LABEL_COLUMN)
            + "  "
            + pad_start(format_rate(line.extreme_rate), _EXTREME_RATE_COLUMN)
            + "  "
            + format_day(line.extreme_on)
            for line in block.lines
        ]
    return rows


def render(
    sent_at: datetime,
    current: float,
    as_of: date,
    windows: Sequence[WindowLine],
    reverses: Sequence[ReverseBlock],
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
        reverses: 종목별 역방향 요약.
        health: 점검 항목.

    Returns:
        보낼 문구.

    Raises:
        ValueError: 창이 하나도 없을 때.
    """
    if not windows:
        raise ValueError("비교할 창이 없어 알림을 만들 수 없습니다.")

    return "\n".join(
        [
            f"[주간] {format_day(sent_at.date())} {sent_at:%H:%M}",
            "",
            f"원달러  {format_krw(current, 2)}   {format_day(as_of)}",
            *_window_rows(windows),
            "",
            "역방향",
            *_reverse_rows(reverses),
            "",
            "점검",
            f"  {health.label}   {health.period}",
            f"  {health.detail}",
        ]
    )

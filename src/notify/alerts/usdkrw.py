"""원달러 평균대비와 지난주 역방향 요약을 계산한다.

평균대비는 부호가 곧 의미다 — 음수면 평균보다 싸다. 판정 어휘를 붙이지 않고
숫자만 낸다.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime

import pandas as pd

from notify.alerts.formatting import (
    alert,
    bold,
    format_day,
    format_day_paren,
    format_krw,
    format_rate,
)
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

    지난주 값이 무엇인지(최고·최저·신호)는 저장하지 않고 문구를 만들 때 정한다.
    라벨과 강조 여부가 같은 판정에서 나오므로, 두 곳에서 따로 정하면 어긋난다.

    Attributes:
        direction: 폭등 또는 폭락.
        rate_1st: 1위 등락률.
        rate_20th: 20위 등락률.
        extreme_rate: 지난주 값.
        extreme_on: 그 값이 나온 날.
    """

    direction: str
    rate_1st: float
    rate_20th: float
    extreme_rate: float
    extreme_on: date


@dataclass(frozen=True)
class ReverseBlock:
    """종목 하나의 역방향 요약."""

    symbol: str
    lines: Sequence[ReverseLine]


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


def reached_threshold(extreme_rate: float, rate_20th: float) -> bool:
    """지난주 값이 순위 등락률에 닿았는지 본다.

    폭등은 이상, 폭락은 이하다. **순위 등락률의 부호가 방향을 말한다** —
    폭등 20위는 양수, 폭락 20위는 음수다.

    Args:
        extreme_rate: 지난주 값. 비율.
        rate_20th: 20위 등락률. 비율.

    Returns:
        닿았으면 True.
    """
    if rate_20th >= 0:
        return extreme_rate >= rate_20th
    return extreme_rate <= rate_20th


def _extreme_row(line: ReverseLine) -> str:
    """지난주 값 줄을 만든다.

    **신호였으면 강조한다.** 역방향은 몇 달을 조용할 수 있어, 있었던 주에는
    그 줄이 눈에 걸려야 한다.

    Args:
        line: 역방향 요약 한 방향.

    Returns:
        지난주 값 줄.
    """
    value = f"{format_rate(line.extreme_rate)} {format_day_paren(line.extreme_on)}"
    if reached_threshold(line.extreme_rate, line.rate_20th):
        return alert(f"지난주 신호 {value}")

    label = "지난주 최고" if line.rate_20th >= 0 else "지난주 최저"
    return f"{label} {value}"


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
        rows.append(bold(f"역방향 · {block.symbol}"))
        for line in block.lines:
            rows.append(f"{line.direction} 1위 {format_rate(line.rate_1st)}" f" / 20위 {format_rate(line.rate_20th)}")
            rows.append(_extreme_row(line))
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

    rows = [
        f"{bold('주간')} · {format_day(sent_at.date())} {sent_at:%H:%M}",
        "",
        bold(f"원달러 {format_krw(current, 2)}"),
        f"{format_day(as_of)} 기준",
        "",
        *_window_rows(windows),
    ]
    if reverses:
        rows += ["", *_reverse_rows(reverses)]
    rows += ["", bold("점검"), f"{health.label} {health.period}", health.detail]

    return "\n".join(rows)

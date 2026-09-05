"""이동평균 근접도와 보유 비중을 계산한다.

이동평균은 최근 구간의 종가를 더해 개수로 나눈 값이라, 최근 1년치만 있으면
누가 계산해도 같은 값이 나온다.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime

import pandas as pd

from notify.alerts.formatting import (
    display_width,
    format_day,
    format_rate,
    format_weight,
    pad_end,
    pad_start,
)
from notify.alerts.health import HealthLine
from notify.common_constants import MA_PERIOD


def sma(closes: pd.Series, period: int = MA_PERIOD) -> float:
    """단순이동평균을 낸다.

    기간을 못 채우면 값을 만들지 않는다. 짧은 창으로 대신 계산하면 백테스트와
    다른 값이 나오는데, 알림 형태로는 정상으로 보인다.

    Args:
        closes: 종가 계열. 오래된 값이 앞에 온다.
        period: 기간. 거래일 수.

    Returns:
        최근 기간의 단순이동평균.

    Raises:
        ValueError: 계열이 기간보다 짧을 때.
    """
    if period <= 0:
        raise ValueError(f"이동평균 기간은 1 이상이어야 합니다. 지금 값: {period}")
    if len(closes) < period:
        raise ValueError(f"이동평균을 내려면 종가가 {period}개 있어야 합니다. 지금 {len(closes)}개입니다.")

    return float(closes.tail(period).mean())


def ma_proximity(close: float, ma: float) -> float:
    """이동평균 근접도를 낸다.

    평균선 위면 양수, 아래면 음수다.

    Args:
        close: 종가.
        ma: 이동평균.

    Returns:
        근접도. 비율 (0.1 = 평균선보다 10% 위).

    Raises:
        ValueError: 이동평균이 0 일 때.
    """
    if ma == 0:
        raise ValueError("이동평균이 0 이라 근접도를 낼 수 없습니다.")

    return (close - ma) / ma


def position_weights(quantities: Mapping[str, int], prices: Mapping[str, float]) -> dict[str, float]:
    """보유 비중을 낸다.

    비중은 평가액 비율이다. 수량만으로 내면 주당 가격이 달라 뜻 없는 숫자가 나온다.
    평가액은 계산에만 쓰고 알림에 표시하지 않는다.

    Args:
        quantities: 종목별 보유 수량.
        prices: 종목별 현재가.

    Returns:
        종목별 비중. 비율. 보유가 없으면 빈 결과.

    Raises:
        ValueError: 보유 종목의 가격이 없거나 평가액 합이 0 일 때.
    """
    if not quantities:
        return {}

    missing = [ticker for ticker in quantities if ticker not in prices]
    if missing:
        raise ValueError(f"보유 종목의 가격이 없습니다: {', '.join(missing)}. 시세 조회를 확인하세요.")

    valuations = {ticker: quantity * prices[ticker] for ticker, quantity in quantities.items()}
    total = sum(valuations.values())
    if total <= 0:
        raise ValueError("보유 평가액 합이 0 이라 비중을 낼 수 없습니다.")

    return {ticker: valuation / total for ticker, valuation in valuations.items()}


@dataclass(frozen=True)
class ProximityLine:
    """이동평균 근접도 한 종목."""

    ticker: str
    proximity_rate: float


@dataclass(frozen=True)
class HoldingLine:
    """보유 한 종목."""

    ticker: str
    quantity: int
    weight_ratio: float


# 근접도 값이 차지하는 칸. 부호와 소수 둘째 자리까지 들어간다
_RATE_COLUMN = 9

# 근접도를 두 칸으로 늘어놓을 때 칸 사이 간격
_PAIR_GAP = 6

# 보유 줄의 수량과 비중이 차지하는 칸
_QUANTITY_COLUMN = 8
_WEIGHT_COLUMN = 9

# 점검 줄의 라벨과 기간이 차지하는 칸
_HEALTH_LABEL_COLUMN = 9
_HEALTH_PERIOD_COLUMN = 10

def _proximity_cell(line: ProximityLine, ticker_width: int) -> str:
    """근접도 한 칸을 만든다.

    Args:
        line: 근접도.
        ticker_width: 종목 이름이 차지할 칸.

    Returns:
        종목과 값을 이어 붙인 칸.
    """
    return pad_end(line.ticker, ticker_width) + pad_start(format_rate(line.proximity_rate), _RATE_COLUMN)


def _proximity_rows(proximities: Sequence[ProximityLine]) -> list[str]:
    """근접도를 두 칸씩 늘어놓는다.

    Args:
        proximities: 종목별 근접도.

    Returns:
        줄 목록.
    """
    ticker_width = max((display_width(line.ticker) for line in proximities), default=0)
    cells = [_proximity_cell(line, ticker_width) for line in proximities]
    pairs = [cells[index : index + 2] for index in range(0, len(cells), 2)]
    return ["  " + (" " * _PAIR_GAP).join(pair) for pair in pairs]


def _holding_rows(holdings: Sequence[HoldingLine]) -> list[str]:
    """보유 줄을 만든다.

    Args:
        holdings: 보유 종목.

    Returns:
        줄 목록.
    """
    ticker_width = max(display_width(line.ticker) for line in holdings)
    return [
        "  "
        + pad_end(line.ticker, ticker_width)
        + pad_start(f"{line.quantity:,}주", _QUANTITY_COLUMN)
        + pad_start(format_weight(line.weight_ratio), _WEIGHT_COLUMN)
        for line in holdings
    ]


def _health_rows(health: Sequence[HealthLine]) -> list[str]:
    """점검 줄을 만든다.

    Args:
        health: 점검 항목.

    Returns:
        줄 목록.
    """
    return [
        "  "
        + pad_end(line.label, _HEALTH_LABEL_COLUMN)
        + " "
        + pad_end(line.period, _HEALTH_PERIOD_COLUMN)
        + "   "
        + line.detail
        for line in health
    ]


def render(
    sent_at: datetime,
    proximities: Sequence[ProximityLine],
    holdings: Sequence[HoldingLine],
    health: Sequence[HealthLine],
) -> str:
    """이동평균 알림 문구를 만든다.

    보유가 비어도 발송한다. 그 블록을 통째로 빼고 나머지는 그대로 낸다.

    Args:
        sent_at: 발송 시각.
        proximities: 종목별 이동평균 근접도.
        holdings: 보유 종목.
        health: 점검 항목.

    Returns:
        보낼 문구.

    Raises:
        ValueError: 근접도가 하나도 없을 때.
    """
    if not proximities:
        raise ValueError("이동평균 근접도가 비어 있어 알림을 만들 수 없습니다.")

    rows = [
        f"[QBT] {format_day(sent_at.date())} {sent_at:%H:%M}",
        "",
        "MA 근접도",
        *_proximity_rows(proximities),
    ]
    if holdings:
        rows += ["", "보유", *_holding_rows(holdings)]
    rows += ["", "점검", *_health_rows(health)]

    return "\n".join(rows)

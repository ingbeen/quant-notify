"""이동평균 근접도와 보유 비중을 계산하고 버퍼존 알림 문구를 만든다."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime

import pandas as pd

from notify.alerts.formatting import bold, format_rate, format_sent_at, format_weight
from notify.alerts.health import HealthLine
from notify.common_constants import (
    BUFFER_ZONE_SIGNAL_TICKERS,
    BUY_BUFFER_ZONE_RATE,
    MA_PERIOD,
    SELL_BUFFER_ZONE_RATE,
)


def sma(closes: pd.Series) -> float:
    """최근 `MA_PERIOD` 거래일의 단순이동평균을 낸다.

    기간을 못 채우면 값을 만들지 않는다. 짧은 창으로 대신 계산하면 백테스트와 다른 값이
    정상처럼 나간다.

    Args:
        closes: 종가 계열. 오래된 값이 앞에 온다.

    Returns:
        최근 기간의 단순이동평균.

    Raises:
        ValueError: 계열이 기간보다 짧을 때.
    """
    if len(closes) < MA_PERIOD:
        raise ValueError(f"이동평균을 내려면 종가가 {MA_PERIOD}개 있어야 합니다. 지금 {len(closes)}개입니다.")

    return float(closes.tail(MA_PERIOD).mean())


def ma_proximity(close: float, ma: float) -> float:
    """이동평균 근접도를 낸다. 평균선 위면 양수, 아래면 음수다.

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
    """보유 비중을 낸다. 평가액 비율이다 (`docs/DESIGN.md` §4.2).

    Args:
        quantities: 종목별 보유 수량.
        prices: 종목별 현재가. 보유 종목이 모두 들어 있어야 한다.

    Returns:
        종목별 비중. 비율. 보유가 없으면 빈 결과.

    Raises:
        ValueError: 평가액 합이 0 일 때.
    """
    if not quantities:
        return {}

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


def _proximity_text(line: ProximityLine) -> str:
    """근접도를 표시할 말로 바꾼다.

    두 선으로 매매하는 종목은 두 선 사이일 때만 수치를 내고 밖이면 위치를 적는다.
    정확히 선 위인 날은 선 안이다 (`docs/DESIGN.md` §4.3).

    Args:
        line: 한 종목의 근접도.

    Returns:
        수치 또는 위치.
    """
    rate = line.proximity_rate
    if line.ticker in BUFFER_ZONE_SIGNAL_TICKERS:
        if rate > BUY_BUFFER_ZONE_RATE:
            return "매수선 위"
        if rate < -SELL_BUFFER_ZONE_RATE:
            return "매도선 아래"
    return format_rate(rate)


def render(
    sent_at: datetime,
    proximities: Sequence[ProximityLine],
    holdings: Sequence[HoldingLine],
    health: HealthLine,
) -> str:
    """버퍼존 알림 문구를 만든다. 보유가 비면 그 블록을 뺀다.

    Args:
        sent_at: 발송 시각.
        proximities: 종목별 이동평균 근접도.
        holdings: 보유 종목.
        health: 점검 줄.

    Returns:
        보낼 문구.
    """
    rows = [
        f"{bold('QBT')} · {format_sent_at(sent_at)}",
        "",
        bold("MA 근접도"),
        *(f"{line.ticker} {_proximity_text(line)}" for line in proximities),
    ]
    if holdings:
        rows += [
            "",
            bold("보유"),
            *(f"{line.ticker} {line.quantity:,}주 · {format_weight(line.weight_ratio)}" for line in holdings),
        ]
    rows += ["", bold("점검"), f"{health.label} {health.period} · {health.detail}"]

    return "\n".join(rows)

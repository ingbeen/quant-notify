"""역방향 신호를 판정한다.

판정 규격은 `reference/역방향_매매_규칙.md` 1.5 절이 정본이다. 한국과 미국이 같은
산식을 쓰며, 다른 것은 순위 등락률 값과 판정 시각뿐이다.

비교는 가격으로 한다. 신호 가격은 판정일 이전 데이터만으로 정해지므로 장이 열리기
전에 이미 확정돼 있고, 등락률을 되짚어 계산하면 자릿수만 흔들린다.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from notify.alerts.formatting import alert, format_day, format_krw, format_rate, format_usd
from notify.common_constants import REVERSE_MARGIN_RATE
from notify.state.reverse_rank import RankThresholds


class Direction(StrEnum):
    """신호 방향. 폭등과 폭락은 순위를 따로 매긴다."""

    SURGE = "surge"
    PLUNGE = "plunge"


class SignalState(StrEnum):
    """판정 상태.

    표시 어휘는 시장마다 다르다. 한국은 장중 판정이라 도달, 미국은 종가 확정 뒤라
    발생으로 적는다. 판정 자체는 같으므로 여기서는 어휘를 담지 않는다.
    """

    SILENT = "silent"
    NEAR = "near"
    HIT = "hit"


@dataclass(frozen=True)
class SignalPrices:
    """폭등·폭락 신호 가격. 둘을 항상 함께 낸다."""

    surge: float
    plunge: float


@dataclass(frozen=True)
class Judgement:
    """판정 결과."""

    state: SignalState
    direction: Direction | None
    change_rate: float
    current_price: float


def signal_prices(prev_close: float, thresholds: RankThresholds, margin_rate: float = 0.0) -> SignalPrices:
    """신호 가격을 낸다.

    전일 종가에 순위 등락률을 곱한다. `margin_rate` 를 주면 그만큼 앞당긴
    근접 가격이 나온다.

    Args:
        prev_close: 전일 종가.
        thresholds: 순위 등락률.
        margin_rate: 여유. 비율 (0.01 = 1%p).

    Returns:
        폭등·폭락 신호 가격.

    Raises:
        ValueError: 전일 종가가 0 이하일 때.
    """
    if prev_close <= 0:
        raise ValueError(f"전일 종가는 0 보다 커야 합니다. 지금 값: {prev_close}")

    return SignalPrices(
        surge=prev_close * (1 + thresholds.surge_20th - margin_rate),
        plunge=prev_close * (1 + thresholds.plunge_20th + margin_rate),
    )


def judge(
    prev_close: float,
    current_price: float,
    thresholds: RankThresholds,
    margin_rate: float = REVERSE_MARGIN_RATE,
) -> Judgement:
    """오늘이 신호인지 판정한다.

    폭등은 신호 가격 이상, 폭락은 이하일 때 도달이다. 부등호가 방향마다 반대다.
    도달하지 않았어도 여유 안에 들어오면 근접으로 알리고, 여유 밖이면 침묵한다.

    Args:
        prev_close: 전일 종가.
        current_price: 판정 시점 가격.
        thresholds: 순위 등락률.
        margin_rate: 여유. 비율 (0.01 = 1%p).

    Returns:
        판정 결과.

    Raises:
        ValueError: 전일 종가가 0 이하일 때.
    """
    hit = signal_prices(prev_close, thresholds)
    near = signal_prices(prev_close, thresholds, margin_rate)
    change_rate = current_price / prev_close - 1

    def result(state: SignalState, direction: Direction | None) -> Judgement:
        return Judgement(
            state=state, direction=direction, change_rate=change_rate, current_price=current_price
        )

    if current_price >= hit.surge:
        return result(SignalState.HIT, Direction.SURGE)
    if current_price <= hit.plunge:
        return result(SignalState.HIT, Direction.PLUNGE)
    if current_price >= near.surge:
        return result(SignalState.NEAR, Direction.SURGE)
    if current_price <= near.plunge:
        return result(SignalState.NEAR, Direction.PLUNGE)
    return result(SignalState.SILENT, None)


class Market(StrEnum):
    """판정 시각이 다른 두 시장.

    표시 어휘가 갈린다. 한국은 장중에 보므로 값이 아직 확정이 아니고,
    미국은 마감 뒤에 보므로 이미 확정된 종가다.
    """

    KR = "kr"
    US = "us"


# 시장별 표시 어휘. 판정은 같고 읽는 시점이 달라 말이 갈린다
_PRICE_LABEL = {Market.KR: "현재", Market.US: "종가"}
_HIT_WORD = {Market.KR: "도달", Market.US: "발생"}
_DIRECTION_WORD = {Direction.SURGE: "폭등", Direction.PLUNGE: "폭락"}


def _state_word(market: Market, state: SignalState) -> str:
    """상태를 시장에 맞는 말로 바꾼다.

    Args:
        market: 시장.
        state: 판정 상태.

    Returns:
        표시할 말.

    Raises:
        RuntimeError: 침묵 상태로 문구를 만들려 할 때.
    """
    if state is SignalState.NEAR:
        return "근접"
    if state is SignalState.HIT:
        return _HIT_WORD[market]
    raise RuntimeError(f"내부 불변조건 위반: 침묵인데 문구를 만들려 했습니다 ({state}).")


def render(
    market: Market,
    symbol: str,
    judgement: Judgement,
    prices: SignalPrices,
    thresholds: RankThresholds,
    sent_at: datetime,
) -> str:
    """역방향 알림 문구를 만든다.

    신호 가격과 그 순위 등락률을 함께 낸다. 지금 값만 보여주면 얼마나 가까운지 알 수 없다.

    Args:
        market: 시장.
        symbol: 화면에 쓸 종목 이름.
        judgement: 판정 결과.
        prices: 신호 가격.
        thresholds: 순위 등락률.
        sent_at: 발송 시각.

    Returns:
        보낼 문구.

    Raises:
        RuntimeError: 침묵 상태로 문구를 만들려 할 때. 침묵이면 발송하지 않는다.
    """
    if judgement.direction is None:
        raise RuntimeError("내부 불변조건 위반: 방향이 없는데 문구를 만들려 했습니다.")

    # 연 5~8회만 오는 알림이라 온 것 자체가 사건이다. 제목을 강조한다
    heading = alert(
        f"역방향 · {symbol} · {_DIRECTION_WORD[judgement.direction]} {_state_word(market, judgement.state)}"
    )

    money = format_krw if market is Market.KR else format_usd
    is_surge = judgement.direction is Direction.SURGE
    signal_price = prices.surge if is_surge else prices.plunge
    signal_rate = thresholds.surge_20th if is_surge else thresholds.plunge_20th

    rows = [
        f"{label} {money(price)} {format_rate(rate)}"
        for label, price, rate in zip(
            (_PRICE_LABEL[market], "신호"),
            (judgement.current_price, signal_price),
            (judgement.change_rate, signal_rate),
            strict=True,
        )
    ]

    return "\n".join([heading, f"{format_day(sent_at.date())} {sent_at:%H:%M}", "", *rows])

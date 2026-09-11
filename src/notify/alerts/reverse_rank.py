"""역방향 신호를 판정한다.

판정 규격은 `reference/역방향_매매_규칙.md` 1.5 절이 정본이다. 한국과 미국이 같은
산식을 쓰며, 다른 것은 순위 등락률 값과 판정 시각뿐이다.

비교는 가격으로 한다. 신호 가격은 판정일 이전 데이터만으로 정해지므로 장이 열리기
전에 이미 확정돼 있고, 등락률을 되짚어 계산하면 자릿수만 흔들린다.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import StrEnum

import pandas as pd

from notify.alerts.formatting import alert, bold, format_day, format_krw, format_rate, format_usd
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
        return Judgement(state=state, direction=direction, change_rate=change_rate, current_price=current_price)

    if current_price >= hit.surge:
        return result(SignalState.HIT, Direction.SURGE)
    if current_price <= hit.plunge:
        return result(SignalState.HIT, Direction.PLUNGE)
    if current_price >= near.surge:
        return result(SignalState.NEAR, Direction.SURGE)
    if current_price <= near.plunge:
        return result(SignalState.NEAR, Direction.PLUNGE)
    return result(SignalState.SILENT, None)


@dataclass(frozen=True)
class UnreflectedDay:
    """순위 등락률에 아직 반영되지 않은 도달일.

    Attributes:
        on: 그 날짜.
        direction: 폭등 또는 폭락.
        change_rate: 그 날의 등락률. 비율.
    """

    on: date
    direction: Direction
    change_rate: float


def reached_threshold(change_rate: float, rate_20th: float) -> bool:
    """등락률이 순위 등락률에 닿았는지 본다.

    폭등은 이상, 폭락은 이하다. **순위 등락률의 부호가 방향을 말한다** —
    폭등 20위는 양수, 폭락 20위는 음수다.

    Args:
        change_rate: 견줄 등락률. 비율.
        rate_20th: 20위 등락률. 비율.

    Returns:
        닿았으면 True.
    """
    if rate_20th >= 0:
        return change_rate >= rate_20th
    return change_rate <= rate_20th


def unreflected_window(data_to: date, last_confirmed: date, first_computable: date) -> tuple[date, date] | None:
    """반영되지 않은 날을 찾을 창을 낸다.

    `data_to` 는 순위에 이미 들어간 마지막 날이라 그 다음 날부터가 반영되지 않은 구간이다.
    **창 길이를 따로 정하지 않는다** — 길이를 고정하면 그 밖으로 나간 도달일이 조용히 묻힌다.

    받은 시세가 `data_to` 보다 짧으면 시작을 당기고 **경고하지 않는다.** QQQ 는 20위 값이
    몇 년에 한 번 바뀌므로(정본 1.5 절: 최근 5년간 2회) 1년 넘은 `data_to` 가 정상이고,
    매일 도는 판정이 그 사이를 이미 덮었다.

    Args:
        data_to: 순위 값이 매겨진 마지막 날.
        last_confirmed: 마지막 확정 종가일.
        first_computable: 받은 종가로 등락률을 낼 수 있는 첫 거래일.

    Returns:
        창의 (시작, 끝). 검사할 날이 없으면 None.

    Raises:
        ValueError: `data_to` 가 마지막 확정 종가일보다 뒤일 때.
    """
    if data_to > last_confirmed:
        raise ValueError(f"순위 등락률의 data_to ({data_to}) 가 마지막 확정 종가일 ({last_confirmed}) 보다 뒤입니다. " f"날짜를 잘못 적었는지 확인하세요.")

    start = max(data_to + timedelta(days=1), first_computable)
    if start > last_confirmed:
        return None

    return start, last_confirmed


def unreflected_days(changes: pd.Series, thresholds: RankThresholds, data_to: date) -> list[UnreflectedDay]:
    """순위에 반영되지 않은 도달일을 낸다.

    **`data_to` 를 여기서 한 번 더 견준다.** 창이 이미 그 뒤에서 시작하므로 중복이지만,
    창을 고치다 이 가드가 함께 사라지는 것을 막는다. 20위 «안에 든» 날은 갱신한 뒤에도
    도달 조건을 만족한다 — 새 20위가 그 등락률 자신이거나 그보다 낮기 때문이다.
    그래서 도달 여부만 보면 **갱신해도 경고가 꺼지지 않는다.**

    Args:
        changes: 일간 등락률 계열. 날짜를 인덱스로 갖는다. 비율.
        thresholds: 순위 등락률.
        data_to: 순위 값이 매겨진 마지막 날. 이 날까지는 이미 반영됐다.

    Returns:
        반영되지 않은 도달일. 창이 오래된 날부터 오므로 결과도 그 순서다.

    Raises:
        RuntimeError: 인덱스가 날짜가 아닐 때.
    """
    found: list[UnreflectedDay] = []
    for label, rate in changes.items():
        # `datetime` 을 함께 막는다. `pd.Timestamp` 는 `datetime` 의 하위형이고 그것이
        # 다시 `date` 의 하위형이라, 시세에서 바로 온 계열(DatetimeIndex)이 이 검사를
        # 통과한 뒤 다음 줄에서 **필드 이름이 없는 TypeError** 로 멈춘다
        if not isinstance(label, date) or isinstance(label, datetime):
            raise RuntimeError(f"내부 불변조건 위반: 등락률 인덱스가 날짜가 아닙니다: {label!r}")
        if label <= data_to:
            continue

        change_rate = float(rate)
        if reached_threshold(change_rate, thresholds.surge_20th):
            direction = Direction.SURGE
        elif reached_threshold(change_rate, thresholds.plunge_20th):
            direction = Direction.PLUNGE
        else:
            continue

        found.append(UnreflectedDay(on=label, direction=direction, change_rate=change_rate))

    return found


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


def _unreflected_rows(data_to: date, unreflected: Sequence[UnreflectedDay]) -> list[str]:
    """순위에 반영되지 않은 날을 줄로 만든다.

    **기준일을 함께 적는다.** 어느 날까지의 순위인지 모르면 「왜 갱신이 필요한지」가
    드러나지 않는다.

    Args:
        data_to: 순위 값이 매겨진 마지막 날.
        unreflected: 반영되지 않은 도달일.

    Returns:
        줄 목록.
    """
    return [
        f"순위값 {format_day(data_to)} 기준",
        *(
            f"{format_day(day.on)} {_DIRECTION_WORD[day.direction]} {format_rate(day.change_rate)}"
            for day in unreflected
        ),
    ]


def _staleness_rows(data_to: date, unreflected: Sequence[UnreflectedDay], pending_row: str | None) -> list[str]:
    """신호 문구에 붙일 순위 갱신 블록을 만든다.

    Args:
        data_to: 순위 값이 매겨진 마지막 날.
        unreflected: 확정 종가로 잡힌 반영되지 않은 도달일.
        pending_row: 종가가 아직 확정이 아닌 오늘 줄. 없으면 None.

    Returns:
        줄 목록. 알릴 것이 없으면 빈 목록.
    """
    if not unreflected and pending_row is None:
        return []

    rows = [bold("순위 갱신 필요"), *_unreflected_rows(data_to, unreflected)]
    if pending_row is not None:
        rows.append(pending_row)
    return rows


def render(
    market: Market,
    symbol: str,
    judgement: Judgement,
    prices: SignalPrices,
    thresholds: RankThresholds,
    sent_at: datetime,
    data_to: date,
    unreflected: Sequence[UnreflectedDay] = (),
) -> str:
    """역방향 알림 문구를 만든다.

    신호 가격과 그 순위 등락률을 함께 낸다. 지금 값만 보여주면 얼마나 가까운지 알 수 없다.

    **신호가 났으면 순위 갱신이 필요할 수 있다.** 20위 안에 새로 드는 것이 곧 신호의
    정의이므로(정본 1.5 절), 그 블록을 같은 알림에 붙여 사용자가 연결을 기억하지
    않게 한다.

    Args:
        market: 시장.
        symbol: 화면에 쓸 종목 이름.
        judgement: 판정 결과.
        prices: 신호 가격.
        thresholds: 순위 등락률.
        sent_at: 발송 시각.
        data_to: 순위 값이 매겨진 마지막 날.
        unreflected: 확정 종가로 잡힌 반영되지 않은 도달일.

    Returns:
        보낼 문구.

    Raises:
        RuntimeError: 침묵 상태로 문구를 만들려 할 때. 침묵이면 발송하지 않는다.
    """
    if judgement.direction is None:
        raise RuntimeError("내부 불변조건 위반: 방향이 없는데 문구를 만들려 했습니다.")

    # 연 5~8회만 오는 알림이라 온 것 자체가 사건이다. 제목을 강조한다
    heading = alert(f"역방향 · {symbol} · {_DIRECTION_WORD[judgement.direction]} {_state_word(market, judgement.state)}")

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

    # 한국 장중 도달은 그날 종가가 아직 없어 순위에 들어갈지 단정할 수 없다. 확정된 날과
    # **같은 모양**으로 적고 `(미확정)` 을 달아, 여러 날이 나열될 때 어느 줄이 오늘인지
    # 드러낸다 — 날짜 없이 조건만 적으면 바로 위 날짜를 꾸미는 말로 읽힌다
    pending_row = None
    if market is Market.KR and judgement.state is SignalState.HIT:
        pending_row = (
            f"{format_day(sent_at.date())} {_DIRECTION_WORD[judgement.direction]}"
            f" {format_rate(judgement.change_rate)} (미확정)"
        )

    staleness = _staleness_rows(data_to, unreflected, pending_row)
    if staleness:
        rows += ["", *staleness]

    return "\n".join([heading, f"{format_day(sent_at.date())} {sent_at:%H:%M}", "", *rows])


def render_staleness(
    symbol: str,
    data_to: date,
    unreflected: Sequence[UnreflectedDay],
    sent_at: datetime,
) -> str:
    """순위 갱신만 알리는 문구를 만든다.

    **신호가 멀어 침묵할 날에도 보낸다.** 역방향은 몇 달을 조용할 수 있어, 낡은 순위를
    침묵으로 두면 「신호가 없어서 조용한 것」과 구분되지 않는다 (docs/DESIGN.md 7.3 절).

    Args:
        symbol: 화면에 쓸 종목 이름.
        data_to: 순위 값이 매겨진 마지막 날.
        unreflected: 확정 종가로 잡힌 반영되지 않은 도달일.
        sent_at: 발송 시각.

    Returns:
        보낼 문구.

    Raises:
        RuntimeError: 알릴 것이 없는데 문구를 만들려 할 때.
    """
    if not unreflected:
        raise RuntimeError("내부 불변조건 위반: 반영되지 않은 날이 없는데 갱신 문구를 만들려 했습니다.")

    heading = alert(f"역방향 · {symbol} · 순위 갱신 필요")
    rows = _unreflected_rows(data_to, unreflected)

    return "\n".join([heading, f"{format_day(sent_at.date())} {sent_at:%H:%M}", "", *rows])

"""알림을 실행하는 명령줄 진입점.

알림마다 데이터를 따로 받는다. 캐시로 공유하면 알림 사이에 결합이 생기고 신선도 검증이
따라오는데, 아끼는 것은 종가 한 개다.

**판정 대상 날짜**는 알림마다 다르다.

- 이동평균과 미국 역방향은 한국 아침에 돌므로 **직전 미국 거래일**의 종가를 본다.
  한국 기준 어제가 미국 거래일이 아니면 새 종가가 없어 조용히 끝낸다.
- 한국 역방향은 **그날 장중**에 돌므로 오늘이 한국 거래일이어야 한다.
- 주간 알림은 요일로만 돌며 환율 기준일은 **받은 자료의 마지막 날**을 쓴다.

일일 알림 셋은 판정에 쓸 값을 **날짜로 집는다.** 그 날짜의 값이 없으면 멈춘다 —
계열의 끝을 위치로 집으면 하루 전 값으로 조용히 판정하게 된다 (docs/DESIGN.md 7.4 절).
"""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Sequence
from datetime import date, datetime, timedelta

import pandas as pd
from dotenv import dotenv_values

from notify.alerts import buffer_zone, failure, usdkrw
from notify.alerts.formatting import format_day
from notify.alerts.health import (
    WORKFLOW_USDKRW,
    HealthLine,
    RunCounter,
    count_success_runs,
    measure_runs,
    previous_day_health,
    today_health,
    weekly_health,
)
from notify.alerts.reverse_rank import Market, judge, signal_prices
from notify.alerts.reverse_rank import render as render_reverse
from notify.common_constants import (
    BUFFER_ZONE_TICKERS,
    ECOS_USDKRW_ITEM_CODE,
    ECOS_USDKRW_STAT_CODE,
    POSITIONS_PATH,
    PROJECT_ROOT,
    REVERSE_RANK_PATH,
    TICKER_QQQ,
    TZ_KST,
    USDKRW_WINDOW_YEARS,
)
from notify.data.calendar import (
    KR_CALENDAR,
    US_CALENDAR,
    is_kr_trading_day,
    is_us_trading_day,
    previous_kr_trading_day,
    previous_trading_day,
    previous_us_trading_day,
    trading_days_between,
)
from notify.data.ecos_client import ENV_ECOS_API_KEY, fetch_usdkrw
from notify.data.yfinance_client import close_on, closes_through, fetch_closes, fetch_intraday_price
from notify.notifier import telegram
from notify.state.positions import load_positions
from notify.state.reverse_rank import RankEntry, load_reverse_rank
from notify.utils.logger import get_logger

logger = get_logger(__name__)

ENV_FILE_PATH = PROJECT_ROOT / ".env"

# 알림 이름
ALERT_BUFFER_ZONE = "buffer_zone"
ALERT_REVERSE_KR = "reverse_rank_kr"
ALERT_REVERSE_US = "reverse_rank_us"
ALERT_USDKRW = "usdkrw"
ALERT_NAMES = (ALERT_BUFFER_ZONE, ALERT_REVERSE_KR, ALERT_REVERSE_US, ALERT_USDKRW)

# state 파일이 쓰는 종목 열쇠
RANK_KEY_KODEX = "kodex200"
RANK_KEY_QQQ = "qqq"

# 화면에 쓸 종목 이름
SYMBOL_KODEX = "KODEX 200"

# KODEX 200 의 야후 티커
YF_TICKER_KODEX = "069500.KS"

# 환율 조회 기간. 10년 창을 채우고 여유를 둔다
USDKRW_LOOKBACK_DAYS = 365 * 11

# 지난주 구간의 끝. 월요일에서 며칠 뒤인지를 적는다.
#
# **두 구간이 갈린다.** 역방향 요약은 거래일을 보므로 금요일까지고, 점검은 실행일을
# 보므로 토요일까지다 — 미국장 알림이 화~토에 돌기 때문이다 (docs/DESIGN.md 6.4 절).
TRADING_WEEK_OFFSET = 4
RUN_WEEK_OFFSET = 5


def _config(name: str, required: bool = True) -> str:
    """설정값을 읽는다.

    환경 변수를 먼저 보고 없으면 `.env` 를 본다. 워크플로는 환경 변수로 넘긴다.

    Args:
        name: 설정 이름.
        required: 없을 때 예외를 낼지 여부.

    Returns:
        설정값. 없고 필수가 아니면 빈 문자열.

    Raises:
        ValueError: 필수인데 값이 없을 때.
    """
    value = os.environ.get(name) or dotenv_values(ENV_FILE_PATH).get(name) or ""
    value = value.strip()
    if required and not value:
        raise ValueError(f"{name} 가 없습니다. `.env` 또는 워크플로 시크릿에 넣으세요.")
    return value


def _run_counter(repository: str, token: str):
    """실행 이력을 세는 함수를 만든다.

    Args:
        repository: `소유자/저장소` 형태.
        token: GitHub 토큰.

    Returns:
        워크플로와 날짜를 받아 성공 수를 돌려주는 함수.
    """

    def counter(workflow: str, day: date) -> int:
        return count_success_runs(repository, token, workflow, day)

    return counter


def _health_counter():
    """설정이 갖춰졌으면 실제 조회를, 아니면 0 을 돌려주는 함수를 만든다.

    Returns:
        실행 수를 세는 함수.
    """
    repository = _config("GITHUB_REPOSITORY", required=False)
    token = _config("GITHUB_TOKEN", required=False)
    if repository and token:
        return _run_counter(repository, token)

    def unavailable(workflow: str, day: date) -> int:
        del workflow, day
        raise ValueError("GITHUB_REPOSITORY 또는 GITHUB_TOKEN 이 없어 실행 이력을 조회할 수 없습니다.")

    return unavailable


def _load_rank(key: str) -> RankEntry:
    """순위 등락률에서 한 종목을 꺼낸다.

    Args:
        key: 종목 열쇠.

    Returns:
        그 종목의 순위 등락률.

    Raises:
        ValueError: 파일에 그 종목이 없을 때.
    """
    entries = load_reverse_rank(REVERSE_RANK_PATH)
    if key not in entries:
        raise ValueError(f"순위 등락률 파일에 '{key}' 가 없습니다: {REVERSE_RANK_PATH}")
    return entries[key]


def run_buffer_zone(now: datetime) -> str | None:
    """이동평균 알림 문구를 만든다.

    Args:
        now: 실행 시각.

    Returns:
        보낼 문구. 볼 종가가 없으면 None.
    """
    target = now.date() - timedelta(days=1)
    if not is_us_trading_day(target):
        logger.debug(f"{target} 은 미국 휴장이라 새 종가가 없습니다.")
        return None

    positions = load_positions(POSITIONS_PATH)
    tickers = list(dict.fromkeys([*BUFFER_ZONE_TICKERS, *(p.ticker for p in positions)]))
    closes = fetch_closes(tickers)
    through = {ticker: closes_through(series, target, ticker) for ticker, series in closes.items()}
    prices = {ticker: float(series.iloc[-1]) for ticker, series in through.items()}

    proximities = [
        buffer_zone.ProximityLine(
            ticker=ticker,
            proximity_rate=buffer_zone.ma_proximity(prices[ticker], buffer_zone.sma(through[ticker])),
        )
        for ticker in BUFFER_ZONE_TICKERS
    ]

    holdings: list[buffer_zone.HoldingLine] = []
    if positions:
        weights = buffer_zone.position_weights(
            quantities={p.ticker: p.quantity for p in positions},
            prices=prices,
        )
        holdings = [buffer_zone.HoldingLine(p.ticker, p.quantity, weights[p.ticker]) for p in positions]

    # 최근 것이 위에 온다. 미국 역방향만 당일인 이유는 발화 시각에 있다 (health 모듈 문서).
    #
    # 전일 줄에 `target` 을 넘기지 않는다. 지금은 값이 같지만 `target` 은 **미국 종가를
    # 고르는 날짜**라, 나중에 직전 미국 거래일 조회로 바뀌면 미국 휴장 다음날에 한국
    # 역방향 실행이 통째로 빠진다 — 에러 없이
    counter = _health_counter()
    health = [
        today_health(now.date(), counter),
        previous_day_health(now.date() - timedelta(days=1), counter),
        _weekly_slot(_last_monday(now.date()), counter),
    ]

    return buffer_zone.render(sent_at=now, proximities=proximities, holdings=holdings, health=health)


def _last_monday(today: date) -> date:
    """가장 최근에 지나간 월요일을 찾는다.

    오늘이 월요일이면 지난주 월요일을 돌려준다. 주간 알림과 이 알림은 같은 아침에 돌아
    순서가 정해져 있지 않으므로, 오늘 것을 세면 아직 돌지 않은 실행을 빠진 것으로 읽는다.

    Args:
        today: 오늘 날짜.

    Returns:
        가장 최근 월요일.
    """
    offset = today.weekday()
    return today - timedelta(days=offset if offset else 7)


def _weekly_slot(monday: date, counter: RunCounter) -> HealthLine:
    """주간 알림이 지난 월요일에 돌았는지 적는다.

    Args:
        monday: 지난 월요일.
        counter: 실행 수를 세는 함수.

    Returns:
        점검 줄.
    """
    report = measure_runs("", WORKFLOW_USDKRW, [monday], counter)
    return HealthLine("최근 주간", format_day(monday), report.text)


def _korea_prices(now: datetime) -> tuple[float, float] | None:
    """한국 역방향이 볼 두 값을 받는다.

    **장중 판정이다.** 오늘 현재가를 전일 종가와 견준다. 일봉에는 장중에 당일
    미확정 봉이 섞여 오므로 전일 종가를 날짜로 골라낸다.

    Args:
        now: 실행 시각.

    Returns:
        (전일 종가, 현재가). 휴장이면 None.
    """
    if not is_kr_trading_day(now.date()):
        logger.debug(f"{now.date()} 는 한국 휴장입니다.")
        return None

    closes = fetch_closes([YF_TICKER_KODEX])[YF_TICKER_KODEX]
    previous = close_on(closes, previous_kr_trading_day(now.date()), YF_TICKER_KODEX)
    return previous, fetch_intraday_price(YF_TICKER_KODEX, now.date())


def _united_states_prices(now: datetime) -> tuple[float, float] | None:
    """미국 역방향이 볼 두 값을 받는다.

    **마감 뒤 판정이다.** 직전 미국 거래일의 확정 종가를 그 전날과 견준다.

    Args:
        now: 실행 시각.

    Returns:
        (전일 종가, 당일 종가). 휴장이면 None.

    Raises:
        ValueError: 두 거래일 중 하나라도 종가를 받지 못했을 때.
    """
    target = now.date() - timedelta(days=1)
    if not is_us_trading_day(target):
        logger.debug(f"{target} 은 미국 휴장이라 새 종가가 없습니다.")
        return None

    closes = fetch_closes([TICKER_QQQ])[TICKER_QQQ]
    previous = close_on(closes, previous_us_trading_day(target), TICKER_QQQ)
    return previous, close_on(closes, target, TICKER_QQQ)


def _run_reverse(market: Market, now: datetime) -> str | None:
    """역방향 알림 문구를 만든다.

    **두 시장은 보는 값이 다르다** — 한국은 그날 장중 현재가를, 미국은 직전 거래일
    종가를 본다. 판정과 문구는 같다.

    Args:
        market: 시장.
        now: 실행 시각.

    Returns:
        보낼 문구. 휴장이거나 신호가 멀면 None.
    """
    if market is Market.KR:
        prices = _korea_prices(now)
        symbol, rank_key = SYMBOL_KODEX, RANK_KEY_KODEX
    else:
        prices = _united_states_prices(now)
        symbol, rank_key = TICKER_QQQ, RANK_KEY_QQQ

    if prices is None:
        return None

    prev_close, current = prices
    entry = _load_rank(rank_key)
    judgement = judge(prev_close=prev_close, current_price=current, thresholds=entry.thresholds)
    if judgement.direction is None:
        logger.debug("신호가 여유 밖이라 보내지 않습니다.")
        return None

    return render_reverse(
        market=market,
        symbol=symbol,
        judgement=judgement,
        prices=signal_prices(prev_close, entry.thresholds),
        thresholds=entry.thresholds,
        sent_at=now,
    )


def _weekly_changes(closes: pd.Series, ticker: str, calendar_code: str, start: date, end: date) -> pd.Series:
    """지난주 각 거래일의 일간 등락률을 낸다.

    **인접한 「행」이 아니라 인접한 「거래일」을 견준다.** `pct_change` 는 날짜를 보지 않으므로
    계열에서 하루가 빠지면 그 자리가 이틀치 수익률이 되고, 뒤 날짜의 이름을 달고 나온다.
    그 값이 1일 기준인 순위 등락률과 견줘져 알림에 실리므로 요약이 조용히 틀린다.

    창의 첫 날은 **그 직전 거래일** 종가가 있어야 나온다. 그 날은 창 밖이라
    행 수를 세는 검사로는 잡히지 않는다.

    Args:
        closes: 종가 계열.
        ticker: 종목. 실패 문구에 쓴다.
        calendar_code: 거래소 코드.
        start: 지난주 시작일.
        end: 지난주 종료일.

    Returns:
        날짜를 인덱스로 갖는 일간 등락률. 비율.

    Raises:
        ValueError: 거래일 종가나 그 직전 거래일 종가가 없을 때.
    """
    rates = {
        day: close_on(closes, day, ticker) / close_on(closes, previous_trading_day(calendar_code, day), ticker) - 1
        for day in trading_days_between(calendar_code, start, end)
    }
    return pd.Series(rates, dtype="float64")


def _weekly_extreme_line(symbol_key: str, changes: pd.Series) -> list[usdkrw.ReverseLine]:
    """한 종목의 지난주 역방향 요약을 만든다.

    Args:
        symbol_key: 순위 등락률 파일의 종목 열쇠.
        changes: 지난주 일간 등락률.

    Returns:
        폭등·폭락 두 줄.

    Raises:
        ValueError: 지난주 거래일이 없을 때.
    """
    entry = _load_rank(symbol_key)
    extremes = usdkrw.weekly_extremes(changes)

    return [
        usdkrw.ReverseLine(
            "폭등",
            entry.thresholds.surge_1st,
            entry.thresholds.surge_20th,
            extremes.highest.change_rate,
            extremes.highest.on,
        ),
        usdkrw.ReverseLine(
            "폭락",
            entry.thresholds.plunge_1st,
            entry.thresholds.plunge_20th,
            extremes.lowest.change_rate,
            extremes.lowest.on,
        ),
    ]


def run_usdkrw(now: datetime) -> str:
    """원달러 주간 알림 문구를 만든다.

    Args:
        now: 실행 시각.

    Returns:
        보낼 문구.
    """
    end = now.date()
    start = end - timedelta(days=USDKRW_LOOKBACK_DAYS)
    # 다른 설정과 같은 길로 읽는다. `.env` 를 직접 열면 워크플로에서 못 찾는다 —
    # Actions 에는 그 파일이 없고 시크릿이 환경 변수로 들어온다
    api_key = _config(ENV_ECOS_API_KEY)
    series = fetch_usdkrw(api_key, ECOS_USDKRW_STAT_CODE, ECOS_USDKRW_ITEM_CODE, start, end)

    as_of = series.index[-1]
    current = float(series.iloc[-1])
    windows = [
        usdkrw.WindowLine(
            years=years,
            mean_price=float(usdkrw.window_slice(series, as_of, years).mean()),
            deviation_rate=usdkrw.mean_deviation(current, usdkrw.window_slice(series, as_of, years)),
        )
        for years in USDKRW_WINDOW_YEARS
    ]

    week_start = _last_monday(end)
    trading_week_end = week_start + timedelta(days=TRADING_WEEK_OFFSET)
    closes = fetch_closes([YF_TICKER_KODEX, TICKER_QQQ])
    reverses = [
        usdkrw.ReverseBlock(
            SYMBOL_KODEX,
            _weekly_extreme_line(
                RANK_KEY_KODEX,
                _weekly_changes(closes[YF_TICKER_KODEX], YF_TICKER_KODEX, KR_CALENDAR, week_start, trading_week_end),
            ),
        ),
        usdkrw.ReverseBlock(
            TICKER_QQQ,
            _weekly_extreme_line(
                RANK_KEY_QQQ,
                _weekly_changes(closes[TICKER_QQQ], TICKER_QQQ, US_CALENDAR, week_start, trading_week_end),
            ),
        ),
    ]

    health = weekly_health(week_start, week_start + timedelta(days=RUN_WEEK_OFFSET), _health_counter())
    return usdkrw.render(sent_at=now, current=current, as_of=as_of, windows=windows, reverses=reverses, health=health)


def build_message(alert: str, now: datetime) -> str | None:
    """알림 하나의 문구를 만든다.

    Args:
        alert: 알림 이름.
        now: 실행 시각.

    Returns:
        보낼 문구. 보낼 것이 없으면 None.

    Raises:
        ValueError: 알림 이름을 모를 때.
    """
    if alert == ALERT_BUFFER_ZONE:
        return run_buffer_zone(now)
    if alert == ALERT_REVERSE_KR:
        return _run_reverse(Market.KR, now)
    if alert == ALERT_REVERSE_US:
        return _run_reverse(Market.US, now)
    if alert == ALERT_USDKRW:
        return run_usdkrw(now)
    raise ValueError(f"모르는 알림입니다: {alert}")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """명령줄 인자를 읽는다.

    Args:
        argv: 인자 목록.

    Returns:
        읽은 인자.
    """
    parser = argparse.ArgumentParser(description="알림을 실행합니다.")
    parser.add_argument("alert", choices=ALERT_NAMES, help="실행할 알림")
    parser.add_argument("--dry-run", action="store_true", help="보내지 않고 문구만 표준출력으로 찍습니다")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """알림을 실행한다.

    Args:
        argv: 인자 목록.

    Returns:
        종료 코드. 실패하면 1.
    """
    args = parse_args(argv)
    now = datetime.now(TZ_KST)

    try:
        message = build_message(args.alert, now)
    except Exception as exc:
        logger.warning(f"{args.alert} 실행이 실패했습니다: {exc}")
        if not args.dry_run:
            token = _config("TELEGRAM_BOT_TOKEN", required=False)
            chat_id = _config("TELEGRAM_CHAT_ID", required=False)
            if token and chat_id:
                telegram.send_without_raising(token, chat_id, failure.render(args.alert, exc, now))
        else:
            print(failure.render(args.alert, exc, now))
        return 1

    if message is None:
        logger.debug(f"{args.alert} 은 보낼 것이 없어 조용히 끝냅니다.")
        return 0

    if args.dry_run:
        print(message)
        return 0

    telegram.send(_config("TELEGRAM_BOT_TOKEN"), _config("TELEGRAM_CHAT_ID"), message)
    return 0


if __name__ == "__main__":
    sys.exit(main())

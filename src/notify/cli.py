"""알림을 실행하는 명령줄 진입점.

알림마다 데이터를 따로 받는다 (`docs/DESIGN.md` §5.4). 판정에 쓸 종가는 위치가 아니라
날짜로 집는다 (§7.4).
"""

from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence
from datetime import datetime, timedelta

from notify.alerts import buffer_zone, failure, health, usdkrw
from notify.common_constants import (
    ALERT_BUFFER_ZONE,
    ALERT_USDKRW,
    BUFFER_ZONE_TICKERS,
    POSITIONS_PATH,
    TZ_KST,
    USDKRW_WINDOW_YEARS,
)
from notify.data import github_runs
from notify.data.calendar import is_us_trading_day, us_session_close
from notify.data.ecos_client import fetch_usdkrw
from notify.data.yfinance_client import closes_through, fetch_closes
from notify.notifier import telegram
from notify.state.positions import load_positions
from notify.utils.config import ENV_ECOS_API_KEY, ENV_TELEGRAM_BOT_TOKEN, ENV_TELEGRAM_CHAT_ID, read_config
from notify.utils.logger import get_logger

logger = get_logger(__name__)


def run_buffer_zone(now: datetime) -> str | None:
    """버퍼존 알림 문구를 만든다.

    한국 아침에 돌아 **직전 미국 거래일**의 종가를 본다. 한국 기준 어제가 미국 거래일이 아니면
    볼 새 종가가 없어 조용히 끝낸다.

    Args:
        now: 실행 시각.

    Returns:
        보낼 문구. 볼 종가가 없으면 None.

    Raises:
        ValueError: 그 거래일의 미국장이 아직 마감 전일 때. 장중 일봉의 그날 값은 확정 종가가 아니다.
    """
    target = now.date() - timedelta(days=1)
    if not is_us_trading_day(target):
        logger.debug(f"{target} 은 미국 휴장이라 새 종가가 없습니다.")
        return None

    close_at = us_session_close(target)
    if now < close_at:
        raise ValueError(
            f"{target} 미국장이 아직 마감 전입니다 (마감 {close_at.astimezone(TZ_KST):%m-%d %H:%M} KST). " "마감 뒤에 다시 실행하세요."
        )

    positions = load_positions(POSITIONS_PATH)
    tickers = list(dict.fromkeys([*BUFFER_ZONE_TICKERS, *(p.ticker for p in positions)]))
    through = {ticker: closes_through(series, target, ticker) for ticker, series in fetch_closes(tickers).items()}
    prices = {ticker: float(series.iloc[-1]) for ticker, series in through.items()}

    proximities = [
        buffer_zone.ProximityLine(
            ticker=ticker,
            proximity_rate=buffer_zone.ma_proximity(prices[ticker], buffer_zone.sma(through[ticker])),
        )
        for ticker in BUFFER_ZONE_TICKERS
    ]
    weights = buffer_zone.position_weights({p.ticker: p.quantity for p in positions}, prices)
    holdings = [buffer_zone.HoldingLine(p.ticker, p.quantity, weights[p.ticker]) for p in positions]

    return buffer_zone.render(
        sent_at=now,
        proximities=proximities,
        holdings=holdings,
        health=health.recent_weekly_health(now.date(), github_runs.run_counter()),
    )


def run_usdkrw(now: datetime) -> str:
    """원달러 주간 알림 문구를 만든다. 환율 기준일은 받은 자료의 마지막 날이다.

    Args:
        now: 실행 시각.

    Returns:
        보낼 문구.
    """
    end = now.date()
    # 가장 긴 창보다 1년을 더 받는다. 정상이면 첫 자료가 창 시작보다 앞서, 창 시작 검사가 여유 없이 판정한다
    start = usdkrw.years_before(end, max(USDKRW_WINDOW_YEARS) + 1)
    series = fetch_usdkrw(read_config(ENV_ECOS_API_KEY), start, end)

    return usdkrw.render(
        sent_at=now,
        current=float(series.iloc[-1]),
        as_of=series.index[-1],
        windows=[usdkrw.window_line(series, years) for years in USDKRW_WINDOW_YEARS],
        health=health.last_week_health(end, github_runs.run_counter()),
    )


# 알림 이름 → 문구를 만드는 함수. None 을 내면 보낼 것이 없다
ALERTS: dict[str, Callable[[datetime], str | None]] = {
    ALERT_BUFFER_ZONE: run_buffer_zone,
    ALERT_USDKRW: run_usdkrw,
}


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """명령줄 인자를 읽는다.

    Args:
        argv: 인자 목록.

    Returns:
        읽은 인자.
    """
    parser = argparse.ArgumentParser(description="알림을 실행합니다.")
    parser.add_argument("alert", choices=list(ALERTS), help="실행할 알림")
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
        message = ALERTS[args.alert](now)
    except Exception as exc:
        logger.warning(f"{args.alert} 실행이 실패했습니다: {exc}")
        text = failure.render(args.alert, exc, now)
        if args.dry_run:
            print(text)
            return 1

        token = read_config(ENV_TELEGRAM_BOT_TOKEN, required=False)
        chat_id = read_config(ENV_TELEGRAM_CHAT_ID, required=False)
        if token and chat_id:
            telegram.send_without_raising(token, chat_id, text)
        else:
            logger.warning("텔레그램 설정이 없어 실패 알림을 보내지 못했습니다.")
        return 1

    if message is None:
        logger.debug(f"{args.alert} 은 보낼 것이 없어 조용히 끝냅니다.")
        return 0

    if args.dry_run:
        print(message)
        return 0

    telegram.send(read_config(ENV_TELEGRAM_BOT_TOKEN), read_config(ENV_TELEGRAM_CHAT_ID), message)
    return 0

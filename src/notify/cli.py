"""알림을 실행하는 명령줄 진입점.

알림마다 데이터를 따로 받는다. 캐시로 공유하면 알림 사이에 결합이 생기고 신선도 검증이
따라온다.

**판정 대상 날짜**는 알림마다 다르다.

- 이동평균은 한국 아침에 돌므로 **직전 미국 거래일**의 종가를 본다.
  한국 기준 어제가 미국 거래일이 아니면 새 종가가 없어 조용히 끝낸다.
- 주간 알림은 요일로만 돌며 환율 기준일은 **받은 자료의 마지막 날**을 쓴다.

이동평균 알림은 판정에 쓸 값을 **날짜로 집는다.** 그 날짜의 값이 없으면 멈춘다 —
계열의 끝을 위치로 집으면 하루 전 값으로 조용히 판정하게 된다 (docs/DESIGN.md 7.4 절).
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from datetime import date, datetime, timedelta

from notify.alerts import buffer_zone, failure, usdkrw
from notify.alerts.formatting import format_day
from notify.alerts.health import (
    WORKFLOW_USDKRW,
    HealthLine,
    RunCounter,
    count_success_runs,
    measure_runs,
    weekly_health,
)
from notify.common_constants import (
    BUFFER_ZONE_TICKERS,
    ECOS_USDKRW_ITEM_CODE,
    ECOS_USDKRW_STAT_CODE,
    POSITIONS_PATH,
    TZ_KST,
    USDKRW_WINDOW_YEARS,
)
from notify.data.calendar import is_us_trading_day
from notify.data.ecos_client import ENV_ECOS_API_KEY, fetch_usdkrw
from notify.data.yfinance_client import closes_through, fetch_closes
from notify.notifier import telegram
from notify.state.positions import load_positions
from notify.utils.config import read_config
from notify.utils.logger import get_logger

logger = get_logger(__name__)

# 알림 이름
ALERT_BUFFER_ZONE = "buffer_zone"
ALERT_USDKRW = "usdkrw"
ALERT_NAMES = (ALERT_BUFFER_ZONE, ALERT_USDKRW)

# 환율 조회 기간. 10년 창을 채우고 여유를 둔다
USDKRW_LOOKBACK_DAYS = 365 * 11

# 지난주 점검 구간의 끝. 월요일에서 며칠 뒤인지를 적는다.
#
# 점검은 실행일을 보므로 토요일까지다 — 버퍼존이 화~토에 돌기 때문이다 (docs/DESIGN.md 7.3 절).
RUN_WEEK_OFFSET = 5


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
    repository = read_config("GITHUB_REPOSITORY", required=False)
    token = read_config("GITHUB_TOKEN", required=False)
    if repository and token:
        return _run_counter(repository, token)

    def unavailable(workflow: str, day: date) -> int:
        del workflow, day
        raise ValueError("GITHUB_REPOSITORY 또는 GITHUB_TOKEN 이 없어 실행 이력을 조회할 수 없습니다.")

    return unavailable


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

    health = [_weekly_slot(_previous_monday(now.date()), _health_counter())]

    return buffer_zone.render(sent_at=now, proximities=proximities, holdings=holdings, health=health)


def _previous_monday(today: date) -> date:
    """가장 최근에 지나간 월요일을 찾는다. **점검 줄이 쓴다.**

    오늘이 월요일이면 지난주 월요일을 돌려준다. 주간 알림과 버퍼존은 같은 아침에 걸릴 수
    있고 순서가 정해져 있지 않으므로, 오늘 것을 세면 아직 돌지 않은 실행을 빠진 것으로 읽는다.

    Args:
        today: 오늘 날짜.

    Returns:
        가장 최근 월요일.
    """
    offset = today.weekday()
    return today - timedelta(days=offset if offset else 7)


def _last_week_monday(today: date) -> date:
    """지난주의 월요일을 찾는다. **주간 점검이 쓴다.**

    **실행 요일에 흔들리지 않는다.** 「가장 최근 월요일」로 잡으면 화요일 이후에 돌릴 때
    이번 주를 집어 구간의 끝이 미래가 되고, 아직 오지 않은 날까지 세어 덜 돌았다고
    강조한다 — 정시 트리거가 실패했을 때의 수동 복구(docs/DESIGN.md 7.2 절)가 거짓 경고를 낸다.

    **월요일에는 두 뜻이 같은 날을 가리킨다.** 정시 실행이 월요일뿐이라 이 어긋남은
    평소에 드러나지 않는다.

    Args:
        today: 오늘 날짜.

    Returns:
        지난주 월요일.
    """
    return today - timedelta(days=today.weekday() + 7)


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


def run_usdkrw(now: datetime) -> str:
    """원달러 주간 알림 문구를 만든다.

    **지난주 구간은 실행 요일과 무관하다.** 정시 실행은 월요일 아침뿐이지만 수동 복구는
    그 뒤 아무 날에나 일어난다.

    Args:
        now: 실행 시각.

    Returns:
        보낼 문구.
    """
    end = now.date()
    start = end - timedelta(days=USDKRW_LOOKBACK_DAYS)
    # 다른 설정과 같은 길로 읽는다. `.env` 를 직접 열면 워크플로에서 못 찾는다 —
    # Actions 에는 그 파일이 없고 시크릿이 환경 변수로 들어온다
    api_key = read_config(ENV_ECOS_API_KEY)
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

    week_start = _last_week_monday(end)
    health = weekly_health(week_start, week_start + timedelta(days=RUN_WEEK_OFFSET), _health_counter())
    return usdkrw.render(sent_at=now, current=current, as_of=as_of, windows=windows, health=health)


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
            token = read_config("TELEGRAM_BOT_TOKEN", required=False)
            chat_id = read_config("TELEGRAM_CHAT_ID", required=False)
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

    telegram.send(read_config("TELEGRAM_BOT_TOKEN"), read_config("TELEGRAM_CHAT_ID"), message)
    return 0


if __name__ == "__main__":
    sys.exit(main())

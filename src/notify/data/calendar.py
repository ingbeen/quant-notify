"""미국·한국의 거래일을 판정한다.

cron 은 요일만 알고 휴장을 모른다. 휴장일에 실행이 걸리면 알림은 조용히 끝난다 —
보낼 것이 없는 날에 빈 알림을 내지 않는다.
"""

from __future__ import annotations

from datetime import date

import exchange_calendars as xcals

from notify.utils.logger import get_logger

logger = get_logger(__name__)

# 거래소 코드
US_CALENDAR = "XNYS"
KR_CALENDAR = "XKRX"


def is_trading_day(calendar_code: str, day: date) -> bool:
    """그 날이 거래일인지 본다.

    Args:
        calendar_code: 거래소 코드.
        day: 판정할 날짜.

    Returns:
        거래일이면 True.

    Raises:
        ValueError: 달력이 다루는 범위를 벗어난 날짜일 때.
    """
    calendar = xcals.get_calendar(calendar_code)

    first = calendar.first_session.date()
    last = calendar.last_session.date()
    if not first <= day <= last:
        raise ValueError(f"{calendar_code} 달력이 {day} 를 다루지 않습니다 (범위 {first} ~ {last}). " f"exchange-calendars 를 갱신하세요.")

    return bool(calendar.is_session(day.isoformat()))


def is_us_trading_day(day: date) -> bool:
    """미국 증시가 열리는 날인지 본다.

    Args:
        day: 판정할 날짜.

    Returns:
        거래일이면 True.
    """
    return is_trading_day(US_CALENDAR, day)


def is_kr_trading_day(day: date) -> bool:
    """한국 증시가 열리는 날인지 본다.

    Args:
        day: 판정할 날짜.

    Returns:
        거래일이면 True.
    """
    return is_trading_day(KR_CALENDAR, day)


def previous_trading_day(calendar_code: str, day: date) -> date:
    """그 날보다 앞선 가장 가까운 거래일을 찾는다.

    Args:
        calendar_code: 거래소 코드.
        day: 기준 날짜. 이 날은 포함하지 않는다.

    Returns:
        직전 거래일.

    Raises:
        ValueError: 달력이 다루는 범위를 벗어난 날짜일 때.
    """
    calendar = xcals.get_calendar(calendar_code)

    first = calendar.first_session.date()
    last = calendar.last_session.date()
    if not first < day <= last:
        raise ValueError(
            f"{calendar_code} 달력이 {day} 의 직전 거래일을 다루지 않습니다 (범위 {first} ~ {last}). " f"exchange-calendars 를 갱신하세요."
        )

    return calendar.previous_session(day.isoformat()).date()


def previous_us_trading_day(day: date) -> date:
    """미국 증시의 직전 거래일을 찾는다.

    Args:
        day: 기준 날짜.

    Returns:
        직전 거래일.
    """
    return previous_trading_day(US_CALENDAR, day)


def previous_kr_trading_day(day: date) -> date:
    """한국 증시의 직전 거래일을 찾는다.

    Args:
        day: 기준 날짜.

    Returns:
        직전 거래일.
    """
    return previous_trading_day(KR_CALENDAR, day)

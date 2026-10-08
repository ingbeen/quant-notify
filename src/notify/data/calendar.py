"""미국 거래일과 장 마감 시각을 판정한다. cron 은 요일만 알고 휴장을 모른다."""

from __future__ import annotations

from datetime import date, datetime

import exchange_calendars as xcals

# 뉴욕증권거래소
_US_CALENDAR = "XNYS"


def is_us_trading_day(day: date) -> bool:
    """미국 증시가 열리는 날인지 본다.

    Args:
        day: 판정할 날짜.

    Returns:
        거래일이면 True.

    Raises:
        ValueError: 달력이 다루는 범위(실행 시점 기준 20년 전 ~ 1년 뒤) 밖일 때.
    """
    return bool(xcals.get_calendar(_US_CALENDAR).is_session(day.isoformat()))


def us_session_close(day: date) -> datetime:
    """그 거래일의 미국장 마감 시각을 낸다. 조기 마감을 반영한다.

    Args:
        day: 미국 거래일.

    Returns:
        마감 시각. UTC 시간대가 붙어 있다.

    Raises:
        ValueError: 거래일이 아닐 때.
    """
    return xcals.get_calendar(_US_CALENDAR).session_close(day.isoformat()).to_pydatetime()

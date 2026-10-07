"""거래일 판정을 고정한다.

cron 은 요일만 알고 휴장을 모른다. 판정이 틀리면 휴장일에 빈 알림이 나가거나,
거래일에 알림이 통째로 빠진다.
"""

from __future__ import annotations

from datetime import date

import pytest

from notify.data.calendar import is_us_trading_day


class TestTradingDay:
    """거래일과 휴장일."""

    def test_weekday_is_a_trading_day(self) -> None:
        """평일은 거래일이다."""
        friday = date(2026, 9, 4)

        assert is_us_trading_day(friday)

    def test_weekend_is_closed(self) -> None:
        """주말은 휴장이다."""
        saturday = date(2026, 9, 5)

        assert not is_us_trading_day(saturday)

    def test_us_holiday_is_closed(self) -> None:
        """미국 공휴일은 휴장이다.

        2026-09-07 은 미국 노동절이다. 이 날을 거래일로 읽으면 다음날 아침 버퍼존이
        없는 종가를 찾다 실패 알림을 낸다.
        """
        labor_day = date(2026, 9, 7)

        assert not is_us_trading_day(labor_day)

    def test_out_of_range_raises(self) -> None:
        """달력이 다루지 않는 날짜는 예외다.

        조용히 False 를 돌려주면 알림이 통째로 빠진 것을 휴장으로 오해한다.
        """
        with pytest.raises(ValueError, match="갱신"):
            is_us_trading_day(date(2099, 1, 4))

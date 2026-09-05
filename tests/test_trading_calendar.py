"""거래일 판정을 고정한다.

cron 은 요일만 알고 휴장을 모른다. 판정이 틀리면 휴장일에 빈 알림이 나가거나,
거래일에 알림이 통째로 빠진다.
"""

from __future__ import annotations

from datetime import date

import pytest

from notify.data.calendar import (
    is_kr_trading_day,
    is_us_trading_day,
    previous_kr_trading_day,
    previous_us_trading_day,
)


class TestTradingDay:
    """거래일과 휴장일."""

    def test_weekday_is_a_trading_day(self) -> None:
        """평일은 양쪽 다 거래일이다."""
        friday = date(2026, 9, 4)

        assert is_us_trading_day(friday)
        assert is_kr_trading_day(friday)

    def test_weekend_is_closed(self) -> None:
        """주말은 양쪽 다 휴장이다."""
        saturday = date(2026, 9, 5)

        assert not is_us_trading_day(saturday)
        assert not is_kr_trading_day(saturday)

    def test_markets_differ_on_the_same_day(self) -> None:
        """같은 날에도 시장마다 다르다.

        2026-09-07 은 미국 노동절이라 뉴욕은 쉬지만 한국은 연다.
        한 달력으로 두 시장을 판정하면 이 날 알림이 어긋난다.
        """
        labor_day = date(2026, 9, 7)

        assert not is_us_trading_day(labor_day)
        assert is_kr_trading_day(labor_day)

    def test_korean_holiday_closes_only_korea(self) -> None:
        """한국 공휴일에는 한국만 쉰다.

        2026-10-09 는 한글날이다.
        """
        hangul_day = date(2026, 10, 9)

        assert not is_kr_trading_day(hangul_day)
        assert is_us_trading_day(hangul_day)

    def test_christmas_closes_both(self) -> None:
        """크리스마스는 양쪽 다 휴장이다."""
        christmas = date(2026, 12, 25)

        assert not is_us_trading_day(christmas)
        assert not is_kr_trading_day(christmas)

    def test_out_of_range_raises(self) -> None:
        """달력이 다루지 않는 날짜는 예외다.

        조용히 False 를 돌려주면 알림이 통째로 빠진 것을 휴장으로 오해한다.
        """
        with pytest.raises(ValueError, match="갱신"):
            is_us_trading_day(date(2099, 1, 4))


class TestPreviousTradingDay:
    """직전 거래일."""

    def test_finds_the_day_before(self) -> None:
        """앞선 거래일을 찾는다."""
        assert previous_us_trading_day(date(2026, 9, 4)) == date(2026, 9, 3)

    def test_skips_the_weekend(self) -> None:
        """주말을 건너뛴다. 월요일의 직전 거래일은 금요일이다."""
        assert previous_kr_trading_day(date(2026, 9, 7)) == date(2026, 9, 4)

    def test_skips_a_holiday(self) -> None:
        """휴장일도 건너뛴다.

        2026-09-08(화) 기준 미국의 직전 거래일은 노동절(09-07)이 아니라 09-04(금)이다.
        """
        assert previous_us_trading_day(date(2026, 9, 8)) == date(2026, 9, 4)

    def test_markets_differ(self) -> None:
        """같은 날 기준이어도 시장마다 직전 거래일이 다르다."""
        assert previous_us_trading_day(date(2026, 9, 8)) == date(2026, 9, 4)
        assert previous_kr_trading_day(date(2026, 9, 8)) == date(2026, 9, 7)

    def test_out_of_range_raises(self) -> None:
        """달력이 다루지 않는 날짜는 예외다."""
        with pytest.raises(ValueError, match="갱신"):
            previous_us_trading_day(date(2099, 1, 4))

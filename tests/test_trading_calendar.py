"""미국 거래일과 장 마감 판정을 고정한다. 버퍼존의 침묵과 장 마감 가드가 여기에 기댄다."""

from __future__ import annotations

from datetime import UTC, date, datetime

from notify.data.calendar import is_us_trading_day, us_session_close


class TestTradingDay:
    """거래일과 휴장일."""

    def test_us_holiday_is_closed(self) -> None:
        """미국 공휴일은 휴장이다.

        2026-09-07 은 미국 노동절이다. 이 날을 거래일로 읽으면 다음날 아침 버퍼존이
        없는 종가를 찾다 실패 알림을 낸다.
        """
        labor_day = date(2026, 9, 7)

        assert not is_us_trading_day(labor_day)

    def test_early_close_is_known(self) -> None:
        """조기 마감일의 마감 시각을 안다. 16:00 으로 박으면 그날 수동 실행을 장중으로 오판한다.

        2026-11-27 은 추수감사절 다음 날이라 13:00 ET(18:00 UTC)에 닫는다.
        """
        assert us_session_close(date(2026, 11, 27)) == datetime(2026, 11, 27, 18, 0, tzinfo=UTC)

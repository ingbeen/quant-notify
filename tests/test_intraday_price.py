"""장중 판정이 보는 두 값을 고정한다.

한국 역방향은 **그날 장중 현재가**를 전일 종가와 견준다. 그런데 장중에 일봉을 받으면
**당일 미확정 봉이 마지막에 섞여 온다.** 그것을 전일 종가로 쓰면 신호 가격이 통째로
어긋나는데, 알림 형태로는 정상으로 보여 사람이 알아차릴 수 없다.

그래서 전일 종가를 위치가 아니라 **날짜로** 고른다. 이 파일이 그 규칙을 지킨다.
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from notify.data.yfinance_client import previous_close

# 2026-09-07 은 월요일이다. 장중에 이 날 봉이 섞여 올 수 있다
TODAY = date(2026, 9, 7)


def _series(days: list[date], values: list[float]) -> pd.Series:
    """날짜를 인덱스로 갖는 종가 계열을 만든다.

    Args:
        days: 날짜들.
        values: 종가들.

    Returns:
        종가 계열.
    """
    return pd.Series(values, index=pd.DatetimeIndex([pd.Timestamp(day) for day in days]), dtype="float64")


class TestPreviousClose:
    """전일 종가 고르기."""

    def test_drops_today_bar(self) -> None:
        """당일 봉이 섞여 오면 버리고 그 앞을 쓴다.

        이 한 줄이 장중 판정의 정확성을 좌우한다.
        """
        closes = _series([date(2026, 9, 3), date(2026, 9, 4), TODAY], [105000.0, 107615.0, 106200.0])

        assert previous_close(closes, TODAY) == 107615.0

    def test_uses_the_last_row_when_today_is_absent(self) -> None:
        """당일 봉이 없으면 마지막 행이 전일 종가다."""
        closes = _series([date(2026, 9, 3), date(2026, 9, 4)], [105000.0, 107615.0])

        assert previous_close(closes, TODAY) == 107615.0

    def test_skips_holidays_and_weekends(self) -> None:
        """휴장이 껴 있어도 오늘 이전의 마지막 값을 고른다."""
        closes = _series([date(2026, 8, 28), date(2026, 9, 4)], [104000.0, 107615.0])

        assert previous_close(closes, TODAY) == 107615.0

    def test_raises_when_nothing_precedes_today(self) -> None:
        """오늘 이전 종가가 없으면 예외다. 당일 값을 전일로 쓰지 않는다."""
        closes = _series([TODAY], [106200.0])

        with pytest.raises(ValueError, match="전일 종가"):
            previous_close(closes, TODAY)

    def test_raises_on_empty_series(self) -> None:
        """계열이 비면 예외다."""
        with pytest.raises(ValueError):
            previous_close(_series([], []), TODAY)

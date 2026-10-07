"""주간 점검의 「지난주」 구간과 종가 자르기를 고정한다.

지난주 구간은 실행 요일이 아니라 달력이 정한다. 수동 복구가 그 주 아무 날에나 일어나므로,
실행 요일에 따라 구간이 밀리면 아직 오지 않은 날까지 세어 덜 돌았다는 거짓 경고가 난다.
"""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import pytest

from notify import cli
from notify.data.yfinance_client import closes_through

QQQ = "QQQ"

# 지난주의 월요일
WEEK_START = date(2026, 8, 31)

# 08-31 주의 «다음» 월요일. 이 주 아무 날에 돌려도 지난주는 08-31 주여야 한다
WEEK_AFTER = date(2026, 9, 7)


def _series(days: list[date], values: list[float], tz: str = "Asia/Seoul") -> pd.Series:
    """`Ticker.history` 가 남기는 모양의 종가 계열을 만든다.

    Args:
        days: 날짜들.
        values: 종가들.
        tz: 거래소 시간대.

    Returns:
        종가 계열.
    """
    index = pd.DatetimeIndex([pd.Timestamp(day, tz=tz) for day in days])
    return pd.Series(values, index=index, dtype="float64")


class TestLastWeekIsIndependentOfTheRunDay:
    """「지난주」가 실행 요일에 흔들리지 않는지.

    주간 알림은 월요일 아침에 돌지만 **수동 실행은 그 뒤 아무 날에나** 일어난다
    (`docs/DESIGN.md` §7.2 — 트리거가 실패하면 사람이 다시 돌린다). 실행 요일이
    구간을 밀면 점검 구간이 **미래로 넘어가** 아직 오지 않은 날까지 센다.
    """

    def test_every_run_day_in_the_week_gives_the_same_window(self) -> None:
        """같은 주 안에서는 어느 날에 돌려도 같은 지난주를 가리킨다.

        **일요일까지 센다.** 거기서 `weekday()` 가 6 이라 13일을 되짚는데, 한국에서는
        일요일을 주의 «시작» 으로 보는 관습이 있어 답이 한 주 어긋나 보이기 쉽다.
        이 함수는 `weekday()` 가 정하는 월요일 시작 주를 따른다.
        """
        windows = {cli._last_week_monday(WEEK_AFTER + timedelta(days=offset)) for offset in range(7)}

        assert windows == {WEEK_START}

    def test_monday_keeps_the_current_behaviour(self) -> None:
        """월요일 결과가 바뀌지 않는다. 정시 실행이 유일하게 돌던 경로다."""
        assert cli._last_week_monday(WEEK_AFTER) == WEEK_START

    def test_the_window_never_reaches_into_the_future(self) -> None:
        """점검 구간의 끝(토요일)이 실행일보다 앞이다. 아직 오지 않은 날을 세지 않는다."""
        for offset in range(7):
            today = WEEK_AFTER + timedelta(days=offset)
            week_end = cli._last_week_monday(today) + timedelta(days=cli.RUN_WEEK_OFFSET)

            assert week_end < today

    def test_previous_monday_still_means_the_nearest_one(self) -> None:
        """버퍼존 점검이 쓰는 쪽은 «가장 최근에 지나간» 월요일 그대로다.

        두 뜻이 한 함수에 묶여 있었고 **월요일에만 겹쳐서** 어긋남이 드러나지 않았다.
        """
        assert cli._previous_monday(WEEK_AFTER + timedelta(days=1)) == WEEK_AFTER
        assert cli._previous_monday(WEEK_AFTER) == WEEK_START


class TestClosesThrough:
    """그 날짜까지 자르기."""

    def test_cuts_off_rows_after_that_day(self) -> None:
        """뒤에 붙어 온 행을 잘라낸다. 이동평균 창이 그쪽으로 밀리지 않게 한다."""
        days = [date(2026, 9, 3), date(2026, 9, 4), date(2026, 9, 8)]
        closes = _series(days, [717.67, 718.96, 718.36], tz="America/New_York")

        through = closes_through(closes, date(2026, 9, 4), QQQ)

        assert len(through) == 2
        assert float(through.iloc[-1]) == 718.96

    def test_keeps_everything_when_that_day_is_last(self) -> None:
        """자를 것이 없으면 그대로 돌려준다."""
        days = [date(2026, 9, 3), date(2026, 9, 4)]
        closes = _series(days, [717.67, 718.96], tz="America/New_York")

        assert len(closes_through(closes, date(2026, 9, 4), QQQ)) == 2

    def test_raises_when_that_day_is_missing(self) -> None:
        """그 날짜가 없으면 멈춘다. 그 앞 행으로 대신하지 않는다."""
        days = [date(2026, 9, 3), date(2026, 9, 4)]
        closes = _series(days, [717.67, 718.96], tz="America/New_York")

        with pytest.raises(ValueError):
            closes_through(closes, date(2026, 9, 8), QQQ)

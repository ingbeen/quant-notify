"""주간 요약이 «인접한 거래일»을 견주는지 고정한다.

주간 역방향 요약은 지난주 각 날의 **일간** 등락률을 내고, 그 값을 1일 기준인 순위 등락률과
견줍니다. 그런데 `pct_change()` 는 날짜를 보지 않고 **인접한 행**을 견주므로, 계열에서 하루가
빠지면 그 자리가 **이틀치 수익률**이 되고 뒤 날짜의 이름을 달고 창에 들어옵니다.

지난주 08-31~09-04 에서 09-01 만 빠뜨리면 최고가 `+2.00% (09-02)` 에서 `+1.00% (08-31)` 로
바뀝니다. **값과 날짜가 둘 다 틀리고, 실제보다 낮게 보고합니다** — 신호에 근접했던 주를
조용했던 주로 읽게 만듭니다. 이 줄은 「신호가 없었다」를 확인하는 용도라(`docs/DESIGN.md` §4.4)
그 오해가 그대로 판단이 됩니다.

행 수만 세는 검사로는 못 잡습니다. **월요일 등락률은 전주 금요일 종가가 있어야 나오는데**
그 금요일은 창 밖이라 개수에 잡히지 않습니다. 그래서 달력이 정한 거래일마다 **그 직전
거래일과** 짝지어 냅니다.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import cast

import pandas as pd
import pytest

from notify import cli
from notify.data.calendar import KR_CALENDAR, US_CALENDAR, trading_days_between
from notify.data.yfinance_client import closes_through

KODEX = "069500.KS"
QQQ = "QQQ"

# 지난주 08-31(월) ~ 09-04(금). 08-28 은 그 전주 금요일로, 월요일 등락률에 필요하다
PRIOR_FRIDAY = date(2026, 8, 28)
WEEK_START = date(2026, 8, 31)
WEEK_END = date(2026, 9, 4)

# 이 값이면 일간 등락률이 +1.00 / -0.99 / +2.00 / +0.42 / +0.28 (%) 로 떨어진다
WEEK_DAYS = [PRIOR_FRIDAY, WEEK_START, date(2026, 9, 1), date(2026, 9, 2), date(2026, 9, 3), WEEK_END]
WEEK_CLOSES = [700.0, 707.0, 700.0, 714.0, 717.0, 719.0]

# 2026-09-07(월)은 미국 노동절 휴장이고 한국은 거래일이다
HOLIDAY_WEEK_START = date(2026, 9, 7)
HOLIDAY_WEEK_END = date(2026, 9, 11)

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


def _percent(changes: pd.Series) -> dict[str, float]:
    """등락률 계열을 대조하기 쉬운 모양으로 바꾼다.

    Args:
        changes: 등락률 계열. 날짜를 인덱스로 갖는다.

    Returns:
        `MM-DD` 를 열쇠로 갖는 백분율 사전. 소수 둘째 자리까지.
    """
    return {cast(date, day).strftime("%m-%d"): round(float(rate) * 100, 2) for day, rate in changes.items()}


class TestTradingDaysBetween:
    """달력에서 거래일을 뽑는다."""

    def test_includes_both_ends(self) -> None:
        """양끝을 포함한다."""
        days = trading_days_between(KR_CALENDAR, WEEK_START, WEEK_END)

        assert days[0] == WEEK_START
        assert days[-1] == WEEK_END
        assert len(days) == 5

    def test_skips_a_us_holiday(self) -> None:
        """미국 노동절이 낀 주는 나흘이다."""
        days = trading_days_between(US_CALENDAR, HOLIDAY_WEEK_START, HOLIDAY_WEEK_END)

        assert HOLIDAY_WEEK_START not in days
        assert len(days) == 4

    def test_korea_keeps_that_same_day(self) -> None:
        """같은 주가 한국 달력에서는 닷새다. 두 달력을 따로 봐야 하는 이유다."""
        days = trading_days_between(KR_CALENDAR, HOLIDAY_WEEK_START, HOLIDAY_WEEK_END)

        assert HOLIDAY_WEEK_START in days
        assert len(days) == 5

    def test_raises_outside_the_calendar_range(self) -> None:
        """달력이 다루지 않는 날짜는 멈춘다. 조용히 빈 목록을 돌려주지 않는다."""
        with pytest.raises(ValueError):
            trading_days_between(US_CALENDAR, date(2099, 1, 4), date(2099, 1, 8))


class TestWeeklyChangesUseAdjacentTradingDays:
    """지난주 등락률 내기."""

    def test_each_day_is_measured_against_the_previous_trading_day(self) -> None:
        """거래일마다 그 직전 거래일과 견준다."""
        closes = _series(WEEK_DAYS, WEEK_CLOSES)

        changes = cli._change_rates(closes, KODEX, KR_CALENDAR, WEEK_START, WEEK_END)

        assert _percent(changes) == {"08-31": 1.00, "09-01": -0.99, "09-02": 2.00, "09-03": 0.42, "09-04": 0.28}

    def test_monday_uses_the_previous_friday(self) -> None:
        """월요일 등락률은 창 밖인 전주 금요일 종가를 쓴다."""
        closes = _series(WEEK_DAYS, WEEK_CLOSES)

        changes = cli._change_rates(closes, KODEX, KR_CALENDAR, WEEK_START, WEEK_END)

        assert round(float(changes[WEEK_START]) * 100, 2) == 1.00

    def test_raises_when_a_day_inside_the_window_is_missing(self) -> None:
        """창 안의 하루가 비면 멈춘다. 이틀치 수익률을 하루치로 내지 않는다.

        예전 산식은 이 자리에서 최고를 `+1.00% (08-31)` 로 냈다. 실제 최고는 `+2.00% (09-02)` 다.
        """
        closes = _series(WEEK_DAYS, WEEK_CLOSES).drop(pd.Timestamp(date(2026, 9, 1), tz="Asia/Seoul"))

        with pytest.raises(ValueError, match=r"069500\.KS"):
            cli._change_rates(closes, KODEX, KR_CALENDAR, WEEK_START, WEEK_END)

    def test_raises_when_the_day_before_the_window_is_missing(self) -> None:
        """창 «직전» 거래일이 비어도 멈춘다.

        전주 금요일은 지난주 창 밖이라 **행 수를 세는 검사로는 잡히지 않는다.**
        그것이 없으면 월요일 등락률이 조용히 사흘치가 된다.
        """
        closes = _series(WEEK_DAYS, WEEK_CLOSES).drop(pd.Timestamp(PRIOR_FRIDAY, tz="Asia/Seoul"))

        with pytest.raises(ValueError, match=r"069500\.KS"):
            cli._change_rates(closes, KODEX, KR_CALENDAR, WEEK_START, WEEK_END)

    def test_us_window_skips_the_holiday(self) -> None:
        """미국 달력에서는 휴장일을 아예 세지 않는다. 그 날 종가가 없어도 멈추지 않는다."""
        days = [date(2026, 9, 4), date(2026, 9, 8), date(2026, 9, 9), date(2026, 9, 10), date(2026, 9, 11)]
        closes = _series(days, [700.0, 707.0, 700.0, 714.0, 717.0], tz="America/New_York")

        changes = cli._change_rates(closes, QQQ, US_CALENDAR, HOLIDAY_WEEK_START, HOLIDAY_WEEK_END)

        assert list(_percent(changes)) == ["09-08", "09-09", "09-10", "09-11"]
        assert _percent(changes)["09-08"] == 1.00


class TestLastWeekIsIndependentOfTheRunDay:
    """「지난주」가 실행 요일에 흔들리지 않는지.

    주간 알림은 월요일 아침에 돌지만 **수동 실행은 그 뒤 아무 날에나** 일어난다
    (`docs/DESIGN.md` §7.2 — 트리거가 실패하면 사람이 다시 돌린다). 실행 요일이
    구간을 밀면 창이 **미래로 넘어가** 아직 없는 종가를 요구하고, 복구 경로가 막힌다.
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
        """구간의 끝이 실행일보다 앞이다. 미래 거래일의 종가를 요구하지 않는다."""
        for offset in range(7):
            today = WEEK_AFTER + timedelta(days=offset)
            week_end = cli._last_week_monday(today) + timedelta(days=cli.TRADING_WEEK_OFFSET)

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

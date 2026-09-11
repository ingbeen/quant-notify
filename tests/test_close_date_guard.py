"""판정이 읽는 값이 그 날짜의 것인지 고정한다.

yfinance 는 거래일 행을 주면서 **종가만 비워** 보내는 일이 있다. 2026-09-09 오전에
SPY·QQQ·GLD·TLT 넷 모두의 09-08 행이 그랬고, 약 1시간 40분 뒤 값이 채워졌다.

빈 값은 `_extract_close` 가 떨구므로 **자취가 남지 않는다.** 남은 계열의 끝을 그대로
쓰면 하루 전 종가로 판정하게 되는데, 알림 형태로는 정상으로 보여 알아차릴 수 없다.
특히 미국 역방향은 전일 종가와 당일 종가를 함께 읽으므로, 가운데 하루가 비면
**신호 가격 전체가 어긋난다.**

그래서 위치가 아니라 **날짜로** 고르고, 없으면 멈춘다 (`docs/DESIGN.md` 7.4절
「보간하지 않습니다 — 값이 없으면 없다고 하고 멈춥니다」). 이 파일이 그 규칙을 지킨다.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pandas as pd
import pytest

from notify import cli
from notify.common_constants import TZ_KST
from notify.data.yfinance_client import close_on

KODEX = "069500.KS"
QQQ = "QQQ"

# 2026-09-07(월)은 미국 노동절 휴장이고 한국은 거래일이다. 두 달력이 갈리는 날이라
# 미국에서 09-08 의 직전 거래일은 09-04(금)로 건너뛰고, 한국에서는 09-07 이다
FRI = date(2026, 9, 4)
MON = date(2026, 9, 7)
TUE = date(2026, 9, 8)
WED = date(2026, 9, 9)

NEW_YORK = "America/New_York"
SEOUL = "Asia/Seoul"


def _series(days: list[date], values: list[float], tz: str = NEW_YORK) -> pd.Series:
    """`Ticker.history` 가 남기는 모양의 종가 계열을 만든다.

    인덱스에 **거래소 현지 tz** 가 붙는다. 날짜 비교가 여기서 어긋나면 값이 조용히 틀린다.

    Args:
        days: 날짜들.
        values: 종가들.
        tz: 거래소 시간대.

    Returns:
        종가 계열.
    """
    index = pd.DatetimeIndex([pd.Timestamp(day, tz=tz) for day in days])
    return pd.Series(values, index=index, dtype="float64")


def _at(day: date, hour: int, minute: int) -> datetime:
    """KST 실행 시각을 만든다.

    Args:
        day: 날짜.
        hour: 시.
        minute: 분.

    Returns:
        KST 시각.
    """
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=TZ_KST)


def _install_closes(monkeypatch: pytest.MonkeyPatch, closes: dict[str, pd.Series]) -> list[list[str]]:
    """`cli.fetch_closes` 를 가짜로 바꾼다.

    Args:
        monkeypatch: pytest 픽스처.
        closes: 종목별로 돌려줄 종가 계열.

    Returns:
        요청된 종목 목록이 순서대로 쌓이는 목록.
    """
    calls: list[list[str]] = []

    def fake(tickers: list[str], period: str = "1y") -> dict[str, pd.Series]:
        del period
        calls.append(list(tickers))
        return {ticker: closes[ticker] for ticker in tickers}

    monkeypatch.setattr(cli, "fetch_closes", fake)
    return calls


def _forbid_fetch(monkeypatch: pytest.MonkeyPatch) -> None:
    """휴장이면 조회 자체를 하지 않아야 한다.

    Args:
        monkeypatch: pytest 픽스처.
    """

    def never(*args: object, **kwargs: object) -> object:
        del args, kwargs
        raise AssertionError("휴장일에는 시세를 받지 않는다")

    monkeypatch.setattr(cli, "fetch_closes", never)
    monkeypatch.setattr(cli, "fetch_intraday_price", never)


class TestCloseOn:
    """그 날짜의 종가 고르기."""

    def test_picks_the_close_on_that_day(self) -> None:
        """요청한 날짜의 종가를 돌려준다."""
        closes = _series([FRI, TUE], [718.96, 718.36])

        assert close_on(closes, TUE, QQQ) == 718.36

    def test_picks_by_date_not_by_position(self) -> None:
        """마지막 행이 아니라 **요청한 날짜**를 고른다.

        뒤에 더 최근 행이 붙어 와도 판정 대상 날짜의 값을 써야 한다.
        """
        closes = _series([FRI, TUE, WED], [718.96, 718.36, 730.00])

        assert close_on(closes, TUE, QQQ) == 718.36

    def test_reads_a_new_york_index(self) -> None:
        """미국 종목의 `America/New_York` 인덱스에서도 날짜로 맞춘다."""
        closes = _series([FRI, TUE], [770.19, 765.96], tz=NEW_YORK)

        assert close_on(closes, TUE, "SPY") == 765.96

    def test_reads_a_seoul_index(self) -> None:
        """한국 종목의 `Asia/Seoul` 인덱스에서도 같다."""
        closes = _series([FRI, MON], [105720.0, 110820.0], tz=SEOUL)

        assert close_on(closes, MON, KODEX) == 110820.0

    def test_raises_when_that_day_is_missing(self) -> None:
        """그 날짜가 없으면 멈춘다. 하루 전 값으로 대신하지 않는다."""
        closes = _series([FRI], [718.96])

        with pytest.raises(ValueError):
            close_on(closes, TUE, QQQ)

    def test_message_names_the_ticker_and_both_days(self) -> None:
        """실패 문구가 종목·요청 날짜·마지막 종가일을 담는다.

        이 문구는 텔레그램 실패 알림에 그대로 실린다. 얼마나 낡았는지가 담겨야
        사용자가 다시 돌릴지 정할 수 있다 (`docs/DESIGN.md` 7.4절).
        """
        closes = _series([FRI], [718.96])

        with pytest.raises(ValueError) as caught:
            close_on(closes, TUE, QQQ)

        message = str(caught.value)
        assert QQQ in message
        assert str(TUE) in message
        assert str(FRI) in message

    def test_raises_on_empty_series(self) -> None:
        """계열이 비어도 그 자리에서 멈춘다."""
        with pytest.raises(ValueError):
            close_on(_series([], []), TUE, QQQ)


class TestUnitedStatesPricesNeedBothDays:
    """미국 역방향은 전일 종가와 당일 종가를 **둘 다** 날짜로 확인한다."""

    def test_pairs_the_target_with_the_previous_trading_day(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """직전 거래일이 휴장을 건너뛴다. 09-08 의 짝은 09-07(노동절)이 아니라 09-04 다."""
        _install_closes(monkeypatch, {QQQ: _series([FRI, TUE], [718.96, 718.36])})

        inputs = cli._united_states_prices(_at(WED, 7, 30))

        assert inputs is not None
        assert (inputs.prev_close, inputs.current) == (718.96, 718.36)
        assert inputs.last_confirmed == TUE

    def test_raises_when_the_target_close_is_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """당일 종가가 비면 멈춘다. 하루 전 종가로 판정하지 않는다."""
        _install_closes(monkeypatch, {QQQ: _series([date(2026, 9, 3), FRI], [717.67, 718.96])})

        with pytest.raises(ValueError):
            cli._united_states_prices(_at(WED, 7, 30))

    def test_raises_when_the_previous_trading_day_close_is_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """전일 종가가 비면 멈춘다.

        당일 종가만 보면 정상으로 보이는 자리다. 09-08 이 빠진 채 09-09 가 채워지면
        `iloc[-2]` 는 09-04 를 집어 **전일 종가가 나흘 전 값**이 된다.
        """
        _install_closes(monkeypatch, {QQQ: _series([FRI, WED], [718.96, 730.00])})

        with pytest.raises(ValueError):
            cli._united_states_prices(_at(date(2026, 9, 10), 7, 30))

    def test_holiday_stays_silent_without_fetching(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """휴장이면 조용히 끝낸다. 가드가 휴장을 실패로 바꾸지 않는다."""
        _forbid_fetch(monkeypatch)

        assert cli._united_states_prices(_at(TUE, 7, 30)) is None


class TestKoreaPricesNeedThePreviousTradingDay:
    """한국 역방향의 전일 종가도 날짜로 고른다."""

    def test_skips_the_unconfirmed_bar_of_today(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """장중에 섞여 온 당일 미확정 봉을 전일 종가로 쓰지 않는다."""
        _install_closes(monkeypatch, {KODEX: _series([FRI, MON, TUE], [105720.0, 110820.0, 110335.0], tz=SEOUL)})
        monkeypatch.setattr(cli, "fetch_intraday_price", lambda ticker, today: 111000.0)

        inputs = cli._korea_prices(_at(TUE, 14, 30))

        assert inputs is not None
        assert (inputs.prev_close, inputs.current) == (110820.0, 111000.0)
        assert inputs.last_confirmed == MON

    def test_raises_when_the_previous_trading_day_close_is_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """직전 한국 거래일 종가가 비면 멈춘다. 그 전날로 밀려 쓰지 않는다."""
        _install_closes(monkeypatch, {KODEX: _series([FRI, TUE], [105720.0, 110335.0], tz=SEOUL)})
        monkeypatch.setattr(cli, "fetch_intraday_price", lambda ticker, today: 111000.0)

        with pytest.raises(ValueError):
            cli._korea_prices(_at(TUE, 14, 30))

    def test_holiday_stays_silent_without_fetching(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """한국 휴장이면 조용히 끝낸다."""
        _forbid_fetch(monkeypatch)

        assert cli._korea_prices(_at(date(2026, 9, 6), 14, 30)) is None


class TestBufferZoneNeedsTheTargetClose:
    """이동평균 알림도 target 날짜의 종가로 낸다."""

    @staticmethod
    def _long_series(last_value: float) -> pd.Series:
        """이동평균을 낼 만큼 긴 계열을 만든다.

        TUE 까지 200행이고 그중 TUE 만 104.0, 나머지는 100.0 이다. 그 뒤 WED 한 행이 더 붙는다.
        target(TUE)까지 잘라 쓰면 SMA 100.02 · 근접도 +3.98% 가 나오고, WED 가 섞이면 달라진다.

        Args:
            last_value: WED 행의 종가.

        Returns:
            201행 종가 계열.
        """
        days = [TUE - timedelta(days=offset) for offset in range(199, -1, -1)] + [WED]
        return _series(days, [100.0] * 199 + [104.0, last_value])

    def _run(self, monkeypatch: pytest.MonkeyPatch, closes: dict[str, pd.Series]) -> str | None:
        """점검 줄 조회를 막고 이동평균 알림을 만든다.

        Args:
            monkeypatch: pytest 픽스처.
            closes: 종목별 종가 계열.

        Returns:
            알림 문구.
        """
        _install_closes(monkeypatch, closes)
        monkeypatch.setattr(cli, "_health_counter", lambda: (lambda workflow, day: 1))
        return cli.run_buffer_zone(_at(WED, 7, 30))

    def test_uses_the_target_close_not_the_last_row(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """뒤에 더 최근 행이 붙어 와도 target(09-08) 종가와 그 날까지의 창으로 근접도를 낸다.

        `iloc[-1]` 로 고르면 WED 값이 잡혀 근접도가 통째로 달라진다.
        """
        closes = {ticker: self._long_series(130.0) for ticker in cli.BUFFER_ZONE_TICKERS}

        message = self._run(monkeypatch, closes)

        assert message is not None
        assert message.count("+3.98%") == len(cli.BUFFER_ZONE_TICKERS)

    def test_moving_average_ignores_rows_after_the_target(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """이동평균 창도 target 에서 끊는다.

        수동 재실행을 미국 장중(22:30~05:00 KST)에 하면 당일 미확정 봉이 섞여 온다.
        그것이 200일 창에 들어가면 근접도가 0.1%p 남짓 어긋나는데, 소수 둘째 자리까지
        내므로 화면에 그대로 보인다.
        """
        closes = {ticker: self._long_series(130.0) for ticker in cli.BUFFER_ZONE_TICKERS}
        cut = {ticker: series.iloc[:-1] for ticker, series in closes.items()}

        with_extra_row = self._run(monkeypatch, closes)
        without_extra_row = self._run(monkeypatch, cut)

        assert with_extra_row == without_extra_row

    def test_raises_when_a_ticker_is_missing_the_target_close(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """한 종목이라도 target 종가가 비면 멈춘다. 반쪽 알림을 내지 않는다."""
        closes = {ticker: self._long_series(130.0) for ticker in cli.BUFFER_ZONE_TICKERS}
        missing = cli.BUFFER_ZONE_TICKERS[-1]
        closes[missing] = closes[missing].drop(closes[missing].index[-2])

        with pytest.raises(ValueError):
            self._run(monkeypatch, closes)

    def test_holiday_stays_silent_without_fetching(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """전날이 미국 휴장이면 조용히 끝낸다."""
        _forbid_fetch(monkeypatch)

        assert cli.run_buffer_zone(_at(TUE, 7, 30)) is None

"""버퍼존이 읽는 종가가 그 날짜의 확정 종가인지 고정한다.

위치가 아니라 날짜로 고르고, 없거나 아직 마감 전이면 멈춘다 (`docs/DESIGN.md` §7.4).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
import pytest

from notify import cli
from notify.common_constants import TZ_KST
from notify.data import github_runs
from notify.data.yfinance_client import closes_through

QQQ = "QQQ"

# 2026-09-07(월)은 미국 노동절 휴장이다. 09-08(화) 아침 버퍼존은 볼 종가가 없다
FRI = date(2026, 9, 4)
TUE = date(2026, 9, 8)
WED = date(2026, 9, 9)


def _series(days: list[date], values: list[float]) -> pd.Series:
    """`fetch_closes` 가 내는 모양의 종가 계열을 만든다. 거래소 현지 날짜가 인덱스다.

    Args:
        days: 날짜들.
        values: 종가들.

    Returns:
        종가 계열.
    """
    return pd.Series(values, index=pd.Index(days), dtype="float64")


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

    def fake(tickers: list[str]) -> dict[str, pd.Series]:
        calls.append(list(tickers))
        return {ticker: closes[ticker] for ticker in tickers}

    monkeypatch.setattr(cli, "fetch_closes", fake)
    return calls


def _forbid_fetch(monkeypatch: pytest.MonkeyPatch) -> None:
    """시세 조회를 하면 실패하게 만든다. 조회 전에 끝나야 하는 경우에 건다.

    Args:
        monkeypatch: pytest 픽스처.
    """

    def never(*args: object, **kwargs: object) -> object:
        del args, kwargs
        raise AssertionError("이 경우에는 시세를 받지 않는다")

    monkeypatch.setattr(cli, "fetch_closes", never)


class TestClosesThrough:
    """그 날짜까지 자르기."""

    def test_cuts_off_rows_after_that_day(self) -> None:
        """뒤에 붙어 온 행을 잘라낸다. 이동평균 창이 그쪽으로 밀리지 않게 한다."""
        closes = _series([date(2026, 9, 3), FRI, TUE], [717.67, 718.96, 718.36])

        through = closes_through(closes, FRI, QQQ)

        assert len(through) == 2
        assert float(through.iloc[-1]) == 718.96

    def test_keeps_everything_when_that_day_is_last(self) -> None:
        """자를 것이 없으면 그대로 돌려준다."""
        closes = _series([date(2026, 9, 3), FRI], [717.67, 718.96])

        assert len(closes_through(closes, FRI, QQQ)) == 2

    def test_message_names_the_ticker_and_both_days(self) -> None:
        """그 날짜가 없으면 멈추고, 실패 문구가 종목 · 요청 날짜 · 마지막 종가일을 담는다.

        얼마나 낡았는지가 담겨야 사용자가 다시 돌릴지 정할 수 있다.
        """
        closes = _series([FRI], [718.96])

        with pytest.raises(ValueError) as caught:
            closes_through(closes, TUE, QQQ)

        message = str(caught.value)
        assert QQQ in message
        assert str(TUE) in message
        assert str(FRI) in message

    def test_raises_on_empty_series(self) -> None:
        """계열이 비어도 그 자리에서 멈춘다."""
        with pytest.raises(ValueError):
            closes_through(_series([], []), TUE, QQQ)


class TestBufferZoneNeedsTheTargetClose:
    """이동평균 알림도 target 날짜의 종가로 낸다."""

    @staticmethod
    def _long_series(last_value: float) -> pd.Series:
        """이동평균을 낼 만큼 긴 계열을 만든다.

        TUE 까지 200행이고 그중 TUE 만 102.0, 나머지는 100.0 이다. 그 뒤 WED 한 행이 더 붙는다.
        target(TUE)까지 잘라 쓰면 SMA 100.01 · 근접도 +1.99% 가 나오고, WED 가 섞이면 달라진다.

        근접도를 매수선(+3%) 안에 둔다. 밖이면 SPY·QQQ 가 수치 대신 `매수선 위` 로 나와,
        WED 가 섞여도 문구가 같아 이 검사가 그 두 종목에서 꺼진다.

        Args:
            last_value: WED 행의 종가.

        Returns:
            201행 종가 계열.
        """
        days = [TUE - timedelta(days=offset) for offset in range(199, -1, -1)] + [WED]
        return _series(days, [100.0] * 199 + [102.0, last_value])

    def _run(self, monkeypatch: pytest.MonkeyPatch, closes: dict[str, pd.Series]) -> str | None:
        """점검 줄 조회를 막고 이동평균 알림을 만든다.

        Args:
            monkeypatch: pytest 픽스처.
            closes: 종목별 종가 계열.

        Returns:
            알림 문구.
        """
        _install_closes(monkeypatch, closes)
        monkeypatch.setattr(github_runs, "run_counter", lambda: (lambda workflow, day: 1))
        return cli.run_buffer_zone(_at(WED, 7, 30))

    def test_uses_the_target_close_not_the_last_row(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """뒤에 더 최근 행이 붙어 와도 target(09-08) 종가와 그 날까지의 창으로 근접도를 낸다.

        `iloc[-1]` 로 고르면 WED 값이 잡혀 근접도가 통째로 달라진다.
        """
        closes = {ticker: self._long_series(130.0) for ticker in cli.BUFFER_ZONE_TICKERS}

        message = self._run(monkeypatch, closes)

        assert message is not None
        assert message.count("+1.99%") == len(cli.BUFFER_ZONE_TICKERS)

    def test_moving_average_ignores_rows_after_the_target(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """이동평균 창도 target 에서 끊는다. target 뒤에 붙어 온 미확정 봉을 창에 넣지 않는다."""
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

    def test_holdings_are_weighted_by_the_target_close(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """보유 종목도 함께 받아 target 종가의 평가액 비중으로 적는다. 버퍼존 티커와 겹치면 한 번만 받는다."""
        body = '[[positions]]\nticker = "QLD"\nquantity = 2\n\n[[positions]]\nticker = "GLD"\nquantity = 1\n'
        (tmp_path / "positions.toml").write_text(body, encoding="utf-8")
        closes = {ticker: self._long_series(130.0) for ticker in (*cli.BUFFER_ZONE_TICKERS, "QLD")}
        calls = _install_closes(monkeypatch, closes)
        monkeypatch.setattr(github_runs, "run_counter", lambda: (lambda workflow, day: 1))

        message = cli.run_buffer_zone(_at(WED, 7, 30))

        assert calls == [[*cli.BUFFER_ZONE_TICKERS, "QLD"]]
        assert message is not None
        assert "<b>보유</b>\nQLD 2주 · 66.7%\nGLD 1주 · 33.3%" in message

    def test_holiday_stays_silent_without_fetching(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """전날이 미국 휴장이면 조용히 끝낸다."""
        _forbid_fetch(monkeypatch)

        assert cli.run_buffer_zone(_at(TUE, 7, 30)) is None

    def test_stops_before_the_us_close_without_fetching(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """미국장이 아직 마감 전이면 조회하지 않고 멈춘다.

        KST 01:00 의 target(어제)은 진행 중인 미국 세션이라, 받은 일봉의 그날 값은 확정 종가가 아니다.
        """
        _forbid_fetch(monkeypatch)

        with pytest.raises(ValueError, match="마감"):
            cli.run_buffer_zone(_at(date(2026, 9, 10), 1, 0))

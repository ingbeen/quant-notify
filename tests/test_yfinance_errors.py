"""조회 실패의 원인이 그대로 올라오는지 고정한다.

`yf.download` 는 종목별 예외를 **삼키고** 빈 프레임을 돌려준다. 그러면 실패 알림에
`YFRateLimitError` 인지 `YFPricesMissingError` 인지가 남지 않아, **다시 돌리면 될 일인지
티커가 없어진 것인지** 읽는 사람이 가릴 수 없다. 실제로 2026-09-07 14:30 실행이 429 로
실패했을 때 알림에는 그 사실이 없었고, Actions 로그를 열어야만 원인을 알 수 있었다.

그래서 예외를 그대로 올리는 `Ticker.history(raise_errors=True)` 를 쓴다. 이 파일이
그 정책을 지킨다 — 라이브러리 판이 바뀌어 다시 삼켜지면 여기서 먼저 어긋난다.
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest
from yfinance.exceptions import YFPricesMissingError, YFRateLimitError

from notify.data import yfinance_client
from notify.data.yfinance_client import fetch_closes, fetch_intraday_price, previous_close

KODEX = "069500.KS"
QQQ = "QQQ"


def _frame(values: list[float], days: list[date], tz: str = "Asia/Seoul") -> pd.DataFrame:
    """`Ticker.history` 가 주는 모양의 프레임을 만든다.

    컬럼이 **한 겹**이고 인덱스에 **거래소 현지 tz** 가 붙는다. `yf.download` 응답과
    다른 두 가지가 이것이다.

    Args:
        values: 종가들.
        days: 날짜들.
        tz: 거래소 시간대.

    Returns:
        시세 프레임.
    """
    index = pd.DatetimeIndex([pd.Timestamp(day, tz=tz) for day in days])
    return pd.DataFrame({"Close": values, "Volume": [0] * len(values)}, index=index)


def _install(monkeypatch: pytest.MonkeyPatch, responses: dict[str, pd.DataFrame | Exception]) -> list[str]:
    """가짜 `yf.Ticker` 를 심는다.

    **`yf.download` 도 함께 막는다.** 그 호출이 되살아나면 예외가 다시 삼켜지므로,
    되살아났다는 사실 자체를 실패로 만든다.

    Args:
        monkeypatch: pytest 픽스처.
        responses: 종목별로 돌려줄 프레임 또는 던질 예외.

    Returns:
        조회된 종목이 순서대로 쌓이는 목록.
    """
    calls: list[str] = []

    class FakeTicker:
        def __init__(self, ticker: str) -> None:
            self._ticker = ticker

        def history(self, **kwargs: object) -> pd.DataFrame:
            del kwargs
            calls.append(self._ticker)
            outcome = responses[self._ticker]
            if isinstance(outcome, Exception):
                raise outcome
            return outcome

    def forbidden_download(*args: object, **kwargs: object) -> object:
        del args, kwargs
        raise AssertionError("yf.download 는 종목별 예외를 삼킨다. Ticker.history 를 쓴다.")

    monkeypatch.setattr(yfinance_client.yf, "Ticker", FakeTicker)
    monkeypatch.setattr(yfinance_client.yf, "download", forbidden_download)
    return calls


class TestFetchClosesCarriesTheCause:
    """일봉 조회 실패의 원인 전달."""

    def test_rate_limit_names_the_exception_class(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """429 면 예외 클래스명이 메시지에 담긴다. 이름이 있어야 로그에서 찾을 수 있다."""
        _install(monkeypatch, {KODEX: YFRateLimitError()})

        with pytest.raises(ValueError, match="YFRateLimitError"):
            fetch_closes([KODEX])

    def test_rate_limit_keeps_the_original_message(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """라이브러리가 준 문장을 그대로 남긴다. 요약하면 재실행 판단 근거가 사라진다."""
        _install(monkeypatch, {KODEX: YFRateLimitError()})

        with pytest.raises(ValueError, match="Too Many Requests"):
            fetch_closes([KODEX])

    def test_delisted_ticker_carries_its_own_cause(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """상장폐지와 429 는 다른 실패다. 문구로 갈려야 재실행할지 정할 수 있다."""
        _install(monkeypatch, {KODEX: YFPricesMissingError(KODEX, "1y")})

        with pytest.raises(ValueError, match="YFPricesMissingError"):
            fetch_closes([KODEX])

    def test_message_names_the_failed_ticker(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """어느 종목에서 실패했는지 담는다. 여러 종목을 받을 때 이것이 없으면 못 찾는다."""
        frame = _frame([100.0], [date(2026, 9, 4)], tz="America/New_York")
        _install(monkeypatch, {QQQ: frame, KODEX: YFRateLimitError()})

        with pytest.raises(ValueError, match=r"069500\.KS"):
            fetch_closes([QQQ, KODEX])


class TestFetchClosesFailsWhole:
    """부분 성공을 만들지 않는다."""

    def test_one_failure_fails_the_whole_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """앞 종목이 멀쩡해도 뒤가 실패하면 전체가 실패한다. 반쪽 결과를 돌려주지 않는다."""
        frame = _frame([100.0], [date(2026, 9, 4)], tz="America/New_York")
        _install(monkeypatch, {QQQ: frame, KODEX: YFRateLimitError()})

        with pytest.raises(ValueError):
            fetch_closes([QQQ, KODEX])

    def test_stops_at_the_first_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """첫 실패에서 멈춘다.

        실제 실패는 429 이고, 그 상태에서 남은 종목을 부르면 같은 실패를 더 만들 뿐이다.
        """
        calls = _install(monkeypatch, {KODEX: YFRateLimitError(), QQQ: YFRateLimitError()})

        with pytest.raises(ValueError):
            fetch_closes([KODEX, QQQ])

        assert calls == [KODEX]

    def test_empty_series_is_a_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """예외가 없어도 종가가 비면 실패로 돌린다. 빈 값으로 판정에 들어가지 않는다."""
        _install(monkeypatch, {KODEX: _frame([], [])})

        with pytest.raises(ValueError, match=r"069500\.KS"):
            fetch_closes([KODEX])


class TestFetchClosesNormalPath:
    """정상 조회."""

    def test_returns_a_series_per_ticker(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """한 겹 컬럼 프레임에서 종가를 꺼낸다."""
        days = [date(2026, 9, 3), date(2026, 9, 4)]
        _install(monkeypatch, {KODEX: _frame([107615.0, 108000.0], days)})

        closes = fetch_closes([KODEX])

        assert list(closes) == [KODEX]
        assert list(closes[KODEX]) == [107615.0, 108000.0]

    def test_drops_missing_values(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """빈 값이 섞여 오면 버린다. 채우지 않는다."""
        days = [date(2026, 9, 3), date(2026, 9, 4), date(2026, 9, 7)]
        _install(monkeypatch, {KODEX: _frame([107615.0, float("nan"), 108000.0], days)})

        assert list(fetch_closes([KODEX])[KODEX]) == [107615.0, 108000.0]

    def test_asks_only_for_the_requested_tickers(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """요청한 종목만, 요청한 순서대로 조회한다."""
        frame_kr = _frame([107615.0], [date(2026, 9, 4)])
        frame_us = _frame([566.30], [date(2026, 9, 4)], tz="America/New_York")
        calls = _install(monkeypatch, {KODEX: frame_kr, QQQ: frame_us})

        fetch_closes([KODEX, QQQ])

        assert calls == [KODEX, QQQ]


class TestFetchIntradayPrice:
    """장중 조회도 같은 정책이다."""

    def test_carries_the_cause(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """장중 경로에서도 원인이 담긴다. 한국 역방향이 이 경로로 실패했다."""
        _install(monkeypatch, {KODEX: YFRateLimitError()})

        with pytest.raises(ValueError, match="YFRateLimitError"):
            fetch_intraday_price(KODEX)

    def test_takes_the_last_bar(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """마지막 봉을 현재가로 쓴다."""
        days = [date(2026, 9, 7), date(2026, 9, 7)]
        _install(monkeypatch, {KODEX: _frame([107000.0, 107500.0], days)})

        assert fetch_intraday_price(KODEX) == 107500.0

    def test_empty_frame_is_a_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """봉이 하나도 없으면 실패로 돌린다."""
        _install(monkeypatch, {KODEX: _frame([], [])})

        with pytest.raises(ValueError, match=r"069500\.KS"):
            fetch_intraday_price(KODEX)


class TestPreviousCloseOnTzAwareIndex:
    """tz 가 붙은 인덱스에서도 전일 종가를 날짜로 고른다.

    `Ticker.history` 는 `yf.download` 와 달리 거래소 현지 tz 를 인덱스에 남긴다.
    날짜 비교가 여기서 어긋나면 신호 가격이 통째로 틀리는데 알림 형태로는 정상으로 보인다.
    """

    def test_drops_today_bar_on_seoul_index(self) -> None:
        """장중에 섞여 온 당일 봉을 버린다. 인덱스가 `Asia/Seoul` 이어도 같다."""
        frame = _frame([107615.0, 108000.0], [date(2026, 9, 4), date(2026, 9, 7)])

        assert previous_close(frame["Close"], date(2026, 9, 7)) == 107615.0

    def test_drops_today_bar_on_new_york_index(self) -> None:
        """미국 종목의 `America/New_York` 인덱스에서도 같다."""
        frame = _frame([566.30, 570.00], [date(2026, 9, 3), date(2026, 9, 4)], tz="America/New_York")

        assert previous_close(frame["Close"], date(2026, 9, 4)) == 566.30

    def test_raises_when_every_bar_is_today(self) -> None:
        """오늘 이전 종가가 없으면 멈춘다. 당일 봉을 전일 종가로 대신 쓰지 않는다."""
        frame = _frame([108000.0], [date(2026, 9, 7)])

        with pytest.raises(ValueError):
            previous_close(frame["Close"], date(2026, 9, 7))

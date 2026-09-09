"""장중 판정이 보는 두 값을 고정한다.

한국 역방향은 **그날 장중 현재가**를 전일 종가와 견준다. 두 값 모두 날짜가 어긋날 수 있다.

전일 종가 쪽 — 장중에 일봉을 받으면 **당일 미확정 봉이 마지막에 섞여 온다.** 그것을
전일 종가로 쓰면 신호 가격이 통째로 어긋난다. 그래서 위치가 아니라 **직전 거래일 날짜로** 고른다.

현재가 쪽 — 마지막 1분봉이 어제 것이면 전일 종가와 엉뚱한 짝이 되어 등락률이 어긋난다.
1분봉은 20분 남짓 지연되지만 날짜는 같으므로, **날짜만** 본다.

둘 다 알림 형태로는 정상으로 보여 사람이 알아차릴 수 없다. 이 파일이 그 규칙을 지킨다.
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from notify.data import yfinance_client
from notify.data.yfinance_client import close_on, fetch_intraday_price

KODEX = "069500.KS"

# 2026-09-07 은 월요일이다. 장중에 이 날 봉이 섞여 오고, 직전 한국 거래일은 09-04(금)이다
TODAY = date(2026, 9, 7)
PREVIOUS = date(2026, 9, 4)


def _series(days: list[date], values: list[float]) -> pd.Series:
    """날짜를 인덱스로 갖는 종가 계열을 만든다.

    Args:
        days: 날짜들.
        values: 종가들.

    Returns:
        종가 계열.
    """
    return pd.Series(values, index=pd.DatetimeIndex([pd.Timestamp(day) for day in days]), dtype="float64")


def _install_intraday(monkeypatch: pytest.MonkeyPatch, days: list[date], values: list[float]) -> None:
    """1분봉을 돌려주는 가짜 `yf.Ticker` 를 심는다.

    Args:
        monkeypatch: pytest 픽스처.
        days: 봉의 날짜들.
        values: 봉의 종가들.
    """
    index = pd.DatetimeIndex([pd.Timestamp(day, tz="Asia/Seoul") for day in days])
    frame = pd.DataFrame({"Close": values, "Volume": [0] * len(values)}, index=index)

    class FakeTicker:
        def __init__(self, ticker: str) -> None:
            del ticker

        def history(self, **kwargs: object) -> pd.DataFrame:
            del kwargs
            return frame

    monkeypatch.setattr(yfinance_client.yf, "Ticker", FakeTicker)


class TestPreviousCloseIsPickedByDate:
    """전일 종가 고르기."""

    def test_drops_today_bar(self) -> None:
        """당일 봉이 섞여 오면 직전 거래일 봉을 쓴다.

        이 한 줄이 장중 판정의 정확성을 좌우한다.
        """
        closes = _series([date(2026, 9, 3), PREVIOUS, TODAY], [105000.0, 107615.0, 106200.0])

        assert close_on(closes, PREVIOUS, KODEX) == 107615.0

    def test_works_when_today_bar_is_absent(self) -> None:
        """당일 봉이 없어도 직전 거래일 봉을 그대로 고른다."""
        closes = _series([date(2026, 9, 3), PREVIOUS], [105000.0, 107615.0])

        assert close_on(closes, PREVIOUS, KODEX) == 107615.0

    def test_raises_when_the_previous_trading_day_is_missing(self) -> None:
        """직전 거래일 종가가 없으면 멈춘다. 그 전날로 밀려 쓰지 않는다."""
        closes = _series([date(2026, 8, 28), TODAY], [104000.0, 106200.0])

        with pytest.raises(ValueError, match=r"069500\.KS"):
            close_on(closes, PREVIOUS, KODEX)

    def test_raises_when_every_bar_is_today(self) -> None:
        """당일 봉밖에 없으면 멈춘다. 그것을 전일 종가로 대신 쓰지 않는다."""
        closes = _series([TODAY], [106200.0])

        with pytest.raises(ValueError):
            close_on(closes, PREVIOUS, KODEX)

    def test_raises_on_empty_series(self) -> None:
        """계열이 비면 예외다."""
        with pytest.raises(ValueError):
            close_on(_series([], []), PREVIOUS, KODEX)


class TestIntradayPriceMustBeToday:
    """현재가 고르기."""

    def test_accepts_the_last_bar_of_today(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """마지막 봉이 오늘 것이면 현재가로 쓴다. 20분 남짓 지연돼도 날짜는 오늘이다."""
        _install_intraday(monkeypatch, [TODAY, TODAY], [107000.0, 107500.0])

        assert fetch_intraday_price(KODEX, TODAY) == 107500.0

    def test_raises_when_the_last_bar_is_from_another_day(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """마지막 봉이 어제 것이면 멈춘다. 전일 종가와 엉뚱한 짝을 만들지 않는다."""
        _install_intraday(monkeypatch, [PREVIOUS, PREVIOUS], [106000.0, 106075.0])

        with pytest.raises(ValueError, match=r"069500\.KS"):
            fetch_intraday_price(KODEX, TODAY)

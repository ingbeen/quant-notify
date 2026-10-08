"""yfinance 로 일봉 조정 종가를 받는다.

조정 종가를 쓰고 `auto_adjust` 를 명시한다 — 원시 종가로 내면 이동평균이 백테스트와 어긋난다.
`yf.download` 대신 `Ticker.history(raise_errors=True)` 를 쓴다 — 앞의 것은 종목별 예외를 삼켜
실패 알림에서 원인이 사라진다 (`docs/research/데이터소스_실측.md` §2).
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

import pandas as pd
import yfinance as yf

from notify.utils.logger import get_logger

logger = get_logger(__name__)

# 받아올 기간과 봉 간격. 1년이면 200일 이동평균에 넉넉하다
_PERIOD = "1y"
_INTERVAL = "1d"

# 응답에서 읽을 컬럼
_CLOSE_COLUMN = "Close"


def _history(ticker: str) -> pd.DataFrame:
    """한 종목의 시세를 받는다.

    예외 클래스명을 함께 싣는다 — 조회 한도(`YFRateLimitError`)는 다시 돌리면 되고
    종목 소멸(`YFPricesMissingError`)은 종목을 고쳐야 한다.

    Args:
        ticker: 받을 종목.

    Returns:
        시세 프레임.

    Raises:
        ValueError: 조회가 실패했을 때.
    """
    try:
        return yf.Ticker(ticker).history(period=_PERIOD, interval=_INTERVAL, auto_adjust=True, raise_errors=True)
    except Exception as exc:
        raise ValueError(f"[{ticker}] 시세 조회에 실패했습니다: {type(exc).__name__}: {exc}") from None


def _extract_close(frame: pd.DataFrame, ticker: str) -> pd.Series:
    """응답에서 종가를 꺼내고 인덱스를 거래소 현지 날짜로 바꾼다.

    빈 종가는 버린다. 그날 행이 자취 없이 사라지므로 판정은 날짜로 값을 집는다 (`closes_through`).

    Args:
        frame: 시세 프레임. 인덱스에 거래소 현지 시간대가 붙어 있다.
        ticker: 꺼낼 종목. 문구에 쓴다.

    Returns:
        날짜를 인덱스로 갖는 종가 계열.

    Raises:
        ValueError: 종가가 응답에 없을 때.
    """
    if _CLOSE_COLUMN not in frame.columns:
        raise ValueError(f"[{ticker}] 종가가 응답에 없습니다.")

    closes = frame[_CLOSE_COLUMN].dropna()
    days = pd.DatetimeIndex(closes.index).date
    return pd.Series(closes.to_numpy(dtype="float64"), index=pd.Index(days), dtype="float64")


def fetch_closes(tickers: Sequence[str]) -> dict[str, pd.Series]:
    """종목별 조정 종가 계열을 받는다.

    한 종목이라도 실패하면 전체를 실패로 돌린다 (`docs/DESIGN.md` §7.4). **첫 실패에서 멈춘다** —
    조회 한도에 걸린 상태에서 남은 종목을 불러도 같은 실패만 늘어난다.

    Args:
        tickers: 받을 종목.

    Returns:
        종목별 종가 계열. 거래소 현지 날짜를 인덱스로 갖는다.

    Raises:
        ValueError: 조회가 실패했거나, 값이 빈 종목이나 0 이하 종가가 있을 때.
    """
    closes: dict[str, pd.Series] = {}
    for ticker in tickers:
        series = _extract_close(_history(ticker), ticker)
        if series.empty:
            raise ValueError(f"[{ticker}] 시세가 비어 있습니다. 조회를 다시 실행하세요.")
        if (series <= 0).any():
            first = series.index[series <= 0][0]
            raise ValueError(f"[{ticker}] 0 이하 종가가 있습니다 ({first}). 값을 채우지 않고 멈춥니다.")
        closes[ticker] = series

    counts = ", ".join(f"{ticker} {len(series)}행" for ticker, series in closes.items())
    logger.debug(f"조정 종가를 받았습니다 ({counts})")
    return closes


def closes_through(closes: pd.Series, day: date, ticker: str) -> pd.Series:
    """그 날짜까지의 종가만 남긴다.

    **위치가 아니라 날짜로 자른다.** 빈 종가가 떨어져 나간 날은 계열의 끝이 하루 전 값이 되고,
    장중에 받으면 당일 미확정 봉이 끝에 온다 (`docs/DESIGN.md` §7.4).

    Args:
        closes: 날짜를 인덱스로 갖는 종가 계열.
        day: 마지막으로 담을 날짜.
        ticker: 종목. 실패 문구에 쓴다.

    Returns:
        그 날짜까지의 종가. 마지막 값이 그 날짜의 종가다.

    Raises:
        ValueError: 그 날짜의 종가가 없을 때.
    """
    through = closes[closes.index <= day]
    if through.empty or through.index[-1] != day:
        latest = f"마지막 종가일 {closes.index[-1]}" if not closes.empty else "받은 종가 없음"
        raise ValueError(f"[{ticker}] {day} 종가를 받지 못했습니다 ({latest}). 조회를 다시 실행하세요.")

    return through

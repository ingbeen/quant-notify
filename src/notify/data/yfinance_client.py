"""yfinance 로 미국 상장 종목의 종가를 받는다.

**조정 종가를 쓴다.** 배당과 분할을 반영한 값이라야 백테스트가 낸 이동평균과 같은
값이 나온다. 원시 종가로 계산하면 200일 이동평균이 0.1% 남짓 어긋나는데,
근접도를 소수 둘째 자리까지 내므로 그 차이가 화면에 그대로 보인다.

기본값에 기대지 않고 `auto_adjust` 를 명시한다. 라이브러리 판이 바뀌면 기본값도 바뀐다.
"""

from __future__ import annotations

from collections.abc import Sequence

import pandas as pd
import yfinance as yf

from notify.utils.logger import get_logger

logger = get_logger(__name__)

# 받아올 기간. 200일 이동평균에 필요한 거래일보다 넉넉하다
DEFAULT_PERIOD = "1y"

# 응답에서 읽을 컬럼
_CLOSE_COLUMN = "Close"


def _extract_close(frame: pd.DataFrame, ticker: str) -> pd.Series:
    """응답에서 한 종목의 종가 계열을 꺼낸다.

    여러 종목을 함께 받으면 컬럼이 두 겹으로 오고, 한 종목만 받아도 두 겹으로 온다.

    Args:
        frame: yfinance 응답.
        ticker: 꺼낼 종목.

    Returns:
        종가 계열.

    Raises:
        ValueError: 그 종목의 종가가 응답에 없을 때.
    """
    columns = frame.columns
    try:
        column = (_CLOSE_COLUMN, ticker) if isinstance(columns, pd.MultiIndex) else _CLOSE_COLUMN
        series = frame[column]
    except KeyError:
        raise ValueError(f"[{ticker}] 종가가 응답에 없습니다.") from None

    if not isinstance(series, pd.Series):
        raise ValueError(f"[{ticker}] 종가 형식이 예상과 다릅니다.")

    return series.dropna().astype("float64")


def fetch_closes(tickers: Sequence[str], period: str = DEFAULT_PERIOD) -> dict[str, pd.Series]:
    """종목별 조정 종가 계열을 받는다.

    한 종목이라도 비면 전체를 실패로 돌린다. 반쪽 결과로 알림을 내면 읽는 사람이
    무엇이 빠졌는지 알아차리기 어렵다.

    Args:
        tickers: 받을 종목.
        period: 기간 문자열 (예: 1y).

    Returns:
        종목별 종가 계열. 날짜를 인덱스로 갖는다.

    Raises:
        ValueError: 종목 목록이 비었거나, 조회가 실패했거나, 값이 빈 종목이 있을 때.
    """
    if not tickers:
        raise ValueError("받을 종목이 없습니다.")

    try:
        frame = yf.download(list(tickers), period=period, auto_adjust=True, progress=False)
    except Exception as exc:
        raise ValueError(f"시세 조회에 실패했습니다: {exc}") from None

    if not isinstance(frame, pd.DataFrame) or frame.empty:
        raise ValueError(f"시세를 받지 못했습니다: {', '.join(tickers)}. 조회를 다시 실행하세요.")

    closes: dict[str, pd.Series] = {}
    empty: list[str] = []
    for ticker in tickers:
        series = _extract_close(frame, ticker)
        if series.empty:
            empty.append(ticker)
            continue
        closes[ticker] = series

    if empty:
        raise ValueError(f"시세가 빈 종목이 있습니다: {', '.join(empty)}. 조회를 다시 실행하세요.")

    counts = ", ".join(f"{ticker} {len(series)}행" for ticker, series in closes.items())
    logger.debug(f"조정 종가를 받았습니다 ({counts})")
    return closes

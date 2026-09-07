"""yfinance 로 시세를 받는다. 일봉 종가와 장중 현재가 둘 다 여기서 받는다.

**조정 종가를 쓴다.** 배당과 분할을 반영한 값이라야 백테스트가 낸 이동평균과 같은
값이 나온다. 원시 종가로 계산하면 200일 이동평균이 0.1% 남짓 어긋나는데,
근접도를 소수 둘째 자리까지 내므로 그 차이가 화면에 그대로 보인다.

기본값에 기대지 않고 `auto_adjust` 를 명시한다. 라이브러리 판이 바뀌면 기본값도 바뀐다.

**`yf.download` 을 쓰지 않는다.** 그것은 종목별 예외를 삼키고 빈 프레임을 돌려주므로,
조회가 왜 실패했는지가 실패 알림에서 사라진다 — 조회 한도에 걸린 것인지 종목이
없어진 것인지 가릴 수 없으면 다시 돌릴지를 정할 수 없다. `Ticker.history` 는
`raise_errors` 를 주면 예외를 그대로 올린다 (`docs/research/데이터소스_실측.md`).

**한국 종목도 여기서 받는다.** pykrx 를 쓰지 않는 이유는 일봉 종가가 이미 같은 값으로
확인됐고(`docs/research/데이터소스_실측.md`), pykrx 는 가져오는 시점에 로그인하면서
**계정 아이디를 표준출력에 직접 찍기** 때문이다. 퍼블릭 저장소는 Actions 로그가 공개다.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

import pandas as pd
import yfinance as yf

from notify.utils.logger import get_logger

logger = get_logger(__name__)

# 받아올 기간. 200일 이동평균에 필요한 거래일보다 넉넉하다
DEFAULT_PERIOD = "1y"

# 일봉 간격
DAILY_INTERVAL = "1d"

# 장중 조회 설정. 하루치 1분봉의 마지막 값이 현재가다
INTRADAY_PERIOD = "1d"
INTRADAY_INTERVAL = "1m"

# 응답에서 읽을 컬럼
_CLOSE_COLUMN = "Close"


def _history(ticker: str, period: str, interval: str) -> pd.DataFrame:
    """한 종목의 시세를 받는다.

    **실패하면 원인을 담아 올린다.** 예외 클래스명을 함께 적는 것은 조회 한도
    (`YFRateLimitError`)와 종목 소멸(`YFPricesMissingError`)이 대응이 다르기 때문이다.
    앞은 다시 돌리면 되고 뒤는 종목을 고쳐야 한다.

    Args:
        ticker: 받을 종목.
        period: 기간 문자열 (예: 1y).
        interval: 봉 간격 (예: 1d).

    Returns:
        시세 프레임.

    Raises:
        ValueError: 조회가 실패했을 때.
    """
    try:
        return yf.Ticker(ticker).history(period=period, interval=interval, auto_adjust=True, raise_errors=True)
    except Exception as exc:
        raise ValueError(f"[{ticker}] 시세 조회에 실패했습니다: {type(exc).__name__}: {exc}") from None


def _extract_close(frame: pd.DataFrame, ticker: str) -> pd.Series:
    """응답에서 종가 계열을 꺼낸다.

    Args:
        frame: 시세 프레임.
        ticker: 꺼낼 종목. 문구에 쓴다.

    Returns:
        종가 계열.

    Raises:
        ValueError: 종가가 응답에 없을 때.
    """
    if _CLOSE_COLUMN not in frame.columns:
        raise ValueError(f"[{ticker}] 종가가 응답에 없습니다.")

    return frame[_CLOSE_COLUMN].dropna().astype("float64")


def fetch_closes(tickers: Sequence[str], period: str = DEFAULT_PERIOD) -> dict[str, pd.Series]:
    """종목별 조정 종가 계열을 받는다.

    한 종목이라도 비면 전체를 실패로 돌린다. 반쪽 결과로 알림을 내면 읽는 사람이
    무엇이 빠졌는지 알아차리기 어렵다.

    **첫 실패에서 멈춘다.** 실제로 겪는 실패는 조회 한도이고, 그 상태에서 남은 종목을
    부르면 같은 실패를 더 만들 뿐이다.

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

    closes: dict[str, pd.Series] = {}
    for ticker in tickers:
        series = _extract_close(_history(ticker, period, DAILY_INTERVAL), ticker)
        if series.empty:
            raise ValueError(f"[{ticker}] 시세가 비어 있습니다. 조회를 다시 실행하세요.")
        closes[ticker] = series

    counts = ", ".join(f"{ticker} {len(series)}행" for ticker, series in closes.items())
    logger.debug(f"조정 종가를 받았습니다 ({counts})")
    return closes


def _index_date(stamp: object) -> date:
    """시세 인덱스 값을 날짜로 바꾼다.

    Args:
        stamp: 인덱스 값.

    Returns:
        날짜.

    Raises:
        RuntimeError: 인덱스가 날짜도 시각도 아닐 때.
    """
    to_date = getattr(stamp, "date", None)
    if callable(to_date):
        converted = to_date()
        if isinstance(converted, date):
            return converted
    if isinstance(stamp, date):
        return stamp

    raise RuntimeError(f"내부 불변조건 위반: 시세 인덱스가 날짜가 아닙니다: {stamp!r}")


def previous_close(closes: pd.Series, today: date) -> float:
    """오늘보다 앞선 마지막 종가를 고른다.

    **장중에 일봉을 받으면 당일 미확정 봉이 섞여 온다.** 그것을 전일 종가로 쓰면
    신호 가격이 통째로 어긋나는데, 알림 형태로는 정상으로 보여 알아차릴 수 없다.

    인덱스에는 거래소 현지 시간대가 붙어 오므로 날짜로 바꿔 견준다.

    Args:
        closes: 종가 계열. 날짜나 시각을 인덱스로 갖는다.
        today: 오늘 날짜.

    Returns:
        오늘 이전의 마지막 종가.

    Raises:
        ValueError: 오늘 이전 종가가 하나도 없을 때.
    """
    earlier = closes[[_index_date(stamp) < today for stamp in closes.index]]
    if earlier.empty:
        raise ValueError(f"{today} 이전의 종가가 없어 전일 종가를 정할 수 없습니다.")

    return float(earlier.iloc[-1])


def fetch_intraday_price(ticker: str) -> float:
    """장중 현재가를 받는다.

    하루치 1분봉의 마지막 값을 쓴다. **일봉과 같은 조정 기준으로 받는다** —
    전일 종가와 견주어 등락률을 내므로 기준이 갈리면 그 차이가 등락률에 섞인다.

    Args:
        ticker: 받을 종목.

    Returns:
        현재가.

    Raises:
        ValueError: 조회가 실패했거나 봉이 하나도 없을 때.
    """
    series = _extract_close(_history(ticker, INTRADAY_PERIOD, INTRADAY_INTERVAL), ticker)
    if series.empty:
        raise ValueError(f"[{ticker}] 장중 시세가 비어 있습니다. 장이 열려 있는지 확인하세요.")

    price = float(series.iloc[-1])
    logger.debug(f"[{ticker}] 장중 현재가를 받았습니다 ({len(series)}봉, 마지막 {series.index[-1]})")
    return price

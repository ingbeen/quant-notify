"""KODEX 200 장중 시세 소스를 실측한다.

역방향 한국 알림은 **장중 12:00 과 14:30 에 현재가를 봐야** 한다. 그런데 어느 소스가
장중 값을 주는지 검증된 바가 없다. pykrx 와 yfinance 를 같은 시각에 불러 값과 지연을 견준다.

**평일 장중(09:00~15:30 KST)에 실행해야 뜻이 있다.** 장이 닫혀 있으면 두 소스 모두
직전 거래일 종가를 돌려주므로 무엇이 장중 값인지 가릴 수 없다.

같은 실행 안에서 잠시 뒤 한 번 더 부른다. 값이 움직이면 장중 시세이고,
그대로면 확정된 종가를 받고 있는 것이다.

실행:
    poetry run python scripts/probe_intraday.py
"""

from __future__ import annotations

import os
import time
from datetime import datetime

import yfinance as yf
from dotenv import dotenv_values

from notify.common_constants import PROJECT_ROOT, TZ_KST

# pykrx 는 가져오는 시점에 로그인을 시도하고 자격증명을 환경 변수에서만 읽는다.
# 그래서 가져오기 전에 `.env` 값을 환경 변수로 올린다.
for _name, _value in dotenv_values(PROJECT_ROOT / ".env").items():
    if _name.startswith("KRX_") and _value:
        os.environ.setdefault(_name, _value)

from pykrx import stock  # noqa: E402

# KODEX 200
KRX_TICKER = "069500"
YF_TICKER = "069500.KS"

# 두 번째 조회까지 기다리는 시간 (초)
RECHECK_SECONDS = 90

# 장 시간 (KST)
MARKET_OPEN = (9, 0)
MARKET_CLOSE = (15, 30)


def _now() -> datetime:
    """현재 시각을 한국 시간으로 돌려준다.

    Returns:
        한국 시간 기준 현재 시각.
    """
    return datetime.now(TZ_KST)


def _is_market_hours(moment: datetime) -> bool:
    """장중인지 본다.

    Args:
        moment: 판정할 시각.

    Returns:
        평일 정규장 시간이면 True.
    """
    if moment.weekday() >= 5:
        return False
    minutes = moment.hour * 60 + moment.minute
    return MARKET_OPEN[0] * 60 + MARKET_OPEN[1] <= minutes <= MARKET_CLOSE[0] * 60 + MARKET_CLOSE[1]


def probe_pykrx() -> tuple[float | None, str]:
    """pykrx 로 당일 시세를 받는다.

    Returns:
        가격과 설명. 받지 못했으면 가격이 None.
    """
    today = _now().strftime("%Y%m%d")
    try:
        frame = stock.get_market_ohlcv_by_date(today, today, KRX_TICKER)
    except Exception as exc:
        return None, f"조회 실패: {exc}"

    if frame is None or frame.empty:
        return None, "당일 행이 없습니다"

    return float(frame["종가"].iloc[-1]), f"{len(frame)}행"


def probe_yfinance() -> tuple[float | None, str]:
    """yfinance 로 당일 시세를 받는다.

    Returns:
        가격과 설명. 받지 못했으면 가격이 None.
    """
    try:
        frame = yf.download(YF_TICKER, period="5d", interval="1m", auto_adjust=True, progress=False)
    except Exception as exc:
        return None, f"조회 실패: {exc}"

    if frame is None or frame.empty:
        return None, "행이 없습니다"

    close = frame["Close"]
    last_index = frame.index[-1]
    return float(close.iloc[-1].item()), f"마지막 봉 {last_index}"


def report(label: str) -> tuple[float | None, float | None]:
    """두 소스를 한 번씩 부르고 결과를 찍는다.

    Args:
        label: 회차 이름.

    Returns:
        pykrx 가격과 yfinance 가격.
    """
    print(f"\n[{label}] {_now().strftime('%Y-%m-%d %H:%M:%S')} KST")

    krx_price, krx_note = probe_pykrx()
    yf_price, yf_note = probe_yfinance()

    print(f"  pykrx      {krx_price if krx_price is not None else '없음':>12}   {krx_note}")
    print(f"  yfinance   {yf_price if yf_price is not None else '없음':>12}   {yf_note}")

    if krx_price is not None and yf_price is not None:
        print(f"  차이       {krx_price - yf_price:>12.2f}")

    return krx_price, yf_price


def main() -> None:
    """장중 여부를 밝히고 두 번 조회해 값이 움직이는지 본다."""
    now = _now()
    print(f"KRX_ID 설정됨: {bool(os.environ.get('KRX_ID'))}")
    print(f"장중 여부    : {_is_market_hours(now)}")
    if not _is_market_hours(now):
        print("  [주의] 장중이 아닙니다. 두 소스 모두 직전 종가를 돌려줄 수 있어 판정이 되지 않습니다.")

    first = report("1회차")
    print(f"\n{RECHECK_SECONDS}초 기다립니다...")
    time.sleep(RECHECK_SECONDS)
    second = report("2회차")

    print("\n[판정]")
    for name, before, after in (("pykrx", first[0], second[0]), ("yfinance", first[1], second[1])):
        if before is None or after is None:
            print(f"  {name:<10} 값을 받지 못해 판정할 수 없습니다")
        elif before == after:
            print(f"  {name:<10} 값이 그대로입니다 — 장중 시세가 아닐 수 있습니다")
        else:
            print(f"  {name:<10} 값이 움직였습니다 ({before} -> {after}) — 장중 시세입니다")


if __name__ == "__main__":
    main()

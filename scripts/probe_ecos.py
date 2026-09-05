"""ECOS 통계표·항목 코드와 응답 시간을 실측한다.

통계표 코드와 항목 코드를 기억으로 적지 않고 이 프로브로 확인한다. 코드가 어긋나면
조회는 성공하는데 다른 계열이 와서, 알림 숫자가 조용히 틀린다.

10년치 응답 시간도 함께 잰다. 워크플로 제한 시간 안에 드는지 알아야 한다.

실행:
    poetry run python scripts/probe_ecos.py
"""

from __future__ import annotations

import time
from datetime import date, timedelta

from notify.data.ecos_client import fetch_usdkrw, load_api_key, request_json

# 통계표 이름에서 찾을 키워드
KEYWORD = "환율"

# 확인할 통계표. 맞는지 이 프로브로 검증한다
CANDIDATE_STAT_CODE = "731Y003"

# 원달러 정규장 종가로 알려진 항목
CANDIDATE_ITEM_CODE = "0000003"


def probe_table_list(api_key: str) -> None:
    """통계표 목록에서 키워드가 든 표를 찾는다.

    Args:
        api_key: 인증키.
    """
    payload = request_json(api_key, "StatisticTableList", "1", "1000")
    body = payload.get("StatisticTableList")
    rows = body.get("row") if isinstance(body, dict) else []

    print(f"\n[통계표] '{KEYWORD}' 가 든 표")
    if not isinstance(rows, list):
        print("  목록을 받지 못했습니다.")
        return

    for row in rows:
        if not isinstance(row, dict):
            continue
        name = str(row.get("STAT_NAME", ""))
        if KEYWORD in name:
            print(f"  {row.get('STAT_CODE'):<12} {name}  (주기: {row.get('CYCLE')})")


def probe_item_list(api_key: str) -> None:
    """후보 통계표의 항목 목록을 본다.

    Args:
        api_key: 인증키.
    """
    payload = request_json(api_key, "StatisticItemList", "1", "100", CANDIDATE_STAT_CODE)
    body = payload.get("StatisticItemList")
    rows = body.get("row") if isinstance(body, dict) else []

    print(f"\n[항목] 통계표 {CANDIDATE_STAT_CODE}")
    if not isinstance(rows, list):
        print("  목록을 받지 못했습니다.")
        return

    for row in rows:
        if not isinstance(row, dict):
            continue
        print(f"  {row.get('ITEM_CODE'):<10} {row.get('ITEM_NAME')}  (주기: {row.get('CYCLE')})")


def probe_series(api_key: str) -> None:
    """10년치를 받아 행 수와 응답 시간을 잰다.

    Args:
        api_key: 인증키.
    """
    end = date.today()
    start = end - timedelta(days=365 * 10)

    print(f"\n[조회] {CANDIDATE_STAT_CODE} / {CANDIDATE_ITEM_CODE}  {start} ~ {end}")
    started = time.monotonic()
    series = fetch_usdkrw(api_key, CANDIDATE_STAT_CODE, CANDIDATE_ITEM_CODE, start, end)
    elapsed = time.monotonic() - started

    print(f"  행 수      {len(series)}")
    print(f"  기간       {series.index[0]} ~ {series.index[-1]}")
    print(f"  마지막 값  {series.iloc[-1]}")
    print(f"  응답 시간  {elapsed:.2f}초")


def main() -> None:
    """프로브를 차례로 실행한다."""
    api_key = load_api_key()
    probe_table_list(api_key)
    probe_item_list(api_key)
    probe_series(api_key)


if __name__ == "__main__":
    main()

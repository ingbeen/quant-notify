"""한국은행 ECOS 오픈API 로 원달러 환율을 받는다.

인증키는 **인자로 받기만 한다** — 설정을 읽는 길은 `utils/config.py` 하나다. 인증키가 요청
URL 경로에 들어가므로 예외를 여기서 가려 다시 낸다 (`docs/DESIGN.md` §3.4).
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import requests

from notify.utils.logger import get_logger, mask_credentials

logger = get_logger(__name__)

BASE_URL = "https://ecos.bok.or.kr/api"

# 원달러 정규장 종가(15:30). 비슷한 계열이 여럿이고 어느 것을 골라도 조회는 성공한다 —
# 근거는 `docs/research/데이터소스_실측.md` §1.1 · §1.2
_STAT_CODE = "731Y003"
_ITEM_CODE = "0000003"

# 응답 언어와 형식
_FORMAT = "json"
_LANG = "kr"

# 한 번에 받을 수 있는 최대 행 수
MAX_ROWS = 100000

# 조회 제한 시간 (초)
TIMEOUT_SECONDS = 30


def fetch_usdkrw(api_key: str, start: date, end: date) -> pd.Series:
    """원달러 일별 종가를 받는다.

    Args:
        api_key: 인증키.
        start: 시작일.
        end: 종료일.

    Returns:
        날짜를 인덱스로 갖는 종가 계열.

    Raises:
        ValueError: 조회가 실패했거나, ECOS 가 오류를 돌려줬거나, 받은 행이 없거나,
            숫자로 읽히지 않거나 0 이하인 값이 있을 때.
    """
    segments = [_FORMAT, _LANG, "1", str(MAX_ROWS), _STAT_CODE, "D", f"{start:%Y%m%d}", f"{end:%Y%m%d}", _ITEM_CODE]
    url = "/".join([BASE_URL, "StatisticSearch", api_key, *segments])

    try:
        response = requests.get(url, timeout=TIMEOUT_SECONDS)
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as exc:
        raise ValueError(f"ECOS 조회에 실패했습니다: {mask_credentials(str(exc))}") from None

    if not isinstance(payload, dict):
        raise ValueError("ECOS 응답 형식이 예상과 다릅니다.")

    result = payload.get("RESULT")
    if isinstance(result, dict):
        raise ValueError(f"ECOS 가 오류를 돌려줬습니다: {result.get('CODE')} {result.get('MESSAGE')}")

    body = payload.get("StatisticSearch")
    rows = body.get("row") if isinstance(body, dict) else None
    if not isinstance(rows, list) or not rows:
        raise ValueError(f"ECOS 에서 받은 환율 행이 없습니다 ({start} ~ {end}). 통계표·항목 코드를 확인하세요.")

    frame = pd.DataFrame(rows)
    index = pd.to_datetime(frame["TIME"], format="%Y%m%d").dt.date
    values = pd.to_numeric(frame["DATA_VALUE"], errors="coerce")

    series = pd.Series(values.to_numpy(), index=pd.Index(index), dtype="float64").sort_index()
    if series.isna().any():
        raise ValueError("ECOS 응답에 숫자로 읽히지 않는 환율이 있습니다. 값을 채우지 않고 멈춥니다.")
    if (series <= 0).any():
        raise ValueError("ECOS 응답에 0 이하 환율이 있습니다. 값을 채우지 않고 멈춥니다.")

    logger.debug(f"환율 {len(series)}행을 받았습니다 ({series.index[0]} ~ {series.index[-1]})")
    return series

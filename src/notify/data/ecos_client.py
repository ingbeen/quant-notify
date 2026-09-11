"""한국은행 ECOS 오픈API 로 원달러 환율을 받는다.

ECOS 는 **인증키를 요청 URL 경로에 넣는다.** 그래서 두 가지를 지킨다.

1. 인증키를 **인자로 받기만 한다.** 이 모듈은 자격증명을 찾아 읽지 않는다 — 그 일은
   `utils/config.py` 한 곳이 하고, 여기서 파일을 또 열면 읽는 길이 둘로 갈린다.
2. 예외 메시지에 주소를 그대로 담지 않는다. `requests` 의 예외는 주소를 담는데,
   이 저장소는 실행 로그가 공개되는 곳에서 돈다.
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import requests

from notify.utils.logger import get_logger, mask_credentials

logger = get_logger(__name__)

# 인증키가 담긴 환경 변수 이름. **값을 읽는 것은 `utils/config.py` 가 한다** —
# 여기서 파일을 직접 열면 워크플로에만 없는 `.env` 에 기대게 된다
ENV_ECOS_API_KEY = "ECOS_API_KEY"

BASE_URL = "https://ecos.bok.or.kr/api"

# 응답 언어와 형식
_FORMAT = "json"
_LANG = "kr"

# 한 번에 받을 수 있는 최대 행 수
MAX_ROWS = 100000

# 조회 제한 시간 (초)
TIMEOUT_SECONDS = 30


def request_json(api_key: str, service: str, *segments: str) -> dict[str, object]:
    """ECOS 에 요청을 보내고 JSON 을 받는다.

    Args:
        api_key: 인증키.
        service: 서비스 이름 (예: StatisticTableList).
        *segments: 서비스 뒤에 붙는 경로 조각.

    Returns:
        응답 JSON.

    Raises:
        ValueError: 요청이 실패했거나 응답이 JSON 이 아니거나 ECOS 가 오류를 돌려줄 때.
    """
    url = "/".join([BASE_URL, service, api_key, _FORMAT, _LANG, *segments])

    try:
        response = requests.get(url, timeout=TIMEOUT_SECONDS)
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as exc:
        raise ValueError(f"ECOS 조회에 실패했습니다: {mask_credentials(str(exc))}") from None
    except ValueError as exc:
        raise ValueError(f"ECOS 응답이 JSON 이 아닙니다: {mask_credentials(str(exc))}") from None

    if not isinstance(payload, dict):
        raise ValueError("ECOS 응답 형식이 예상과 다릅니다.")

    result = payload.get("RESULT")
    if isinstance(result, dict):
        raise ValueError(f"ECOS 가 오류를 돌려줬습니다: {result.get('CODE')} {result.get('MESSAGE')}")

    return payload


def fetch_usdkrw(api_key: str, stat_code: str, item_code: str, start: date, end: date) -> pd.Series:
    """원달러 일별 종가를 받는다.

    Args:
        api_key: 인증키.
        stat_code: 통계표 코드.
        item_code: 항목 코드.
        start: 시작일.
        end: 종료일.

    Returns:
        날짜를 인덱스로 갖는 종가 계열.

    Raises:
        ValueError: 조회가 실패했거나 받은 행이 없을 때.
    """
    payload = request_json(
        api_key,
        "StatisticSearch",
        "1",
        str(MAX_ROWS),
        stat_code,
        "D",
        start.strftime("%Y%m%d"),
        end.strftime("%Y%m%d"),
        item_code,
    )

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

    logger.debug(f"환율 {len(series)}행을 받았습니다 ({series.index[0]} ~ {series.index[-1]})")
    return series

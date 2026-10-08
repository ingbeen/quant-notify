"""GitHub Actions 실행 이력을 센다. 점검 줄이 읽는다 (`docs/DESIGN.md` §7.3)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime, time
from functools import partial

import requests

from notify.common_constants import TZ_KST
from notify.utils.config import ENV_GITHUB_REPOSITORY, ENV_GITHUB_TOKEN, read_config
from notify.utils.logger import mask_credentials

GITHUB_API = "https://api.github.com"

# 조회 제한 시간 (초)
TIMEOUT_SECONDS = 15

# 워크플로 파일 이름과 KST 날짜를 받아 그날 성공한 실행 수를 내는 함수. 테스트가 갈아 끼운다
RunCounter = Callable[[str, date], int]


def kst_day_bounds(day: date) -> tuple[datetime, datetime]:
    """KST 하루의 시작과 끝을 낸다.

    `created` 필터는 UTC 기준이라 KST 하루를 UTC 구간으로 바꿔 묻는다 (`docs/DESIGN.md` §7.3).
    **끝은 `time.max` 가 아니라 23:59:59 다.** 실행 시각이 초 단위라 마이크로초는 질의에서 잘리는데,
    `time.max` 면 그 절삭이 서식 문자열에 숨어 이웃한 날과 맞닿는지 검사할 수 없다.

    Args:
        day: KST 날짜.

    Returns:
        (하루의 시작, 하루의 끝). 시간대가 붙어 있다.
    """
    return (
        datetime.combine(day, time(0, 0, 0), tzinfo=TZ_KST),
        datetime.combine(day, time(23, 59, 59), tzinfo=TZ_KST),
    )


def _utc_text(moment: datetime) -> str:
    """시각을 UTC `Z` 표기로 적는다.

    Args:
        moment: 시간대가 붙은 시각.

    Returns:
        `2026-09-10T14:59:59Z` 형태.
    """
    return f"{moment.astimezone(UTC):%Y-%m-%dT%H:%M:%SZ}"


def count_success_runs(repository: str, token: str, workflow: str, day: date) -> int:
    """그 날 성공한 실행 수를 센다.

    Args:
        repository: `소유자/저장소` 형태.
        token: GitHub 토큰.
        workflow: 워크플로 파일 이름.
        day: 조회할 날짜. **KST 기준이다.**

    Returns:
        성공한 실행 수.

    Raises:
        ValueError: 조회가 실패했거나 응답 형식이 예상과 다를 때.
    """
    start, end = kst_day_bounds(day)
    url = f"{GITHUB_API}/repos/{repository}/actions/workflows/{workflow}/runs"
    params = {"created": f"{_utc_text(start)}..{_utc_text(end)}", "status": "success"}
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}

    try:
        response = requests.get(url, params=params, headers=headers, timeout=TIMEOUT_SECONDS)
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as exc:
        raise ValueError(f"실행 이력 조회에 실패했습니다: {mask_credentials(str(exc))}") from None

    total = payload.get("total_count") if isinstance(payload, dict) else None
    if not isinstance(total, int):
        raise ValueError("실행 이력 응답에 total_count 가 없습니다.")
    return total


def run_counter() -> RunCounter:
    """설정이 갖춰졌으면 실제 조회를, 아니면 늘 실패하는 계수 함수를 낸다.

    로컬에는 보통 `GITHUB_REPOSITORY` 가 없다. 그때 점검 줄은 「이력 조회 실패」가 되고 본 알림은 나간다.

    Returns:
        실행 수를 세는 함수.
    """
    repository = read_config(ENV_GITHUB_REPOSITORY, required=False)
    token = read_config(ENV_GITHUB_TOKEN, required=False)
    if repository and token:
        return partial(count_success_runs, repository, token)

    def unavailable(workflow: str, day: date) -> int:
        del workflow, day
        raise ValueError(f"{ENV_GITHUB_REPOSITORY} 또는 {ENV_GITHUB_TOKEN} 이 없어 실행 이력을 조회할 수 없습니다.")

    return unavailable

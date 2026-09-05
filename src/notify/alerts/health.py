"""점검 줄 — 상태를 만들지 않는 하트비트.

GitHub Actions 실행 이력을 읽을 뿐 아무것도 저장하지 않는다. 이력은 GitHub 이 이미
갖고 있고 워크플로가 읽기만 한다.

`2/2` 는 **"2번 돌았다"이지 "2번 알림이 왔다"가 아니다.** 역방향은 신호가 멀면 침묵하고
그 실행도 성공으로 끝난다. 점검이 보는 것은 실행 여부이고, 발송 여부는 알림이 왔는지로 안다.
둘을 섞으면 조용한 것이 정상인지를 다시 구분할 수 없게 된다.

**자기 자신은 셀 수 없다.** 조회하는 시점에 아직 실행 중이므로 전일과 지난주를 본다.

**조회가 실패해도 본 알림은 정상 발송한다.** 점검 때문에 알림이 막히면 안 된다.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date, timedelta

import requests

from notify.alerts.formatting import format_day
from notify.data.calendar import is_kr_trading_day, is_us_trading_day
from notify.utils.logger import get_logger

logger = get_logger(__name__)

# 워크플로 파일 이름
WORKFLOW_BUFFER_ZONE = "buffer_zone.yml"
WORKFLOW_REVERSE_KR = "reverse_rank_kr.yml"
WORKFLOW_REVERSE_US = "reverse_rank_us.yml"
WORKFLOW_USDKRW = "usdkrw.yml"

# 거래일 하루에 예정된 실행 횟수
RUNS_PER_TRADING_DAY = {
    WORKFLOW_BUFFER_ZONE: 1,
    WORKFLOW_REVERSE_KR: 2,
    WORKFLOW_REVERSE_US: 1,
}

# 조회가 실패했을 때 쓰는 표시. 본 알림은 그대로 발송한다
LOOKUP_FAILED = "조회 실패"

# 조회 제한 시간 (초)
TIMEOUT_SECONDS = 15

GITHUB_API = "https://api.github.com"

# 워크플로 이름을 실행 횟수로 바꾸는 함수. 조회를 갈아 끼울 수 있게 인자로 받는다
RunCounter = Callable[[str, date], int]


@dataclass(frozen=True)
class HealthLine:
    """점검 블록의 한 줄.

    Attributes:
        label: 무엇을 본 기간인지 (예: 전일).
        period: 그 기간의 날짜 표기.
        detail: 워크플로별 실행 횟수. 조회가 실패하면 그 사실을 적는다.
    """

    label: str
    period: str
    detail: str


def count_success_runs(repository: str, token: str, workflow: str, day: date) -> int:
    """그 날 성공한 실행 수를 센다.

    Args:
        repository: `소유자/저장소` 형태.
        token: GitHub 토큰. 워크플로가 기본 제공하는 것을 쓴다.
        workflow: 워크플로 파일 이름.
        day: 조회할 날짜.

    Returns:
        성공한 실행 수.

    Raises:
        ValueError: 조회가 실패했거나 응답 형식이 예상과 다를 때.
    """
    url = f"{GITHUB_API}/repos/{repository}/actions/workflows/{workflow}/runs"
    params = {"created": day.isoformat(), "status": "success"}
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}

    try:
        response = requests.get(url, params=params, headers=headers, timeout=TIMEOUT_SECONDS)
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as exc:
        raise ValueError(f"실행 이력 조회에 실패했습니다: {exc}") from None

    total = payload.get("total_count") if isinstance(payload, dict) else None
    if not isinstance(total, int):
        raise ValueError("실행 이력 응답에 total_count 가 없습니다.")
    return total


def expected_runs(workflow: str, day: date) -> int:
    """그 날 예정된 실행 수를 낸다.

    휴장이면 0 이다. cron 은 요일만 알고 휴장을 모르므로 여기서 가른다.

    Args:
        workflow: 워크플로 파일 이름.
        day: 판정할 날짜.

    Returns:
        예정된 실행 수.
    """
    if workflow == WORKFLOW_USDKRW:
        return 1 if day.weekday() == 0 else 0

    per_day = RUNS_PER_TRADING_DAY.get(workflow, 0)
    if workflow == WORKFLOW_REVERSE_KR:
        return per_day if is_kr_trading_day(day) else 0
    return per_day if is_us_trading_day(day) else 0


def _fraction(label: str, workflow: str, days: Sequence[date], count_runs: RunCounter) -> str:
    """워크플로 하나의 실행 수를 `label 성공/예정` 으로 적는다.

    Args:
        label: 화면에 쓸 이름.
        workflow: 워크플로 파일 이름.
        days: 볼 날짜들.
        count_runs: 실행 수를 세는 함수.

    Returns:
        `label 성공/예정` 형태.
    """
    expected = sum(expected_runs(workflow, day) for day in days)
    actual = sum(count_runs(workflow, day) for day in days)
    return f"{label} {actual}/{expected}"


def _detail(entries: Sequence[tuple[str, str]], days: Sequence[date], count_runs: RunCounter) -> str:
    """점검 상세를 만든다.

    조회가 실패해도 예외를 밖으로 내보내지 않는다. 점검 때문에 본 알림이 막히면 안 된다.

    Args:
        entries: (화면 이름, 워크플로 파일 이름) 목록.
        days: 볼 날짜들.
        count_runs: 실행 수를 세는 함수.

    Returns:
        상세 문자열. 조회가 실패하면 그 사실을 적는다.
    """
    try:
        return " · ".join(_fraction(label, workflow, days, count_runs) for label, workflow in entries)
    except Exception as exc:
        logger.warning(f"점검 조회에 실패해 본문만 보냅니다: {exc}")
        return LOOKUP_FAILED


def daily_health(previous_day: date, count_runs: RunCounter) -> HealthLine:
    """전일 이력을 담은 점검 줄을 만든다.

    Args:
        previous_day: 전 거래일.
        count_runs: 실행 수를 세는 함수.

    Returns:
        점검 줄.
    """
    # 두 번째 라벨에 「역방향」을 되풀이하지 않는다. 정본 문구가 `역방향 KR 2/2 · US 1/1` 이다
    entries = [("역방향 KR", WORKFLOW_REVERSE_KR), ("US", WORKFLOW_REVERSE_US)]
    return HealthLine(
        label="전일",
        period=format_day(previous_day),
        detail=_detail(entries, [previous_day], count_runs),
    )


def weekly_health(start: date, end: date, count_runs: RunCounter) -> HealthLine:
    """지난주 이력을 담은 점검 줄을 만든다.

    Args:
        start: 지난주 시작일.
        end: 지난주 종료일.
        count_runs: 실행 수를 세는 함수.

    Returns:
        점검 줄.

    Raises:
        ValueError: 시작일이 종료일보다 뒤일 때.
    """
    if start > end:
        raise ValueError(f"지난주 시작일({start})이 종료일({end})보다 뒤입니다.")

    days = [start + timedelta(days=offset) for offset in range((end - start).days + 1)]
    entries = [
        ("버퍼존", WORKFLOW_BUFFER_ZONE),
        ("역방향 KR", WORKFLOW_REVERSE_KR),
        ("US", WORKFLOW_REVERSE_US),
    ]
    return HealthLine(
        label="지난주",
        period=f"{format_day(start)} ~ {format_day(end)}",
        detail=_detail(entries, days, count_runs),
    )

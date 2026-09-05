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

from notify.alerts.formatting import alert, format_day
from notify.utils.logger import get_logger

logger = get_logger(__name__)

# 워크플로 파일 이름
WORKFLOW_BUFFER_ZONE = "buffer_zone.yml"
WORKFLOW_REVERSE_KR = "reverse_rank_kr.yml"
WORKFLOW_REVERSE_US = "reverse_rank_us.yml"
WORKFLOW_USDKRW = "usdkrw.yml"

# 발화 요일. date.weekday() 를 쓴다 (0=월). cron-job.org 설정과 같아야 한다
#
# 미국장 알림은 화~토다 — 한국 아침에 보는 것은 전날 미국 종가이고,
# 일·월은 전날이 항상 미국 휴장이라 부를 이유가 없다.
_US_ALERT_WEEKDAYS = frozenset({1, 2, 3, 4, 5})
_KR_ALERT_WEEKDAYS = frozenset({0, 1, 2, 3, 4})
_WEEKLY_ALERT_WEEKDAY = 0

# 한국 역방향은 하루 두 번 본다 (장중 12:00 · 14:30)
_KR_RUNS_PER_DAY = 2

# 조회가 실패했을 때 쓰는 표시. 본 알림은 그대로 발송한다
LOOKUP_FAILED = "이력 조회 실패"

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

    **요일로만 센다. 휴장 판정을 두지 않는다.** 실제 횟수는 워크플로 실행 이력을
    세는데, 휴장이어도 워크플로는 돌고 조용히 끝나며 성공으로 집계된다. 예정에만
    휴장을 반영하면 토요일과 공휴일마다 숫자가 어긋난다.

    휴장이었는지는 점검 줄이 아니라 **알림이 왔는지로** 안다.

    Args:
        workflow: 워크플로 파일 이름.
        day: 판정할 날짜.

    Returns:
        예정된 실행 수. 모르는 워크플로면 0.
    """
    weekday = day.weekday()

    if workflow == WORKFLOW_USDKRW:
        return 1 if weekday == _WEEKLY_ALERT_WEEKDAY else 0
    if workflow == WORKFLOW_REVERSE_KR:
        return _KR_RUNS_PER_DAY if weekday in _KR_ALERT_WEEKDAYS else 0
    if workflow in (WORKFLOW_BUFFER_ZONE, WORKFLOW_REVERSE_US):
        return 1 if weekday in _US_ALERT_WEEKDAYS else 0
    return 0


@dataclass(frozen=True)
class RunReport:
    """워크플로 하나를 재어 본 결과.

    Attributes:
        text: 화면에 쓸 문자열. 예정보다 적거나 조회가 실패하면 강조가 붙는다.
        lookup_failed: 실행 이력 조회 자체가 실패했는지. 실행이 모자란 것과 다르다.
    """

    text: str
    lookup_failed: bool


def measure_runs(label: str, workflow: str, days: Sequence[date], count_runs: RunCounter) -> RunReport:
    """워크플로 하나를 재서 `label 성공/예정` 으로 적는다.

    **예정보다 적게 돌았으면 강조한다.** 알림이 빠진 날을 숫자만으로는 알아차릴 수 없다.

    조회가 실패해도 예외를 올리지 않는다. 그 워크플로만 실패로 적고 나머지 숫자는 살린다 —
    한 덩어리로 뭉개면 무엇이 실패했는지 알 수 없다.

    Args:
        label: 화면에 쓸 이름. 비우면 숫자만 적는다.
        workflow: 워크플로 파일 이름.
        days: 볼 날짜들.
        count_runs: 실행 수를 세는 함수.

    Returns:
        잰 결과.
    """
    expected = sum(expected_runs(workflow, day) for day in days)

    try:
        actual = sum(count_runs(workflow, day) for day in days)
    except Exception as exc:
        logger.warning(f"{workflow} 실행 이력을 읽지 못했습니다: {exc}")
        return RunReport(alert(f"{label} {LOOKUP_FAILED}".strip()), lookup_failed=True)

    text = f"{label} {actual}/{expected}".strip()
    return RunReport(alert(text) if actual < expected else text, lookup_failed=False)


def _detail(entries: Sequence[tuple[str, str]], days: Sequence[date], count_runs: RunCounter) -> str:
    """점검 상세를 만든다.

    조회가 실패해도 예외를 밖으로 내보내지 않는다. 점검 때문에 본 알림이 막히면 안 된다.
    **전부 실패했으면 워크플로마다 같은 말을 되풀이하지 않고 한 번만 적는다.**

    Args:
        entries: (화면 이름, 워크플로 파일 이름) 목록.
        days: 볼 날짜들.
        count_runs: 실행 수를 세는 함수.

    Returns:
        상세 문자열.
    """
    reports = [measure_runs(label, workflow, days, count_runs) for label, workflow in entries]
    if reports and all(report.lookup_failed for report in reports):
        return alert(LOOKUP_FAILED)
    return " · ".join(report.text for report in reports)


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

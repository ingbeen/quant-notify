"""점검 줄 — 상태를 만들지 않는 하트비트.

두 알림이 서로의 지난 실행 수를 센다. 무엇을 언제 세고 왜 그렇게 세는지의 정본은
`docs/DESIGN.md` §7.3 이다.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta

from notify.alerts.formatting import alert, format_day
from notify.common_constants import ALERT_BUFFER_ZONE, ALERT_USDKRW
from notify.data.github_runs import RunCounter
from notify.utils.logger import get_logger

logger = get_logger(__name__)

# 워크플로 파일 이름
WORKFLOW_BUFFER_ZONE = f"{ALERT_BUFFER_ZONE}.yml"
WORKFLOW_USDKRW = f"{ALERT_USDKRW}.yml"

# 발화 요일. date.weekday() 를 쓴다 (0=월). cron-job.org 설정과 같아야 한다 (`docs/DESIGN.md` §6.4)
_BUFFER_ZONE_WEEKDAYS = frozenset({1, 2, 3, 4, 5})
_USDKRW_WEEKDAY = 0

# 조회가 실패했을 때 쓰는 표시. 본 알림은 그대로 발송한다
LOOKUP_FAILED = "이력 조회 실패"


@dataclass(frozen=True)
class HealthLine:
    """점검 블록의 한 줄.

    Attributes:
        label: 무엇을 본 기간인지 (예: 지난주).
        period: 그 기간의 날짜 표기.
        detail: 실행 횟수. 조회가 실패하면 그 사실을 적는다.
    """

    label: str
    period: str
    detail: str


def expected_runs(workflow: str, day: date) -> int:
    """그 날 예정된 실행 수를 낸다. **요일로만 센다** — 휴장을 넣지 않는다.

    Args:
        workflow: 워크플로 파일 이름.
        day: 판정할 날짜.

    Returns:
        예정된 실행 수.

    Raises:
        RuntimeError: 모르는 워크플로일 때.
    """
    weekday = day.weekday()

    if workflow == WORKFLOW_USDKRW:
        return 1 if weekday == _USDKRW_WEEKDAY else 0
    if workflow == WORKFLOW_BUFFER_ZONE:
        return 1 if weekday in _BUFFER_ZONE_WEEKDAYS else 0

    # 0 을 돌려주면 분모가 0 이 되어 덜 돌았을 때의 강조가 통째로 꺼진다.
    # 이름은 위 상수로만 들어오므로 여기 닿았다면 코드가 틀린 것이다
    raise RuntimeError(f"내부 불변조건 위반: 모르는 워크플로입니다: {workflow!r}")


def _measure_runs(label: str, workflow: str, days: Sequence[date], count_runs: RunCounter) -> str:
    """워크플로 하나를 재서 `label 성공/예정` 으로 적는다. 예정보다 적게 돌았으면 강조한다.

    조회가 실패하면 예외를 올리지 않고 그 사실만 적는다. **예정 수는 `try` 밖에서 낸다** —
    그것이 실패하면 조회 실패가 아니라 코드 버그다.

    Args:
        label: 화면에 쓸 이름. 비우면 숫자만 적는다.
        workflow: 워크플로 파일 이름.
        days: 볼 날짜들.
        count_runs: 실행 수를 세는 함수.

    Returns:
        화면에 쓸 문자열.

    Raises:
        RuntimeError: 모르는 워크플로 이름일 때.
    """
    expected = sum(expected_runs(workflow, day) for day in days)

    try:
        actual = sum(count_runs(workflow, day) for day in days)
    except ValueError as exc:
        logger.warning(f"{workflow} 실행 이력을 읽지 못했습니다: {exc}")
        return alert(LOOKUP_FAILED)

    text = f"{label} {actual}/{expected}".strip()
    return alert(text) if actual < expected else text


def _monday(day: date) -> date:
    """그 날이 속한 주의 월요일을 낸다. 주는 `weekday()` 대로 월요일에 시작한다.

    Args:
        day: 날짜.

    Returns:
        그 주의 월요일.
    """
    return day - timedelta(days=day.weekday())


def recent_weekly_health(today: date, count_runs: RunCounter) -> HealthLine:
    """이번 주 월요일에 주간 알림이 돌았는지 적는다. **버퍼존이 쓴다.**

    버퍼존은 화 ~ 토에만 여기 온다. 월요일에는 전날이 미국 휴장이라 점검 줄 전에 끝난다.

    Args:
        today: 실행일.
        count_runs: 실행 수를 세는 함수.

    Returns:
        점검 줄.
    """
    monday = _monday(today)
    return HealthLine("최근 주간", format_day(monday), _measure_runs("", WORKFLOW_USDKRW, [monday], count_runs))


def last_week_health(today: date, count_runs: RunCounter) -> HealthLine:
    """지난주 버퍼존 실행을 적는다. **주간 알림이 쓴다.**

    「지난주」는 실행 요일이 아니라 달력이 정하고, 버퍼존의 마지막 발화 요일(토)까지 본다.

    Args:
        today: 실행일.
        count_runs: 실행 수를 세는 함수.

    Returns:
        점검 줄.
    """
    start = _monday(today) - timedelta(days=7)
    days = [start + timedelta(days=offset) for offset in range(max(_BUFFER_ZONE_WEEKDAYS) + 1)]
    return HealthLine(
        label="지난주",
        period=f"{format_day(days[0])} ~ {format_day(days[-1])}",
        detail=_measure_runs("버퍼존", WORKFLOW_BUFFER_ZONE, days, count_runs),
    )

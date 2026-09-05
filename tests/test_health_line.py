"""점검 줄을 고정한다.

점검은 조용한 것과 죽은 것을 가른다. 분모(예정 횟수)가 틀리면 정상인데 이상해 보이거나
이상한데 정상으로 보인다.

**분모는 요일로만 센다.** 분자가 워크플로 실행 이력을 세므로 분모도 실행 기준이어야 한다 —
휴장이어도 워크플로는 돌고 조용히 끝나며 성공으로 집계된다. 이 파일은 그 정합을 지킨다.

조회가 실패해도 본 알림은 나가야 한다 — 점검 때문에 알림이 막히면 안 된다.
"""

from __future__ import annotations

from datetime import date

import pytest

from notify.alerts.formatting import RED_DOT
from notify.alerts.health import (
    LOOKUP_FAILED,
    WORKFLOW_BUFFER_ZONE,
    WORKFLOW_REVERSE_KR,
    WORKFLOW_REVERSE_US,
    WORKFLOW_USDKRW,
    daily_health,
    expected_runs,
    weekly_health,
)

# 2026-09-04 는 금요일이다
FRIDAY = date(2026, 9, 4)

# 2026-09-05 는 토요일이다. 미국장 알림은 이 날 전날(금) 종가를 본다
SATURDAY = date(2026, 9, 5)

# 2026-09-06 은 일요일이다
SUNDAY = date(2026, 9, 6)

# 2026-09-07 은 월요일이고 미국만 노동절로 쉰다
MONDAY = date(2026, 9, 7)

# 2026-10-05 는 월요일이고 한국이 쉰다 (추석 연휴)
KR_HOLIDAY = date(2026, 10, 5)

US_ALERTS = (WORKFLOW_BUFFER_ZONE, WORKFLOW_REVERSE_US)


def _always(count: int):
    """항상 같은 수를 돌려주는 계수 함수를 만든다.

    Args:
        count: 돌려줄 수.

    Returns:
        계수 함수.
    """

    def counter(workflow: str, day: date) -> int:
        del workflow, day
        return count

    return counter


def _raising(workflow: str, day: date) -> int:
    """조회 실패를 흉내 낸다.

    Args:
        workflow: 워크플로 이름.
        day: 날짜.

    Raises:
        ValueError: 항상.
    """
    del workflow, day
    raise ValueError("실행 이력 조회에 실패했습니다")


def _raising_only(failing: str):
    """한 워크플로만 조회가 실패하는 계수 함수를 만든다.

    Args:
        failing: 실패시킬 워크플로 이름.

    Returns:
        계수 함수.
    """

    def counter(workflow: str, day: date) -> int:
        if workflow == failing:
            raise ValueError("실행 이력 조회에 실패했습니다")
        return expected_runs(workflow, day)

    return counter


class TestExpectedRuns:
    """예정 횟수."""

    def test_reverse_kr_runs_twice_on_weekdays(self) -> None:
        """한국 역방향은 평일에 두 번 돈다."""
        assert expected_runs(WORKFLOW_REVERSE_KR, FRIDAY) == 2

    def test_us_alerts_run_once_from_tuesday_to_saturday(self) -> None:
        """미국장 알림은 화~토에 한 번씩 돈다.

        한국 아침에 보는 것은 전날 미국 종가다. 금요일 종가는 토요일 아침에 본다.
        """
        for workflow in US_ALERTS:
            assert expected_runs(workflow, FRIDAY) == 1
            assert expected_runs(workflow, SATURDAY) == 1

    def test_us_alerts_are_not_expected_on_sunday_or_monday(self) -> None:
        """일·월에는 미국장 알림이 예정되지 않는다. 전날이 항상 미국 휴장이다."""
        for workflow in US_ALERTS:
            assert expected_runs(workflow, SUNDAY) == 0
            assert expected_runs(workflow, MONDAY) == 0

    def test_reverse_kr_is_not_expected_on_weekend(self) -> None:
        """한국 역방향은 주말에 예정되지 않는다."""
        assert expected_runs(WORKFLOW_REVERSE_KR, SATURDAY) == 0
        assert expected_runs(WORKFLOW_REVERSE_KR, SUNDAY) == 0

    def test_market_holidays_do_not_change_the_count(self) -> None:
        """휴장이어도 예정 횟수는 그대로다.

        워크플로는 휴장에도 돌고 조용히 끝나며 성공으로 집계된다. 분모만 휴장을
        반영하면 그 날 숫자가 어긋난다.
        """
        assert expected_runs(WORKFLOW_REVERSE_KR, KR_HOLIDAY) == 2
        assert expected_runs(WORKFLOW_REVERSE_KR, MONDAY) == 2

    def test_weekly_alert_runs_on_monday(self) -> None:
        """주간 알림은 월요일에만 예정된다."""
        assert expected_runs(WORKFLOW_USDKRW, MONDAY) == 1
        assert expected_runs(WORKFLOW_USDKRW, FRIDAY) == 0

    def test_unknown_workflow_expects_nothing(self) -> None:
        """모르는 워크플로는 0 이다."""
        assert expected_runs("nope.yml", FRIDAY) == 0


class TestDailyHealth:
    """전일 점검 줄."""

    def test_full_run_reads_as_expected(self) -> None:
        """예정대로 돌면 분자와 분모가 같고 강조가 없다."""

        def counter(workflow: str, day: date) -> int:
            return expected_runs(workflow, day)

        line = daily_health(FRIDAY, counter)

        assert line.label == "전일"
        assert line.period == "09-04 (금)"
        assert line.detail == "역방향 KR 2/2 · US 1/1"

    def test_missing_run_is_emphasised(self) -> None:
        """예정보다 적게 돌면 그 워크플로만 강조한다.

        알림이 빠진 날은 숫자만으로 알아차릴 수 없다.
        """
        line = daily_health(FRIDAY, _always(1))

        assert line.detail == f"{RED_DOT} <b>역방향 KR 1/2</b> · US 1/1"

    def test_partial_lookup_failure_keeps_the_other_numbers(self) -> None:
        """한 워크플로만 조회가 실패하면 나머지 숫자는 살린다."""
        line = daily_health(FRIDAY, _raising_only(WORKFLOW_REVERSE_US))

        assert line.detail == f"역방향 KR 2/2 · {RED_DOT} <b>US {LOOKUP_FAILED}</b>"

    def test_total_lookup_failure_is_said_once(self) -> None:
        """전부 실패했으면 같은 말을 되풀이하지 않는다. 본 알림은 그대로 나간다."""
        line = daily_health(FRIDAY, _raising)

        assert line.detail == f"{RED_DOT} <b>{LOOKUP_FAILED}</b>"
        assert line.period == "09-04 (금)"


class TestWeeklyHealth:
    """지난주 점검 줄."""

    def test_sums_over_the_week(self) -> None:
        """한 주의 예정 횟수를 모두 더한다.

        점검 구간은 토요일까지다. 미국장 알림이 그 날에도 돌기 때문이다.
        """

        def counter(workflow: str, day: date) -> int:
            return expected_runs(workflow, day)

        line = weekly_health(date(2026, 8, 31), SATURDAY, counter)

        assert line.label == "지난주"
        assert line.period == "08-31 (월) ~ 09-05 (토)"
        assert line.detail == "버퍼존 5/5 · 역방향 KR 10/10 · US 5/5"

    def test_saturday_run_is_counted(self) -> None:
        """토요일 실행이 구간에 든다. 금요일에서 끊으면 그 날 빠짐을 못 잡는다."""

        def counter(workflow: str, day: date) -> int:
            return 0 if day == SATURDAY else expected_runs(workflow, day)

        line = weekly_health(date(2026, 8, 31), SATURDAY, counter)

        assert f"{RED_DOT} <b>버퍼존 4/5</b>" in line.detail

    def test_lookup_failure_does_not_raise(self) -> None:
        """조회가 실패해도 기간은 그대로 적는다."""
        line = weekly_health(date(2026, 8, 31), SATURDAY, _raising)

        assert line.detail == f"{RED_DOT} <b>{LOOKUP_FAILED}</b>"

    def test_reversed_period_raises(self) -> None:
        """시작일이 종료일보다 뒤면 예외다."""
        with pytest.raises(ValueError):
            weekly_health(FRIDAY, date(2026, 8, 31), _always(1))

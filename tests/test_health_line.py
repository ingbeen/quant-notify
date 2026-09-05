"""점검 줄을 고정한다.

점검은 조용한 것과 죽은 것을 가른다. 분모(예정 횟수)가 틀리면 정상인데 이상해 보이거나
이상한데 정상으로 보인다.

조회가 실패해도 본 알림은 나가야 한다 — 점검 때문에 알림이 막히면 안 된다.
"""

from __future__ import annotations

from datetime import date

import pytest

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

# 2026-09-04 는 금요일이고 양쪽 다 거래일이다
FRIDAY = date(2026, 9, 4)

# 2026-09-05 는 토요일이다
SATURDAY = date(2026, 9, 5)

# 2026-09-07 은 월요일이고 미국만 노동절로 쉰다
LABOR_DAY = date(2026, 9, 7)


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


class TestExpectedRuns:
    """예정 횟수."""

    def test_reverse_kr_runs_twice_a_trading_day(self) -> None:
        """한국 역방향은 거래일에 두 번 돈다."""
        assert expected_runs(WORKFLOW_REVERSE_KR, FRIDAY) == 2

    def test_reverse_us_runs_once_a_trading_day(self) -> None:
        """미국 역방향은 거래일에 한 번 돈다."""
        assert expected_runs(WORKFLOW_REVERSE_US, FRIDAY) == 1

    def test_buffer_zone_runs_once_a_trading_day(self) -> None:
        """버퍼존은 거래일에 한 번 돈다."""
        assert expected_runs(WORKFLOW_BUFFER_ZONE, FRIDAY) == 1

    def test_nothing_is_expected_on_weekend(self) -> None:
        """주말에는 아무것도 예정되지 않는다."""
        for workflow in (WORKFLOW_BUFFER_ZONE, WORKFLOW_REVERSE_KR, WORKFLOW_REVERSE_US):
            assert expected_runs(workflow, SATURDAY) == 0

    def test_holiday_differs_by_market(self) -> None:
        """미국 휴장일에 한국 역방향은 그대로 예정된다.

        한 달력으로 두 시장을 판정하면 이 날 분모가 틀린다.
        """
        assert expected_runs(WORKFLOW_REVERSE_US, LABOR_DAY) == 0
        assert expected_runs(WORKFLOW_REVERSE_KR, LABOR_DAY) == 2

    def test_weekly_alert_runs_on_monday(self) -> None:
        """주간 알림은 월요일에만 예정된다. 휴장과 무관하다."""
        assert expected_runs(WORKFLOW_USDKRW, LABOR_DAY) == 1
        assert expected_runs(WORKFLOW_USDKRW, FRIDAY) == 0


class TestDailyHealth:
    """전일 점검 줄."""

    def test_reports_each_workflow(self) -> None:
        """워크플로별로 성공과 예정을 함께 적는다."""
        line = daily_health(FRIDAY, _always(1))

        assert line.label == "전일"
        assert line.period == "09-04 (금)"
        assert line.detail == "역방향 KR 1/2 · US 1/1"

    def test_full_run_reads_as_expected(self) -> None:
        """예정대로 돌면 분자와 분모가 같다."""

        def counter(workflow: str, day: date) -> int:
            return expected_runs(workflow, day)

        assert daily_health(FRIDAY, counter).detail == "역방향 KR 2/2 · US 1/1"

    def test_lookup_failure_does_not_raise(self) -> None:
        """조회가 실패해도 예외를 내보내지 않는다. 본 알림은 그대로 나간다."""
        line = daily_health(FRIDAY, _raising)

        assert line.detail == LOOKUP_FAILED
        assert line.period == "09-04 (금)"


class TestWeeklyHealth:
    """지난주 점검 줄."""

    def test_sums_over_the_week(self) -> None:
        """한 주의 예정 횟수를 모두 더한다."""

        def counter(workflow: str, day: date) -> int:
            return expected_runs(workflow, day)

        line = weekly_health(date(2026, 8, 31), FRIDAY, counter)

        assert line.label == "지난주"
        assert line.period == "08-31 (월) ~ 09-04 (금)"
        assert line.detail == "버퍼존 5/5 · 역방향 KR 10/10 · US 5/5"

    def test_lookup_failure_does_not_raise(self) -> None:
        """조회가 실패해도 기간은 그대로 적는다."""
        line = weekly_health(date(2026, 8, 31), FRIDAY, _raising)

        assert line.detail == LOOKUP_FAILED

    def test_reversed_period_raises(self) -> None:
        """시작일이 종료일보다 뒤면 예외다."""
        with pytest.raises(ValueError):
            weekly_health(FRIDAY, date(2026, 8, 31), _always(1))

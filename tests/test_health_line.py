"""점검 줄을 고정한다.

점검은 조용한 것과 죽은 것을 가른다. 분모(예정 횟수)가 틀리면 정상인데 이상해 보이거나
이상한데 정상으로 보인다.

**분모는 요일로만 센다.** 분자가 워크플로 실행 이력을 세므로 분모도 실행 기준이어야 한다 —
휴장이어도 워크플로는 돌고 조용히 끝나며 성공으로 집계된다. 이 파일은 그 정합을 지킨다.

**분자는 KST 하루를 본다.** GitHub 의 `created` 필터가 UTC 기준이라, 07:20~07:30 KST 에 도는
미국장 알림은 UTC 로 전날이 된다. 날짜를 그대로 넘기면 하루 어긋난 실행을 세게 된다.

조회가 실패해도 본 알림은 나가야 한다 — 점검 때문에 알림이 막히면 안 된다.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pandas as pd
import pytest

from notify import cli
from notify.alerts import health
from notify.alerts.formatting import RED_DOT
from notify.alerts.health import (
    LOOKUP_FAILED,
    WORKFLOW_BUFFER_ZONE,
    WORKFLOW_REVERSE_KR,
    WORKFLOW_REVERSE_US,
    WORKFLOW_USDKRW,
    expected_runs,
    previous_day_health,
    today_health,
    weekly_health,
)
from notify.common_constants import MA_PERIOD, TZ_KST
from notify.state.positions import Position

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

# 조회 구간 시험에 쓰는 KST 날짜. 아래 발화 시각들이 모두 이 하루에 들어야 한다
LOOKUP_DAY = date(2026, 9, 10)

# 미국 역방향은 07:20 KST 에 돈다. UTC 로는 **전날 22:20** 이라 날짜가 하루 어긋난다
US_REVERSE_FIRED_AT = datetime(2026, 9, 9, 22, 20, tzinfo=UTC)

# 버퍼존은 07:30 KST 에 돈다. 같은 이유로 전날 22:30 이다
BUFFER_ZONE_FIRED_AT = datetime(2026, 9, 9, 22, 30, tzinfo=UTC)

# 한국 역방향은 12:00 · 14:30 KST 에 돈다. UTC 로도 같은 날짜라 여태 맞아 보였다
KR_REVERSE_FIRED_AT = (
    datetime(2026, 9, 10, 3, 0, tzinfo=UTC),
    datetime(2026, 9, 10, 5, 30, tzinfo=UTC),
)

# 버퍼존 조립을 시험하는 실행일. 금요일이고 전일(09-10)은 미국 거래일이다
RUN_DAY = date(2026, 9, 11)

# RUN_DAY 기준 지난 월요일
LAST_MONDAY = date(2026, 9, 7)


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


def _as_expected(workflow: str, day: date) -> int:
    """예정대로 전부 성공한 상황을 흉내 낸다.

    Args:
        workflow: 워크플로 이름.
        day: 날짜.

    Returns:
        그 날 예정된 실행 수.
    """
    return expected_runs(workflow, day)


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


class _FakeResponse:
    """`requests` 응답을 흉내 낸다. 테스트가 밖으로 나가지 않게 한다."""

    def __init__(self, payload: dict[str, object]) -> None:
        """응답 본문을 담는다.

        Args:
            payload: 돌려줄 본문.
        """
        self._payload = payload

    def raise_for_status(self) -> None:
        """성공 응답이므로 아무것도 하지 않는다."""

    def json(self) -> dict[str, object]:
        """응답 본문을 돌려준다.

        Returns:
            본문.
        """
        return self._payload


class TestRunLookupWindow:
    """실행 이력을 조회하는 구간.

    GitHub 의 `created` 필터는 UTC 기준인데 점검이 다루는 날짜는 KST 다.
    미국장 알림은 아침 07:20~07:30 KST 에 도는데 그것이 UTC 로는 전날 밤이라,
    날짜를 그대로 넘기면 **하루 어긋난 실행**을 세게 된다.
    """

    def test_day_runs_from_midnight_to_the_last_second(self) -> None:
        """KST 하루가 00:00:00 에서 23:59:59 까지다."""
        start, end = health.kst_day_bounds(LOOKUP_DAY)

        assert start == datetime(2026, 9, 10, 0, 0, 0, tzinfo=TZ_KST)
        assert end == datetime(2026, 9, 10, 23, 59, 59, tzinfo=TZ_KST)

    def test_morning_alerts_fall_inside_their_kst_day(self) -> None:
        """아침 알림의 발화 시각이 그 KST 날짜 구간에 든다.

        이것이 이 버그의 본체다. UTC 날짜로 물으면 이 실행들이 하루 뒤로 밀리고,
        하필 그 자리에 **같은 아침에 도는** 실행이 있어 조회 시점에 아직 진행 중이다.
        """
        start, end = health.kst_day_bounds(LOOKUP_DAY)

        assert start <= US_REVERSE_FIRED_AT <= end
        assert start <= BUFFER_ZONE_FIRED_AT <= end

    def test_korea_alerts_stay_inside_the_same_kst_day(self) -> None:
        """한국 역방향의 발화 시각도 그대로 든다.

        이쪽은 UTC 로도 날짜가 같아 여태 맞아 보였다. 고치면서 깨뜨리면 안 된다.
        """
        start, end = health.kst_day_bounds(LOOKUP_DAY)

        for fired_at in KR_REVERSE_FIRED_AT:
            assert start <= fired_at <= end

    def test_adjacent_days_neither_overlap_nor_gap(self) -> None:
        """이웃한 두 날의 구간이 맞닿는다.

        겹치면 한 실행이 두 번 세지고, 벌어지면 그 사이 실행이 사라진다.
        """
        _, first_end = health.kst_day_bounds(LOOKUP_DAY)
        second_start, _ = health.kst_day_bounds(LOOKUP_DAY + timedelta(days=1))

        assert first_end + timedelta(seconds=1) == second_start


class TestRunQuery:
    """실행 이력 질의."""

    def test_query_carries_the_kst_window(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """질의에 KST 하루 구간과 성공 필터가 함께 실린다.

        변환만 맞고 질의에 안 실리면 아무것도 고쳐지지 않는다.
        """
        captured: dict[str, object] = {}

        def fake_get(url: str, *, params: dict[str, str], headers: dict[str, str], timeout: int) -> _FakeResponse:
            del headers, timeout
            captured["url"] = url
            captured["params"] = params
            return _FakeResponse({"total_count": 1})

        monkeypatch.setattr(health.requests, "get", fake_get)
        total = health.count_success_runs("ingbeen/quant-notify", "TOKEN", WORKFLOW_REVERSE_US, LOOKUP_DAY)

        assert total == 1
        assert captured["params"] == {
            "created": "2026-09-09T15:00:00Z..2026-09-10T14:59:59Z",
            "status": "success",
        }


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

    def test_us_reverse_is_expected_whenever_buffer_zone_runs(self) -> None:
        """버퍼존이 도는 날엔 미국 역방향도 돈다.

        버퍼존이 오늘 점검을 찍으므로, 그 분모는 언제나 1 이어야 한다.
        둘의 요일이 갈라지면 도는 날마다 `0/0` 이나 `0/1` 이 뜬다.
        """
        for offset in range(7):
            day = MONDAY + timedelta(days=offset)
            if expected_runs(WORKFLOW_BUFFER_ZONE, day):
                assert expected_runs(WORKFLOW_REVERSE_US, day) == 1

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

    def test_unknown_workflow_stops(self) -> None:
        """모르는 워크플로는 멈춘다. 조용히 0 을 돌려주지 않는다.

        분모가 0 이면 `actual < expected` 가 영원히 거짓이 되어 **덜 돌았을 때의 강조가
        통째로 꺼진다** — 점검 줄이 존재하는 이유가 사라지는데 화면은 정상으로 보인다.
        워크플로 이름은 모듈 상수로만 들어오므로 모르는 이름은 **코드 버그**다.
        """
        with pytest.raises(RuntimeError, match="nope.yml"):
            expected_runs("nope.yml", FRIDAY)


class TestTodayHealth:
    """오늘 점검 줄.

    미국 역방향은 버퍼존보다 10분 먼저 돌므로 **같은 아침에** 셀 수 있다.
    역방향은 신호가 멀면 침묵하니 알림이 왔는지로는 돌았는지를 알 수 없고,
    그래서 이 줄이 그날 아침의 유일한 증거다.
    """

    def test_counts_only_the_us_reverse(self) -> None:
        """오늘 줄은 미국 역방향만 담는다.

        한국 역방향은 12:00·14:30 이라 이 시점에 아직 돌지 않았다.
        """
        line = today_health(FRIDAY, _as_expected)

        assert line.label == "오늘"
        assert line.period == "09-04 (금)"
        assert line.detail == "역방향 US 1/1"

    def test_missing_run_is_emphasised(self) -> None:
        """오늘 아침 US 가 안 돌았으면 강조한다."""
        line = today_health(FRIDAY, _always(0))

        assert line.detail == f"{RED_DOT} <b>역방향 US 0/1</b>"

    def test_lookup_failure_does_not_raise(self) -> None:
        """조회가 실패해도 기간은 그대로 적는다. 본 알림은 그대로 나간다."""
        line = today_health(FRIDAY, _raising)

        assert line.detail == f"{RED_DOT} <b>{LOOKUP_FAILED}</b>"
        assert line.period == "09-04 (금)"


class TestPreviousDayHealth:
    """전일 점검 줄.

    한국 역방향만 담는다. 미국 역방향은 당일 줄로 옮겼다.
    """

    def test_counts_only_the_korea_reverse(self) -> None:
        """예정대로 돌면 분자와 분모가 같고 강조가 없다."""
        line = previous_day_health(FRIDAY, _as_expected)

        assert line.label == "전일"
        assert line.period == "09-04 (금)"
        assert line.detail == "역방향 KR 2/2"

    def test_missing_run_is_emphasised(self) -> None:
        """예정보다 적게 돌면 강조한다. 알림이 빠진 날은 숫자만으로 알아차릴 수 없다."""
        line = previous_day_health(FRIDAY, _always(1))

        assert line.detail == f"{RED_DOT} <b>역방향 KR 1/2</b>"

    def test_lookup_failure_does_not_raise(self) -> None:
        """조회가 실패해도 기간은 그대로 적는다."""
        line = previous_day_health(FRIDAY, _raising)

        assert line.detail == f"{RED_DOT} <b>{LOOKUP_FAILED}</b>"
        assert line.period == "09-04 (금)"


class TestWeeklyHealth:
    """지난주 점검 줄."""

    def test_sums_over_the_week(self) -> None:
        """한 주의 예정 횟수를 모두 더한다.

        점검 구간은 토요일까지다. 미국장 알림이 그 날에도 돌기 때문이다.
        """
        line = weekly_health(date(2026, 8, 31), SATURDAY, _as_expected)

        assert line.label == "지난주"
        assert line.period == "08-31 (월) ~ 09-05 (토)"
        assert line.detail == "버퍼존 5/5 · 역방향 KR 10/10 · US 5/5"

    def test_saturday_run_is_counted(self) -> None:
        """토요일 실행이 구간에 든다. 금요일에서 끊으면 그 날 빠짐을 못 잡는다."""

        def counter(workflow: str, day: date) -> int:
            return 0 if day == SATURDAY else expected_runs(workflow, day)

        line = weekly_health(date(2026, 8, 31), SATURDAY, counter)

        assert f"{RED_DOT} <b>버퍼존 4/5</b>" in line.detail

    def test_partial_lookup_failure_keeps_the_other_numbers(self) -> None:
        """한 워크플로만 조회가 실패하면 나머지 숫자는 살린다.

        한 덩어리로 뭉개면 무엇이 실패했는지 알 수 없다.
        """
        line = weekly_health(date(2026, 8, 31), SATURDAY, _raising_only(WORKFLOW_REVERSE_US))

        assert line.detail == f"버퍼존 5/5 · 역방향 KR 10/10 · {RED_DOT} <b>US {LOOKUP_FAILED}</b>"

    def test_total_lookup_failure_is_said_once(self) -> None:
        """전부 실패했으면 같은 말을 되풀이하지 않는다. 본 알림은 그대로 나간다."""
        line = weekly_health(date(2026, 8, 31), SATURDAY, _raising)

        assert line.detail == f"{RED_DOT} <b>{LOOKUP_FAILED}</b>"

    def test_reversed_period_raises(self) -> None:
        """시작일이 종료일보다 뒤면 예외다."""
        with pytest.raises(ValueError):
            weekly_health(FRIDAY, date(2026, 8, 31), _always(1))


class TestBufferZoneHealthDates:
    """버퍼존이 점검 줄마다 어떤 날짜를 넘기는지 고정한다.

    줄을 하나씩 따로 부르는 테스트는 **인자를 맞바꿔도 통과한다.** 이 저장소가 실제로
    겪은 고장이 「세는 날짜가 어긋난 것」이었으므로, 조립하는 자리에서 다시 못 박는다.
    """

    @staticmethod
    def _install(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, date]]:
        """시세와 보유를 막고, 점검이 무엇을 언제 물었는지 받아 적는다.

        Args:
            monkeypatch: pytest 픽스처.

        Returns:
            (워크플로, 날짜) 기록. 물어본 순서대로 쌓인다.
        """
        target = RUN_DAY - timedelta(days=1)
        days = [target - timedelta(days=offset) for offset in range(MA_PERIOD - 1, -1, -1)]
        index = pd.DatetimeIndex([pd.Timestamp(day, tz="America/New_York") for day in days])
        closes = pd.Series([100.0] * MA_PERIOD, index=index, dtype="float64")
        asked: list[tuple[str, date]] = []

        def fetch(tickers: Sequence[str], period: str = "1y") -> dict[str, pd.Series]:
            del period
            return {ticker: closes for ticker in tickers}

        def no_positions(path: Path) -> list[Position]:
            del path
            return []

        def counter(workflow: str, day: date) -> int:
            asked.append((workflow, day))
            return expected_runs(workflow, day)

        monkeypatch.setattr(cli, "fetch_closes", fetch)
        monkeypatch.setattr(cli, "load_positions", no_positions)
        monkeypatch.setattr(cli, "_health_counter", lambda: counter)
        return asked

    def test_each_line_asks_for_the_date_its_workflow_ran(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """세 줄이 각각 제 날짜를 묻는다.

        미국 역방향만 당일이다. 전일 줄에 당일을 넘기면 아직 돌지 않은 하루를 세고,
        당일 줄에 전일을 넘기면 어제 것을 오늘로 적는다 — 둘 다 조용히 틀린다.
        """
        asked = self._install(monkeypatch)

        message = cli.run_buffer_zone(datetime(2026, 9, 11, 7, 30, tzinfo=TZ_KST))

        assert message is not None
        assert asked == [
            (WORKFLOW_REVERSE_US, RUN_DAY),
            (WORKFLOW_REVERSE_KR, RUN_DAY - timedelta(days=1)),
            (WORKFLOW_USDKRW, LAST_MONDAY),
        ]

    def test_lines_are_ordered_newest_first(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """점검 블록이 오늘 → 전일 → 최근 주간 순으로 쌓인다."""
        self._install(monkeypatch)

        message = cli.run_buffer_zone(datetime(2026, 9, 11, 7, 30, tzinfo=TZ_KST))

        assert message is not None
        assert message.endswith("오늘 09-11 (금) · 역방향 US 1/1\n전일 09-10 (목) · 역방향 KR 2/2\n최근 주간 09-07 (월) · 1/1")

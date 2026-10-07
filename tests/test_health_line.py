"""점검 줄을 고정한다.

점검은 조용한 것과 죽은 것을 가른다. 분모(예정 횟수)가 틀리면 정상인데 이상해 보이거나
이상한데 정상으로 보인다.

**분모는 요일로만 센다.** 분자가 워크플로 실행 이력을 세므로 분모도 실행 기준이어야 한다 —
휴장이어도 워크플로는 돌고 조용히 끝나며 성공으로 집계된다. 이 파일은 그 정합을 지킨다.

**분자는 KST 하루를 본다.** GitHub 의 `created` 필터가 UTC 기준이라, 07:30 KST 에 도는
아침 알림은 UTC 로 전날이 된다. 날짜를 그대로 넘기면 하루 어긋난 실행을 세게 된다.

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
    WORKFLOW_USDKRW,
    RunCounter,
    expected_runs,
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

# 2026-09-07 은 월요일이고 미국 노동절이다
MONDAY = date(2026, 9, 7)

# 2026-09-08 은 화요일이다. 버퍼존이 보는 전날(09-07)이 미국 휴장이다
AFTER_US_HOLIDAY = date(2026, 9, 8)

US_ALERTS = (WORKFLOW_BUFFER_ZONE,)

# 조회 구간 시험에 쓰는 KST 날짜. 아래 발화 시각이 이 하루에 들어야 한다
LOOKUP_DAY = date(2026, 9, 10)

# 버퍼존은 07:30 KST 에 돈다. UTC 로는 **전날 22:30** 이라 날짜가 하루 어긋난다
BUFFER_ZONE_FIRED_AT = datetime(2026, 9, 9, 22, 30, tzinfo=UTC)

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
    아침 알림은 07:30 KST 에 도는데 그것이 UTC 로는 전날 밤이라,
    날짜를 그대로 넘기면 **하루 어긋난 실행**을 세게 된다.
    """

    def test_day_runs_from_midnight_to_the_last_second(self) -> None:
        """KST 하루가 00:00:00 에서 23:59:59 까지다."""
        start, end = health.kst_day_bounds(LOOKUP_DAY)

        assert start == datetime(2026, 9, 10, 0, 0, 0, tzinfo=TZ_KST)
        assert end == datetime(2026, 9, 10, 23, 59, 59, tzinfo=TZ_KST)

    def test_morning_alerts_fall_inside_their_kst_day(self) -> None:
        """아침 알림의 발화 시각이 그 KST 날짜 구간에 든다.

        이것이 이 버그의 본체다. UTC 날짜로 물으면 이 실행이 하루 앞 날짜로 세어진다.
        """
        start, end = health.kst_day_bounds(LOOKUP_DAY)

        assert start <= BUFFER_ZONE_FIRED_AT <= end

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
        total = health.count_success_runs("ingbeen/quant-notify", "TOKEN", WORKFLOW_BUFFER_ZONE, LOOKUP_DAY)

        assert total == 1
        assert captured["params"] == {
            "created": "2026-09-09T15:00:00Z..2026-09-10T14:59:59Z",
            "status": "success",
        }


class TestExpectedRuns:
    """예정 횟수."""

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

    def test_market_holidays_do_not_change_the_count(self) -> None:
        """휴장이어도 예정 횟수는 그대로다.

        버퍼존은 전날이 미국 휴장이어도 돌고 조용히 끝나며 성공으로 집계된다. 분모만
        휴장을 반영하면 그 날 숫자가 어긋난다.
        """
        assert expected_runs(WORKFLOW_BUFFER_ZONE, AFTER_US_HOLIDAY) == 1

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


class TestWeeklyHealth:
    """지난주 점검 줄."""

    def test_sums_over_the_week(self) -> None:
        """한 주의 예정 횟수를 모두 더한다.

        점검 구간은 토요일까지다. 미국장 알림이 그 날에도 돌기 때문이다.
        """
        line = weekly_health(date(2026, 8, 31), SATURDAY, _as_expected)

        assert line.label == "지난주"
        assert line.period == "08-31 (월) ~ 09-05 (토)"
        assert line.detail == "버퍼존 5/5"

    def test_saturday_run_is_counted(self) -> None:
        """토요일 실행이 구간에 든다. 금요일에서 끊으면 그 날 빠짐을 못 잡는다."""

        def counter(workflow: str, day: date) -> int:
            return 0 if day == SATURDAY else expected_runs(workflow, day)

        line = weekly_health(date(2026, 8, 31), SATURDAY, counter)

        assert f"{RED_DOT} <b>버퍼존 4/5</b>" in line.detail

    def test_total_lookup_failure_is_said_once(self) -> None:
        """전부 실패했으면 같은 말을 되풀이하지 않는다. 본 알림은 그대로 나간다."""
        line = weekly_health(date(2026, 8, 31), SATURDAY, _raising)

        assert line.detail == f"{RED_DOT} <b>{LOOKUP_FAILED}</b>"

    def test_reversed_period_raises(self) -> None:
        """시작일이 종료일보다 뒤면 예외다."""
        with pytest.raises(ValueError):
            weekly_health(FRIDAY, date(2026, 8, 31), _always(1))


class TestBufferZoneHealthDates:
    """버퍼존이 점검 줄에 어떤 날짜를 넘기는지 고정한다.

    줄을 따로 부르는 테스트는 **조립하는 자리에서 넘기는 날짜가 틀려도 통과한다.** 이
    저장소가 실제로 겪은 고장이 「세는 날짜가 어긋난 것」이었으므로, 조립하는 자리에서 다시 못 박는다.
    """

    @staticmethod
    def _install(monkeypatch: pytest.MonkeyPatch, respond: RunCounter = expected_runs) -> list[tuple[str, date]]:
        """시세와 보유를 막고, 점검이 무엇을 언제 물었는지 받아 적는다.

        Args:
            monkeypatch: pytest 픽스처.
            respond: 물어본 워크플로와 날짜에 돌려줄 실행 수. 기본은 예정대로 다 돈 상황이다.

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
            return respond(workflow, day)

        monkeypatch.setattr(cli, "fetch_closes", fetch)
        monkeypatch.setattr(cli, "load_positions", no_positions)
        monkeypatch.setattr(cli, "_health_counter", lambda: counter)
        return asked

    def test_asks_only_for_the_last_weekly_run(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """주간 알림이 지난 월요일에 돌았는지만 묻는다.

        다른 날을 넘기면 예정이 0 인 날을 세어 `0/0` 이 되고, 주간 알림이 빠져도 드러나지 않는다.
        """
        asked = self._install(monkeypatch)

        message = cli.run_buffer_zone(datetime(2026, 9, 11, 7, 30, tzinfo=TZ_KST))

        assert message is not None
        assert asked == [(WORKFLOW_USDKRW, LAST_MONDAY)]

    def test_block_holds_the_weekly_line_only(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """점검 블록은 최근 주간 한 줄이다."""
        self._install(monkeypatch)

        message = cli.run_buffer_zone(datetime(2026, 9, 11, 7, 30, tzinfo=TZ_KST))

        assert message is not None
        assert message.endswith("<b>점검</b>\n최근 주간 09-07 (월) · 1/1")

    def test_lookup_failure_still_sends(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """실행 이력 조회가 실패해도 본 알림은 나가고, 점검 줄에 그 사실을 적는다.

        점검 때문에 알림이 막히면 안 된다. 로컬 dry-run 은 토큰이 없어 늘 이 경로를 탄다.
        """
        self._install(monkeypatch, _raising)

        message = cli.run_buffer_zone(datetime(2026, 9, 11, 7, 30, tzinfo=TZ_KST))

        assert message is not None
        assert message.endswith(f"최근 주간 09-07 (월) · {RED_DOT} <b>{LOOKUP_FAILED}</b>")

    def test_missing_weekly_run_is_emphasised(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """지난 월요일 주간 알림이 안 돌았으면 강조한다. 빠진 날은 숫자만으로 알아차릴 수 없다."""
        self._install(monkeypatch, _always(0))

        message = cli.run_buffer_zone(datetime(2026, 9, 11, 7, 30, tzinfo=TZ_KST))

        assert message is not None
        assert message.endswith(f"최근 주간 09-07 (월) · {RED_DOT} <b>0/1</b>")


class TestWeeklyAlertHealthDates:
    """주간 알림이 점검 줄에 어떤 날짜를 넘기는지 고정한다.

    지난주 구간은 실행 요일이 아니라 달력이 정한다. 화요일 수동 복구에서 이번 주를 집으면
    아직 오지 않은 날까지 세어 덜 돌았다고 거짓으로 강조한다 (`docs/DESIGN.md` §7.3).
    """

    # 화요일 수동 복구. 「가장 최근 월요일」(09-07)과 「지난주 월요일」(08-31)이 갈리는 날이다
    RECOVERY_RUN = datetime(2026, 9, 8, 7, 30, tzinfo=TZ_KST)

    @staticmethod
    def _install(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, date]]:
        """환율 조회와 설정을 막고, 점검이 무엇을 언제 물었는지 받아 적는다.

        주간 알림은 시세를 받지 않는다 — 부르면 실패로 만든다.

        Args:
            monkeypatch: pytest 픽스처.

        Returns:
            (워크플로, 날짜) 기록. 물어본 순서대로 쌓인다.
        """
        days = pd.date_range("2015-09-01", "2026-09-04", freq="D").date
        rates = pd.Series([1300.0] * len(days), index=pd.Index(days), dtype="float64")
        asked: list[tuple[str, date]] = []

        def fetch_usdkrw(api_key: str, stat_code: str, item_code: str, start: date, end: date) -> pd.Series:
            del api_key, stat_code, item_code, start, end
            return rates

        def no_closes(*args: object, **kwargs: object) -> object:
            del args, kwargs
            raise AssertionError("주간 알림은 시세를 받지 않는다")

        def counter(workflow: str, day: date) -> int:
            asked.append((workflow, day))
            return expected_runs(workflow, day)

        monkeypatch.setattr(cli, "fetch_usdkrw", fetch_usdkrw)
        monkeypatch.setattr(cli, "fetch_closes", no_closes)
        monkeypatch.setattr(cli, "read_config", lambda name, required=True: "KEY")
        monkeypatch.setattr(cli, "_health_counter", lambda: counter)
        return asked

    def test_counts_last_week_from_monday_to_saturday(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """화요일에 돌려도 지난주 월~토의 버퍼존 실행을 센다."""
        asked = self._install(monkeypatch)

        cli.run_usdkrw(self.RECOVERY_RUN)

        assert asked == [(WORKFLOW_BUFFER_ZONE, date(2026, 8, 31) + timedelta(days=offset)) for offset in range(6)]

    def test_block_ends_the_alert(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """점검 블록이 지난주 구간과 버퍼존 실행 수로 문구를 끝낸다."""
        self._install(monkeypatch)

        message = cli.run_usdkrw(self.RECOVERY_RUN)

        assert message.endswith("<b>점검</b>\n지난주 08-31 (월) ~ 09-05 (토)\n버퍼존 5/5")

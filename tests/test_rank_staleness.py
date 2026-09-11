"""순위 등락률이 낡았는지 판정하는 규칙을 고정한다.

이 판정은 두 방향으로 조용히 틀릴 수 있어 테스트를 먼저 세운다.

하나는 **경고가 꺼지지 않는 것**이다. 20위 안에 든 날은 갱신한 뒤에도
`등락률 >= 새 20위` 를 만족한다 — 새 20위가 그 값 자신이거나 그보다 낮기 때문이다.
그래서 도달 여부만 보면 경고가 영구히 켜지고, 흔해진 경고는 정작 사건일 때 묻힌다.

다른 하나는 **검사가 조용히 꺼지는 것**이다. 사람이 손으로 적는 파일이라
`data_to` 에 미래 날짜가 들어올 수 있고, 그러면 창이 비어 아무것도 검사하지 않는데
알림은 정상으로 보인다.

판정 규격은 `reference/역방향_매매_규칙.md` 1.5 절이 정본이다.
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from notify.alerts.reverse_rank import (
    Direction,
    unreflected_days,
    unreflected_window,
)
from notify.state.reverse_rank import RankThresholds

# 순위 값이 매겨진 마지막 날. `state/reverse_rank.toml` 의 kodex200 실측값이다
DATA_TO = date(2026, 8, 26)

# 마지막 확정 종가일. 한국 역방향이 장중에 보는 직전 거래일이다
LAST_CONFIRMED = date(2026, 9, 10)

# 받은 종가 계열에서 등락률을 낼 수 있는 첫 거래일. 첫 날은 직전 종가가 없어 빠진다
FIRST_COMPUTABLE = date(2025, 9, 12)


def _changes(rates: dict[date, float]) -> pd.Series:
    """날짜별 등락률 계열을 만든다.

    Args:
        rates: 날짜를 열쇠로 갖는 등락률. 비율 (0.0610 = +6.10%).

    Returns:
        날짜를 인덱스로 갖는 등락률 계열.
    """
    return pd.Series(rates, dtype="float64")


class TestUnreflectedWindow:
    """창 경계 — 어디서부터 어디까지 볼 것인가."""

    def test_window_starts_the_day_after_data_to(self) -> None:
        """창은 `data_to` 다음 날부터 마지막 확정 종가일까지다.

        `data_to` 는 순위에 이미 들어간 마지막 날이므로, 그 뒤가 반영되지 않은 구간이다.
        """
        window = unreflected_window(DATA_TO, LAST_CONFIRMED, FIRST_COMPUTABLE)

        assert window == (date(2026, 8, 27), LAST_CONFIRMED)

    def test_no_window_when_data_to_matches_the_last_confirmed_day(self) -> None:
        """방금 갱신한 상태에서는 검사할 날이 없다.

        이 상태가 정상인데 예외를 내면, 갱신한 다음 실행부터 실패 알림이 나간다.
        """
        assert unreflected_window(LAST_CONFIRMED, LAST_CONFIRMED, FIRST_COMPUTABLE) is None

    def test_no_window_when_data_to_is_ahead_of_the_last_confirmed_day(self) -> None:
        """`data_to` 가 마지막 확정 종가일보다 뒤여도 여기서는 조용히 비운다.

        **장중 판정은 마지막 확정 종가일이 「전일」이다.** 사용자가 마감 뒤 재계산해
        오늘 날짜로 올린 정상 파일이 정확히 이 모양이라, 예외를 내면 그날의 신호 대신
        실패 알림이 간다.

        **말이 안 되는 미래 날짜는 파일을 읽는 자리가 막는다** —
        `tests/test_state_loading.py` 가 그쪽을 묶는다. 검사가 조용히 꺼지는 구멍은
        거기서 닫힌다.
        """
        assert unreflected_window(date(2026, 9, 11), LAST_CONFIRMED, FIRST_COMPUTABLE) is None

    def test_window_starts_at_the_first_computable_day_when_data_to_is_older(self) -> None:
        """`data_to` 가 받은 시세보다 오래되면 시작이 첫 계산가능일로 당겨진다.

        QQQ 는 최근 5년간 20위 값이 2회만 바뀌었다(정본 1.5 절) — 1년 넘은 `data_to` 가
        정상이다. 그래서 여기서 경고를 내지 않고 조용히 당긴다.
        """
        window = unreflected_window(date(2024, 6, 3), LAST_CONFIRMED, FIRST_COMPUTABLE)

        assert window == (FIRST_COMPUTABLE, LAST_CONFIRMED)

    def test_data_to_wins_when_it_is_newer_than_the_first_computable_day(self) -> None:
        """`data_to` 가 첫 계산가능일보다 최근이면 그쪽이 시작을 정한다."""
        window = unreflected_window(DATA_TO, LAST_CONFIRMED, FIRST_COMPUTABLE)

        assert window is not None
        assert window[0] > FIRST_COMPUTABLE


class TestUnreflectedDays:
    """도달 판정 — 창 안에서 무엇을 잡는가."""

    def test_catches_a_day_that_reaches_the_surge_rank(self, kodex_thresholds: dict[str, float]) -> None:
        """20위에 도달했고 `data_to` 보다 뒤인 날을 잡는다."""
        signal_day = date(2026, 9, 3)
        changes = _changes({signal_day: kodex_thresholds["surge_20th"] + 0.007})

        found = unreflected_days(changes, RankThresholds(**kodex_thresholds), DATA_TO)

        assert [(day.on, day.direction) for day in found] == [(signal_day, Direction.SURGE)]

    def test_catches_a_day_that_reaches_the_plunge_rank(self, kodex_thresholds: dict[str, float]) -> None:
        """폭락도 같은 규칙으로 잡는다. 부등호가 반대다."""
        signal_day = date(2026, 9, 3)
        changes = _changes({signal_day: kodex_thresholds["plunge_20th"] - 0.007})

        found = unreflected_days(changes, RankThresholds(**kodex_thresholds), DATA_TO)

        assert [(day.on, day.direction) for day in found] == [(signal_day, Direction.PLUNGE)]

    def test_ignores_a_day_already_inside_the_rank(self, kodex_thresholds: dict[str, float]) -> None:
        """20위에 도달했지만 `data_to` 이하인 날은 이미 반영된 날이다."""
        changes = _changes({date(2026, 8, 20): kodex_thresholds["surge_20th"] + 0.007})

        assert unreflected_days(changes, RankThresholds(**kodex_thresholds), DATA_TO) == []

    def test_data_to_itself_counts_as_reflected(self, kodex_thresholds: dict[str, float]) -> None:
        """`data_to` 당일은 순위에 들어간 날이므로 잡지 않는다.

        경계를 `>=` 로 두면 갱신 직후에도 그 날이 계속 잡혀 경고가 꺼지지 않는다.
        """
        changes = _changes({DATA_TO: kodex_thresholds["surge_20th"] + 0.007})

        assert unreflected_days(changes, RankThresholds(**kodex_thresholds), DATA_TO) == []

    def test_exact_equality_counts_as_reached(self, kodex_thresholds: dict[str, float]) -> None:
        """20위 값에 정확히 닿으면 동률도 도달이다 — 정본 1.5 절 「도달하거나 넘으면」."""
        signal_day = date(2026, 9, 3)
        changes = _changes({signal_day: kodex_thresholds["surge_20th"]})

        found = unreflected_days(changes, RankThresholds(**kodex_thresholds), DATA_TO)

        assert [day.on for day in found] == [signal_day]

    def test_ignores_a_day_short_of_the_rank(self, kodex_thresholds: dict[str, float]) -> None:
        """20위에 못 미치는 날은 순위를 바꾸지 않으므로 잡지 않는다."""
        changes = _changes({date(2026, 9, 3): kodex_thresholds["surge_20th"] - 0.001})

        assert unreflected_days(changes, RankThresholds(**kodex_thresholds), DATA_TO) == []

    def test_carries_the_change_rate_of_each_day(self, kodex_thresholds: dict[str, float]) -> None:
        """문구가 등락률을 보여주므로 판정이 그 값을 함께 낸다."""
        rate = kodex_thresholds["surge_20th"] + 0.007
        changes = _changes({date(2026, 9, 3): rate})

        found = unreflected_days(changes, RankThresholds(**kodex_thresholds), DATA_TO)

        assert found[0].change_rate == pytest.approx(rate)

    def test_returns_every_unreflected_day_in_order(self, kodex_thresholds: dict[str, float]) -> None:
        """반영되지 않은 날이 여럿이면 모두 낸다. 오래된 날이 앞에 온다."""
        first = date(2026, 9, 2)
        second = date(2026, 9, 8)
        changes = _changes(
            {
                first: kodex_thresholds["surge_20th"] + 0.002,
                date(2026, 9, 4): 0.0,
                second: kodex_thresholds["plunge_20th"] - 0.002,
            }
        )

        found = unreflected_days(changes, RankThresholds(**kodex_thresholds), DATA_TO)

        assert [day.on for day in found] == [first, second]

    def test_empty_changes_find_nothing(self, kodex_thresholds: dict[str, float]) -> None:
        """창에 거래일이 없으면 빈 결과다. 예외를 내지 않는다."""
        assert unreflected_days(_changes({}), RankThresholds(**kodex_thresholds), DATA_TO) == []


class TestIndependentRanking:
    """폭등 순위와 폭락 순위를 따로 본다 — 절대값 기준이 아니다."""

    def test_surge_side_does_not_borrow_the_plunge_threshold(self, kodex_thresholds: dict[str, float]) -> None:
        """폭락 임계의 절대값에 못 미쳐도 폭등 임계를 넘으면 잡는다.

        KODEX 200 은 폭등 6.10% · 폭락 -6.31% 라 두 값의 크기가 다르다.
        절대값 하나로 합치면 이 구간이 통째로 묻힌다.
        """
        rate = kodex_thresholds["surge_20th"] + 0.001
        assert rate < abs(kodex_thresholds["plunge_20th"])
        changes = _changes({date(2026, 9, 3): rate})

        found = unreflected_days(changes, RankThresholds(**kodex_thresholds), DATA_TO)

        assert [day.direction for day in found] == [Direction.SURGE]

    def test_plunge_side_does_not_borrow_the_surge_threshold(self, kodex_thresholds: dict[str, float]) -> None:
        """폭등 임계만큼 내려도 폭락 임계에 못 미치면 잡지 않는다."""
        rate = -(kodex_thresholds["surge_20th"] + 0.001)
        assert abs(rate) < abs(kodex_thresholds["plunge_20th"])
        changes = _changes({date(2026, 9, 3): rate})

        assert unreflected_days(changes, RankThresholds(**kodex_thresholds), DATA_TO) == []


class TestIndexMustBePlainDates:
    """인덱스가 날짜여야 한다 — 하위형이 검사를 비켜 가지 못하게 한다."""

    def test_timestamp_index_is_rejected_with_the_invariant_message(self, kodex_thresholds: dict[str, float]) -> None:
        """`pd.Timestamp` 인덱스는 불변조건 위반으로 멈춘다.

        `pd.Timestamp` 는 `datetime` 의, `datetime` 은 `date` 의 하위형이다. 형 검사를
        그냥 통과시키면 시세에서 바로 온 계열이 **필드 이름이 없는 TypeError** 로 멈춘다.
        """
        changes = pd.Series([0.07], index=pd.DatetimeIndex([pd.Timestamp("2026-09-03")]), dtype="float64")

        with pytest.raises(RuntimeError, match="내부 불변조건 위반"):
            unreflected_days(changes, RankThresholds(**kodex_thresholds), DATA_TO)


class TestUpdateClearsTheNotice:
    """갱신하면 경고가 꺼진다 — 이 판정의 존재 이유."""

    def test_the_same_day_is_not_caught_after_the_rank_is_updated(self, kodex_thresholds: dict[str, float]) -> None:
        """갱신 뒤에는 그 날이 더는 잡히지 않는다.

        **`data_to` 를 함께 보지 않으면 이 테스트가 깨진다.** 그 날이 20위 안에 들어오면
        새 20위는 그 등락률 자신이거나 그보다 낮아지므로, 도달 조건은 갱신 뒤에도
        계속 참이다. 여기서는 최악(동률)을 준다 — 새 20위를 그 값 자신으로 둔다.
        """
        signal_day = date(2026, 9, 3)
        rate = kodex_thresholds["surge_20th"] + 0.007
        changes = _changes({signal_day: rate})

        before = unreflected_days(changes, RankThresholds(**kodex_thresholds), DATA_TO)
        assert [day.on for day in before] == [signal_day]

        updated = RankThresholds(**{**kodex_thresholds, "surge_20th": rate})
        after = unreflected_days(changes, updated, signal_day)

        assert after == []

    def test_the_window_closes_after_the_rank_is_updated(self) -> None:
        """갱신으로 `data_to` 가 올라가면 창 자체가 닫힌다."""
        assert unreflected_window(DATA_TO, LAST_CONFIRMED, FIRST_COMPUTABLE) is not None
        assert unreflected_window(LAST_CONFIRMED, LAST_CONFIRMED, FIRST_COMPUTABLE) is None

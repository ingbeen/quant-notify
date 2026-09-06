"""원달러 평균대비와 지난주 역방향 요약의 인바리언트를 고정한다.

평균대비는 부호가 곧 의미다 — 음수면 평균보다 싸다. 부호가 뒤집히면 읽는 방향이
통째로 반대가 되는데, 숫자만 보면 알아차릴 수 없다.
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from notify.alerts.usdkrw import mean_deviation, weekly_extremes, window_slice
from notify.common_constants import USDKRW_WINDOW_YEARS


def _flat(value: float, days: int) -> pd.Series:
    """평균이 곧 그 값이 되는 종가 계열을 만든다.

    Args:
        value: 종가.
        days: 거래일 수.

    Returns:
        종가 계열.
    """
    return pd.Series([value] * days, dtype="float64")


class TestWindows:
    """비교 창."""

    def test_four_windows(self) -> None:
        """창은 1·3·5·10년 넷이다. 하나만 내지 않는다."""
        assert USDKRW_WINDOW_YEARS == (1, 3, 5, 10)


class TestMeanDeviation:
    """평균대비."""

    def test_ratio_against_window_mean(self) -> None:
        """평균대비는 현재를 창 평균으로 나눈 뒤 1 을 뺀 비율이다."""
        assert mean_deviation(current=1384.80, window_closes=_flat(1462.0, 246)) == pytest.approx(1384.80 / 1462.0 - 1)

    def test_matches_the_recorded_calculation(self) -> None:
        """실측 검산과 같은 값이 나온다.

        1,384.80 을 최근 1년 평균 1,462원과 견주면 -5.3% 다.
        """
        rate = mean_deviation(current=1384.80, window_closes=_flat(1462.0, 246))

        assert round(rate * 100, 1) == -5.3

    def test_cheaper_than_average_is_negative(self) -> None:
        """평균보다 싸면 음수다."""
        assert mean_deviation(current=900.0, window_closes=_flat(1000.0, 10)) < 0

    def test_dearer_than_average_is_positive(self) -> None:
        """평균보다 비싸면 양수다."""
        assert mean_deviation(current=1100.0, window_closes=_flat(1000.0, 10)) > 0

    def test_equal_to_average_is_zero(self) -> None:
        """평균과 같으면 0 이다."""
        assert mean_deviation(current=1000.0, window_closes=_flat(1000.0, 10)) == pytest.approx(0.0)

    def test_result_is_a_ratio_not_percent(self) -> None:
        """결과는 비율이다. 10% 비싸면 0.1 이지 10 이 아니다."""
        assert mean_deviation(current=1100.0, window_closes=_flat(1000.0, 10)) == pytest.approx(0.1)

    def test_uses_the_mean_not_the_last_value(self) -> None:
        """창의 평균을 쓴다. 마지막 값이나 중앙값이 아니다."""
        closes = pd.Series([1000.0, 1000.0, 1000.0, 2000.0], dtype="float64")

        assert mean_deviation(current=1250.0, window_closes=closes) == pytest.approx(0.0)

    def test_empty_window_raises(self) -> None:
        """빈 창은 평균을 낼 수 없으므로 예외다."""
        with pytest.raises(ValueError):
            mean_deviation(current=1000.0, window_closes=pd.Series([], dtype="float64"))


class TestWeeklyExtremes:
    """지난주 역방향 요약 — 방향별 양끝."""

    @staticmethod
    def _week() -> pd.Series:
        """한 주의 일간 등락률. 비율."""
        return pd.Series(
            [0.0082, -0.0350, 0.0120, -0.0015, 0.0210],
            index=[date(2026, 8, 31), date(2026, 9, 1), date(2026, 9, 2), date(2026, 9, 3), date(2026, 9, 4)],
            dtype="float64",
        )

    def test_highest_is_the_most_risen_day(self) -> None:
        """가장 오른 날을 낸다."""
        result = weekly_extremes(self._week())

        assert result.highest.change_rate == pytest.approx(0.0210)
        assert result.highest.on == date(2026, 9, 4)

    def test_lowest_is_the_most_fallen_day(self) -> None:
        """가장 내린 날을 낸다."""
        result = weekly_extremes(self._week())

        assert result.lowest.change_rate == pytest.approx(-0.0350)
        assert result.lowest.on == date(2026, 9, 1)

    def test_two_ends_are_not_collapsed_into_one(self) -> None:
        """양끝을 절대값 하나로 합치지 않는다.

        이 주는 절대값이 가장 큰 날이 내린 쪽이라, 절대값으로 합치면 오른 쪽이
        통째로 사라진다. 순위가 방향별로 매겨지므로 양쪽을 함께 내야 짝이 맞는다.
        """
        result = weekly_extremes(self._week())

        assert abs(result.lowest.change_rate) > abs(result.highest.change_rate)
        assert result.highest.on != result.lowest.on

    def test_all_up_week_still_reports_a_lowest(self) -> None:
        """모두 오른 주에도 가장 덜 오른 날을 최저로 낸다. 빈칸을 만들지 않는다."""
        week = pd.Series(
            [0.0100, 0.0200, 0.0050],
            index=[date(2026, 9, 1), date(2026, 9, 2), date(2026, 9, 3)],
            dtype="float64",
        )

        result = weekly_extremes(week)

        assert result.lowest.change_rate == pytest.approx(0.0050)
        assert result.highest.change_rate == pytest.approx(0.0200)

    def test_empty_week_raises(self) -> None:
        """거래일이 하나도 없으면 양끝을 만들 수 없으므로 예외다."""
        with pytest.raises(ValueError):
            weekly_extremes(pd.Series([], dtype="float64"))


class TestWindowSlice:
    """비교 창 자르기."""

    @staticmethod
    def _daily() -> pd.Series:
        """하루 간격 종가 계열. 2025-09-01 부터 2026-09-04 까지."""
        days = pd.date_range("2025-09-01", "2026-09-04", freq="D").date
        return pd.Series([1000.0] * len(days), index=pd.Index(days), dtype="float64")

    def test_includes_both_ends(self) -> None:
        """창은 시작일과 종료일을 모두 포함한다.

        시작일을 빼면 거래일이 하나 줄고 평균이 어긋난다. 정본 검산이 양끝을 포함한다.
        """
        window = window_slice(self._daily(), end=date(2026, 9, 4), years=1)

        assert window.index[0] == date(2025, 9, 4)
        assert window.index[-1] == date(2026, 9, 4)

    def test_excludes_days_before_the_window(self) -> None:
        """창보다 앞선 날은 넣지 않는다."""
        window = window_slice(self._daily(), end=date(2026, 9, 4), years=1)

        assert date(2025, 9, 3) not in set(window.index)

    def test_longer_window_holds_more_days(self) -> None:
        """창이 길수록 담기는 날이 많다."""
        short = window_slice(self._daily(), end=date(2026, 9, 4), years=1)
        whole = window_slice(self._daily(), end=date(2026, 9, 4), years=3)

        assert len(whole) > len(short)

    def test_empty_window_raises(self) -> None:
        """창에 자료가 하나도 없으면 예외다. 빈 평균을 만들지 않는다."""
        with pytest.raises(ValueError):
            window_slice(self._daily(), end=date(2020, 1, 1), years=1)

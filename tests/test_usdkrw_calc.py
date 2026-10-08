"""원달러 평균대비의 인바리언트를 고정한다.

평균대비는 부호가 곧 의미다 — 음수면 평균보다 싸다. 부호가 뒤집히면 읽는 방향이
통째로 반대가 되는데, 숫자만 보면 알아차릴 수 없다.
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from notify.alerts.usdkrw import mean_deviation, window_line, window_slice
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
        """평균대비는 현재를 창 평균으로 나눈 뒤 1 을 뺀 비율이다. 실측 검산(1,384.80 ÷ 1,462 − 1 = −5.3%)과 같다."""
        rate = mean_deviation(current=1384.80, window_closes=_flat(1462.0, 246))

        assert rate == pytest.approx(1384.80 / 1462.0 - 1)
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


class TestWindowSlice:
    """비교 창 자르기."""

    @staticmethod
    def _daily() -> pd.Series:
        """하루 간격 종가 계열. 2023-09-01 부터 2026-09-04 까지."""
        days = pd.date_range("2023-09-01", "2026-09-04", freq="D").date
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

    def test_leap_day_end_starts_on_february_28th(self) -> None:
        """기준일이 2/29 여도 창을 자른다. 그 해에 2/29 가 없으면 2/28 부터다."""
        days = pd.date_range("2026-01-01", "2028-03-01", freq="D").date
        closes = pd.Series([1000.0] * len(days), index=pd.Index(days), dtype="float64")

        window = window_slice(closes, end=date(2028, 2, 29), years=1)

        assert window.index[0] == date(2027, 2, 28)

    def test_data_starting_after_the_window_raises(self) -> None:
        """자료가 창 시작일보다 늦게 시작하면 멈춘다. 짧은 자료로 긴 창의 평균을 내지 않는다."""
        with pytest.raises(ValueError, match="2021-08-01"):
            window_slice(self._daily(), end=date(2026, 8, 1), years=5)


class TestWindowLine:
    """창 하나의 줄."""

    def test_last_value_is_current_and_the_window_ends_on_its_day(self) -> None:
        """마지막 값을 현재로 보고, 그 날까지의 창 평균과 평균대비를 낸다."""
        days = pd.date_range("2024-01-01", "2026-09-04", freq="D").date
        closes = pd.Series([1000.0] * (len(days) - 1) + [1100.0], index=pd.Index(days), dtype="float64")
        # 2025-09-04 ~ 2026-09-04 양끝 포함 366일 중 마지막 하루만 1,100원이다
        expected_mean = (1000.0 * 365 + 1100.0) / 366

        line = window_line(closes, years=1)

        assert line.years == 1
        assert line.mean_price == pytest.approx(expected_mean)
        assert line.deviation_rate == pytest.approx(1100.0 / expected_mean - 1)

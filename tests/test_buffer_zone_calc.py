"""이동평균 근접도와 보유 비중의 인바리언트를 고정한다.

근접도는 사용자가 매일 읽는 숫자다. 산식이 어긋나면 평균선 위아래가 뒤집혀 보이는데,
알림 형태로는 정상이라 티가 나지 않는다.
"""

from __future__ import annotations

import pandas as pd
import pytest

from notify.alerts.buffer_zone import ma_proximity, position_weights, sma
from notify.common_constants import MA_PERIOD


def _closes(value: float, days: int) -> pd.Series:
    """같은 종가가 이어지는 계열을 만든다.

    Args:
        value: 종가.
        days: 거래일 수.

    Returns:
        종가 계열.
    """
    return pd.Series([value] * days, dtype="float64")


class TestMovingAverage:
    """단순이동평균."""

    def test_period_is_two_hundred(self) -> None:
        """이동평균 기간은 200 거래일이다."""
        assert MA_PERIOD == 200

    def test_mean_of_the_last_period(self) -> None:
        """이동평균은 최근 기간의 종가를 더해 개수로 나눈 값이다."""
        closes = pd.Series([float(i) for i in range(1, MA_PERIOD + 1)], dtype="float64")

        assert sma(closes) == pytest.approx(sum(range(1, MA_PERIOD + 1)) / MA_PERIOD)

    def test_only_the_last_period_counts(self) -> None:
        """기간보다 긴 계열이 와도 최근 구간만 본다."""
        older = _closes(10.0, MA_PERIOD)
        recent = _closes(20.0, MA_PERIOD)
        closes = pd.concat([older, recent], ignore_index=True)

        assert sma(closes) == pytest.approx(20.0)

    def test_exactly_period_length_is_enough(self) -> None:
        """기간과 같은 길이면 계산할 수 있다."""
        assert sma(_closes(100.0, MA_PERIOD)) == pytest.approx(100.0)

    def test_shorter_than_period_raises(self) -> None:
        """기간을 못 채우면 값을 만들지 않고 예외를 낸다.

        보간하지 않는다. 짧은 창으로 대신 계산하면 백테스트와 다른 값이 나온다.
        """
        with pytest.raises(ValueError):
            sma(_closes(100.0, MA_PERIOD - 1))

    def test_empty_series_raises(self) -> None:
        """빈 계열은 예외다."""
        with pytest.raises(ValueError):
            sma(pd.Series([], dtype="float64"))


class TestProximity:
    """근접도."""

    def test_ratio_against_moving_average(self) -> None:
        """근접도는 종가와 이동평균의 차이를 이동평균으로 나눈 비율이다."""
        assert ma_proximity(close=638.12, ma=605.42) == pytest.approx((638.12 - 605.42) / 605.42)

    def test_above_average_is_positive(self) -> None:
        """평균선 위면 양수다."""
        assert ma_proximity(close=110.0, ma=100.0) > 0

    def test_below_average_is_negative(self) -> None:
        """평균선 아래면 음수다."""
        assert ma_proximity(close=90.0, ma=100.0) < 0

    def test_on_the_average_is_zero(self) -> None:
        """평균선 위에 정확히 있으면 0 이다."""
        assert ma_proximity(close=100.0, ma=100.0) == pytest.approx(0.0)

    def test_result_is_a_ratio_not_percent(self) -> None:
        """결과는 비율이다. 10% 위면 0.1 이지 10 이 아니다."""
        assert ma_proximity(close=110.0, ma=100.0) == pytest.approx(0.1)

    def test_zero_average_raises(self) -> None:
        """이동평균이 0 이면 나눌 수 없으므로 예외를 낸다."""
        with pytest.raises(ValueError):
            ma_proximity(close=100.0, ma=0.0)


class TestWeights:
    """보유 비중."""

    def test_weight_uses_valuation_not_quantity(self) -> None:
        """비중은 평가액 비율이다. 수량 비율이 아니다.

        주당 가격이 다르면 수량 비율과 평가액 비율이 어긋난다.
        """
        weights = position_weights(
            quantities={"SPY": 12, "TLT": 45},
            prices={"SPY": 638.12, "TLT": 88.40},
        )

        assert weights["SPY"] > weights["TLT"]

    def test_weights_sum_to_one(self) -> None:
        """비중의 합은 1 이다."""
        weights = position_weights(
            quantities={"QLD": 200, "GLD": 10},
            prices={"QLD": 120.0, "GLD": 315.88},
        )

        assert sum(weights.values()) == pytest.approx(1.0)

    def test_weight_is_a_ratio(self) -> None:
        """비중은 비율이다. 반씩 가지면 0.5 다."""
        weights = position_weights(
            quantities={"A": 1, "B": 1},
            prices={"A": 100.0, "B": 100.0},
        )

        assert weights["A"] == pytest.approx(0.5)

    def test_missing_price_raises(self) -> None:
        """보유 종목의 가격이 없으면 예외를 낸다. 그 종목을 빼고 계산하지 않는다."""
        with pytest.raises(ValueError):
            position_weights(quantities={"SPY": 12, "TLT": 45}, prices={"SPY": 638.12})

    def test_empty_positions_give_empty_weights(self) -> None:
        """보유가 없으면 빈 결과다. 예외가 아니다."""
        assert position_weights(quantities={}, prices={}) == {}

    def test_zero_total_valuation_raises(self) -> None:
        """평가액 합이 0 이면 비중을 낼 수 없으므로 예외를 낸다."""
        with pytest.raises(ValueError):
            position_weights(quantities={"SPY": 0}, prices={"SPY": 638.12})

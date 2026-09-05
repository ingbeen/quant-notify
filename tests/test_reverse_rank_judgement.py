"""역방향 신호 판정의 인바리언트를 고정한다.

판정 산식이 틀리면 알림이 조용히 거짓말을 한다. 틀린 값도 알림 형태로는 정상으로 보여
사람이 알아차릴 수 없으므로, 산식을 테스트로 먼저 묶는다.

판정 규격은 `reference/역방향_매매_규칙.md` 1.5 절이 정본이다.
"""

from __future__ import annotations

import pytest

from notify.alerts.reverse_rank import (
    Direction,
    Judgement,
    SignalState,
    judge,
    signal_prices,
)
from notify.common_constants import REVERSE_MARGIN_RATE
from notify.state.reverse_rank import RankThresholds


def _judge(prev_close: float, change_rate: float, thresholds: dict[str, float]) -> Judgement:
    """등락률을 가격으로 환산해 판정한다.

    Args:
        prev_close: 전일 종가.
        change_rate: 오늘 등락률. 비율 (0.0610 = +6.10%).
        thresholds: 순위 등락률 필드를 담은 매핑.

    Returns:
        판정 결과.
    """
    return judge(
        prev_close=prev_close,
        current_price=prev_close * (1 + change_rate),
        thresholds=RankThresholds(**thresholds),
    )


class TestSignalPrices:
    """신호 가격 산식."""

    def test_prices_come_from_prev_close_and_rank_rate(
        self, kodex_prev_close: float, kodex_thresholds: dict[str, float]
    ) -> None:
        """신호 가격은 전일 종가에 순위 등락률을 곱해 나온다."""
        prices = signal_prices(kodex_prev_close, RankThresholds(**kodex_thresholds))

        assert prices.surge == pytest.approx(kodex_prev_close * (1 + kodex_thresholds["surge_20th"]))
        assert prices.plunge == pytest.approx(kodex_prev_close * (1 + kodex_thresholds["plunge_20th"]))

    def test_surge_is_above_and_plunge_is_below_prev_close(
        self, kodex_prev_close: float, kodex_thresholds: dict[str, float]
    ) -> None:
        """폭등 신호 가격은 전일 종가보다 위, 폭락 신호 가격은 아래에 놓인다."""
        prices = signal_prices(kodex_prev_close, RankThresholds(**kodex_thresholds))

        assert prices.plunge < kodex_prev_close < prices.surge

    def test_prices_are_fixed_before_market_opens(
        self, kodex_prev_close: float, kodex_thresholds: dict[str, float]
    ) -> None:
        """같은 전일 종가와 순위 값이면 몇 번을 계산해도 같은 가격이 나온다.

        신호 가격은 판정일 이전 데이터만 쓰므로 장이 열리기 전에 이미 확정돼 있다.
        """
        thresholds = RankThresholds(**kodex_thresholds)

        assert signal_prices(kodex_prev_close, thresholds) == signal_prices(kodex_prev_close, thresholds)


class TestComparisonDirection:
    """부등호 방향 — 폭등과 폭락에서 서로 반대다."""

    def test_surge_hits_when_price_reaches_or_exceeds(
        self, kodex_prev_close: float, kodex_thresholds: dict[str, float]
    ) -> None:
        """폭등은 신호 가격 이상일 때 도달이다."""
        result = _judge(kodex_prev_close, kodex_thresholds["surge_20th"] + 0.005, kodex_thresholds)

        assert result.state is SignalState.HIT
        assert result.direction is Direction.SURGE

    def test_plunge_hits_when_price_reaches_or_falls_below(
        self, kodex_prev_close: float, kodex_thresholds: dict[str, float]
    ) -> None:
        """폭락은 신호 가격 이하일 때 도달이다."""
        result = _judge(kodex_prev_close, kodex_thresholds["plunge_20th"] - 0.005, kodex_thresholds)

        assert result.state is SignalState.HIT
        assert result.direction is Direction.PLUNGE

    def test_surge_does_not_hit_below_signal_price(
        self, kodex_prev_close: float, kodex_thresholds: dict[str, float]
    ) -> None:
        """폭등 신호 가격에 못 미치면 도달이 아니다.

        부등호가 뒤집히면 이 지점이 도달로 잡힌다.
        """
        result = _judge(kodex_prev_close, kodex_thresholds["surge_20th"] - 0.005, kodex_thresholds)

        assert result.state is not SignalState.HIT

    def test_plunge_does_not_hit_above_signal_price(
        self, kodex_prev_close: float, kodex_thresholds: dict[str, float]
    ) -> None:
        """폭락 신호 가격보다 위면 도달이 아니다."""
        result = _judge(kodex_prev_close, kodex_thresholds["plunge_20th"] + 0.005, kodex_thresholds)

        assert result.state is not SignalState.HIT

    def test_exact_equality_counts_as_hit(
        self, kodex_prev_close: float, kodex_thresholds: dict[str, float]
    ) -> None:
        """신호 가격에 정확히 닿으면 동률도 도달로 센다."""
        thresholds = RankThresholds(**kodex_thresholds)
        prices = signal_prices(kodex_prev_close, thresholds)

        surge = judge(prev_close=kodex_prev_close, current_price=prices.surge, thresholds=thresholds)
        plunge = judge(prev_close=kodex_prev_close, current_price=prices.plunge, thresholds=thresholds)

        assert surge.state is SignalState.HIT
        assert surge.direction is Direction.SURGE
        assert plunge.state is SignalState.HIT
        assert plunge.direction is Direction.PLUNGE


class TestIndependentRanking:
    """폭등 순위와 폭락 순위는 따로 매긴다 — 절대값 기준이 아니다."""

    def test_surge_hits_even_when_below_plunge_magnitude(
        self, kodex_prev_close: float, kodex_thresholds: dict[str, float]
    ) -> None:
        """폭락 임계의 절대값에 못 미쳐도 폭등 임계를 넘으면 도달이다.

        KODEX 200 은 폭등 6.10% · 폭락 -6.31% 라 두 값의 크기가 다르다.
        절대값 하나로 합치면 이 구간이 통째로 묻힌다.
        """
        change_rate = kodex_thresholds["surge_20th"] + 0.001
        assert change_rate < abs(kodex_thresholds["plunge_20th"])

        result = _judge(kodex_prev_close, change_rate, kodex_thresholds)

        assert result.state is SignalState.HIT
        assert result.direction is Direction.SURGE

    def test_plunge_does_not_hit_at_surge_magnitude(
        self, kodex_prev_close: float, kodex_thresholds: dict[str, float]
    ) -> None:
        """폭등 임계만큼 내려도 폭락 임계에 못 미치면 도달이 아니다."""
        change_rate = -(kodex_thresholds["surge_20th"] + 0.001)
        assert abs(change_rate) < abs(kodex_thresholds["plunge_20th"])

        result = _judge(kodex_prev_close, change_rate, kodex_thresholds)

        assert result.state is not SignalState.HIT

    def test_both_directions_are_carried_together(
        self, kodex_prev_close: float, kodex_thresholds: dict[str, float]
    ) -> None:
        """폭등과 폭락 신호 가격을 항상 함께 낸다 — 하나만 주면 반대 방향을 놓친다."""
        prices = signal_prices(kodex_prev_close, RankThresholds(**kodex_thresholds))

        assert prices.surge != prices.plunge


class TestMarginAndSilence:
    """여유 1%p 와 침묵 조건."""

    def test_margin_is_one_percent_point(self) -> None:
        """여유는 1%p 다. 비율로 0.01 이다."""
        assert REVERSE_MARGIN_RATE == 0.01

    def test_near_inside_margin(self, kodex_prev_close: float, kodex_thresholds: dict[str, float]) -> None:
        """도달하지 않았어도 여유 안에 들어오면 근접이다."""
        result = _judge(
            kodex_prev_close,
            kodex_thresholds["surge_20th"] - REVERSE_MARGIN_RATE / 2,
            kodex_thresholds,
        )

        assert result.state is SignalState.NEAR
        assert result.direction is Direction.SURGE

    def test_margin_boundary_is_inclusive(
        self, kodex_prev_close: float, kodex_thresholds: dict[str, float]
    ) -> None:
        """여유 경계에 정확히 걸치면 근접에 포함한다."""
        thresholds = RankThresholds(**kodex_thresholds)
        near = signal_prices(kodex_prev_close, thresholds, REVERSE_MARGIN_RATE)

        surge = judge(prev_close=kodex_prev_close, current_price=near.surge, thresholds=thresholds)
        plunge = judge(prev_close=kodex_prev_close, current_price=near.plunge, thresholds=thresholds)

        assert surge.state is SignalState.NEAR
        assert plunge.state is SignalState.NEAR

    def test_silent_outside_margin(self, kodex_prev_close: float, kodex_thresholds: dict[str, float]) -> None:
        """여유 밖이면 침묵이다. 방향도 남기지 않는다."""
        result = _judge(
            kodex_prev_close,
            kodex_thresholds["surge_20th"] - REVERSE_MARGIN_RATE * 2,
            kodex_thresholds,
        )

        assert result.state is SignalState.SILENT
        assert result.direction is None

    def test_flat_day_is_silent(self, kodex_prev_close: float, kodex_thresholds: dict[str, float]) -> None:
        """전일 종가 그대로면 양쪽 다 멀어 침묵이다."""
        result = _judge(kodex_prev_close, 0.0, kodex_thresholds)

        assert result.state is SignalState.SILENT

    def test_plunge_side_has_its_own_margin(
        self, kodex_prev_close: float, kodex_thresholds: dict[str, float]
    ) -> None:
        """폭락 쪽 여유는 임계보다 위쪽으로 잡힌다 — 부호를 따라 방향이 뒤집힌다."""
        result = _judge(
            kodex_prev_close,
            kodex_thresholds["plunge_20th"] + REVERSE_MARGIN_RATE / 2,
            kodex_thresholds,
        )

        assert result.state is SignalState.NEAR
        assert result.direction is Direction.PLUNGE


class TestChangeRate:
    """등락률 계산."""

    def test_change_rate_is_ratio_against_prev_close(
        self, kodex_prev_close: float, kodex_thresholds: dict[str, float]
    ) -> None:
        """등락률은 전일 종가 대비 비율이다."""
        result = _judge(kodex_prev_close, 0.0538, kodex_thresholds)

        assert result.change_rate == pytest.approx(0.0538)


class TestSharedAcrossMarkets:
    """한국과 미국이 같은 판정을 쓴다."""

    def test_qqq_uses_the_same_rule(self, qqq_thresholds: dict[str, float]) -> None:
        """QQQ 도 같은 산식으로 판정한다. 다른 것은 순위 값뿐이다."""
        prev_close = 603.42
        result = _judge(prev_close, qqq_thresholds["surge_20th"] + 0.001, qqq_thresholds)

        assert result.state is SignalState.HIT
        assert result.direction is Direction.SURGE

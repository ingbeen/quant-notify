"""알림 문구를 문자열 단위로 고정한다.

문구는 사용자가 매일 읽는 산출물이다. 정본은 `docs/DESIGN.md` 4.5 절이며,
여기 기대값은 그 예시를 그대로 옮긴 것이다. 코드가 이것과 달라지면 문서가 아니라
코드가 틀린 것이다.

**강조가 어디에 붙는지도 함께 묶는다.** 빨간 점은 역방향·실패·점검 이상에만 붙는다.
정기 알림에 번지면 색이 흔해져 정작 사건일 때 눈에 걸리지 않는다.
"""

from __future__ import annotations

from datetime import date, datetime

import pytest

from notify.alerts.buffer_zone import HoldingLine, ProximityLine
from notify.alerts.buffer_zone import render as render_buffer_zone
from notify.alerts.failure import render as render_failure
from notify.alerts.formatting import RED_DOT
from notify.alerts.health import HealthLine, daily_health, expected_runs, weekly_health
from notify.alerts.reverse_rank import Market, judge, render, signal_prices
from notify.alerts.usdkrw import ReverseBlock, ReverseLine, WindowLine
from notify.alerts.usdkrw import render as render_usdkrw
from notify.common_constants import TZ_KST
from notify.state.reverse_rank import RankThresholds

# KODEX 200 순위 등락률
KODEX = RankThresholds(surge_1st=0.2417, surge_20th=0.0610, plunge_1st=-0.1246, plunge_20th=-0.0631)

# QQQ 순위 등락률
QQQ = RankThresholds(surge_1st=0.1684, surge_20th=0.0742, plunge_1st=-0.1198, plunge_20th=-0.0687)


def _render(
    market: Market,
    symbol: str,
    thresholds: RankThresholds,
    prev_close: float,
    current_price: float,
    sent_at: datetime,
) -> str:
    """판정부터 문구까지 한 번에 만든다.

    Args:
        market: 시장.
        symbol: 화면에 쓸 종목 이름.
        thresholds: 순위 등락률.
        prev_close: 전일 종가.
        current_price: 판정 시점 가격.
        sent_at: 발송 시각.

    Returns:
        보낼 문구.
    """
    return render(
        market=market,
        symbol=symbol,
        judgement=judge(prev_close=prev_close, current_price=current_price, thresholds=thresholds),
        prices=signal_prices(prev_close, thresholds),
        thresholds=thresholds,
        sent_at=sent_at,
    )


class TestReverseRankKorea:
    """한국 역방향 문구."""

    def test_matches_the_documented_example(self) -> None:
        """정본 예시와 글자 단위로 같다."""
        text = _render(
            Market.KR,
            "KODEX 200",
            KODEX,
            prev_close=112285.0,
            current_price=106200.0,
            sent_at=datetime(2026, 9, 4, 12, 0, tzinfo=TZ_KST),
        )

        assert text == (
            f"{RED_DOT} <b>역방향 · KODEX 200 · 폭락 근접</b>\n"
            "09-04 (금) 12:00\n"
            "\n"
            "현재 106,200원 -5.42%\n"
            "신호 105,200원 -6.31%"
        )

    def test_uses_reached_for_intraday(self) -> None:
        """장중 판정이라 도달이라고 적는다. 발생이 아니다."""
        text = _render(
            Market.KR,
            "KODEX 200",
            KODEX,
            prev_close=112285.0,
            current_price=100000.0,
            sent_at=datetime(2026, 9, 4, 14, 30, tzinfo=TZ_KST),
        )

        assert text.startswith(f"{RED_DOT} <b>역방향 · KODEX 200 · 폭락 도달</b>")

    def test_surge_side_reads_the_other_threshold(self) -> None:
        """폭등 쪽은 폭등 순위 등락률을 신호로 낸다."""
        text = _render(
            Market.KR,
            "KODEX 200",
            KODEX,
            prev_close=112285.0,
            current_price=118100.0,
            sent_at=datetime(2026, 9, 4, 12, 0, tzinfo=TZ_KST),
        )

        assert "폭등 근접" in text
        assert "+6.10%" in text


class TestReverseRankUnitedStates:
    """미국 역방향 문구."""

    def test_matches_the_documented_example(self) -> None:
        """정본 예시와 글자 단위로 같다."""
        text = _render(
            Market.US,
            "QQQ",
            QQQ,
            prev_close=574.70,
            current_price=619.50,
            sent_at=datetime(2026, 9, 4, 7, 30, tzinfo=TZ_KST),
        )

        assert text == (
            f"{RED_DOT} <b>역방향 · QQQ · 폭등 발생</b>\n" "09-04 (금) 07:30\n" "\n" "종가 $619.50 +7.80%\n" "신호 $617.34 +7.42%"
        )

    def test_uses_occurred_not_reached(self) -> None:
        """종가가 확정된 뒤라 발생이라고 적는다."""
        text = _render(
            Market.US,
            "QQQ",
            QQQ,
            prev_close=574.70,
            current_price=619.50,
            sent_at=datetime(2026, 9, 4, 7, 30, tzinfo=TZ_KST),
        )

        assert "폭등 발생" in text
        assert "도달" not in text


class TestSilence:
    """침묵."""

    def test_rendering_a_silent_judgement_raises(self) -> None:
        """침묵인데 문구를 만들려 하면 예외다. 침묵이면 발송하지 않는다."""
        judgement = judge(prev_close=112285.0, current_price=112285.0, thresholds=KODEX)

        with pytest.raises(RuntimeError, match="내부 불변조건 위반"):
            render(
                market=Market.KR,
                symbol="KODEX 200",
                judgement=judgement,
                prices=signal_prices(112285.0, KODEX),
                thresholds=KODEX,
                sent_at=datetime(2026, 9, 4, 12, 0, tzinfo=TZ_KST),
            )


class TestBufferZone:
    """이동평균 알림 문구."""

    @staticmethod
    def _render(holdings: list[HoldingLine]) -> str:
        """정본 예시와 같은 조건으로 문구를 만든다.

        Args:
            holdings: 보유 종목.

        Returns:
            보낼 문구.
        """
        return render_buffer_zone(
            sent_at=datetime(2026, 9, 4, 7, 30, tzinfo=TZ_KST),
            proximities=[
                ProximityLine("SPY", 0.1156),
                ProximityLine("QQQ", 0.1938),
                ProximityLine("GLD", 0.0246),
                ProximityLine("TLT", -0.0098),
            ],
            holdings=holdings,
            health=[
                HealthLine("전일", "09-03 (목)", "역방향 KR 2/2 · US 1/1"),
                HealthLine("최근 주간", "08-31 (월)", "1/1"),
            ],
        )

    def test_matches_the_documented_example(self) -> None:
        """정본 예시와 글자 단위로 같다."""
        text = self._render([HoldingLine("QLD", 200, 0.873), HoldingLine("GLD", 10, 0.127)])

        assert text == (
            "<b>QBT</b> · 09-04 (금) 07:30\n"
            "\n"
            "<b>MA 근접도</b>\n"
            "SPY +11.56%\n"
            "QQQ +19.38%\n"
            "GLD +2.46%\n"
            "TLT -0.98%\n"
            "\n"
            "<b>보유</b>\n"
            "QLD 200주 · 87.3%\n"
            "GLD 10주 · 12.7%\n"
            "\n"
            "<b>점검</b>\n"
            "전일 09-03 (목) · 역방향 KR 2/2 · US 1/1\n"
            "최근 주간 08-31 (월) · 1/1"
        )

    def test_carries_no_red_dot_when_healthy(self) -> None:
        """정기 알림에는 색을 쓰지 않는다. 점검이 정상이면 빨간 점이 없다."""
        assert RED_DOT not in self._render([HoldingLine("QLD", 200, 0.873)])

    def test_empty_holdings_drop_the_block(self) -> None:
        """보유가 없으면 그 블록을 통째로 빼고 알림은 그대로 낸다."""
        text = self._render([])

        assert "보유" not in text
        assert "MA 근접도" in text
        assert "점검" in text

    def test_no_proximity_raises(self) -> None:
        """근접도가 하나도 없으면 알림을 만들지 않는다."""
        with pytest.raises(ValueError):
            render_buffer_zone(
                sent_at=datetime(2026, 9, 4, 7, 30, tzinfo=TZ_KST),
                proximities=[],
                holdings=[],
                health=[],
            )


class TestUsdKrw:
    """원달러 주간 알림 문구."""

    @staticmethod
    def _render(kodex_plunge_rate: float = -0.0350) -> str:
        """정본 예시와 같은 조건으로 문구를 만든다.

        Args:
            kodex_plunge_rate: KODEX 200 의 지난주 최저 등락률. 신호 여부를 가른다.

        Returns:
            보낼 문구.
        """
        return render_usdkrw(
            sent_at=datetime(2026, 9, 7, 7, 30, tzinfo=TZ_KST),
            current=1384.80,
            as_of=date(2026, 9, 4),
            windows=[
                WindowLine(1, 1462, -0.053),
                WindowLine(3, 1404, -0.013),
                WindowLine(5, 1351, 0.025),
                WindowLine(10, 1247, 0.111),
            ],
            reverses=[
                ReverseBlock(
                    "KODEX 200",
                    [
                        ReverseLine("폭등", 0.2417, 0.0610, 0.0210, date(2026, 9, 4)),
                        ReverseLine("폭락", -0.1246, -0.0631, kodex_plunge_rate, date(2026, 9, 1)),
                    ],
                ),
                ReverseBlock(
                    "QQQ",
                    [
                        ReverseLine("폭등", 0.1684, 0.0742, 0.0325, date(2026, 9, 2)),
                        ReverseLine("폭락", -0.1198, -0.0687, -0.0088, date(2026, 9, 1)),
                    ],
                ),
            ],
            health=HealthLine("지난주", "08-31 (월) ~ 09-05 (토)", "버퍼존 5/5 · 역방향 KR 10/10 · US 5/5"),
        )

    def test_matches_the_documented_example(self) -> None:
        """정본 예시와 글자 단위로 같다."""
        assert self._render() == (
            "<b>주간</b> · 09-07 (월) 07:30\n"
            "\n"
            "<b>원달러 1,384.80원</b>\n"
            "09-04 (금) 기준\n"
            "\n"
            "1년 평균 1,462원 대비 -5.3%\n"
            "3년 평균 1,404원 대비 -1.3%\n"
            "5년 평균 1,351원 대비 +2.5%\n"
            "10년 평균 1,247원 대비 +11.1%\n"
            "\n"
            "<b>역방향 · KODEX 200</b>\n"
            "폭등 1위 +24.17% / 20위 +6.10%\n"
            "지난주 최고 +2.10% (09-04 금)\n"
            "폭락 1위 -12.46% / 20위 -6.31%\n"
            "지난주 최저 -3.50% (09-01 화)\n"
            "\n"
            "<b>역방향 · QQQ</b>\n"
            "폭등 1위 +16.84% / 20위 +7.42%\n"
            "지난주 최고 +3.25% (09-02 수)\n"
            "폭락 1위 -11.98% / 20위 -6.87%\n"
            "지난주 최저 -0.88% (09-01 화)\n"
            "\n"
            "<b>점검</b>\n"
            "지난주 08-31 (월) ~ 09-05 (토)\n"
            "버퍼존 5/5 · 역방향 KR 10/10 · US 5/5"
        )

    def test_quiet_week_carries_no_red_dot(self) -> None:
        """신호가 없던 주에는 색을 쓰지 않는다."""
        assert RED_DOT not in self._render()

    def test_signal_week_marks_only_that_row(self) -> None:
        """지난주 값이 20위 등락률에 닿으면 그 줄만 신호로 바뀌고 강조된다."""
        text = self._render(kodex_plunge_rate=-0.0648)

        assert f"{RED_DOT} <b>지난주 신호 -6.48% (09-01 화)</b>" in text
        assert "지난주 최고 +2.10% (09-04 금)" in text
        assert "지난주 최저" not in text.split("<b>역방향 · QQQ</b>")[0]
        assert text.count(RED_DOT) == 1

    def test_boundary_counts_as_a_signal(self) -> None:
        """20위 등락률과 같으면 신호다. 규격이 「이 값 이상」이다."""
        assert f"{RED_DOT} <b>지난주 신호 -6.31%" in self._render(kodex_plunge_rate=-0.0631)

    def test_carries_no_verdict_words(self) -> None:
        """판정 어휘를 붙이지 않는다. 예측력이 없는 지표가 행동 지시가 되면 안 된다."""
        text = self._render()

        for word in ("쌈", "비쌈", "저평가", "고평가", "매수", "매도"):
            assert word not in text


class TestFailure:
    """실패 알림 문구."""

    def test_matches_the_documented_example(self) -> None:
        """정본 예시와 글자 단위로 같다."""
        text = render_failure(
            "buffer_zone",
            RuntimeError("yfinance 조회 실패 — QQQ"),
            datetime(2026, 9, 4, 7, 31, tzinfo=TZ_KST),
        )

        assert text == (
            f"{RED_DOT} <b>실패 · buffer_zone</b>\n" "09-04 (금) 07:31\n" "\n" "RuntimeError: yfinance 조회 실패 — QQQ"
        )

    def test_carries_no_guidance(self) -> None:
        """안내 문구를 붙이지 않는다. 제목과 예외 메시지뿐이다."""
        text = render_failure("usdkrw", ValueError("x"), datetime(2026, 9, 4, 7, 31, tzinfo=TZ_KST))

        assert "재시도" not in text
        assert "Run workflow" not in text
        assert len(text.split("\n")) == 4

    def test_masks_credentials_in_the_message(self) -> None:
        """예외에 담긴 인증키를 가린다. 실패 알림도 로그에 남는다."""
        key = "ABCD1234EFGH5678"
        error = ValueError(f"조회 실패: https://ecos.bok.or.kr/api/StatisticSearch/{key}/json")

        text = render_failure("usdkrw", error, datetime(2026, 9, 4, 7, 31, tzinfo=TZ_KST))

        assert key not in text

    def test_escapes_markup_in_the_message(self) -> None:
        """예외 메시지에 섞인 태그 문자를 가린다. 안 가리면 문구 전체가 깨진다."""
        error = ValueError("<b>주의</b> & 실패")

        text = render_failure("usdkrw", error, datetime(2026, 9, 4, 7, 31, tzinfo=TZ_KST))

        assert "&lt;b&gt;주의&lt;/b&gt; &amp; 실패" in text
        assert "<b>주의</b>" not in text


class TestHealthLineFlowsIntoAlerts:
    """점검 줄이 알림 문구까지 이어지는지 본다.

    점검 줄을 손으로 넣어 문구만 맞추면, 실제로 만들어지는 값이 달라도 알아차리지 못한다.
    두 쪽을 이어서 정본과 대조한다.
    """

    @staticmethod
    def _as_expected(workflow: str, day: date) -> int:
        """예정대로 전부 성공한 상황을 흉내 낸다.

        Args:
            workflow: 워크플로 이름.
            day: 날짜.

        Returns:
            그 날 예정된 실행 수.
        """
        return expected_runs(workflow, day)

    def test_daily_line_matches_the_documented_row(self) -> None:
        """전일 점검 줄이 정본의 그 줄로 이어진다."""
        line = daily_health(date(2026, 9, 3), self._as_expected)

        text = render_buffer_zone(
            sent_at=datetime(2026, 9, 4, 7, 30, tzinfo=TZ_KST),
            proximities=[ProximityLine("SPY", 0.1156), ProximityLine("QQQ", 0.1938)],
            holdings=[],
            health=[line, HealthLine("최근 주간", "08-31 (월)", "1/1")],
        )

        assert "전일 09-03 (목) · 역방향 KR 2/2 · US 1/1" in text

    def test_weekly_line_matches_the_documented_row(self) -> None:
        """지난주 점검 줄이 정본의 그 두 줄로 이어진다."""
        line = weekly_health(date(2026, 8, 31), date(2026, 9, 5), self._as_expected)

        text = render_usdkrw(
            sent_at=datetime(2026, 9, 7, 7, 30, tzinfo=TZ_KST),
            current=1384.80,
            as_of=date(2026, 9, 4),
            windows=[WindowLine(1, 1462, -0.053)],
            reverses=[],
            health=line,
        )

        assert "지난주 08-31 (월) ~ 09-05 (토)\n버퍼존 5/5 · 역방향 KR 10/10 · US 5/5" in text

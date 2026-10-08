"""알림 문구를 문자열 단위로 고정한다.

기대값은 `docs/DESIGN.md` §4.3 의 예시를 그대로 옮긴 것이다 — 다르면 코드가 틀린 것이다.
빨간 점이 붙는 자리도 함께 묶는다.
"""

from __future__ import annotations

from datetime import date, datetime

from notify.alerts.buffer_zone import HoldingLine, ProximityLine
from notify.alerts.buffer_zone import render as render_buffer_zone
from notify.alerts.failure import render as render_failure
from notify.alerts.formatting import RED_DOT
from notify.alerts.health import HealthLine
from notify.alerts.usdkrw import WindowLine
from notify.alerts.usdkrw import render as render_usdkrw
from notify.common_constants import TZ_KST

# 버퍼존 정본 예시의 점검 줄
WEEKLY_LINE = HealthLine("최근 주간", "08-31 (월)", "1/1")


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
            health=WEEKLY_LINE,
        )

    def test_matches_the_documented_example(self) -> None:
        """정본 예시와 글자 단위로 같다."""
        text = self._render([HoldingLine("QLD", 200, 0.873), HoldingLine("GLD", 10, 0.127)])

        assert text == (
            "<b>QBT</b> · 09-04 (금) 07:30\n"
            "\n"
            "<b>MA 근접도</b>\n"
            "SPY 매수선 위\n"
            "QQQ 매수선 위\n"
            "GLD +2.46%\n"
            "TLT -0.98%\n"
            "\n"
            "<b>보유</b>\n"
            "QLD 200주 · 87.3%\n"
            "GLD 10주 · 12.7%\n"
            "\n"
            "<b>점검</b>\n"
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

    @staticmethod
    def _proximity_row(ticker: str, rate: float) -> str:
        """근접도 한 종목만 넣고 그 종목의 줄을 꺼낸다.

        Args:
            ticker: 종목.
            rate: 근접도. 비율.

        Returns:
            그 종목의 줄.
        """
        text = render_buffer_zone(
            sent_at=datetime(2026, 9, 4, 7, 30, tzinfo=TZ_KST),
            proximities=[ProximityLine(ticker, rate)],
            holdings=[],
            health=WEEKLY_LINE,
        )
        return next(row for row in text.split("\n") if row.startswith(f"{ticker} "))

    def test_matches_the_documented_variant(self) -> None:
        """선 밖과 선 안이 섞인 변형이 정본 블록과 글자 단위로 같다."""
        text = render_buffer_zone(
            sent_at=datetime(2026, 9, 4, 7, 30, tzinfo=TZ_KST),
            proximities=[
                ProximityLine("SPY", -0.0612),
                ProximityLine("QQQ", -0.0342),
                ProximityLine("GLD", 0.0246),
                ProximityLine("TLT", -0.0098),
            ],
            holdings=[],
            health=WEEKLY_LINE,
        )

        assert "<b>MA 근접도</b>\nSPY 매도선 아래\nQQQ -3.42%\nGLD +2.46%\nTLT -0.98%\n" in text

    def test_rate_between_the_lines_is_shown(self) -> None:
        """두 선 사이면 수치를 낸다."""
        for ticker in ("SPY", "QQQ"):
            assert self._proximity_row(ticker, 0.0184) == f"{ticker} +1.84%"

    def test_rate_on_a_line_is_still_between(self) -> None:
        """정확히 선 위인 날은 아직 넘지 않았다.

        quant 의 판정이 `종가 > 상단` · `종가 < 하단` 으로 등호를 넣지 않는다.
        """
        for ticker in ("SPY", "QQQ"):
            assert self._proximity_row(ticker, 0.03) == f"{ticker} +3.00%"
            assert self._proximity_row(ticker, -0.05) == f"{ticker} -5.00%"

    def test_above_the_buy_line_reads_as_position(self) -> None:
        """매수선을 넘으면 수치 대신 위치를 적는다."""
        for ticker in ("SPY", "QQQ"):
            assert self._proximity_row(ticker, 0.0301) == f"{ticker} 매수선 위"

    def test_below_the_sell_line_reads_as_position(self) -> None:
        """매도선 아래면 수치 대신 위치를 적는다. 폭락일에도 방향이 드러난다."""
        for ticker in ("SPY", "QQQ"):
            assert self._proximity_row(ticker, -0.0501) == f"{ticker} 매도선 아래"

    def test_reference_tickers_always_show_the_rate(self) -> None:
        """GLD·TLT 는 선 밖이어도 수치를 낸다.

        Q-2-2XS 에서 B&H 라 두 선이 적용되지 않는다. 문구를 붙이면 매매하지 않는 종목에
        행동을 암시한다.
        """
        assert self._proximity_row("GLD", 0.10) == "GLD +10.00%"
        assert self._proximity_row("TLT", -0.08) == "TLT -8.00%"


class TestUsdKrw:
    """원달러 주간 알림 문구."""

    @staticmethod
    def _render() -> str:
        """정본 예시와 같은 조건으로 문구를 만든다.

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
            health=HealthLine("지난주", "08-31 (월) ~ 09-05 (토)", "버퍼존 5/5"),
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
            "<b>점검</b>\n"
            "지난주 08-31 (월) ~ 09-05 (토)\n"
            "버퍼존 5/5"
        )

    def test_carries_no_red_dot_when_healthy(self) -> None:
        """정기 알림에는 색을 쓰지 않는다. 점검이 정상이면 빨간 점이 없다."""
        assert RED_DOT not in self._render()

    def test_carries_no_verdict_words(self) -> None:
        """판정 어휘를 붙이지 않는다. 예측력이 없는 지표가 행동 지시가 되면 안 된다."""
        text = self._render()

        for word in ("쌈", "비쌈", "저평가", "고평가", "매수", "매도"):
            assert word not in text


class TestFailure:
    """실패 알림 문구."""

    def test_matches_the_documented_example(self) -> None:
        """정본 예시와 글자 단위로 같다."""
        reason = "[QQQ] 시세 조회에 실패했습니다: YFRateLimitError: Too Many Requests. Rate limited. Try after a while."
        text = render_failure("buffer_zone", ValueError(reason), datetime(2026, 9, 4, 7, 31, tzinfo=TZ_KST))

        assert text == (f"{RED_DOT} <b>실패 · buffer_zone</b>\n" "09-04 (금) 07:31\n" "\n" f"ValueError: {reason}")

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

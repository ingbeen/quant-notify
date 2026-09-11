"""낡음 판정을 알림에 잇는 층을 고정한다.

`tests/test_rank_staleness.py` 가 판정 «규칙»을 묶는다면, 이 파일은 그 규칙에 **무엇을
넘기는가**를 묶는다. 둘을 잇는 자리에서 조용히 틀릴 수 있는 것이 셋이다.

- **거래소 달력을 바꿔 끼우면** 한국 휴장이 미국 휴장으로 판정돼 검사 구간이 달라진다
- **마지막 확정 종가일을 오늘로 주면** 아직 종가가 없는 날이 검사에 들어온다
- **검사가 실패하면 신호 알림까지 삼킨다** — 연 5~8회뿐인 사건을 잃는다
- **「검사할 날이 없다」를 오류로 읽으면** 마감 뒤 갱신한 정상 파일이 실패 알림을 낸다

네 경우 모두 판정 함수만 보는 테스트로는 전부 통과한다.
"""

from __future__ import annotations

from datetime import date, datetime

import pandas as pd
import pytest

from notify import cli
from notify.alerts.reverse_rank import Market
from notify.common_constants import TZ_KST
from notify.state.reverse_rank import RankEntry, RankThresholds

KODEX = "069500.KS"
QQQ = "QQQ"

# 2026-09-07(월)은 미국 노동절 휴장이고 한국은 거래일이다. 달력을 바꿔 끼우면 이 날에서 갈린다
FRI = date(2026, 9, 4)
MON = date(2026, 9, 7)
TUE = date(2026, 9, 8)
WED = date(2026, 9, 9)

# 종가 공백을 창 «안» 에 두기 위한 두 날. 09-03(목)을 빼면 그 자리가 공백이 된다
GAP_START = date(2026, 9, 1)
GAP_NEXT = date(2026, 9, 2)

NEW_YORK = "America/New_York"
SEOUL = "Asia/Seoul"


def _series(days: list[date], values: list[float], tz: str) -> pd.Series:
    """`Ticker.history` 가 남기는 모양의 종가 계열을 만든다.

    Args:
        days: 날짜들.
        values: 종가들.
        tz: 거래소 시간대.

    Returns:
        종가 계열.
    """
    index = pd.DatetimeIndex([pd.Timestamp(day, tz=tz) for day in days])
    return pd.Series(values, index=index, dtype="float64")


def _at(day: date, hour: int, minute: int) -> datetime:
    """KST 실행 시각을 만든다.

    Args:
        day: 날짜.
        hour: 시.
        minute: 분.

    Returns:
        KST 시각.
    """
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=TZ_KST)


def _install(
    monkeypatch: pytest.MonkeyPatch,
    ticker: str,
    closes: pd.Series,
    thresholds: dict[str, float],
    data_to: date,
    intraday: float | None = None,
) -> None:
    """시세와 순위 등락률을 가짜로 바꾼다.

    Args:
        monkeypatch: pytest 픽스처.
        ticker: 돌려줄 종목.
        closes: 그 종목의 종가 계열.
        thresholds: 순위 등락률 필드를 담은 매핑.
        data_to: 순위 값이 매겨진 마지막 날.
        intraday: 장중 현재가. 한국 알림에만 쓴다.
    """
    monkeypatch.setattr(cli, "fetch_closes", lambda tickers, period="1y": {ticker: closes})
    monkeypatch.setattr(
        cli,
        "_load_rank",
        lambda key: RankEntry(
            thresholds=RankThresholds(**thresholds),
            data_from=date(2002, 10, 15),
            data_to=data_to,
        ),
    )
    if intraday is not None:
        monkeypatch.setattr(cli, "fetch_intraday_price", lambda ticker, today: intraday)


class TestKoreaUsesItsOwnCalendarAndYesterday:
    """한국 알림은 한국 달력과 «전일» 을 본다."""

    def test_breaks_silence_for_a_stale_rank(
        self, monkeypatch: pytest.MonkeyPatch, kodex_thresholds: dict[str, float]
    ) -> None:
        """신호가 멀어도 순위가 낡았으면 보낸다.

        09-07 은 **한국 거래일이고 미국 휴장**이다. 달력을 미국으로 바꿔 끼우면 검사 구간에
        거래일이 하나도 없어 이 알림이 통째로 사라진다.
        """
        _install(
            monkeypatch,
            KODEX,
            _series([FRI, MON, TUE], [100000.0, 107000.0, 114500.0], tz=SEOUL),
            kodex_thresholds,
            data_to=FRI,
            intraday=107000.0,
        )

        text = cli._run_reverse(Market.KR, _at(TUE, 14, 30))

        assert text is not None
        assert "순위 갱신 필요" in text
        assert "09-07 (월) 폭등 +7.00%" in text

    def test_does_not_scan_today(self, monkeypatch: pytest.MonkeyPatch, kodex_thresholds: dict[str, float]) -> None:
        """오늘은 종가가 아직 없으므로 검사에 넣지 않는다.

        마지막 확정 종가일을 오늘로 주면 09-08 이 함께 잡힌다. 장중에 받은 일봉에는 당일
        미확정 봉이 섞여 오므로, 그 값을 확정 종가처럼 판정하면 **알림이 사실보다 앞서간다.**
        """
        _install(
            monkeypatch,
            KODEX,
            _series([FRI, MON, TUE], [100000.0, 107000.0, 114500.0], tz=SEOUL),
            kodex_thresholds,
            data_to=FRI,
            intraday=107000.0,
        )

        text = cli._run_reverse(Market.KR, _at(TUE, 14, 30))

        assert text is not None
        assert "09-07 (월) 폭등 +7.00%" in text
        # 09-08 을 검사에 넣었다면 114,500 / 107,000 - 1 = +7.01% 줄이 함께 나온다
        assert "+7.01%" not in text

    def test_stays_silent_when_the_rank_is_current(
        self, monkeypatch: pytest.MonkeyPatch, kodex_thresholds: dict[str, float]
    ) -> None:
        """신호가 멀고 순위도 최신이면 아무것도 보내지 않는다."""
        _install(
            monkeypatch,
            KODEX,
            _series([FRI, MON, TUE], [100000.0, 107000.0, 114500.0], tz=SEOUL),
            kodex_thresholds,
            data_to=MON,
            intraday=107000.0,
        )

        assert cli._run_reverse(Market.KR, _at(TUE, 14, 30)) is None


class TestUnitedStatesUsesItsOwnCalendarAndToday:
    """미국 알림은 미국 달력과 «판정 대상 그 날» 을 본다."""

    def test_confirmed_signal_carries_the_block(
        self, monkeypatch: pytest.MonkeyPatch, qqq_thresholds: dict[str, float]
    ) -> None:
        """종가가 확정됐으므로 판정 대상 날이 그대로 갱신 대상으로 적힌다.

        달력을 한국으로 바꿔 끼우면 09-07(미국 휴장)이 구간에 들어오고 그 종가가 없어
        검사가 실패한다 — 블록이 사라지는 것으로 드러난다.
        """
        _install(
            monkeypatch,
            QQQ,
            _series([FRI, TUE], [574.70, 619.50], tz=NEW_YORK),
            qqq_thresholds,
            data_to=FRI,
        )

        text = cli._run_reverse(Market.US, _at(WED, 7, 20))

        assert text is not None
        assert "폭등 발생" in text
        assert "순위 갱신 필요" in text
        assert "09-08 (화) 폭등 +7.80%" in text
        assert "미확정" not in text


class TestScanFailureNeverSwallowsTheSignal:
    """검사가 실패해도 신호 알림은 나간다 — 그날의 신호는 그날만 유효하다."""

    def test_signal_survives_a_gap_in_the_window(
        self, monkeypatch: pytest.MonkeyPatch, qqq_thresholds: dict[str, float]
    ) -> None:
        """창 안에 종가 공백이 있어도 신호를 보낸다. 블록만 빠진다.

        yfinance 는 거래일 행을 주면서 종가만 비워 보내는 일이 있고, 창은 최대 1년이라
        그 확률이 창 길이에 비례한다. 검사를 신호보다 먼저 두면 **연 5~8회뿐인 사건을
        공백 하나에 잃는다.**

        09-03 이 빠진 계열을 준다. 창이 09-02 부터 열리므로 공백이 창 **안**에 들어온다 —
        계열의 첫 날을 비우면 창 시작이 당겨져 공백을 비켜 가므로 그것으로는 재현되지 않는다.
        """
        _install(
            monkeypatch,
            QQQ,
            _series([GAP_START, GAP_NEXT, FRI, TUE], [500.0, 510.0, 574.70, 619.50], tz=NEW_YORK),
            qqq_thresholds,
            data_to=GAP_START,
        )

        text = cli._run_reverse(Market.US, _at(WED, 7, 20))

        assert text is not None
        assert "폭등 발생" in text
        assert "순위 갱신 필요" not in text

    def test_silent_run_still_fails_loudly_on_a_gap(
        self, monkeypatch: pytest.MonkeyPatch, qqq_thresholds: dict[str, float]
    ) -> None:
        """신호가 없으면 공백을 삼키지 않는다.

        삼키면 검사가 조용히 꺼진 채 알림은 정상으로 보인다. 지킬 신호가 없을 때는
        실패로 드러내는 것이 맞다.
        """
        _install(
            monkeypatch,
            QQQ,
            _series([GAP_START, GAP_NEXT, FRI, TUE], [500.0, 510.0, 574.70, 574.70], tz=NEW_YORK),
            qqq_thresholds,
            data_to=GAP_START,
        )

        with pytest.raises(ValueError):
            cli._run_reverse(Market.US, _at(WED, 7, 20))


class TestFreshRankDateIsNotAnError:
    """마감 뒤 «오늘» 날짜로 갱신한 파일은 정상이다.

    장중 판정은 마지막 확정 종가일이 **전일**이다. 그래서 「`data_to` 가 마지막 확정
    종가일보다 뒤인가」로 재면, 사용자가 마감 뒤 재계산해 오늘 날짜로 올린 **정상 파일**이
    걸린다 — 연 5~8회뿐인 신호 대신 실패 알림이 간다.

    **검사할 날이 없는 것과 값이 틀린 것은 다르다.** 말이 안 되는 미래 날짜는 파일을
    읽는 자리가 막고(`tests/test_state_loading.py`), 여기서는 조용히 비운다.
    """

    def test_data_to_on_today_stays_silent(
        self, monkeypatch: pytest.MonkeyPatch, kodex_thresholds: dict[str, float]
    ) -> None:
        """오늘로 갱신한 직후 장중 재실행은 그냥 조용하다."""
        _install(
            monkeypatch,
            KODEX,
            _series([FRI, MON, TUE], [100000.0, 107000.0, 114500.0], tz=SEOUL),
            kodex_thresholds,
            data_to=TUE,
            intraday=107000.0,
        )

        assert cli._run_reverse(Market.KR, _at(TUE, 14, 30)) is None

    def test_data_to_on_today_does_not_swallow_a_signal(
        self, monkeypatch: pytest.MonkeyPatch, kodex_thresholds: dict[str, float]
    ) -> None:
        """신호가 난 날이면 그 신호는 그대로 나간다. 갱신 블록만 없다."""
        _install(
            monkeypatch,
            KODEX,
            _series([FRI, MON, TUE], [100000.0, 107000.0, 114500.0], tz=SEOUL),
            kodex_thresholds,
            data_to=TUE,
            intraday=115000.0,
        )

        text = cli._run_reverse(Market.KR, _at(TUE, 14, 30))

        assert text is not None
        assert "폭등 도달" in text
        assert "순위 갱신 필요" in text
        # 확정 종가로 잡힌 날은 없고, 오늘 장중 줄만 붙는다
        assert "09-07 (월)" not in text

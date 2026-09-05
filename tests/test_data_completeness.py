"""부분 성공을 만들지 않는다는 정책을 고정한다.

반쪽 알림은 읽는 사람이 빠진 것을 알아차리기 어렵다. 티커 하나가 실패하면
전체를 실패로 처리한다.
"""

from __future__ import annotations

import pytest

from notify.data.validation import ensure_complete


class TestEnsureComplete:
    """조회 결과 완전성 검사."""

    def test_all_present_passes_through(self) -> None:
        """요청한 티커가 모두 값을 가지면 그대로 돌려준다."""
        fetched = {"SPY": 638.12, "QQQ": 566.30}

        assert ensure_complete(fetched, required=("SPY", "QQQ")) == fetched

    def test_missing_ticker_raises(self) -> None:
        """요청한 티커가 결과에 없으면 예외를 낸다."""
        with pytest.raises(ValueError):
            ensure_complete({"SPY": 638.12}, required=("SPY", "QQQ"))

    def test_none_value_raises(self) -> None:
        """값이 비어 있으면 예외를 낸다. 키만 있는 것으로는 부족하다."""
        with pytest.raises(ValueError):
            ensure_complete({"SPY": 638.12, "QQQ": None}, required=("SPY", "QQQ"))

    def test_one_failure_fails_the_whole_set(self) -> None:
        """넷 중 하나만 빠져도 전체가 실패한다. 성공한 셋을 살려 보내지 않는다."""
        fetched: dict[str, float | None] = {"SPY": 638.12, "QQQ": 566.30, "GLD": 315.88, "TLT": None}

        with pytest.raises(ValueError):
            ensure_complete(fetched, required=("SPY", "QQQ", "GLD", "TLT"))

    def test_error_names_the_missing_ticker(self) -> None:
        """예외 메시지에 빠진 티커가 담긴다. 무엇이 없었는지 알아야 다시 돌릴 수 있다."""
        with pytest.raises(ValueError, match="TLT"):
            ensure_complete({"SPY": 638.12, "TLT": None}, required=("SPY", "TLT"))

    def test_extra_tickers_are_dropped(self) -> None:
        """요청하지 않은 티커는 결과에 남기지 않는다."""
        fetched = {"SPY": 638.12, "QQQ": 566.30}

        assert ensure_complete(fetched, required=("SPY",)) == {"SPY": 638.12}

    def test_no_interpolation(self) -> None:
        """값이 없을 때 앞 값이나 평균으로 채우지 않는다. 없으면 없다고 하고 멈춘다."""
        with pytest.raises(ValueError):
            ensure_complete({"SPY": 100.0, "QQQ": None, "GLD": 300.0}, required=("SPY", "QQQ", "GLD"))

    def test_empty_requirement_gives_empty_result(self) -> None:
        """요청이 없으면 빈 결과다. 예외가 아니다."""
        assert ensure_complete({"SPY": 638.12}, required=()) == {}

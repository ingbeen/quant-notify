"""ECOS 환율 조회가 이상한 응답에서 멈추는지 고정한다.

값을 채우지 않고 멈춘다 (`docs/DESIGN.md` §7.4).
"""

from __future__ import annotations

from datetime import date

import pytest
import requests

from notify.data import ecos_client

START = date(2026, 9, 1)
END = date(2026, 9, 4)


class _FakeResponse:
    """`requests` 응답을 흉내 낸다. 테스트가 밖으로 나가지 않게 한다."""

    def __init__(self, payload: object) -> None:
        """응답 본문을 담는다.

        Args:
            payload: 돌려줄 본문.
        """
        self._payload = payload

    def raise_for_status(self) -> None:
        """성공 응답이므로 아무것도 하지 않는다."""

    def json(self) -> object:
        """응답 본문을 돌려준다.

        Returns:
            본문.
        """
        return self._payload


def _rows(*pairs: tuple[str, str]) -> dict[str, object]:
    """`StatisticSearch` 응답 본문을 만든다.

    Args:
        *pairs: (날짜 `YYYYMMDD`, 값 문자열) 목록.

    Returns:
        응답 본문.
    """
    return {"StatisticSearch": {"row": [{"TIME": day, "DATA_VALUE": value} for day, value in pairs]}}


def _install(monkeypatch: pytest.MonkeyPatch, payload: object) -> None:
    """`requests.get` 을 가짜로 바꾼다.

    Args:
        monkeypatch: pytest 픽스처.
        payload: 돌려줄 본문.
    """

    def fake_get(url: str, timeout: int) -> _FakeResponse:
        del url, timeout
        return _FakeResponse(payload)

    monkeypatch.setattr(ecos_client.requests, "get", fake_get)


class TestRatesMustBePositive:
    """0 이하 환율."""

    def test_non_positive_rate_is_a_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """0 이하 환율은 실재할 수 없다. 평균에 섞이면 평균대비가 조용히 틀린다."""
        _install(monkeypatch, _rows(("20260903", "1384.8"), ("20260904", "0")))

        with pytest.raises(ValueError, match="0 이하"):
            ecos_client.fetch_usdkrw("KEY", START, END)


class TestFailuresStop:
    """조회 실패와 이상한 응답."""

    def test_request_failure_hides_the_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """조회가 실패하면 인증키를 가려 `ValueError` 로 올린다. 원본 예외를 연쇄로 달지 않는다."""
        key = "ABCD1234EFGH5678"

        def fake_get(url: str, timeout: int) -> _FakeResponse:
            del timeout
            raise requests.ConnectionError(f"failed: {url}")

        monkeypatch.setattr(ecos_client.requests, "get", fake_get)

        with pytest.raises(ValueError, match="ECOS 조회") as caught:
            ecos_client.fetch_usdkrw(key, START, END)

        assert key not in str(caught.value)
        assert caught.value.__cause__ is None

    def test_error_result_is_a_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """ECOS 가 오류 코드를 돌려주면 그 코드를 담아 멈춘다."""
        _install(monkeypatch, {"RESULT": {"CODE": "INFO-100", "MESSAGE": "인증키가 유효하지 않습니다."}})

        with pytest.raises(ValueError, match="INFO-100"):
            ecos_client.fetch_usdkrw("KEY", START, END)

    def test_no_rows_is_a_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """받은 행이 없으면 멈춘다. 빈 계열로 평균을 내지 않는다."""
        _install(monkeypatch, {"StatisticSearch": {"row": []}})

        with pytest.raises(ValueError, match="행이 없습니다"):
            ecos_client.fetch_usdkrw("KEY", START, END)

    def test_non_numeric_rate_is_a_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """숫자로 읽히지 않는 값이 있으면 채우지 않고 멈춘다."""
        _install(monkeypatch, _rows(("20260903", "1384.8"), ("20260904", "-")))

        with pytest.raises(ValueError, match="숫자"):
            ecos_client.fetch_usdkrw("KEY", START, END)


class TestNormalPath:
    """정상 응답."""

    def test_rates_are_indexed_by_date_in_order(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """날짜를 인덱스로, 오래된 값이 앞에 오게 정렬한다."""
        _install(monkeypatch, _rows(("20260904", "1384.8"), ("20260903", "1383.1")))

        series = ecos_client.fetch_usdkrw("KEY", START, END)

        assert list(series.index) == [date(2026, 9, 3), date(2026, 9, 4)]
        assert list(series) == [1383.1, 1384.8]

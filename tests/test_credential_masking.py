"""자격증명 마스킹을 고정한다.

**자격증명을 URL 경로에 넣는 API 가 둘이고 형태가 다르다.** ECOS 인증키는 영숫자 한 조각이고,
텔레그램 봇 토큰은 `:` 와 `-` 가 섞인다. 영숫자만 잡는 패턴으로는 토큰이 그대로 새므로
둘을 따로 잡는다.

주소를 그대로 로그에 남기면 자격증명이 박히고, 이 저장소는 실행 로그가 공개되는 곳에서 돈다.
"""

from __future__ import annotations

import logging

import pytest
import requests

from notify.notifier import telegram
from notify.utils.logger import get_logger, mask_credentials

SAMPLE_KEY = "ABCD1234EFGH5678"

# 텔레그램 봇 토큰. 숫자 · 콜론 · 영숫자와 하이픈이 섞인 실제 형태다
SAMPLE_TOKEN = "7123456789:AAF-abcdefGHIJKLmnopQRSTuvwx12345678"


class TestMaskCredentials:
    """문자열 마스킹."""

    def test_masks_key_in_path(self) -> None:
        """경로에 들어간 인증키를 가린다."""
        url = f"https://ecos.bok.or.kr/api/StatisticSearch/{SAMPLE_KEY}/json/kr/1/100"

        assert SAMPLE_KEY not in mask_credentials(url)

    def test_keeps_the_rest_of_the_url(self) -> None:
        """주소의 나머지는 남긴다. 어디를 부르다 실패했는지는 알아야 한다."""
        url = f"https://ecos.bok.or.kr/api/StatisticSearch/{SAMPLE_KEY}/json/kr/1/100"
        masked = mask_credentials(url)

        assert "ecos.bok.or.kr" in masked
        assert "StatisticSearch" in masked

    def test_masks_key_in_query(self) -> None:
        """질의 문자열에 담긴 키도 가린다."""
        assert SAMPLE_KEY not in mask_credentials(f"https://example.com/v1?api_key={SAMPLE_KEY}&range=1y")

    def test_masks_token_in_query(self) -> None:
        """토큰이라는 이름으로 담겨도 가린다."""
        assert SAMPLE_KEY not in mask_credentials(f"https://example.com/v1?token={SAMPLE_KEY}")

    def test_keeps_other_query_parameters(self) -> None:
        """키가 아닌 값은 남긴다."""
        masked = mask_credentials(f"https://example.com/v1?api_key={SAMPLE_KEY}&range=1y")

        assert "range=1y" in masked

    def test_plain_text_is_untouched(self) -> None:
        """가릴 것이 없으면 그대로 둔다."""
        message = "시세를 받지 못한 종목이 있습니다: TLT"

        assert mask_credentials(message) == message

    def test_short_path_segments_are_untouched(self) -> None:
        """짧은 경로 조각은 키가 아니므로 그대로 둔다."""
        masked = mask_credentials("https://ecos.bok.or.kr/api/json/kr/1/100/731Y001")

        assert "json" in masked
        assert "kr" in masked


class TestMaskTelegramToken:
    """텔레그램 봇 토큰.

    토큰에는 `:` 와 `-` 가 섞여 있어 **영숫자만 잡는 경로 패턴에 걸리지 않는다.**
    따로 잡지 않으면 발송 실패 메시지에 그대로 실린다.
    """

    def test_masks_the_token_in_the_send_url(self) -> None:
        """발송 주소에 담긴 토큰을 가린다."""
        url = f"https://api.telegram.org/bot{SAMPLE_TOKEN}/sendMessage"

        assert SAMPLE_TOKEN not in mask_credentials(url)

    def test_keeps_the_rest_of_the_send_url(self) -> None:
        """어디를 부르다 실패했는지는 남긴다."""
        masked = mask_credentials(f"https://api.telegram.org/bot{SAMPLE_TOKEN}/sendMessage")

        assert "api.telegram.org" in masked
        assert "sendMessage" in masked

    def test_masks_the_token_inside_a_requests_message(self) -> None:
        """`requests` 예외 문자열에 섞여 있어도 가린다. 실제로 새는 모양이 이것이다."""
        message = "401 Client Error: Unauthorized for url: " f"https://api.telegram.org/bot{SAMPLE_TOKEN}/sendMessage"

        assert SAMPLE_TOKEN not in mask_credentials(message)

    def test_masks_a_bare_token(self) -> None:
        """주소 없이 찍힌 토큰도 가린다.

        **주소 모양이 아니라 토큰 모양으로 잡기 때문이다.** `/bot` 접두사에 기대면
        접두사 없이 나온 값을 통째로 놓친다.
        """
        assert SAMPLE_TOKEN not in mask_credentials(f"chat_id=123456789 {SAMPLE_TOKEN}")

    def test_words_containing_bot_are_untouched(self) -> None:
        """`bot` 이 든 경로·파일명을 건드리지 않는다.

        전에 `/bot` 접두사로 잡다가 **저장소 이름과 트레이스백을 지웠다** —
        `.../repos/owner/bot-alerts/...` 는 실행 이력 조회가 실패했을 때
        유일하게 쓸모 있는 단서이고, `bot.py",` 는 닫는 따옴표까지 먹혔다.
        """
        for text in (
            "https://example.com/robots.txt",
            "https://example.com/robot/abc",
            "404 for url: https://api.github.com/repos/owner/bot-alerts/actions/workflows/usdkrw.yml/runs",
            'File "/Users/x/src/notify/bot.py", line 12',
        ):
            assert mask_credentials(text) == text

    def test_plain_long_numbers_are_untouched(self) -> None:
        """콜론 뒤 토큰 몸통이 없으면 긴 숫자라도 그대로 둔다."""
        message = "정산월 202607 · 회원 1234567890 건"

        assert mask_credentials(message) == message

    def test_masking_is_idempotent(self) -> None:
        """이미 가린 문자열을 다시 통과시켜도 그대로다.

        마스킹한 메시지가 로거를 한 번 더 지나므로 이 성질이 필요하다.
        """
        once = mask_credentials(f"https://api.telegram.org/bot{SAMPLE_TOKEN}/sendMessage")

        assert mask_credentials(once) == once


class TestSendFailureCarriesNoToken:
    """발송이 실패했을 때 올라가는 예외.

    이 예외는 잡히지 않고 트레이스백으로 나간다 (`docs/DESIGN.md` §7.2 — 텔레그램이
    죽으면 Actions 실패 메일이 맡는다). **그래서 마스킹이 로거가 아니라 발송 모듈
    «안»에서 되어야** 트레이스백까지 덮인다.
    """

    def test_raised_message_has_no_token(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """올라가는 메시지에 토큰이 없다."""

        def _unauthorized(url: str, **kwargs: object) -> None:
            del kwargs
            raise requests.HTTPError(f"401 Client Error: Unauthorized for url: {url}")

        monkeypatch.setattr(telegram.requests, "post", _unauthorized)

        with pytest.raises(ValueError) as caught:
            telegram.send(SAMPLE_TOKEN, "12345", "본문")

        assert SAMPLE_TOKEN not in str(caught.value)
        assert "api.telegram.org" in str(caught.value)

    def test_original_exception_is_not_chained(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """원본 `requests` 예외를 연쇄로 달지 않는다.

        달면 가리지 않은 주소가 트레이스백 위쪽에 다시 찍힌다.
        """

        def _unauthorized(url: str, **kwargs: object) -> None:
            del kwargs
            raise requests.HTTPError(f"401 Client Error: Unauthorized for url: {url}")

        monkeypatch.setattr(telegram.requests, "post", _unauthorized)

        with pytest.raises(ValueError) as caught:
            telegram.send(SAMPLE_TOKEN, "12345", "본문")

        assert caught.value.__cause__ is None
        assert caught.value.__context__ is None or caught.value.__suppress_context__


class TestLoggerMasking:
    """로거를 통과하는 메시지."""

    def test_logger_masks_message(self) -> None:
        """로그로 내보낸 메시지에서도 키가 사라진다."""
        logger = get_logger("notify.test.masking")
        records: list[str] = []

        class _Capture(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                records.append(record.getMessage())

        handler = _Capture()
        logger.addHandler(handler)
        try:
            logger.debug("조회 실패: https://ecos.bok.or.kr/api/StatisticSearch/%s/json", SAMPLE_KEY)
        finally:
            logger.removeHandler(handler)

        assert records
        assert SAMPLE_KEY not in records[0]

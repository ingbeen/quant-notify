"""자격증명 마스킹을 고정한다.

ECOS 는 인증키를 URL 경로에 넣는다. 주소를 그대로 로그에 남기면 키가 박히고,
이 저장소는 실행 로그가 공개되는 곳에서 돈다.
"""

from __future__ import annotations

import logging

from notify.utils.logger import get_logger, mask_credentials

SAMPLE_KEY = "ABCD1234EFGH5678"


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

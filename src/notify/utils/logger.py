"""로깅 설정과 자격증명 마스킹.

로그 포맷에 함수명이 자동으로 들어가므로 메시지에 함수명을 다시 적지 않는다.
INFO 레벨은 쓰지 않는다 — 일반 정보는 DEBUG 로 남긴다.
"""

from __future__ import annotations

import logging
import re
import sys

_FORMAT = "%(asctime)s [%(levelname)s] %(name)s.%(funcName)s: %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# 인증키가 경로에 들어가는 주소에서 키 자리만 잡아낸다
_KEY_IN_PATH = re.compile(r"(?<=/)[A-Za-z0-9]{16,}(?=/|$)")

# 질의 문자열에 담긴 키
_KEY_IN_QUERY = re.compile(r"((?:api[_-]?key|authkey|key|token)=)[^&\s]+", re.IGNORECASE)

_MASK = "***"


def mask_credentials(text: str) -> str:
    """문자열에 담긴 자격증명을 가린다.

    ECOS 는 인증키를 URL 경로에 넣으므로 주소를 그대로 남기면 키가 로그에 박힌다.
    예외 메시지에도 주소가 담기니 로깅 직전에 이 함수를 통과시킨다.

    Args:
        text: 가릴 문자열.

    Returns:
        자격증명 자리가 가려진 문자열.
    """
    masked = _KEY_IN_QUERY.sub(rf"\1{_MASK}", text)
    return _KEY_IN_PATH.sub(_MASK, masked)


class _MaskingFilter(logging.Filter):
    """로그 레코드의 메시지에서 자격증명을 가린다.

    포맷을 끝낸 뒤에 가린다. 인자 하나만 떼어 보면 그 값이 인증키인지 알 수 없어,
    조각난 상태로는 경로 안의 키를 알아보지 못한다.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """레코드를 통과시키기 전에 메시지를 가린다.

        Args:
            record: 로그 레코드.

        Returns:
            항상 True. 레코드를 버리지 않는다.
        """
        record.msg = mask_credentials(record.getMessage())
        record.args = None
        return True


def get_logger(name: str, level: int = logging.DEBUG) -> logging.Logger:
    """이름 있는 로거를 만든다.

    Args:
        name: 로거 이름. 보통 모듈의 `__name__`.
        level: 로그 레벨.

    Returns:
        표준 에러로 내보내는 로거.
    """
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(_FORMAT, datefmt=_DATE_FORMAT))

    # 필터를 로거에 건다. 핸들러에 걸면 나중에 붙는 핸들러가 가려지지 않은 레코드를 받는다
    logger.addFilter(_MaskingFilter())
    logger.addHandler(handler)
    logger.setLevel(level)
    logger.propagate = False
    return logger

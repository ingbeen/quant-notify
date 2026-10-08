"""알림 문구의 공통 표기. 표기 규칙과 그 근거의 정본은 `docs/DESIGN.md` §4.3 이다."""

from __future__ import annotations

from datetime import date, datetime

# 한글 요일. date.weekday() 순서에 맞춘다
_WEEKDAYS = ("월", "화", "수", "목", "금", "토", "일")

# 빨간 점. 소스를 ASCII 로 두려고 이스케이프로 적는다 (전역 규칙 「코드 파일에는 이모지를 쓰지 않는다」)
RED_DOT = "\U0001f534"


def escape_html(text: str) -> str:
    """텔레그램 HTML 모드에서 뜻을 가지는 문자를 막는다.

    **값에만 쓴다.** 조립이 끝난 문구에 쓰면 강조 태그까지 글자로 바뀐다.

    Args:
        text: 가릴 문자열.

    Returns:
        이스케이프한 문자열.
    """
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def bold(text: str) -> str:
    """굵게 표시한다.

    Args:
        text: 강조할 문자열.

    Returns:
        굵게 표시한 문자열.
    """
    return f"<b>{text}</b>"


def alert(text: str) -> str:
    """빨간 점을 붙여 굵게 표시한다. 붙이는 자리는 `docs/DESIGN.md` §4.3 이 정한다.

    Args:
        text: 강조할 문자열.

    Returns:
        빨간 점을 붙여 굵게 표시한 문자열.
    """
    return f"{RED_DOT} {bold(text)}"


def format_day(day: date) -> str:
    """날짜를 알림 표기로 바꾼다.

    Args:
        day: 날짜.

    Returns:
        `MM-DD (요일)` 형태.
    """
    return f"{day:%m-%d} ({_WEEKDAYS[day.weekday()]})"


def format_sent_at(sent_at: datetime) -> str:
    """발송 시각을 알림 표기로 바꾼다.

    Args:
        sent_at: 발송 시각.

    Returns:
        `MM-DD (요일) HH:MM` 형태.
    """
    return f"{format_day(sent_at.date())} {sent_at:%H:%M}"


def format_rate(rate: float, decimals: int = 2) -> str:
    """비율을 백분율 표기로 바꾼다. 부호를 항상 붙인다.

    Args:
        rate: 비율 (0.0610 = +6.10%).
        decimals: 소수 자리.

    Returns:
        부호가 붙은 백분율 문자열.
    """
    return f"{rate * 100:+.{decimals}f}%"


def format_weight(ratio: float) -> str:
    """비중을 백분율 표기로 바꾼다. 부호를 붙이지 않는다.

    Args:
        ratio: 비율 (0.873 = 87.3%).

    Returns:
        백분율 문자열.
    """
    return f"{ratio * 100:.1f}%"


def format_krw(price: float, decimals: int = 0) -> str:
    """원화 가격을 표기한다.

    Args:
        price: 가격.
        decimals: 소수 자리.

    Returns:
        천 단위를 끊고 단위를 붙인 문자열.
    """
    return f"{price:,.{decimals}f}원"

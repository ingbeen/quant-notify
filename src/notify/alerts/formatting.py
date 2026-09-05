"""알림 문구의 공통 표기 규칙.

문구는 고정폭으로 읽힌다. 한글은 두 칸을 차지하므로 글자 수가 아니라 **표시 폭**으로
자리를 맞춰야 열이 어긋나지 않는다.

표기 규칙의 정본은 `docs/DESIGN.md` 4.5 절이다.
"""

from __future__ import annotations

import unicodedata
from datetime import date

# 한글 요일. date.weekday() 순서에 맞춘다
_WEEKDAYS = ("월", "화", "수", "목", "금", "토", "일")

# 두 칸을 차지하는 문자 폭 구분
_WIDE = frozenset({"W", "F"})


def display_width(text: str) -> int:
    """고정폭에서 차지하는 칸 수를 센다.

    Args:
        text: 잴 문자열.

    Returns:
        칸 수. 한글과 전각 기호는 두 칸으로 센다.
    """
    return sum(2 if unicodedata.east_asian_width(char) in _WIDE else 1 for char in text)


def pad_start(text: str, width: int) -> str:
    """표시 폭을 기준으로 오른쪽에 붙인다.

    Args:
        text: 붙일 문자열.
        width: 목표 칸 수.

    Returns:
        앞을 공백으로 채운 문자열. 이미 넘치면 그대로 돌려준다.
    """
    return " " * max(0, width - display_width(text)) + text


def pad_end(text: str, width: int) -> str:
    """표시 폭을 기준으로 왼쪽에 붙인다.

    Args:
        text: 붙일 문자열.
        width: 목표 칸 수.

    Returns:
        뒤를 공백으로 채운 문자열. 이미 넘치면 그대로 돌려준다.
    """
    return text + " " * max(0, width - display_width(text))


def format_day(day: date) -> str:
    """날짜를 알림 표기로 바꾼다.

    Args:
        day: 날짜.

    Returns:
        `MM-DD (요일)` 형태.
    """
    return f"{day:%m-%d} ({_WEEKDAYS[day.weekday()]})"


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


def format_usd(price: float) -> str:
    """달러 가격을 표기한다.

    Args:
        price: 가격.

    Returns:
        기호를 앞에 붙이고 소수 둘째 자리까지 끊은 문자열.
    """
    return f"${price:,.2f}"

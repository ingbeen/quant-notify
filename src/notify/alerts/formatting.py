"""알림 문구의 공통 표기 규칙.

문구는 텔레그램 HTML 모드로 보낸다. **강조 수단은 굵게와 빨간 점 둘뿐이다** —
텔레그램은 글자 색을 지원하지 않고, 고정폭(`<pre>`)은 다른 서식과 조합할 수 없어
강조를 넣으려면 고정폭을 버려야 한다.

그래서 **한 줄에 값 하나를 쌓는다.** 정렬로 뜻을 나르지 않으므로 가로 폭 제약이 없다.
모바일은 긴 줄을 낱말 단위로 접으므로, 열을 맞춰도 좁은 화면에서 그대로 무너진다.

표기 규칙의 정본은 `docs/DESIGN.md` 4.5 절이다.
"""

from __future__ import annotations

from datetime import date

# 한글 요일. date.weekday() 순서에 맞춘다
_WEEKDAYS = ("월", "화", "수", "목", "금", "토", "일")

# 눈에 띄어야 하는 것에만 붙인다 — 역방향 신호 · 실패 · 점검 이상.
# 소스를 ASCII 로 유지하려고 이스케이프로 적는다 (루트 CLAUDE.md 의 이모지 규칙)
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
    """빨간 점을 붙여 굵게 표시한다.

    **꼭 봐야 하는 것에만 쓴다** — 역방향 신호 · 실패 · 점검 이상. 정기 알림에 쓰면
    색이 흔해져 정작 사건일 때 눈에 걸리지 않는다.

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


def format_day_paren(day: date) -> str:
    """날짜를 값 뒤에 덧붙이는 표기로 바꾼다.

    Args:
        day: 날짜.

    Returns:
        `(MM-DD 요일)` 형태.
    """
    return f"({day:%m-%d} {_WEEKDAYS[day.weekday()]})"


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

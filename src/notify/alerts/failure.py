"""실패 알림 문구. 형식의 정본은 `docs/DESIGN.md` §4.3 「실패 알림」이다."""

from __future__ import annotations

from datetime import datetime

from notify.alerts.formatting import alert, escape_html, format_sent_at
from notify.utils.logger import mask_credentials


def render(alert_name: str, error: BaseException, sent_at: datetime) -> str:
    """실패 알림 문구를 만든다.

    예외 메시지는 가리고(조회 주소에 인증키가 들어갈 수 있다) 이스케이프한다(바깥에서 온 문자열이다).

    Args:
        alert_name: 실패한 알림 이름.
        error: 잡은 예외.
        sent_at: 발송 시각.

    Returns:
        보낼 문구.
    """
    detail = escape_html(mask_credentials(f"{type(error).__name__}: {error}"))

    return "\n".join([alert(f"실패 · {alert_name}"), format_sent_at(sent_at), "", detail])

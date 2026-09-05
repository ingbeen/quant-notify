"""텔레그램으로 알림을 보낸다.

**고정폭으로 보낸다.** 문구의 뜻이 정렬에 실려 있어, 비례폭으로 표시되면 열이 무너져
읽을 수 없다. 텔레그램은 `<pre>` 안의 내용을 고정폭으로 보여준다.

**알림 채널 자체의 실패는 다시 알리지 않는다.** 실패 알림을 보내다 실패했다고 또 알림을
보내면 같은 자리에서 돌기만 한다. 그 경우는 로그로만 남기고, GitHub Actions 실패 메일이
마지막 보루가 된다.
"""

from __future__ import annotations

import requests

from notify.utils.logger import get_logger

logger = get_logger(__name__)

TELEGRAM_API = "https://api.telegram.org"

# 발송 제한 시간 (초)
TIMEOUT_SECONDS = 15


def _escape_html(text: str) -> str:
    """텔레그램 HTML 모드에서 뜻을 가지는 문자를 막는다.

    Args:
        text: 보낼 문구.

    Returns:
        이스케이프한 문구.
    """
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build_payload(chat_id: str, text: str) -> dict[str, str | bool]:
    """발송 본문을 만든다.

    Args:
        chat_id: 받을 대화방.
        text: 보낼 문구.

    Returns:
        요청 본문.
    """
    return {
        "chat_id": chat_id,
        "text": f"<pre>{_escape_html(text)}</pre>",
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }


def send(token: str, chat_id: str, text: str) -> None:
    """알림을 보낸다.

    Args:
        token: 봇 토큰.
        chat_id: 받을 대화방.
        text: 보낼 문구.

    Raises:
        ValueError: 발송이 실패했을 때.
    """
    url = f"{TELEGRAM_API}/bot{token}/sendMessage"

    try:
        response = requests.post(url, json=build_payload(chat_id, text), timeout=TIMEOUT_SECONDS)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise ValueError(f"텔레그램 발송에 실패했습니다: {exc}") from None

    logger.debug(f"알림을 보냈습니다 ({len(text)}자)")


def send_without_raising(token: str, chat_id: str, text: str) -> bool:
    """실패해도 예외를 올리지 않고 보낸다.

    **실패 알림을 보낼 때 쓴다.** 여기서 예외를 올리면 실패를 알리려다 다시 실패하고,
    그 실패를 또 알리려 든다.

    Args:
        token: 봇 토큰.
        chat_id: 받을 대화방.
        text: 보낼 문구.

    Returns:
        보냈으면 True.
    """
    try:
        send(token, chat_id, text)
    except Exception as exc:
        logger.warning(f"실패 알림을 보내지 못했습니다: {exc}")
        return False
    return True

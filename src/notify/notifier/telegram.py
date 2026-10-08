"""텔레그램으로 알림을 보낸다.

문구는 이미 HTML 이라 여기서 이스케이프하지 않는다 — 다시 하면 강조 태그까지 글자가 된다.

봇 토큰이 요청 주소에 들어가므로 예외를 **여기서 가려** 다시 낸다. 발송 실패는 잡히지 않고
트레이스백으로 끝나 로거 마스킹이 닿지 않는다 (`docs/DESIGN.md` §3.4 · §7.2).
"""

from __future__ import annotations

import requests

from notify.utils.logger import get_logger, mask_credentials

logger = get_logger(__name__)

TELEGRAM_API = "https://api.telegram.org"

# 발송 제한 시간 (초)
TIMEOUT_SECONDS = 15


def send(token: str, chat_id: str, text: str) -> None:
    """알림을 보낸다.

    Args:
        token: 봇 토큰.
        chat_id: 받을 대화방.
        text: 보낼 문구. 이미 HTML 이다.

    Raises:
        ValueError: 발송이 실패했을 때.
    """
    url = f"{TELEGRAM_API}/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}

    try:
        response = requests.post(url, json=payload, timeout=TIMEOUT_SECONDS)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise ValueError(f"텔레그램 발송에 실패했습니다: {mask_credentials(str(exc))}") from None

    logger.debug(f"알림을 보냈습니다 ({len(text)}자)")


def send_without_raising(token: str, chat_id: str, text: str) -> None:
    """실패해도 예외를 올리지 않고 보낸다.

    **실패 알림을 보낼 때 쓴다.** 여기서 예외를 올리면 실패를 알리려다 다시 실패한다.

    Args:
        token: 봇 토큰.
        chat_id: 받을 대화방.
        text: 보낼 문구.
    """
    try:
        send(token, chat_id, text)
    except Exception as exc:
        logger.warning(f"실패 알림을 보내지 못했습니다: {exc}")

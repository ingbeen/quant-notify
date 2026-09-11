"""텔레그램으로 알림을 보낸다.

**문구가 이미 HTML 이다.** 굵게와 빨간 점으로 강조하므로 여기서 손대지 않고 그대로 보낸다.
값 이스케이프는 문구를 만들 때 끝나 있다 — 여기서 다시 이스케이프하면 강조 태그까지
글자로 바뀐다.

**알림 채널 자체의 실패는 다시 알리지 않는다.** 실패 알림을 보내다 실패했다고 또 알림을
보내면 같은 자리에서 돌기만 한다. 그 경우는 로그로만 남기고, GitHub Actions 실패 메일이
마지막 보루가 된다.

**봇 토큰이 요청 주소에 들어간다.** `requests` 예외 문자열은 주소를 담으므로 그대로 올리면
토큰이 밖으로 나간다 — 이 예외는 잡히지 않고 트레이스백으로 끝나므로 로거 마스킹이 닿지
않는다. 그래서 **여기서 가려서** 다시 낸다. `data/ecos_client.py` 와 같은 방식이다.
"""

from __future__ import annotations

import requests

from notify.utils.logger import get_logger, mask_credentials

logger = get_logger(__name__)

TELEGRAM_API = "https://api.telegram.org"

# 발송 제한 시간 (초)
TIMEOUT_SECONDS = 15


def build_payload(chat_id: str, text: str) -> dict[str, str | bool]:
    """발송 본문을 만든다.

    Args:
        chat_id: 받을 대화방.
        text: 보낼 문구. 이미 HTML 이다.

    Returns:
        요청 본문.
    """
    return {
        "chat_id": chat_id,
        "text": text,
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
        raise ValueError(f"텔레그램 발송에 실패했습니다: {mask_credentials(str(exc))}") from None

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

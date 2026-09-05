"""실패 알림 문구.

**제목과 예외 메시지만 낸다.** 「재시도하지 않습니다」 같은 안내를 붙이지 않는다 —
재시도가 없다는 것은 이미 설계이고, 매번 읽히는 문구가 아니다.

침묵 알림의 실패도 실패 알림을 보낸다. 신호가 없어서 조용한 것과 오류로 조용한 것이
구분되어야 한다.
"""

from __future__ import annotations

from datetime import datetime

from notify.alerts.formatting import format_day
from notify.utils.logger import mask_credentials


def render(alert_name: str, error: BaseException, sent_at: datetime) -> str:
    """실패 알림 문구를 만든다.

    예외 메시지를 마스킹해서 담는다. 조회 주소에 인증키가 들어가는 경우가 있고,
    이 저장소는 실행 로그가 공개되는 곳에서 돈다.

    Args:
        alert_name: 실패한 알림 이름.
        error: 잡은 예외.
        sent_at: 발송 시각.

    Returns:
        보낼 문구.
    """
    detail = mask_credentials(f"{type(error).__name__}: {error}")

    return "\n".join(
        [
            f"[QBT · 실패] {alert_name}   {format_day(sent_at.date())} {sent_at:%H:%M}",
            "",
            detail,
        ]
    )

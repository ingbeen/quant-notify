"""설정값을 읽는다. **읽는 길은 이것 하나다.**

환경 변수를 먼저 보고 없으면 `.env` 를 본다. 로컬은 `.env` 파일이고, GitHub Actions 에는
그 파일이 아예 없어 시크릿이 환경 변수로 들어온다.

**두 길을 두면 워크플로에서만 깨진다.** 전에 ECOS 인증키만 `.env` 를 직접 열고 있었는데,
로컬에는 파일이 있어 테스트도 dry-run 도 전부 통과했고 Actions 에서만 드러났다. 그래서
설정을 읽는 함수를 여기 하나만 둔다 — 파일을 직접 여는 함수를 따로 만들지 않는다.

알림 도메인이 아니라 **실행 환경**을 다루므로 `utils/` 에 둔다.
"""

from __future__ import annotations

import os

from dotenv import dotenv_values

from notify.common_constants import ENV_FILE_PATH


def read_config(name: str, required: bool = True) -> str:
    """설정값을 읽는다.

    Args:
        name: 설정 이름.
        required: 없을 때 예외를 낼지 여부.

    Returns:
        설정값. 없고 필수가 아니면 빈 문자열.

    Raises:
        ValueError: 필수인데 값이 없을 때.
    """
    value = os.environ.get(name) or dotenv_values(ENV_FILE_PATH).get(name) or ""
    value = value.strip()
    if required and not value:
        raise ValueError(f"{name} 가 없습니다. `.env` 또는 워크플로 시크릿에 넣으세요.")
    return value

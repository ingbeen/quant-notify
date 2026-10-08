"""설정값을 읽는다. **읽는 길은 이것 하나다.**

환경 변수를 먼저 보고 없으면 `.env` 를 본다. 로컬은 `.env` 이고, GitHub Actions 에는 그 파일이
없어 시크릿이 환경 변수로 들어온다. 파일을 직접 여는 함수를 따로 두지 않는다 — 길이 둘이면
한쪽 환경에서만 깨진다 (`docs/research/데이터소스_실측.md` §1.7).
"""

from __future__ import annotations

import os

from dotenv import dotenv_values

from notify.common_constants import ENV_FILE_PATH

# 설정 이름. 워크플로가 넣는 환경 변수 이름과 같아야 한다 (`GITHUB_REPOSITORY` 는 Actions 가 기본으로 넣는다)
ENV_TELEGRAM_BOT_TOKEN = "TELEGRAM_BOT_TOKEN"
ENV_TELEGRAM_CHAT_ID = "TELEGRAM_CHAT_ID"
ENV_ECOS_API_KEY = "ECOS_API_KEY"
ENV_GITHUB_REPOSITORY = "GITHUB_REPOSITORY"
ENV_GITHUB_TOKEN = "GITHUB_TOKEN"


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

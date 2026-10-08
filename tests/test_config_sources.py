"""설정값을 어디서 읽는지 고정한다.

워크플로에는 `.env` 가 없고 시크릿이 환경 변수로 들어온다. 그래서 **`.env` 가 없는 상황**에서
환경 변수 경로가 살아 있는지 본다 (`docs/research/데이터소스_실측.md` §1.7).
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from notify import cli
from notify.common_constants import TZ_KST
from notify.utils import config
from notify.utils.config import ENV_ECOS_API_KEY, ENV_GITHUB_TOKEN


@pytest.fixture
def without_env_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """`.env` 가 없는 상황을 만든다. 워크플로가 그 상태다.

    Args:
        monkeypatch: 패치 도구.
        tmp_path: 임시 디렉터리.
    """
    monkeypatch.setattr(config, "ENV_FILE_PATH", tmp_path / "not-there.env")


class TestConfig:
    """설정 읽기."""

    def test_reads_from_environment_without_env_file(
        self, monkeypatch: pytest.MonkeyPatch, without_env_file: None
    ) -> None:
        """`.env` 가 없어도 환경 변수로 읽는다."""
        monkeypatch.setenv(ENV_ECOS_API_KEY, "KEY-FROM-ENVIRONMENT")

        assert config.read_config(ENV_ECOS_API_KEY) == "KEY-FROM-ENVIRONMENT"

    def test_missing_required_value_raises(self, monkeypatch: pytest.MonkeyPatch, without_env_file: None) -> None:
        """필수인데 어디에도 없으면 예외다. 빈 값으로 조회에 들어가지 않는다."""
        monkeypatch.delenv(ENV_ECOS_API_KEY, raising=False)

        with pytest.raises(ValueError, match=ENV_ECOS_API_KEY):
            config.read_config(ENV_ECOS_API_KEY)

    def test_optional_value_returns_empty(self, monkeypatch: pytest.MonkeyPatch, without_env_file: None) -> None:
        """필수가 아니면 빈 문자열을 돌려준다. 점검 줄이 이 경로를 쓴다."""
        monkeypatch.delenv(ENV_GITHUB_TOKEN, raising=False)

        assert config.read_config(ENV_GITHUB_TOKEN, required=False) == ""


class TestUsdKrwReadsTheKeyLikeEverythingElse:
    """원달러 알림의 인증키도 다른 설정과 같은 길로 읽는지 통합 지점에서 확인한다."""

    def test_takes_the_key_from_environment(self, monkeypatch: pytest.MonkeyPatch, without_env_file: None) -> None:
        """`.env` 없이 환경 변수만으로 인증키가 조회 함수까지 닿는다."""
        monkeypatch.setenv(ENV_ECOS_API_KEY, "KEY-FROM-ENVIRONMENT")
        seen: dict[str, str] = {}

        def _capture(api_key: str, start: object, end: object) -> None:
            """인증키만 받아 두고 멈춘다.

            Args:
                api_key: 인증키.
                start: 시작일.
                end: 종료일.

            Raises:
                RuntimeError: 항상. 여기서 더 갈 필요가 없다.
            """
            del start, end
            seen["api_key"] = api_key
            raise RuntimeError("여기까지만 본다")

        monkeypatch.setattr(cli, "fetch_usdkrw", _capture)

        with pytest.raises(RuntimeError, match="여기까지만"):
            cli.run_usdkrw(datetime(2026, 9, 7, 7, 30, tzinfo=TZ_KST))

        assert seen["api_key"] == "KEY-FROM-ENVIRONMENT"

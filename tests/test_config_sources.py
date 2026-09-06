"""설정값을 어디서 읽는지 고정한다.

**로컬과 워크플로는 설정을 다른 데서 받는다.** 로컬은 `.env` 파일이고, GitHub Actions 에는
그 파일이 아예 없어 시크릿이 환경 변수로 들어온다.

이 차이 때문에 실제로 워크플로가 실패했다 — ECOS 인증키만 `.env` 를 직접 열고 있었고,
로컬에는 파일이 있어 **테스트도 dry-run 도 전부 통과했다.** Actions 에서만 드러났다.

그래서 여기서는 **`.env` 가 없는 상황**을 만들어 환경 변수 경로가 살아 있는지 본다.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from notify import cli
from notify.common_constants import TZ_KST


@pytest.fixture
def without_env_file(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    """`.env` 가 없는 상황을 만든다. 워크플로가 그 상태다.

    Args:
        monkeypatch: 패치 도구.
        tmp_path: 임시 디렉터리.
    """
    monkeypatch.setattr(cli, "ENV_FILE_PATH", tmp_path / "not-there.env")


class TestConfig:
    """설정 읽기."""

    def test_reads_from_environment_without_env_file(
        self, monkeypatch: pytest.MonkeyPatch, without_env_file: None
    ) -> None:
        """`.env` 가 없어도 환경 변수로 읽는다."""
        monkeypatch.setenv("ECOS_API_KEY", "KEY-FROM-ENVIRONMENT")

        assert cli._config("ECOS_API_KEY") == "KEY-FROM-ENVIRONMENT"

    def test_missing_required_value_raises(
        self, monkeypatch: pytest.MonkeyPatch, without_env_file: None
    ) -> None:
        """필수인데 어디에도 없으면 예외다. 빈 값으로 조회에 들어가지 않는다."""
        monkeypatch.delenv("ECOS_API_KEY", raising=False)

        with pytest.raises(ValueError, match="ECOS_API_KEY"):
            cli._config("ECOS_API_KEY")

    def test_optional_value_returns_empty(
        self, monkeypatch: pytest.MonkeyPatch, without_env_file: None
    ) -> None:
        """필수가 아니면 빈 문자열을 돌려준다. 점검 줄이 이 경로를 쓴다."""
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)

        assert cli._config("GITHUB_TOKEN", required=False) == ""


class TestUsdKrwReadsTheKeyLikeEverythingElse:
    """원달러 알림의 인증키 경로.

    이 알림만 `.env` 를 직접 열다가 워크플로에서 실패했다. 다른 설정과 같은 길로
    읽는지를 통합 지점에서 확인한다.
    """

    def test_takes_the_key_from_environment(
        self, monkeypatch: pytest.MonkeyPatch, without_env_file: None
    ) -> None:
        """`.env` 없이 환경 변수만으로 인증키가 조회 함수까지 닿는다."""
        monkeypatch.setenv("ECOS_API_KEY", "KEY-FROM-ENVIRONMENT")
        seen: dict[str, str] = {}

        def _capture(api_key: str, stat_code: str, item_code: str, start: object, end: object) -> None:
            """인증키만 받아 두고 멈춘다.

            Args:
                api_key: 인증키.
                stat_code: 통계표 코드.
                item_code: 항목 코드.
                start: 시작일.
                end: 종료일.

            Raises:
                RuntimeError: 항상. 여기서 더 갈 필요가 없다.
            """
            del stat_code, item_code, start, end
            seen["api_key"] = api_key
            raise RuntimeError("여기까지만 본다")

        monkeypatch.setattr(cli, "fetch_usdkrw", _capture)

        with pytest.raises(RuntimeError, match="여기까지만"):
            cli.run_usdkrw(datetime(2026, 9, 7, 7, 30, tzinfo=TZ_KST))

        assert seen["api_key"] == "KEY-FROM-ENVIRONMENT"

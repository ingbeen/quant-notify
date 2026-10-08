"""모든 테스트에 걸리는 격리."""

from __future__ import annotations

from pathlib import Path

import pytest

from notify import cli


@pytest.fixture(autouse=True)
def isolate_positions(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """실제 `state/positions.toml` 대신 비어 있는 임시 경로를 읽게 한다.

    보유 파일은 매매할 때마다 커밋된다. 테스트가 그것을 읽으면 정상 운영이 테스트를 깨뜨린다.
    보유가 필요한 테스트는 같은 `tmp_path` 의 `positions.toml` 에 쓴다.

    Args:
        monkeypatch: 패치 도구.
        tmp_path: 임시 디렉터리.
    """
    monkeypatch.setattr(cli, "POSITIONS_PATH", tmp_path / "positions.toml")

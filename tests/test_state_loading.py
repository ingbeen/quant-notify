"""사람이 쓰는 파일의 로딩과 스키마 검증을 고정한다.

`state/` 는 사람이 손으로 고치는 파일이라 오기입력이 들어온다. 잘못된 값이 그대로
계산에 들어가면 알림이 조용히 틀리므로, 로딩 시점에 막는다.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from notify.state.positions import load_positions

VALID_POSITIONS = """
[[positions]]
ticker = "QLD"
quantity = 200

[[positions]]
ticker = "GLD"
quantity = 10
"""


def _write(tmp_path: Path, name: str, body: str) -> Path:
    """임시 디렉터리에 상태 파일을 쓴다.

    Args:
        tmp_path: 임시 디렉터리.
        name: 파일 이름.
        body: 파일 내용.

    Returns:
        쓴 파일 경로.
    """
    path = tmp_path / name
    path.write_text(body, encoding="utf-8")
    return path


class TestPositionsLoading:
    """보유 종목 파일."""

    def test_loads_ticker_and_quantity(self, tmp_path: Path) -> None:
        """티커와 수량을 읽는다."""
        positions = load_positions(_write(tmp_path, "positions.toml", VALID_POSITIONS))

        assert [p.ticker for p in positions] == ["QLD", "GLD"]
        assert [p.quantity for p in positions] == [200, 10]

    def test_missing_file_gives_empty_list(self, tmp_path: Path) -> None:
        """파일이 없으면 빈 목록이다. 예외가 아니다.

        보유 블록만 비우고 알림은 그대로 나간다.
        """
        assert load_positions(tmp_path / "positions.toml") == []

    def test_empty_file_gives_empty_list(self, tmp_path: Path) -> None:
        """파일이 비어 있어도 빈 목록이다."""
        assert load_positions(_write(tmp_path, "positions.toml", "")) == []

    def test_negative_quantity_raises(self, tmp_path: Path) -> None:
        """수량이 음수면 예외다."""
        body = '[[positions]]\nticker = "QLD"\nquantity = -1\n'

        with pytest.raises(ValueError):
            load_positions(_write(tmp_path, "positions.toml", body))

    def test_zero_quantity_raises(self, tmp_path: Path) -> None:
        """수량이 0 이면 예외다. 보유하지 않는 종목은 줄을 지운다."""
        body = '[[positions]]\nticker = "QLD"\nquantity = 0\n'

        with pytest.raises(ValueError):
            load_positions(_write(tmp_path, "positions.toml", body))

    def test_empty_ticker_raises(self, tmp_path: Path) -> None:
        """티커가 비어 있으면 예외다."""
        body = '[[positions]]\nticker = ""\nquantity = 10\n'

        with pytest.raises(ValueError):
            load_positions(_write(tmp_path, "positions.toml", body))

    def test_duplicate_ticker_raises(self, tmp_path: Path) -> None:
        """같은 티커가 두 번 나오면 예외다. 어느 줄이 맞는지 알 수 없다."""
        body = '[[positions]]\nticker = "QLD"\nquantity = 10\n\n[[positions]]\nticker = "QLD"\nquantity = 20\n'

        with pytest.raises(ValueError):
            load_positions(_write(tmp_path, "positions.toml", body))

    def test_missing_quantity_raises(self, tmp_path: Path) -> None:
        """수량이 없으면 예외다. 기본값을 넣지 않는다."""
        body = '[[positions]]\nticker = "QLD"\n'

        with pytest.raises(ValueError):
            load_positions(_write(tmp_path, "positions.toml", body))

    def test_fractional_quantity_raises(self, tmp_path: Path) -> None:
        """수량이 정수가 아니면 예외다."""
        body = '[[positions]]\nticker = "QLD"\nquantity = 1.5\n'

        with pytest.raises(ValueError):
            load_positions(_write(tmp_path, "positions.toml", body))

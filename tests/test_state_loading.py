"""사람이 쓰는 파일의 로딩과 스키마 검증을 고정한다.

`state/` 는 사람이 손으로 고치는 파일이라 오기입력이 들어온다. 잘못된 값이 그대로
계산에 들어가면 알림이 조용히 틀리므로, 로딩 시점에 막는다.

파일이 없을 때의 동작은 두 파일이 다르다 — `docs/DESIGN.md` 5.2 절을 따른다.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from notify.state.positions import load_positions
from notify.state.reverse_rank import load_reverse_rank

VALID_RANK = """
[kodex200]
data_from = 2002-10-15
data_to = 2026-08-26
surge_1st = 0.2417
surge_20th = 0.0610
plunge_1st = -0.1246
plunge_20th = -0.0631
"""

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


class TestReverseRankLoading:
    """순위 등락률 파일."""

    def test_loads_thresholds(self, tmp_path: Path) -> None:
        """종목별 순위 등락률을 읽는다."""
        loaded = load_reverse_rank(_write(tmp_path, "reverse_rank.toml", VALID_RANK))

        assert loaded["kodex200"].thresholds.surge_20th == pytest.approx(0.0610)
        assert loaded["kodex200"].thresholds.plunge_20th == pytest.approx(-0.0631)

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        """파일이 없으면 예외다.

        신호 가격을 만들 재료가 없어 판정 자체가 불가능하다. 조용히 넘어가면
        신호가 없어서 조용한 것과 구분되지 않는다.
        """
        with pytest.raises(ValueError):
            load_reverse_rank(tmp_path / "reverse_rank.toml")

    def test_empty_file_raises(self, tmp_path: Path) -> None:
        """종목이 하나도 없으면 예외다."""
        with pytest.raises(ValueError):
            load_reverse_rank(_write(tmp_path, "reverse_rank.toml", ""))

    def test_missing_field_raises(self, tmp_path: Path) -> None:
        """필수 필드가 빠지면 예외다."""
        body = "[kodex200]\ndata_to = 2026-08-26\nsurge_20th = 0.0610\n"

        with pytest.raises(ValueError):
            load_reverse_rank(_write(tmp_path, "reverse_rank.toml", body))

    def test_percent_written_as_ratio_raises(self, tmp_path: Path) -> None:
        """등락률을 퍼센트로 적으면 예외다.

        값은 비율이다. 6.10 은 610% 라 하루 등락률로 있을 수 없다.
        이 검사가 없으면 임계가 열 배 느슨해져 알림이 영영 울리지 않는다.
        """
        body = VALID_RANK.replace("surge_20th = 0.0610", "surge_20th = 6.10")

        with pytest.raises(ValueError):
            load_reverse_rank(_write(tmp_path, "reverse_rank.toml", body))

    def test_positive_plunge_raises(self, tmp_path: Path) -> None:
        """폭락 값이 양수면 예외다. 부호가 곧 방향이다."""
        body = VALID_RANK.replace("plunge_20th = -0.0631", "plunge_20th = 0.0631")

        with pytest.raises(ValueError):
            load_reverse_rank(_write(tmp_path, "reverse_rank.toml", body))

    def test_negative_surge_raises(self, tmp_path: Path) -> None:
        """폭등 값이 음수면 예외다."""
        body = VALID_RANK.replace("surge_20th = 0.0610", "surge_20th = -0.0610")

        with pytest.raises(ValueError):
            load_reverse_rank(_write(tmp_path, "reverse_rank.toml", body))

    def test_first_must_be_more_extreme_than_twentieth(self, tmp_path: Path) -> None:
        """1위가 20위보다 덜 극단적이면 예외다. 순위가 뒤바뀐 것이다."""
        body = VALID_RANK.replace("surge_1st = 0.2417", "surge_1st = 0.0500")

        with pytest.raises(ValueError):
            load_reverse_rank(_write(tmp_path, "reverse_rank.toml", body))

    def test_date_with_a_time_raises(self, tmp_path: Path) -> None:
        """날짜에 시각이 붙으면 예외다.

        TOML 은 `2026-08-26T00:00:00` 도 유효한 값으로 읽고, `datetime` 은 `date` 의
        하위형이라 형 검사를 그냥 통과한다. 넘어가면 낡음 판정이 `date` 와 견주다
        **필드 이름이 없는 TypeError** 로 멈춘다 — 로딩 시점에 막아야 고칠 곳이 드러난다.
        """
        body = VALID_RANK.replace("data_to = 2026-08-26", "data_to = 2026-08-26T00:00:00")

        with pytest.raises(ValueError, match="data_to"):
            load_reverse_rank(_write(tmp_path, "reverse_rank.toml", body))

    def test_keeps_the_ranking_period(self, tmp_path: Path) -> None:
        """데이터 구간을 함께 읽는다.

        `data_to` 가 기준일을 겸한다 — 알림이 「이 날 뒤에 20위에 든 날이 있는가」로
        낡음을 판정하므로, 이 값이 없으면 판정 자체가 불가능하다.
        """
        loaded = load_reverse_rank(_write(tmp_path, "reverse_rank.toml", VALID_RANK))

        assert loaded["kodex200"].data_from.isoformat() == "2002-10-15"
        assert loaded["kodex200"].data_to.isoformat() == "2026-08-26"

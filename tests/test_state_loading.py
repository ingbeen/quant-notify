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

    def test_unknown_table_name_raises(self, tmp_path: Path) -> None:
        """표 이름을 잘못 쓰면 멈춘다. 그대로 두면 빈 보유로 읽혀 보유 블록이 조용히 사라진다."""
        body = '[[position]]\nticker = "QLD"\nquantity = 200\n'

        with pytest.raises(ValueError, match="position"):
            load_positions(_write(tmp_path, "positions.toml", body))

    def test_unknown_entry_key_raises(self, tmp_path: Path) -> None:
        """항목의 모르는 키는 멈춘다. 오타 키는 그 값이 버려진 줄 모르게 한다."""
        body = '[[positions]]\nticker = "QLD"\nquantity = 200\nqty = 300\n'

        with pytest.raises(ValueError, match="qty"):
            load_positions(_write(tmp_path, "positions.toml", body))

    @pytest.mark.parametrize("ticker", [" QLD", "qld", "A<B", "069500.KS", "BRK.B"])
    def test_ticker_outside_the_us_symbol_form_raises(self, tmp_path: Path, ticker: str) -> None:
        """미국 상장 종목 코드 형식이 아니면 멈춘다.

        비중은 달러 평가액으로, 종가는 미국 거래일로 집으므로 다른 시장 종목이 섞이면 조용히 틀린다.
        """
        body = f'[[positions]]\nticker = "{ticker}"\nquantity = 10\n'

        with pytest.raises(ValueError, match="ticker"):
            load_positions(_write(tmp_path, "positions.toml", body))

    def test_tickers_this_system_uses_pass(self, tmp_path: Path) -> None:
        """이 시스템이 다루는 티커는 형식 검사를 통과한다. 클래스 주식은 yfinance 표기(하이픈)로 적는다."""
        tickers = ["SPY", "QQQ", "GLD", "TLT", "SSO", "QLD", "BRK-B"]
        body = "".join(f'[[positions]]\nticker = "{ticker}"\nquantity = 1\n\n' for ticker in tickers)

        positions = load_positions(_write(tmp_path, "positions.toml", body))

        assert [p.ticker for p in positions] == tickers

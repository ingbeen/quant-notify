"""테스트 전반이 공유하는 픽스처.

수치는 `reference/` 매매 규칙 문서와 `docs/DESIGN.md` 의 실측값을 그대로 쓴다.
계산 경로가 이미 검증된 값이므로, 산식이 바뀌면 여기서 먼저 어긋난다.
"""

from __future__ import annotations

import pytest


@pytest.fixture
def kodex_thresholds() -> dict[str, float]:
    """KODEX 200 의 순위 등락률. 값은 비율 (0.0610 = +6.10%)."""
    return {
        "surge_1st": 0.2417,
        "surge_20th": 0.0610,
        "plunge_1st": -0.1246,
        "plunge_20th": -0.0631,
    }


@pytest.fixture
def qqq_thresholds() -> dict[str, float]:
    """QQQ 의 순위 등락률. 값은 비율 (0.0742 = +7.42%)."""
    return {
        "surge_1st": 0.1684,
        "surge_20th": 0.0742,
        "plunge_1st": -0.1198,
        "plunge_20th": -0.0687,
    }


@pytest.fixture
def kodex_prev_close() -> float:
    """KODEX 200 의 전일 종가. 2026-08-31 종가 실측값."""
    return 107615.0

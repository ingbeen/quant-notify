"""알림이 쓰는 고정값.

경로 · 알림 이름과, 다른 저장소의 매매 규칙에서 옮겨 적은 값(티커 · 기간 · 두 선 · 창)을 한곳에 둔다.

비율은 모두 0~1 사이 소수다 (0.01 = 1%).
"""

from __future__ import annotations

from pathlib import Path
from zoneinfo import ZoneInfo

# 경로
PROJECT_ROOT = Path(__file__).resolve().parents[2]
STATE_DIR = PROJECT_ROOT / "state"
POSITIONS_PATH = STATE_DIR / "positions.toml"

# 로컬 자격증명. git 에서 제외돼 있고 워크플로에는 존재하지 않는다 (utils/config.py)
ENV_FILE_PATH = PROJECT_ROOT / ".env"

# 알림 이름. 워크플로 파일 이름은 여기에 `.yml` 을 붙인 것이다
ALERT_BUFFER_ZONE = "buffer_zone"
ALERT_USDKRW = "usdkrw"

# 이동평균 근접도를 보는 티커
TICKER_SPY = "SPY"
TICKER_QQQ = "QQQ"
TICKER_GLD = "GLD"
TICKER_TLT = "TLT"
BUFFER_ZONE_TICKERS: tuple[str, ...] = (TICKER_SPY, TICKER_QQQ, TICKER_GLD, TICKER_TLT)

# 매수선·매도선으로 매매하는 티커. 나머지는 Q-2-2XS 에서 B&H 라 근접도를 참고로만 낸다
BUFFER_ZONE_SIGNAL_TICKERS: tuple[str, ...] = (TICKER_SPY, TICKER_QQQ)

# 이동평균 기간 (거래일)
MA_PERIOD = 200

# 매수선·매도선. 정본은 quant FIXED_4P_BUY_BUFFER_ZONE_PCT · FIXED_4P_SELL_BUFFER_ZONE_PCT 다
BUY_BUFFER_ZONE_RATE = 0.03  # 매수선 비율 (0.03 = 이동평균의 3% 위)
SELL_BUFFER_ZONE_RATE = 0.05  # 매도선 비율 (0.05 = 이동평균의 5% 아래)

# 원달러를 견주는 창 (년)
USDKRW_WINDOW_YEARS: tuple[int, ...] = (1, 3, 5, 10)

# 타임존
TZ_KST = ZoneInfo("Asia/Seoul")

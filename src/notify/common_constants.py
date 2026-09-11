"""알림 전반이 공유하는 상수.

티커·기간·여유 폭 같은 값을 한곳에 모은다. 계산 코드에 숫자를 흩어 두면
같은 값이 여러 곳에서 갈라진다.

비율은 모두 0~1 사이 소수다 (0.01 = 1%).
"""

from __future__ import annotations

from pathlib import Path
from zoneinfo import ZoneInfo

# 경로
PROJECT_ROOT = Path(__file__).resolve().parents[2]
STATE_DIR = PROJECT_ROOT / "state"
POSITIONS_PATH = STATE_DIR / "positions.toml"
REVERSE_RANK_PATH = STATE_DIR / "reverse_rank.toml"

# 로컬 자격증명. git 에서 제외돼 있고 워크플로에는 존재하지 않는다 (utils/config.py)
ENV_FILE_PATH = PROJECT_ROOT / ".env"

# 이동평균 근접도를 보는 티커
TICKER_SPY = "SPY"
TICKER_QQQ = "QQQ"
TICKER_GLD = "GLD"
TICKER_TLT = "TLT"
BUFFER_ZONE_TICKERS: tuple[str, ...] = (TICKER_SPY, TICKER_QQQ, TICKER_GLD, TICKER_TLT)

# 이동평균 기간 (거래일)
MA_PERIOD = 200

# 역방향 알림 여유. 비율 (0.01 = 1%p)
REVERSE_MARGIN_RATE = 0.01

# 하루 등락률이 넘을 수 없는 크기. 비율을 퍼센트로 잘못 적은 값을 걸러낸다
MAX_DAILY_CHANGE_RATE = 1.0

# 원달러를 견주는 창 (년)
USDKRW_WINDOW_YEARS: tuple[int, ...] = (1, 3, 5, 10)

# ECOS 원달러 계열. 실측으로 확정했다 — 근거는 docs/research/데이터소스_실측.md
# 731Y001/0000001(매매기준율)은 다른 계열이다. 값이 하루 1~2원씩 어긋난다
ECOS_USDKRW_STAT_CODE = "731Y003"
ECOS_USDKRW_ITEM_CODE = "0000003"

# 타임존
TZ_KST = ZoneInfo("Asia/Seoul")

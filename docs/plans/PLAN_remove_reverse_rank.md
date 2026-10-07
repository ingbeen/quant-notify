# Implementation Plan: 역방향 알림 기능 전체 제거

> 작성/운영 규칙(SoT): `/impl-plan` 스킬(`~/.claude/skills/impl-plan/SKILL.md`)을 반드시 참고하세요.  
> (이 템플릿을 수정하거나 새로운 양식의 계획서를 만들 때도 해당 스킬을 포인터로 두고 준수합니다.)

**상태**: ✅ Done

---

> 상태는 🟡 Draft / 🔄 In Progress / ✅ Done. Done 조건과 기록 규칙은 `/impl-plan` 「3) 스킵 및 완료 규칙」이며 `~/.claude/hooks/plan_lint.py` 가 저장 때 검사한다.

---

**작성일**: 2026-10-06 22:36
**마지막 업데이트**: 2026-10-06 23:41
**관련 범위**: 알림(`alerts/`), 상태(`state/`), 데이터(`data/`), CLI, 워크플로, 문서
**관련 문서**: 루트 `CLAUDE.md`, `docs/DESIGN.md`, `docs/COMMANDS.md`, `README.md`, `reference/README.md`

---

## 1) 목표(Goal)

- [x] 목표 1: 역방향 일일 알림 둘(`reverse_rank_kr` · `reverse_rank_us`)을 워크플로 · CLI · 판정 코드 · 순위 갱신 알림(2c)까지 없앤다
- [x] 목표 2: 주간 원달러 알림에서 **역방향 요약 블록**을 없앤다. 주간 알림은 원달러와 점검 줄만 낸다
- [x] 목표 3: 역방향만 쓰던 상태 파일 · 로더 · 참고 스냅샷을 없앤다 — `state/reverse_rank.toml` · `state/reverse_rank.py` · `reference/역방향_매매_규칙.md`
- [x] 목표 4: 점검 줄에서 **역방향 항목만** 뺀다. 버퍼존 점검은 `최근 주간` 한 줄, 주간 점검은 `버퍼존 N/N` 만 남는다
- [x] 목표 5: 이 제거로 호출처가 0 이 되는 함수 · 상수 · 테스트를 함께 지우고, 문서가 없는 기능을 설명하지 않게 한다

## 2) 비목표(Non-Goals)

- **점검 줄 기능 자체는 남긴다.** `health.py` · GitHub 실행 이력 조회 · `_run_alert.yml` 의 `actions: read` 를 그대로 둔다 (사용자 결정 — 「역방향 항목만 빼기」)
- **남는 일반화 코드를 줄이지 않는다.** `health._detail` 의 다중 워크플로 처리, `calendar.is_trading_day(calendar_code, …)` 는 호출처가 하나로 줄지만 그대로 둔다 — 이번 작업은 제거이고, 줄이는 것은 별도 판단이다
- **외부 스케줄러(cron-job.org) 구조를 바꾸지 않는다.** 정시성이 가장 필요했던 장중 알림(한국 역방향 12:00 · 14:30)이 사라져 `schedule` 로 돌아갈 여지가 생기지만, 그것은 별도 결정이다. DESIGN §6.1 은 장중 예시만 걷어내고 결론은 유지한다
- **`docs/research/데이터소스_실측.md` 를 고치지 않는다.** 날짜가 박힌 실측 기록이라 측정 당시의 사실이다. 역방향 관련 측정도 그대로 둔다
- **`docs/plans/` 의 기존 계획서와 `docs/AUDIT_2026-09-26.md` 를 고치지 않는다.** 둘 다 임시 문서다. 이 작업으로 대상이 사라지는 감사 항목은 Notes 에 적는다
- **DESIGN 의 「근거가 된 사건」 서술은 남긴다.** §4.5 「역방향 줄이 75칸」(정렬 기각 근거), §7.3 KST 조회 고장 경위의 `US 0/1`, §7.3 예정 횟수 버그의 「한국 역방향 6일」, §7.4 의 2026-09-07 429 — 지금 규칙이 왜 이런지의 실측 근거라 기능이 사라져도 참이다
- `positions.toml` · 이동평균 알림의 동작은 바꾸지 않는다 (점검 블록 줄 수만 바뀐다)
- 감사 문서가 지적한 다른 결함(BUG-1 윤일 등)은 고치지 않는다

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- 사용자가 역방향 알림을 없애기로 했다. 범위는 **역방향 기능 전체**, 점검 줄은 **역방향 항목만 빼기**로 정했다 (2026-10-06 사용자 결정)
- **워크플로 파일만 지우면 안 된다.** 다른 두 알림이 이 워크플로의 실행 횟수를 센다 — 버퍼존 점검의 `오늘 · 역방향 US` · `전일 · 역방향 KR`, 주간 점검의 `역방향 KR · US` (`health.py:265-341`). 파일이 사라지면 그 줄들이 매일 빨간 점(`0/N` 또는 `이력 조회 실패`)으로 뜬다
- **주간 요약도 같은 상태 파일을 읽는다.** `usdkrw.py:24` 가 `reverse_rank.reached_threshold` 를, `cli.run_usdkrw` 가 `state/reverse_rank.toml` 과 KODEX · QQQ 일봉을 쓴다 (`cli.py:487-571`)
- cron-job.org 에 이 두 워크플로를 부르는 잡이 3개 있다 (`docs/COMMANDS.md:85-91` — US 07:20 · KR 12:00 · KR 14:30). **코드 밖이라 사용자가 지운다** (Notes 「배포 순서」)

### 조사 결과 — 이 제거로 호출처가 0 이 되는 것

> 숫자는 `grep -rlw <이름> src/notify` 결과(정의 파일 제외)다.

| 대상 | 지금 호출처 | 제거 후 |
| --- | --- | --- |
| `alerts/reverse_rank.py` 전체 | `cli.py` · `usdkrw.py`(`reached_threshold` 1곳) | 0 |
| `state/reverse_rank.py` 전체 | `cli.py` · `alerts/reverse_rank.py` | 0 |
| `formatting.format_usd` | `reverse_rank.py` 1곳 | 0 |
| `formatting.format_day_paren` | `usdkrw._extreme_row` 1곳 | 0 |
| `yfinance_client.close_on` · `first_change_day` · `fetch_intraday_price` · `INTRADAY_*` | `cli.py` 의 역방향 · `_change_rates` 만 | 0 |
| `calendar.KR_CALENDAR` · `is_kr_trading_day` · `previous_trading_day` · `previous_us_trading_day` · `previous_kr_trading_day` · `trading_days_between` | `cli.py` 의 역방향 · `_change_rates` 만 (+ 래퍼끼리) | 0 |
| `common_constants.REVERSE_RANK_PATH` · `REVERSE_MARGIN_RATE` · `MAX_DAILY_CHANGE_RATE` | 역방향 모듈 · 순위 로더만 | 0 |
| `tests/conftest.py` 픽스처 셋 | 지울 테스트 파일 3개만 (`test_reverse_rank_judgement` · `test_rank_staleness` · `test_rank_staleness_wiring`) | 0 |

남는 것: `TICKER_QQQ`(버퍼존 티커) · `US_CALENDAR` · `is_trading_day` · `is_us_trading_day` · `closes_through` · `_index_date` · `fetch_closes` · `format_krw` · `format_rate` · `alert` · `bold`.

**주간 알림은 yfinance 를 더 부르지 않는다.** 역방향 요약이 KODEX · QQQ 일봉을 받던 유일한 이유였다. 그래서 두 알림이 받는 데이터가 겹치지 않게 된다(버퍼존 yfinance · 주간 ECOS) — DESIGN §5.4 · CLAUDE.md 의 「아끼는 것은 종가 한 개」가 거짓이 되므로 고친다.

### 글자 규칙이 막거나 되돌릴 수 없는 결과에 물리는가

해당 없음 — 열린 입력을 글자 규칙으로 판정하는 설계가 없다.

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `.claude/plan-config.json` — 이 저장소의 검증 명령·자동 포맷·근거 승격 목적지 (**값의 SoT**)
- 루트 `CLAUDE.md` — 특히 「계획서 규약 — 이 프로젝트의 설정」 절 (값이 아니라 **판단 근거**)과 「스크립트 실행 규칙」(dry-run 까지만)
- `docs/DESIGN.md` — §4.5 (문구 정본) · §7.3 (점검 줄)
- 전역 `~/.claude/rules/python.md` · `~/.claude/rules/python-tests.md`

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 `/impl-plan` 스킬)

- [x] 역방향 워크플로 · CLI 이름 · 판정 · 순위 갱신 · 주간 역방향 요약 · 순위 파일 · 로더 · 참고 스냅샷이 저장소에 없다 (Phase 1 · 2 의 잔존 참조 검사 0건)
- [x] 버퍼존 점검 블록이 `최근 주간` 한 줄, 주간 점검이 `버퍼존 N/N` 으로 나오고 테스트가 정본 문구로 고정한다
- [x] 이 제거로 호출처가 0 이 된 함수 · 상수 · 픽스처를 지웠다 (위 조사 표 전부)
- [x] 코드 리뷰 실행 및 결과 기록 (마지막 Phase 의 Validation 에 적는다)
- [x] 품질 검증 통과 (마지막 Phase 의 Validation 에 passed/failed/skipped 수를 적는다)
- [x] 자동 포맷 적용 완료 (마지막 Phase에서 실행)
- [x] 문서 업데이트 — `docs/DESIGN.md` 변경 있음 · 루트 `CLAUDE.md` 변경 있음 · `README.md` 변경 있음 · `docs/COMMANDS.md` 변경 있음(실행 명령 · cron 잡 목록) · `reference/README.md` 변경 있음
- [x] 근거 승격 완료 — 이 계획서를 지금 삭제해도 잃을 정보가 없다
      (제거 결정과 그 사유를 DESIGN §8 · 루트 `CLAUDE.md` 기각 목록에 남긴다. 되살릴 때 볼 판을 §8 에 가리킨다)
- [x] 미룬 지적 옮김 — **해당 없음.** 미조치 지적은 전부 거르는 기준 3(버그가 아니다)이라 옮길 것 0건, 거른 목록은 진행 로그 2026-10-06 23:39 와 Done 보고 표에 있다
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 삭제하는 파일

| 파일 | 이유 |
| --- | --- |
| `.github/workflows/reverse_rank_kr.yml` · `reverse_rank_us.yml` | 알림 제거 |
| `src/notify/alerts/reverse_rank.py` | 판정 · 문구 · 낡음 판정 전부. 유일한 외부 사용(`reached_threshold`)이 주간 요약과 함께 사라진다 |
| `src/notify/state/reverse_rank.py` · `state/reverse_rank.toml` | 순위 파일과 로더 |
| `reference/역방향_매매_규칙.md` | 참고 스냅샷. 되살릴 때는 git 이력에서 꺼낸다 |
| `tests/test_reverse_rank_judgement.py` · `test_rank_staleness.py` · `test_rank_staleness_wiring.py` · `test_intraday_price.py` | 대상 함수가 모두 사라진다 (네 파일 모두 역방향 외 테스트가 없음을 확인) |
| `tests/conftest.py` | 픽스처 셋(`kodex_thresholds` · `qqq_thresholds` · `kodex_prev_close`)의 사용처가 위 세 파일뿐 |

### 수정하는 소스

| 파일 | 변경 |
| --- | --- |
| `src/notify/cli.py` | 역방향 import(`reverse_rank` · `state.reverse_rank` · `REVERSE_RANK_PATH` · `TICKER_QQQ` · 달력의 `KR/US_CALENDAR` · `is_kr_trading_day` · `previous_*` · `trading_days_between` · 시세의 `close_on` · `fetch_intraday_price` · `first_change_day` · 점검의 `today_health` · `previous_day_health`) · 상수(`ALERT_REVERSE_*` · `RANK_KEY_*` · `SYMBOL_KODEX` · `YF_TICKER_KODEX` · `TRADING_WEEK_OFFSET`) · 함수(`_load_rank` · `_ReverseInputs` · `_korea_prices` · `_united_states_prices` · `_unreflected` · `_run_reverse` · `_change_rates` · `_weekly_extreme_line`) 삭제. `ALERT_NAMES` · `build_message` 에서 두 이름 삭제. `run_buffer_zone` 점검을 `[_weekly_slot(...)]` 하나로 하고 202-206행 주석 삭제. `run_usdkrw` 에서 시세 조회와 역방향 블록 삭제(지난주 구간 계산은 점검용으로 유지). 모듈 docstring 의 역방향 두 항목 · 「일일 알림 셋」 · 「아끼는 것은 종가 한 개」 정리. `RUN_WEEK_OFFSET` 주석을 「두 구간이 갈린다」 없이 다시 쓴다. `_last_week_monday` docstring 을 점검 기준으로 고친다 — 이번 주를 집으면 «아직 오지 않은 날을 세어 덜 돌았다고 강조한다»가 지금의 실패 양상이다. `pandas` · `dataclass` import 삭제 |
| `src/notify/alerts/health.py` | `WORKFLOW_REVERSE_KR/US` · `_KR_ALERT_WEEKDAYS` · `_KR_RUNS_PER_DAY` · `expected_runs` 의 역방향 분기 · `today_health` · `previous_day_health` 삭제. `weekly_health` 항목을 `("버퍼존", WORKFLOW_BUFFER_ZONE)` 하나로, 「역방향을 되풀이하지 않는다」 주석 삭제. 모듈 docstring 의 발화 표와 「역방향은 침묵」 문단을 남는 두 알림 기준으로 고친다 |
| `src/notify/alerts/usdkrw.py` | 역방향 요약 일체(`WeeklyExtreme(s)` · `_extreme_at` · `weekly_extremes` · `ReverseLine` · `ReverseBlock` · `_extreme_row` · `_reverse_rows`) · `render` 의 `reverses` 인자와 분기 · import(`alert` · `format_day_paren` · `reached_threshold`) 삭제. 모듈 docstring |
| `src/notify/alerts/formatting.py` | `format_usd` · `format_day_paren` 삭제. `RED_DOT` 주석과 `alert` docstring 의 「역방향 신호」 삭제 |
| `src/notify/alerts/failure.py` | docstring 의 「침묵 알림의 실패도…」 문단 삭제 (침묵하는 알림이 없어진다) |
| `src/notify/data/yfinance_client.py` | `first_change_day` · `close_on` · `fetch_intraday_price` · `INTRADAY_*` 삭제. 모듈 docstring 의 「장중 현재가」와 「한국 종목도 여기서 받는다(pykrx)」 문단 삭제 — 한국 종목을 받는 경로가 없어진다 |
| `src/notify/data/calendar.py` | `KR_CALENDAR` · `is_kr_trading_day` · `previous_trading_day` · `previous_us_trading_day` · `previous_kr_trading_day` · `trading_days_between` 삭제. docstring 「미국·한국」→ 미국 |
| `src/notify/common_constants.py` | `REVERSE_RANK_PATH` · `REVERSE_MARGIN_RATE` · `MAX_DAILY_CHANGE_RATE` 삭제 |
| `.github/workflows/_run_alert.yml` | 머리 주석 「알림 넷 … 나머지 셋이」를 둘 기준으로 |

### 수정하는 테스트

| 파일 | 변경 |
| --- | --- |
| `tests/test_alert_rendering.py` | 역방향 상수 · `_render` · `TestReverseRankKorea` · `TestReverseRankUnitedStates` · `TestRankStalenessNotice` · `TestSilence` 삭제. `TestBufferZone` 점검 블록을 `최근 주간` 한 줄로. `TestUsdKrw` 에서 `reverses` 와 역방향 테스트 셋(`signal_week` · `boundary` · `rank_label`) 삭제, 정본 문자열 갱신, `quiet_week` docstring 을 「점검이 정상이면 색이 없다」로. `TestHealthLineFlowsIntoAlerts` 의 오늘·전일 테스트 삭제, 주간 기대값 `버퍼존 5/5`. 모듈 docstring 의 빨간 점 범위 |
| `tests/test_health_line.py` | `TestTodayHealth` · `TestPreviousDayHealth` · 한국 역방향 예정 횟수 테스트 둘 · `us_reverse_is_expected_whenever_buffer_zone_runs` · `partial_lookup_failure`(항목이 하나라 일어날 수 없다) · `_raising_only` · `korea_alerts_stay_inside` 삭제. `morning_alerts_fall_inside_their_kst_day` 는 버퍼존 발화 시각만 남긴다. **휴장 무관 분모 테스트는 버퍼존으로 다시 쓴다** — 전날이 노동절인 2026-09-08(화)에도 1 (정책이 남으므로 지우지 않는다). 조회 질의 테스트의 워크플로를 `WORKFLOW_BUFFER_ZONE` 으로. `US_ALERTS` 를 버퍼존 하나로. 주간 기대값 `버퍼존 5/5`. 버퍼존 조립 테스트의 기대 질의 `[(WORKFLOW_USDKRW, LAST_MONDAY)]` · 문구 끝 `<b>점검</b>\n최근 주간 09-07 (월) · 1/1`. 역방향 발화 시각 상수 · 주석 정리 |
| `tests/test_close_date_guard.py` | `TestUnitedStatesPricesNeedBothDays` · `TestKoreaPricesNeedThePreviousTradingDay` 삭제. `TestCloseOn` 은 `closes_through` 대상으로 바꾸되 **고유한 둘만** 남긴다 — 실패 문구가 종목 · 요청일 · 마지막 종가일을 담는다, 빈 계열이면 멈춘다. 나머지 셋은 `test_weekly_window.TestClosesThrough` 와 같고 서울 tz 는 한국 경로가 없어진다. `_forbid_fetch` 의 `fetch_intraday_price` 줄 삭제(속성이 없으면 `monkeypatch.setattr` 가 실패한다). 쓰이지 않게 되는 상수와 docstring 의 「미국 역방향은」 문단 정리 |
| `tests/test_weekly_window.py` | `TestTradingDaysBetween` · `TestWeeklyChangesUseAdjacentTradingDays` · `TestWeeklyLinesTakeTheRankCutFromTheFile` 삭제. `the_window_never_reaches_into_the_future` 를 점검 구간의 끝(`RUN_WEEK_OFFSET`, 토요일) 기준으로. 모듈 docstring 을 「지난주 점검 구간과 종가 자르기」로. 쓰이지 않게 되는 상수 · 헬퍼 정리 |
| `tests/test_usdkrw_calc.py` | `TestWeeklyExtremes` · import · docstring 의 「지난주 역방향 요약」 삭제 |
| `tests/test_state_loading.py` | `TestReverseRankLoading` · `VALID_RANK` · import 삭제. docstring 「두 파일이 다르다」 정리 |
| `tests/test_yfinance_errors.py` | `TestFetchIntradayPrice` · `TestCloseOnTzAwareIndex` · import 삭제 (일봉 조회 테스트의 `KODEX` 는 종목 무관 시험값이라 둔다) |
| `tests/test_trading_calendar.py` | 한국 단언 삭제, `korean_holiday` · `christmas` · `TestPreviousTradingDay` 삭제, `markets_differ` 를 「미국 공휴일(노동절)은 휴장」으로 |
| `tests/test_cli_failure_path.py` | `TestSilenceIsNotFailure` 의 `reverse_rank_us` → `buffer_zone` (선택지에서 빠지면 `SystemExit`) |

### 수정하는 문서

**`docs/DESIGN.md` — 절별**

| 절 | 변경 |
| --- | --- |
| §2 | 「장중 알림 설계(§6)의 유일한 정량 근거」→ 스케줄 설계 |
| §3.2 | 「같은 원리가 역방향 규칙에도」 문단 삭제 |
| §4 | 제목 「알림 둘」(목차 앵커 포함), 표 두 줄(1 `buffer_zone` · **2** `usdkrw`), 「2a·2b 는 순위가 낡았으면」 문단 삭제, 「미국장 알림(1 · 2b)」→ 알림 1 |
| §4.1 | 역방향 행 삭제 — 역방향 매매를 그만둔다 (Notes 「결정 사항」) |
| §4.3 · §4.4 | **삭제.** §4.4 의 「지난주는 달력이 정한다」 문단은 §7.3 으로 옮기고, 실패 양상을 점검 기준(아직 오지 않은 날을 세어 덜 돌았다고 강조)으로 고친다 |
| §4.5 | 빨간 점 「두 곳 — 실패 · 점검 이상」, 알림 1 예시 점검 블록, 2a · 2b · 2c 절 삭제, 「알림 3」→ 「알림 2」, 예시에서 역방향 블록 삭제와 점검 `버퍼존 5/5`, 예시 뒤 역방향 설명 문단 삭제(환율 기준일 문단은 둔다) |
| §5.1 | 표 「예」를 `positions.toml` 만, 「낡았을 때」를 보유 비중 기준으로 |
| §5.2 | 표의 순위 파일 행, 「값은 비율로」 · 「전일 종가를 넣지 않습니다」 · 「낡아도 안전한 방향」, 하위 절 넷(4자리 · 순위 컷 · `data_to` · 낡음 — 그 안의 「파일이 없을 때」 표와 스냅샷 표 포함) 삭제. 「파일이 없을 때」는 `positions.toml` 한 문장으로 |
| §5.3 | 「역방향 진행 포지션」 행 삭제, 「알림 셋」→ 둘 |
| §5.4 | 두 알림의 데이터가 겹치지 않는다(버퍼존 yfinance · 주간 ECOS)로 다시 쓰고, 원칙(공유하지 않는다)과 그 이유는 유지 |
| §6.1 | 14:30 예시와 역방향 규칙 인용 삭제, 지연 수치만 남긴다 |
| §6.2 | 그림의 `12:00` → `07:30`, 「장중 알림에서」 · 「호출자 넷」 정리 |
| §6.4 | 표 두 줄, 🔴 「US 가 버퍼존보다 먼저」 블록 삭제, 「미국장 알림」→ 알림 1 |
| §7.2 | 「역방향이 조용히 안 돎」 행을 남는 두 알림의 교차 점검으로, 「역방향 KR 은 월~금」 → 월요일은 주간 알림으로 드러난다 |
| §7.3 | 「누가 조회하나」, 발화 표 두 줄(버퍼존 ↔ 주간이 서로 센다), 미국 역방향 당일 · 2c · 한국 역방향 · 「세 줄」 문단 삭제, `2/2` 예시를 버퍼존 휴장 실행으로, 상황 표를 셋(예정대로 · 덜 돌았다 · 조회 실패)으로 줄이고 「워크플로마다 따로」 문단 삭제, 「토요일까지」 절을 표 없이 다시 쓰고 §4.4 에서 옮긴 문단을 붙인다 |
| §7.4 | 「미국 역방향은 전일·당일」 문장, 「인접한 거래일」 항목, 「침묵 알림의 실패」 항목 삭제 |
| §8 | 「역방향 알림」 행 추가(Notes 「DESIGN §8 에 넣을 행」), 캐시 공유 행의 「종가 한 개」 삭제 |
| §9 | 「장중 판정 시각」 미해결 항목과 KODEX 해결 항목 셋 삭제 |
| 확정 이력 | 2026-10-06 행 추가 |

**그 밖의 문서**

| 문서 | 변경 |
| --- | --- |
| 루트 `CLAUDE.md` | 「아끼는 것은 종가 한 개입니다」 삭제 · 기각 목록 「역방향 청산 추적」→ 「역방향 알림」 · verify-lab 행 「역방향·원달러」→ 원달러 · 「순위 등락률은 값만 넘겨받으면…」 · `reference/` 의 순위 등락률 문장 · 「순위 등락률 값은 이 저장소가 계산하지 않습니다」 문단 삭제 · 「조용한 것과 죽은 것」 원칙의 예를 「휴장이면 알림이 조용히 끝난다」로 |
| `README.md` | 알림 표 두 줄 삭제와 주간 내용, 「미국장 알림이 화~토」→ `buffer_zone`, 구조의 `state/` 설명, 「장중 알림에 쓸 수 없습니다」 문구 |
| `docs/COMMANDS.md` | dry-run 두 줄 · 역방향 침묵 안내 · 「미국 역방향」 휴장 안내 · cron 잡 「다섯 개」→ 둘과 표 · 🔴 순서 블록 · 「워크플로 넷」 · `gh workflow run` 두 줄 · 이력 조회 예시의 `reverse_rank_us.yml` → `buffer_zone.yml` · UTC 안내의 역방향 두 곳 · 주간 수동 실행 안내의 근거 절(§4.4 → §7.3)과 내용(점검 구간) |
| `reference/README.md` | 파일 표의 역방향 행 삭제, 스냅샷 날짜 문장, 「순위 등락률」 두 문단 삭제, 「가져오지 않은 것」에 `역방향_매매_규칙.md` 행 추가 — 「역방향 매매를 그만둬 알림을 없앴습니다 (DESIGN §8)」. 다음 세션이 스냅샷을 다시 가져오지 않게 한다 |

- `docs/COMMANDS.md`: **변경 있음** — 실행 명령 두 줄 · `gh workflow run` 두 줄 · cron 잡 목록이 바뀐다
- 의존성: **변경 없음** — `yfinance` · `exchange-calendars` 는 버퍼존이 계속 쓴다 (`pyproject.toml` · `poetry.lock` 그대로)

### 데이터/결과 영향

- **알림 문구가 바뀐다.** 버퍼존 점검 블록이 세 줄 → 한 줄, 주간 알림에서 역방향 두 블록(10줄)이 빠지고 점검 둘째 줄이 `버퍼존 5/5` 가 된다. 정본(DESIGN §4.5)과 테스트를 Phase 0 에서 먼저 고친다
- **주간 알림이 yfinance 를 부르지 않는다.** 조회 한도(429)로 주간 알림이 실패할 경로가 하나 줄어든다
- **외부 조치가 따른다** — cron-job.org 잡 3개 삭제 (Notes 「배포 순서」)
- 저장하는 결과물 · CSV 없음

## 6) 단계별 계획(Phases)

### Phase 0 — 새 문구 정본을 먼저 고정(레드)

> 사용자가 매일 읽는 문구가 바뀌므로 정본과 테스트를 코드보다 먼저 고친다 (루트 `CLAUDE.md` 「계획서 규약」).

**작업 내용**:

- [x] DESIGN §4.5 — 알림 1 예시 점검 블록을 `최근 주간 08-31 (월) · 1/1` 한 줄로, 알림 3(→ 알림 2) 예시에서 역방향 두 블록 삭제 · 점검 `버퍼존 5/5`, 2a · 2b · 2c 절과 예시 뒤 역방향 문단 삭제, 빨간 점 문장
- [x] `test_alert_rendering.py` — `TestBufferZone` · `TestUsdKrw` · `TestHealthLineFlowsIntoAlerts`(주간) 의 기대값을 새 정본으로, `TestUsdKrw._render` 와 주간 `FlowsIntoAlerts` 에서 `reverses` 를 뺀다. 그 `_render` 인자에 기대던 주간 역방향 테스트 셋(`signal_week` · `boundary` · `rank_label`)은 여기서 지운다
- [x] `test_health_line.py` — `TestWeeklyHealth.sums_over_the_week` 기대값 `버퍼존 5/5`, `TestBufferZoneHealthDates` 의 기대 질의와 문구 끝

**Validation**:

- [x] `poetry run pytest tests/test_alert_rendering.py tests/test_health_line.py` — **코드가 만드는 값을 보는 테스트만** 실패한다: `TestUsdKrw` 정본 · 주간 `FlowsIntoAlerts`(`reverses` 누락 `TypeError`) · `sums_over_the_week` · `TestBufferZoneHealthDates` 둘(옛 문구 · 옛 질의). `TestBufferZone` 은 점검 줄을 손으로 넣으므로 **통과하는 것이 맞다.** 실패 목록을 진행 로그에 적는다

---

### Phase 1 — 코드에서 역방향을 걷어낸다(그린)

**작업 내용**:

- [x] 소스 수정 — 5) 「수정하는 소스」 표 전부 (`_run_alert.yml` 은 Phase 2)
- [x] 소스 삭제 — `alerts/reverse_rank.py` · `state/reverse_rank.py`
- [x] 테스트 삭제 — 역방향 전용 네 파일과 `conftest.py`
- [x] 테스트 수정 — 5) 「수정하는 테스트」 표 가운데 Phase 0 에서 하지 않은 것 전부

**Validation**:

- [x] 남은 테스트 파일 전부를 파일 단위로 돌려 통과 — `poetry run pytest tests/test_alert_rendering.py tests/test_health_line.py tests/test_close_date_guard.py tests/test_weekly_window.py tests/test_usdkrw_calc.py tests/test_state_loading.py tests/test_yfinance_errors.py tests/test_trading_calendar.py tests/test_cli_failure_path.py tests/test_config_sources.py tests/test_buffer_zone_calc.py tests/test_credential_masking.py` (failed=0)
- [x] 잔존 참조 0건 — `git grep -n -E "reverse_rank|REVERSE_|역방향|RANK_KEY|rank_cut|KR_CALENDAR|close_on|first_change_day|fetch_intraday_price|format_usd|format_day_paren|previous_(us_|kr_)?trading_day|trading_days_between|weekly_extremes|Reverse(Line|Block)|_change_rates" -- src tests`
- [x] 위 조사 표의 «제거 후 0» 을 정의 grep 으로 재확인 — 정의가 남은 것이 없다

---

### Phase 2 — 워크플로 · 상태 파일 · 참고 스냅샷을 지우고 문서를 맞춘다

**작업 내용**:

- [x] 삭제 — `.github/workflows/reverse_rank_kr.yml` · `reverse_rank_us.yml` · `state/reverse_rank.toml` · `reference/역방향_매매_규칙.md`
- [x] `_run_alert.yml` 머리 주석
- [x] `docs/DESIGN.md` — 5) 표의 나머지 절 전부 (§4.5 는 Phase 0 에서 함)
- [x] 루트 `CLAUDE.md` · `README.md` · `docs/COMMANDS.md` · `reference/README.md`

**Validation**:

- [x] 문서 잔존 참조 — `git grep -n -E "역방향|reverse_rank|순위 등락률|rank_cut|KODEX" -- . ':!docs/plans' ':!docs/AUDIT_2026-09-26.md' ':!docs/research'` 결과가 **허용 목록뿐**이다: DESIGN §8 의 새 행 · 확정 이력 · 비목표에 적은 「근거가 된 사건」 넷 · §8 pykrx 행 · `CLAUDE.md` 기각 목록 · `reference/README.md` 「가져오지 않은 것」 · `test_yfinance_errors.py` 의 시험 종목 `KODEX`. 결과 전부를 진행 로그에 붙인다
- [x] 끊긴 절 포인터 0건 — `git grep -n -E "§4\.4|4\.4 절|알림 2[abc]|알림 3" -- . ':!docs/plans' ':!docs/AUDIT_2026-09-26.md' ':!docs/research'`
- [x] DESIGN 목차 앵커가 바뀐 제목과 맞는다 (`#4-알림-둘`)

---

### 마지막 Phase — 실제 조립 확인 및 최종 검증

**작업 내용**

> 🔴 **체크박스와 상태를 먼저 확정하고, `/commit` 은 맨 마지막에** — 이유는 `/impl-plan` 「5) Commit Messages」.

- [x] dry-run — `poetry run python -m notify buffer_zone --dry-run`. **목적: 점검 블록이 `최근 주간` 한 줄로 실제 조립되는지 본다.** 외부 호출은 yfinance 일봉(버퍼존 티커 넷 + 보유)뿐이다. 로컬에는 `GITHUB_TOKEN` 이 없어 점검이 `이력 조회 실패` 로 나오는 것이 정상이고, 전날(KST)이 미국 휴장이면 출력이 비는 것이 정상이다 — 그때는 진행 로그에 적고 단위 테스트로 갈음한다
- [x] `poetry run python -m notify reverse_rank_kr --dry-run` 이 인자 오류(종료 코드 2)로 끝난다 — 외부 호출 없음
- [x] 주간 알림 dry-run 은 **로컬에서 하지 않는다** — 이 PC 에 `.env` 가 없어 ECOS 인증키가 없다(2026-10-06 22:36 확인). 문구는 단위 테스트의 정본 대조로 검증하고, 배포 뒤 Actions `dry_run` 실행을 사용자 확인 항목으로 둔다 (Notes 「배포 순서」 ③)
- [x] 자동 포맷 적용 — `poetry run black .`
- [x] Validation 절에 `/code-review` 와 품질 검증 **실행 결과**를 적는다
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정
- [x] 🔴 **마지막에 `/commit` 을 실행하고 그 후보를 «이 계획서» 의 `#### Commit Messages` 절에 옮긴다** —
      대화에만 내면 그 절이 빈 채로 남는다. **커밋은 사용자가 한다 — 후보만 낸다**

**Validation**:

> 순서는 `/code-review` → 품질 검증이다. 고칠 것 · 회차 상한 · 수정분 검증은 `/impl-plan` 의 `review.md` 가 정한다.

- [x] `/code-review xhigh` **1회차** (발견 10건 — 버그 2 [무거움 2 · 가벼움 0] · 그 외 8 · 조치: 무거움 2 수정 — 버퍼존 점검 줄의 조회 실패 · 덜 돎 테스트와 주간 알림 점검 날짜 조립 테스트 4개, 변형 3종으로 확인, 주간 dry-run 실행. 그 외 중 계획 목표 5 누락 3건 반영(`kst_day_bounds` 의 07:20 서술 · `HealthLine` 예 「전일」 · 과하게 지운 「조용히 끝나는 알림의 실패」 근거를 `failure.py` 와 DESIGN §7.4 에 휴장 기준으로 복원). 미조치 그 외 5 — 개수 표기 관례 · `_previous_monday` docstring(변경 전부터 틀림, 감사 MIS-9) · `_detail` 일반화(비목표) · `_history(interval)` · `is_trading_day(calendar_code)` 일반화 · 테스트 헬퍼 tz 기본값과 `TestClosesThrough` 배치)
- [x] `/code-review xhigh` **2회차** (발견 10건 — 버그 0 [무거움 0 · 가벼움 0] · 그 외 10 · 조치: 고칠 것(닿는 버그) 0 — 종료. 그 외 중 이번 diff 가 새로 쓴 문장의 사실 오류 2건만 수정 — DESIGN §6.1 「최대 4시간 58분」(§1 사고표의 7시간 45분과 어긋남 → 원래 문장 「중앙값 64분」으로 되돌림) · §7.3 소제목 「(2026-09-11 결정)」(지워진 결정을 가리킴 → 「두 알림이 서로를 셉니다 (2026-10-06 결정)」). 미조치 8 — `_previous_monday` docstring(감사 MIS-9) · §4 표 「항상 발송」(변경 전부터) · `kst_day_window` 포인터(감사 MIS-6) · 주간 점검 API 6회(성능, 감사 RF-7) · 점검 줄 다중 항목 일반화 · `_history` · `is_trading_day` 일반화 · 개수 표기 · 테스트 tz 기본값)
- [x] 수정분 검증 (수정 2건 · 발견 3건 — 무거움 0 · 조치: 미조치 — ① §7.3 소제목 날짜는 「둘만 남긴」 결정의 날짜이고 서로 세는 구조는 2026-09-06 부터 있었음 ② §7.3 본문 「요일이 겹치지 않아」는 정시 실행에만 맞고 수동 실행 겹침을 빠뜨림(월요일 분기는 `test_weekly_window` 가 고정) ③ 실측 문서 :483-485 의 DESIGN §6.4 포인터가 지운 블록을 가리킴(실측 문서는 비목표). 셋 다 문서 서술)
- [x] `poetry run python validate_project.py` (passed=135, failed=0, skipped=0 — Ruff 통과 · PyRight 통과)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

> **Done 직전에 `/commit` 을 실행해 이 절을 채운다. 그전에는 비워 둔다** — 추측으로 적은 줄은 그대로 나간다.

1. 알림 / 역방향 알림 제거
2. 알림 / 역방향 일일 알림 · 주간 역방향 요약 · 순위 파일 제거
3. 알림 / 역방향 매매 중단에 따른 역방향 알림 전체 제거와 점검 줄 축소
4. 알림 / 역방향 판정 · 순위 갱신 알림 · 주간 요약 제거와 버퍼존 · 주간 교차 점검으로의 점검 줄 축소
5. 알림 / 보유텀이 짧은 역방향 매매 중단 — 워크플로 · 판정 코드 · 순위 파일 · 참고 스냅샷 삭제와 설계 문서 정리

## 7) 리스크(Risks)

- **배포와 cron 잡 정리 사이의 틈** — 코드가 먼저 `main` 에 올라가고 잡이 남아 있으면 없는 워크플로를 불러 cron-job.org 실패 메일이 온다(무해). 반대로 잡을 먼저 지우면 옛 코드의 버퍼존 점검에 `🔴 역방향 US 0/1` · `🔴 역방향 KR 0/2` 가 뜬다. → **push 직후, 다음 발화(KR 12:00) 전에 잡 3개를 지운다**
- **매일 읽는 문구가 바뀐다** — 점검 블록이 한 줄로 줄어 「오늘」·「전일」 줄이 사라진다. → 정본(§4.5)과 테스트를 Phase 0 에서 먼저 고정하고 dry-run 으로 실제 조립을 본다
- **지우는 설계 근거가 되살릴 때 필요하다** — 4자리 자르기 · 순위 컷 · `data_to` · 낡음 판정 · 1 ulp 틈 · 장중 지연 같은 판단이 DESIGN 에서 사라진다. → git 이력에 남고, §8 의 새 행이 되살릴 때 볼 판(`e8968f2` 의 DESIGN §4.3 ~ §5.2 · `reference/역방향_매매_규칙.md`)을 가리킨다
- **점검이 덮는 범위가 줄어든다** — 역방향이 있을 때 점검 줄은 「침묵하는 알림」을 감시했다. 남는 두 알림은 늘 발송하므로 도착 자체가 증거이고, 점검은 서로의 빠진 실행(지난 월요일 주간 · 지난주 버퍼존)을 교차로 센다. 감시 공백은 생기지 않는다
- **문서 대량 수정 중 남는 문장이 사라진 기능을 가리킬 수 있다** — Phase 2 의 grep 두 개(잔존 참조 · 끊긴 절 포인터)로 잡는다
- **감사 문서와 어긋난다** — `docs/AUDIT_2026-09-26.md` 의 줄 번호와 일부 항목이 사라진 코드를 가리키게 된다. 임시 문서라 고치지 않고, 대상이 사라지는 항목을 Notes 에 적는다

## 8) 메모(Notes)

### 결정 사항 (2026-10-06 사용자)

- 범위: **역방향 기능 전체** — 일일 알림 둘 · 주간 역방향 요약 · 순위 파일 · 로더 · 참고 스냅샷
- 점검 줄: **역방향 항목만 빼기** — 점검 기능은 유지
- 제거 사유 (사용자 원문): 「보유텀이 너무 짧은건 안 하기로 함」 — 정본 규칙의 보유 한도는 「D+2」(`reference/역방향_매매_규칙.md` §1.3 표)이고 수익이면 그날 청산한다
- **역방향 매매 자체를 그만둔다** (사용자 원문: 「역방향 매매 자체를 그만 두는것이야」) — 그래서 §4.1 「매매법과의 대응」 표의 역방향 행을 **지운다** (알림 없음 행으로 남기지 않는다)
- 알림 번호: 남는 둘을 `알림 1`(버퍼존) · `알림 2`(주간)로 **다시 매긴다** (사용자 원문: 「다시 매겨줘」)

### DESIGN §8 에 넣을 행 (초안)

| 안 | 기각 사유 |
| --- | --- |
| **역방향 알림** (`reverse_rank_kr` · `reverse_rank_us` · 주간 역방향 요약) | **역방향 매매를 그만뒀습니다** (2026-10-06 사용자 결정 — 「보유텀이 너무 짧은건 안 하기로 함」). 규칙의 보유 한도가 D+2 입니다. 되살린다면 `e8968f2` 판의 §4.3 ~ §5.2 와 `reference/역방향_매매_규칙.md` 에서 판정 규격 · 순위 파일 규칙 · 낡음 판정의 근거를 꺼냅니다 |

루트 `CLAUDE.md` 기각 목록에는 「역방향 알림」 한 낱말만 넣는다 — 근거는 §8 한 곳에 둔다.

### 배포 순서 (코드 밖 — 사용자가 한다)

- ① 커밋 · `main` 에 push
- ② **cron-job.org 에서 잡 3개 삭제** — 역방향 US(`20 7 * * 2-6`) · 역방향 KR(`0 12 * * 1-5`) · 역방향 KR(`30 14 * * 1-5`). push 직후, 다음 발화 전에
- ③ (선택) GitHub Actions → `usdkrw` → Run workflow 에서 `dry_run` 을 켜고 실행해 새 주간 문구를 로그로 확인 — 로컬에 ECOS 인증키가 없어 이 경로가 주간 알림의 유일한 실조립 확인이다
- 지운 워크플로의 지난 실행 이력은 Actions 화면에 남는다. 지울 필요 없다

### 이 작업으로 대상이 사라지는 감사 항목 (`docs/AUDIT_2026-09-26.md`)

- **전부 사라짐**: BL-2 · CON-2 · CON-4 · UC-3 · UC-4 · RF-3 · RF-4 · ST-3 · ST-4 · GUARD-4 · GUARD-6 · MIS-7 · MIS-8 · MIS-11 · MIS-12 · MIS-13 · MIS-20 · MIS-22 · MIS-23 · MIS-24 · MIS-25 · VOL-2 · VOL-3 · 부록 A-6
- **저절로 풀림**: MIS-2 (`reverse_rank.toml` 이 없어져 「파일이 없거나 비어 있어도 알림은 발송」이 참이 된다)
- **일부만 사라짐**(감사를 이어갈 때 다시 대조): UC-1 · UC-2 · UF-2 · DEAD-4 · RF-1 · RF-7 · ST-1 · ST-2 · ST-6 · ST-7 · GUARD-1 · TI-2 · MIS-10 · MIS-26 · CON-6 · 부록 A-1 · A-4 · A-5

### 진행 로그 (KST)

- 2026-10-06 22:36: 계획서 작성. 감사 기준 커밋 `321fa4e` 이후 `src/` · `tests/` 변경 0건 확인 — 감사 문서는 미완료라 지우지 않음(사용자 요청 #2)
- 2026-10-06 22:36: 자체 검증 — 1회차 6건 반영(COMMANDS 행 중복 · Phase 0 레드 범위 오기 · 주간 역방향 테스트 삭제 시점 · `cli` 지울 import 명시 · 의존성 무변경 명시 · DESIGN 변경을 절별 표로). 2회차 1건(Phase 0 에 `FlowsIntoAlerts` 의 `reverses` 제거 포함). 3 · 4 · 5회차(의존 모듈 · Phase 순서 · 문서 잔존) 개선 없음 — 종료
- 2026-10-06 22:54: 사용자 답 반영 — 제거 사유 「보유텀이 너무 짧은건 안 하기로 함」 · 역방향 매매 자체를 그만둠(§4.1 행 삭제) · 알림 번호 다시 매김. §8 행 초안과 `reference/README.md` 「가져오지 않은 것」 행을 구체화
- 2026-10-06 22:58: 사용자 승인(「진행」). Phase 0 완료 — §4.5 첫 표의 「등락률」 · 「미국 `$612.40`」 도 함께 고침(`format_usd` 가 사라져 그 표기를 내는 코드가 없어진다). 레드 7건 = `TypeError: render() missing 1 required positional argument: 'reverses'` 4건(`TestUsdKrw` 정본 · 빨간 점 · 판정 어휘, 주간 `FlowsIntoAlerts`) + `AssertionError` 3건(`sums_over_the_week` · `asks_only_for_the_last_weekly_run` · `block_holds_the_weekly_line_only`). `TestBufferZone` 통과(손으로 넣은 점검 줄). 52 passed
- 2026-10-06 23:06: Phase 1 완료 — 남은 테스트 파일 12개 `131 passed`(failed 0). 잔존 참조 `git grep` 0건(종료 코드 1), 지울 정의 grep 0건. 계획 외로 고친 것: `test_health_line` 의 조회 구간 docstring 두 곳(「07:20~07:30 미국장 알림」→ 07:30 아침 알림, 「같은 아침에 도는 실행」 서술 — 역방향 US 가 사라져 그 상황이 없다), `test_close_date_guard` 의 남은 `close_on` 두 테스트는 클래스 이름을 `TestClosesThroughFailure` 로 바꿈
- 2026-10-06 23:12: Phase 2 완료. 문서 잔존 참조 결과 — `CLAUDE.md:42`(기각 목록) · DESIGN `:211`(75칸 근거) · `:538` · `:545`(KST 고장 경위 — 「역방향 알림이 있던 때 — §8」 표시를 붙임) · `:573`(「한국 역방향 6일」 근거) · `:646`(§8 새 행) · `:683`(확정 이력) · `reference/README.md:25`(가져오지 않은 것) · `test_yfinance_errors.py` 의 시험 종목 `KODEX` · **계획 밖 1건** `reference/원달러_백분위_알림.md:145` · `:261` 「KODEX 미국달러선물」(원달러 규칙의 ETF 이름 — 역방향과 무관, 스냅샷이라 고치지 않음). 끊긴 절 포인터 grep 은 DESIGN `:648` 「실측 §4.4」 1건 — 실측 문서의 절이라 오탐. §4.3 포인터 0건, 목차 앵커 일치. 판단: **DESIGN §4.5 번호는 당기지 않음** — DESIGN 밖 7곳(`CLAUDE.md` 2 · 소스 2 · `_run_alert.yml` 1 · 테스트 1 · `reference/README.md` 1)이 「4.5」를 가리켜 당기면 그 전부를 고쳐야 한다. 계획 밖으로 고친 것: §4.5 첫 표의 「날짜」 줄(`(MM-DD 요일)` 표기 삭제 — `format_day_paren` 이 사라짐), §6.1 에 §2 의 최대 지연 사례 한 줄(장중 예시를 지운 자리), §5.2 「파일이 없거나 비어 있으면」 문장
- 2026-10-06 23:22: dry-run — `buffer_zone`: 점검 블록이 `최근 주간 10-05 (월) · 🔴 <b>이력 조회 실패</b>` 한 줄(로컬 토큰 없음, 정상), 종료 코드 0. `reverse_rank_kr`: `invalid choice`, 종료 코드 2. **전제 변경** — 계획서 작성 시(22:36) 없던 `.env` 가 22:45 에 생김(값은 보지 않고 개수만 셈: `ECOS_API_KEY` · `TELEGRAM_BOT_TOKEN` · `TELEGRAM_CHAT_ID` · `GITHUB_TOKEN` 채워짐, `GITHUB_REPOSITORY` 비어 있음). 검증을 낮추는 변경이 아니라 더하는 것이라 `usdkrw` dry-run 도 실행 — 역방향 블록 없이 조립, 점검 `지난주 09-28 (월) ~ 10-03 (토)` · `🔴 <b>이력 조회 실패</b>`, 종료 코드 0
- 2026-10-06 23:22: 리뷰 1회차 처리. 변형 확인(`PYTHONDONTWRITEBYTECODE=1`, `cli.py` 사본 대조로 되돌림 확인) — M1 `_weekly_slot` 이 `measure_runs` 를 건너뜀 → `lookup_failure_still_sends` · `missing_weekly_run_is_emphasised` FAILED · M2 `week_start = _previous_monday(end)` → `counts_last_week_from_monday_to_saturday` · `block_ends_the_alert` FAILED · M3 구간 끝 `timedelta(days=4)` → 같은 둘 FAILED. 세 변형 모두 나머지 4 passed
- 2026-10-06 23:39: 리뷰 2회차(상한) — 닿는 버그 0 이라 종료. 23:22 기록의 §6.1 「§2 의 최대 지연 사례 한 줄」은 §1 과 어긋나 **되돌림**(DESIGN 사본 `scratchpad/DESIGN.md.round2` 를 뜬 뒤 수정). 수정분 검증은 맥락 없는 서브에이전트 1회, 두 hunk 모두 OK
- 2026-10-06 23:39: 미룬 지적 거르기 — 1 · 2회차 미조치와 수정분 검증 발견 전부가 문서 · 정리 · 성능이라 **거르는 기준 3(버그가 아니다)**: 개수 표기 · `_previous_monday` docstring · `_detail` · `buffer_zone.render` 다중 항목 일반화 · `_history(interval)` · `is_trading_day(calendar_code)` · 테스트 `_series` tz 기본값과 `TestClosesThrough` 배치 · §4 표 「항상 발송」 · `kst_day_window` 포인터 · `weekly_health` API 6회 · §7.3 소제목 날짜 · §7.3 「요일이 겹치지 않아」 · 실측 문서 §6.4 포인터. 옮길 것 0건 → `deferred_findings` 파일을 만들지 않음

---

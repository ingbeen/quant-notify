# Implementation Plan: 2026-10-07 전수 분석 권장안 반영

> 작성/운영 규칙(SoT): `/impl-plan` 스킬(`~/.claude/skills/impl-plan/SKILL.md`)을 반드시 참고하세요.  
> (이 템플릿을 수정하거나 새로운 양식의 계획서를 만들 때도 해당 스킬을 포인터로 두고 준수합니다.)

**상태**: ✅ Done

---

> 상태는 🟡 Draft / 🔄 In Progress / ✅ Done. Done 조건과 기록 규칙은 `/impl-plan` 「3) 스킵 및 완료 규칙」이며 `~/.claude/hooks/plan_lint.py` 가 저장 때 검사한다.

---

**작성일**: 2026-10-08 22:00
**마지막 업데이트**: 2026-10-08 23:14
**관련 범위**: 데이터(`data/`), 알림(`alerts/`), 상태(`state/`), CLI, 설정(`utils/`), 테스트, 워크플로, 설정 파일, 문서 전반
**관련 문서**: 루트 `CLAUDE.md`, `docs/DESIGN.md`, `docs/COMMANDS.md`, `README.md`, `docs/research/데이터소스_실측.md`, `reference/`

---

## 1) 목표(Goal)

- [x] 목표 1: **틀린 알림 · 알림 중단을 막는다** — 윤일 실패(BUG-1), 0 이하 가격(GUARD-1), 장 마감 전 수동 실행(GUARD-2), 원달러 창 시작 결손(GUARD-3), 보유 파일의 모르는 키 · 잘못된 티커 · 미국 밖 종목(GUARD-4 · GUARD-5 · BL-1)에서 **조용히 틀리지 않고 멈춘다**
- [x] 목표 2: **보유 파일을 고치는 정상 운영이 테스트를 깨뜨리지 않는다** (BUG-2)
- [x] 목표 3: **코드를 단순하게** — 닿지 않는 가드 · 아무도 넘기지 않는 인자 · 한 줄짜리 래퍼 · 한 항목만 받는 일반화를 걷고, 점검 로직을 `health.py` 에, 외부 조회를 `data/` 에 모은다. **알림 문구는 실패 예시(MIS-1) 외에 바뀌지 않는다**
- [x] 목표 4: **한 사실은 한 곳에** — 코드 docstring 이 DESIGN 을 다시 서술하지 않고, 문서끼리 같은 사실을 반복하지 않는다. 사라진 정본(verify-lab 원달러 문서)을 가리키는 포인터를 없앤다
- [x] 목표 5: **문서를 가볍게** — 지운 기능만의 측정 · 이력 서술 · 끝난 계획서 11건 · 감사 문서 둘을 걷는다. 남길 사실은 먼저 살아있는 문서로 옮긴다

## 2) 비목표(Non-Goals)

- **정상 알림 문구는 바꾸지 않는다.** 버퍼존 · 주간 알림의 정상 출력은 글자 단위로 지금과 같다 (`test_alert_rendering.py` 의 정본 대조가 그대로 통과해야 한다). 바뀌는 것은 DESIGN 의 **실패 예시**(실제 형식으로 바로잡음)와, 새로 멈추는 경우의 **예외 문구**뿐이다
- **점검 합산 방식은 그대로 둔다** (BL-3 수용) — 수동 · `dry_run` 실행도 실행으로 센다는 사실만 DESIGN §7.3 에 한 줄 적는다. 실행 이력 API 로는 정시 · 수동 · `dry_run` 을 가릴 수 없다
- **지난주 점검의 조회 횟수(6회)를 범위 질의로 줄이지 않는다** (RF-8 제외) — 비용이 작고, 날짜별 계수가 예정 횟수 · 테스트와 같은 단위라 단순하다
- **`validate_project.py` 는 고치지 않는다** (RF-7 — 확인 필요 D6) — quant 의 같은 파일과 2줄만 다른 공용 템플릿이다
- **이상치(「절반 값」 종가) 판정은 넣지 않는다** — 실제 폭락(QQQ 2020-03-12 −10.89%)과 가를 기준이 없다. 0 이하만 「불가능 값」으로 멈춘다
- **스냅샷 중 알림이 쓰지 않는 부분(달러 매수 규칙 §1.1 · 비용과 세금 §1.4 · 성적 §2)은 옮기지 않는다** — 매매 규칙이지 알림 규격이 아니다. git 이력(이 저장소 `0e6b0f3`, verify-lab `0746727`)에 남는다
- `docs/MEMORY.md` 는 고치지 않는다 — 옮길 사실은 모두 DESIGN 에 자리가 있다
- cron-job.org 잡 · GitHub 시크릿 등 **코드 밖 설정은 바꾸지 않는다**

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- `docs/AUDIT_2026-10-07.md`(커밋 `0e6b0f3` 기준 전수 분석)의 권장안을 사용자가 전부 승인했다 — 「추천대로 진행」, 「완료 후 AUDIT 문서 전부 제거」 (2026-10-08 사용자). **감사 문서는 이 작업 끝에 지우므로, 이 계획서는 그 문서 없이 읽히게 쓴다.** 항목 ID(BUG-1 등)는 대조용 꼬리표다
- 기준선: Ruff · PyRight 통과, `135 passed, 0 failed, 0 skipped`, 커버리지 85%
- 재현으로 확인한 결함 (scratchpad 사본, 저장소 무변경):
  - **BUG-1** `usdkrw.window_slice` 의 `date(end.year - years, end.month, end.day)` — 기준일 2/29 에 `ValueError: day is out of range for month`. 정시 실행은 2036-03-03(월), 수동은 2028-03-01 ~ 03-02 에 걸린다
  - **BUG-2** `test_close_date_guard._run` 이 `load_positions` 를 막지 않는다 — 보유 한 줄을 넣으면 `3 failed, 132 passed`(`KeyError: 'QLD'`)
  - **GUARD-1** 종가 0 이면 근접도 −100% → `SPY 매도선 아래` (매도 신호로 읽힘). 환율도 0 이하를 검사하지 않는다
  - **GUARD-4** `[[position]]`(표 이름 오타) → 빈 보유로 조용히 통과, 항목의 `qty = 300` 도 무시
  - **GUARD-5 · BL-1** `" QLD"` · `"qld"`(중복 검사 통과) · `"A<B"` · `"069500.KS"` 가 모두 로딩된다. 비중은 통화 구분 없이 `수량 × 가격` 을 더하고, 종가는 미국 거래일로 집는다
- 추론으로 확인한 결함 (외부 호출 없이):
  - **GUARD-2** 미국 장중(KST 00:00 ~ 미국 마감)에 수동 실행하면 `target`(KST 어제)이 진행 중인 세션이라, 장중 일봉이 날짜 가드를 통과해 **미확정 가격이 종가처럼** 판정된다
  - **GUARD-3** 원달러 창은 비었을 때만 멈춘다 — ECOS 가 7년치만 돌려줘도 「10년 평균」으로 나간다. 조회 기간 `365 * 11` 이 가장 긴 창과 따로 박혀 있다(CON-3)
- **원달러 정본이 사라졌다** — verify-lab 이 2026-09-15(`d838db9`)에 `docs/strategy/원달러_백분위_알림.md` 를 지우고 지표 정의를 `docs/조사/원달러_조달.md` §14.2 로 옮기며, **알림 창 · 문구 결정은 「개인 운용 값」이라 뺐다**(그 문서 :607). 이 저장소의 포인터(CLAUDE.md · README · reference · DESIGN)가 모두 없는 파일을 가리킨다
- PyRight 억제 실측: 테스트 실행환경 10개 중 9개 효과 0, `reportPrivateUsage` 만 5건(`test_weekly_window.py` 의 `cli._last_week_monday` · `_previous_monday`). 전역 `reportUnknown*` 는 src 16 · tests 28 건, `reportMissingTypeStubs` 3건 — **둘 다 유지한다**(근본 해결이 `cast` 를 늘리는 것이라 단순성과 맞바꿈)
- 내부 · runtime import 0건, 순환 import 0건, `# type: ignore` 0건 — 할 일 없음

### 사용자 결정 (2026-10-08) — 감사 문서의 권장안

| ID | 결정 |
| --- | --- |
| BL-1 | 보유를 **미국 상장 종목으로 한정**하고 로딩할 때 거부한다 (GUARD-5 와 한 검사) |
| BL-3 | 점검 합산 방식 **수용** — DESIGN §7.3 에 한 줄 |
| ST-7 | 알림이 쓰는 원달러 규칙을 **DESIGN 으로 옮기고 `reference/` 를 지운다** |
| ST-8 | research 문서에서 **지운 기능만의 측정을 걷는다** |
| PLAN-4 · PLAN-5 | 끝난 계획서 11건과 **감사 문서 둘을 지운다** (`docs/plans/.gitkeep` 유지) |

### 확인 필요 — 감사 문서가 권장안을 정하지 않았던 항목 (아래 권장으로 계획을 썼다)

| ID | 권장 (이 계획서의 전제) | 다른 선택지 |
| --- | --- | --- |
| D1 (GUARD-2) | 장 마감 전이면 **조회 전에 `ValueError` 로 멈춘다** — 실패 알림에 마감 시각이 담긴다 | 수용하고 COMMANDS 에 한 줄 |
| D2 (GUARD-3) | **첫 자료가 창 시작일보다 늦으면 멈춘다.** 여유 일수를 두지 않는다 — 조회를 가장 긴 창보다 1년 더 받으므로 정상이면 첫 자료가 약 1년 앞선다 | 수용하고 DESIGN 에 한 줄 |
| D3 (UC-1) | `common_constants.py` 를 **유지**하고 설명만 실제에 맞춘다. **ECOS 코드만** `fetch_usdkrw` 가 인자를 버리면서 `ecos_client` 로 간다 | 모든 단일 사용 상수를 쓰는 모듈 옆으로 |
| D4 (ST-9) | cron-job.org 설정 · PAT 발급(한 번 하는 설정)을 **README 「필요한 것」 아래로** 옮긴다 — COMMANDS 머리말(「일회성은 기재하지 않음」)과 전역 규칙에 맞춘다 | COMMANDS 머리말을 고쳐 그대로 둠 |
| D5 (ST-10) | DESIGN **§4.5 → §4.3** 으로 번호를 당기고, 남는 포인터를 같은 작업에서 고친다 (ST-4 로 코드 포인터가 줄어든 뒤) | 번호 유지 |
| D6 (RF-7) | `validate_project.py` **유지** | 반환코드만 보는 형태로 축소 |
| D7 (A-3) | 다른 저장소에서 옮겨 적은 값을 고정하는 테스트(두 선 비율 · 이동평균 기간 · 신호 티커 · 원달러 창)를 **유지**하고, DESIGN 의 「두 비율은 테스트가 고정합니다」를 그 넷으로 넓힌다 | 비율 둘만 남기고 지움 |

**감사 문서 권장에서 조정한 것** — 실행 순서상 앞 항목이 뒤 항목을 바꾼다

- **A-5(conftest 로 헬퍼 이동)는 BUG-2 fixture 하나만** 올린다. `test_weekly_window.py` 를 해체해 두 파일로 합치면(A-1 · A-4) 나머지 헬퍼는 한 곳씩만 남는다. 한 줄짜리 `_flat` · `_closes` 두 벌은 그대로 둔다 — conftest 함수는 import 해 쓰는 관용이 아니고, 픽스처로 바꾸면 더 길어진다
- **VOL-7(시크릿 목록)은 README 에 둔다** — D4 로 README 가 설정 안내를 맡는다. `_run_alert.yml` 의 env 목록은 코드 쪽이라 두 벌이 불가피하다
- **API 버전 헤더는 두 곳**(README 의 cron 설정 · COMMANDS 의 `curl` 예시)에 남는다 — 명령 자체가 그 헤더를 요구한다
- **ST-2(GitHub 실행 이력 조회를 `data/` 로)는 포함한다** — 「선택」이었으나 ST-1 로 점검 로직을 옮기는 김에 함께 하면 DESIGN §5.4 「조회 코드는 `data/` 에」가 사실이 된다

### 글자 규칙이 막거나 되돌릴 수 없는 결과에 물리는가

**해당한다 — 보유 티커 형식 검사(BL-1 · GUARD-5).** 사람이 쓴 `state/positions.toml` 을 정규식으로 판정하고, 걸리면 **버퍼존 알림 전체가 실패**한다.

- **실제 산출물에 돌린 결과**: 저장소의 `state/positions.toml` 은 주석뿐이라 걸리는 줄이 0건이다. 그래서 **이 저장소가 다루는 실제 티커 집합**에 돌린다 — 버퍼존 티커 `SPY` · `QQQ` · `GLD` · `TLT`, Q-2-2XS 매매 티커 `SSO` · `QLD`, DESIGN 예시 `QLD` · `GLD`, 클래스 주식 표기 `BRK-B`(yfinance 형식). Phase 0 에서 이 8개가 모두 통과하는지 테스트로 고정한다
- **오탐 모양과 탈출구**: ① 점이 든 미국 클래스 표기(`BRK.B`) — yfinance 는 `BRK-B` 로 받으므로 거부 문구에 「하이픈으로 적으세요」를 담는다 ② 소문자 · 공백 — 거부 문구가 고칠 방법을 말한다. **결과가 되돌릴 수 있다** — 실패 알림이 오고, 파일을 고쳐 커밋하면 다음 실행부터 정상이다(누적 상태 없음). 판정은 실행 때마다 새로 한다

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `.claude/plan-config.json` — 이 저장소의 검증 명령·자동 포맷·근거 승격 목적지 (**값의 SoT**)
- 루트 `CLAUDE.md` — 특히 「계획서 규약 — 이 프로젝트의 설정」 절과 「스크립트 실행 규칙」(dry-run 까지만)
- `docs/DESIGN.md` — §4.5(문구 정본) · §5 · §7.3 · §7.4 · §8
- 전역 `~/.claude/rules/python.md` · `~/.claude/rules/python-tests.md`
- 루트 `CLAUDE.md` 를 고치는 Phase 에서 `writing-for-agents` 스킬과 `~/.claude/docs/하네스_동작.md`

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 `/impl-plan` 스킬)

- [x] Phase 0 의 새 멈춤 조건 테스트가 모두 통과하고, 보유를 한 줄 넣은 사본에서도 전체 테스트가 통과한다(BUG-2)
- [x] 정상 알림 문구 정본 대조 테스트(`test_alert_rendering.py` 의 `TestBufferZone` · `TestUsdKrw`)가 **기대 문자열 수정 없이** 통과한다
- [x] 5) Scope 의 소스 · 테스트 · 설정 변경을 모두 반영했고, 지운 심볼의 잔존 참조가 0건이다(Phase 2 의 grep)
- [x] `pyrightconfig.json` 의 테스트 실행환경 블록을 지운 상태로 PyRight 가 통과한다
- [x] 코드 리뷰 실행 및 결과 기록 (마지막 Phase 의 Validation 에 적는다)
- [x] 품질 검증 통과 (마지막 Phase 의 Validation 에 passed/failed/skipped 수를 적는다)
- [x] 자동 포맷 적용 완료 (마지막 Phase에서 실행)
- [x] 문서 업데이트 — `docs/DESIGN.md` 변경 있음 · 루트 `CLAUDE.md` 변경 있음 · `README.md` 변경 있음 · `docs/COMMANDS.md` 변경 있음(설정 절 이동 · 계획 단계 용어) · research 변경 있음 · `reference/` 삭제
- [x] 근거 승격 완료 — 계획서 11건과 감사 문서에서 남는 기능에 걸리는 사실(Phase 6 표)을 살아있는 문서로 옮겼고, 이 계획서를 지금 삭제해도 잃을 정보가 없다
- [x] 미룬 지적 옮김 — **해당 없음.** 미조치 지적 12건이 모두 거르는 기준 1 · 2 · 3 중 하나에 해당해 옮길 것이 0건이다
      (진행 로그 2026-10-08 23:14 · Done 보고 표). `deferred_findings` 파일을 만들지 않았다
- [x] 끝난 계획서 11건 · `docs/AUDIT_2026-09-26.md` · `docs/AUDIT_2026-10-07.md` 를 지웠다 (`docs/plans/.gitkeep` 유지)
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 소스

| 파일 | 변경 |
| --- | --- |
| `src/notify/data/yfinance_client.py` | **받는 시점에 인덱스를 거래소 현지 `date` 로 정규화**(ST-3) — `_index_date` 삭제(FB-3), `closes_through` 는 `closes.index <= day` 로. `fetch_closes(tickers)` · `_history(ticker)` 로 인자 축소(UC-2), 빈 종목 목록 가드 삭제(DEAD-4). **0 이하 종가면 `ValueError`**(GUARD-1). docstring 은 책임 · 불변조건 · 포인터만(ST-4) |
| `src/notify/data/ecos_client.py` | `request_json` 을 `fetch_usdkrw(api_key, start, end)` 안으로(UF-5 · UC-2), 도달 불가 `except ValueError` 삭제(BUG-3), ECOS 코드 두 개를 이 모듈 상수로(D3), **0 이하 환율이면 `ValueError`**(GUARD-1). `ENV_ECOS_API_KEY` 는 config 로(CON-1) |
| `src/notify/data/calendar.py` | `is_us_trading_day(day)` 하나로(UF-2), 미사용 `logger`(DEAD-1) · 범위 검사와 틀린 「갱신하세요」 안내(FB-1) 삭제. **`us_session_close(day) -> datetime`** 추가(GUARD-2) |
| `src/notify/data/github_runs.py` | **신규**(ST-2) — `health.py` 에서 `count_success_runs` · `kst_day_bounds` · `_utc_text` · `GITHUB_API` · `TIMEOUT_SECONDS` · `RunCounter` 를 옮기고, cli 의 `_run_counter` · `_health_counter` 를 `run_counter()` 하나로(UF-1, `functools.partial`). 「자격증명을 담게 되는 날」 가정 주석 삭제(FB-4 — 마스킹은 유지) |
| `src/notify/alerts/health.py` | 순수 계산 · 표기만 남긴다. `measure_runs` 가 조회 실패 때 라벨 없이 `alert(LOOKUP_FAILED)` 를 내는 `str` 반환으로 — `RunReport` · `_detail` 삭제(RF-1 · UC-4 · UF-6, **문구 불변**). `except Exception` → `except ValueError`(FB-2). cli 의 월요일 함수 둘 · `_weekly_slot` · `RUN_WEEK_OFFSET` 을 **오늘 날짜를 받는 공개 함수 둘**(`recent_weekly_health` · `last_week_health`)로 옮기고(ST-1 · RF-6), 지난주 끝 요일을 `max(_US_ALERT_WEEKDAYS)` 에서 낸다(CON-2). 월요일 분기 삭제(DEAD-3). 워크플로 파일 이름을 알림 이름에서 낸다(CON-4). 시작 > 끝 가드 소멸(DEAD-4) |
| `src/notify/alerts/buffer_zone.py` | `sma(closes)` 로 인자 · `period <= 0` 가드 삭제(UC-2 · DEAD-4), `position_weights` 의 보유 가격 누락 가드 삭제(DEAD-4), `render(health: HealthLine)` 하나로(RF-5), 줄 헬퍼 셋을 `render` 안으로(UF-4), 빈 근접도 가드 삭제(DEAD-4), 발송 시각 줄은 `format_sent_at`(RF-4) |
| `src/notify/alerts/usdkrw.py` | `years_before(day, years)` 로 2/29 를 2/28 로(BUG-1), `window_slice` 는 **첫 자료가 창 시작일보다 늦으면 `ValueError`**(GUARD-3 · D2 — 빈 창 검사를 대신함), `window_line(closes, years) -> WindowLine` 신설(RF-2), `mean_deviation` 의 빈 창 가드 삭제(DEAD-4), `_window_rows` 인라인(UF-4), 빈 창 목록 가드 삭제(DEAD-4), `format_sent_at`(RF-4) |
| `src/notify/alerts/formatting.py` | `format_sent_at(sent_at)` 추가(RF-4). 이모지 규칙 포인터를 전역 규칙으로(MIS-8). docstring 축소(ST-4) |
| `src/notify/alerts/failure.py` | `format_sent_at` 사용, docstring 축소(ST-4) |
| `src/notify/state/positions.py` | **모르는 키 거부**(GUARD-4 — 최상위 `positions`, 항목 `ticker` · `quantity` 밖이면 `ValueError`), **티커 형식 `^[A-Z][A-Z0-9-]*$`**(GUARD-5 · BL-1 — 미국 상장만, 거부 문구에 하이픈 안내) |
| `src/notify/utils/config.py` | 설정 이름 상수 5개(`ENV_TELEGRAM_BOT_TOKEN` · `ENV_TELEGRAM_CHAT_ID` · `ENV_ECOS_API_KEY` · `ENV_GITHUB_REPOSITORY` · `ENV_GITHUB_TOKEN`)(CON-1). 이력 서술 docstring 을 현재형으로(HIS-4) |
| `src/notify/utils/logger.py` | `get_logger(name)` 로 인자 축소(UC-2), DESIGN §3.4 를 다시 서술하는 주석 축소(ST-4) |
| `src/notify/notifier/telegram.py` | `send_without_raising` 은 `None` 반환(UF-3), `build_payload` 인라인(UF-5), docstring 축소(ST-4) |
| `src/notify/common_constants.py` | 알림 이름 `ALERT_BUFFER_ZONE` · `ALERT_USDKRW` 를 여기로(CON-4 — cli · health 가 함께 읽음), ECOS 코드 이동(D3), 모듈 설명을 실제에 맞춤(UC-1). 원달러 조회 기간은 cli 가 `usdkrw.years_before(end, max(USDKRW_WINDOW_YEARS) + 1)` 로 내고 `USDKRW_LOOKBACK_DAYS` 를 지운다(CON-3) |
| `src/notify/cli.py` | 디스패치 · 두 알림 조립 · 발송만 남긴다. `ALERTS = {이름: 함수}` 하나로 `ALERT_NAMES` · `build_message` · argparse 목록을 대신한다(RF-3 · UF-7). 버퍼존: 휴장 확인 뒤 **`now < us_session_close(target)` 이면 조회 전에 `ValueError`**(GUARD-2 · D1), 보유 블록 분기 단일화(FB-6). 주간: `window_line` · `years_before` 사용(RF-2 · CON-3). 실패 알림을 못 보낼 때 경고 한 줄(FB-5). `if __name__` 블록 삭제(DEAD-6). 설정 이름은 config 상수(CON-1) |

### 테스트

| 파일 | 변경 |
| --- | --- |
| `tests/conftest.py` | **신규** — `cli.POSITIONS_PATH` 를 `tmp_path` 의 없는 파일로 바꾸는 **autouse** fixture(BUG-2) |
| `tests/test_ecos_errors.py` | **신규**(A-6) — `requests.get` fake 로 인증키 마스킹 · `RESULT` 오류 · 빈 `row` · 숫자 아닌 값 · 0 이하(GUARD-1) |
| `tests/test_weekly_window.py` | **삭제** — 「지난주는 달력이 정한다」는 `test_health_line.py` 로(공개 함수 대상, A-4), `TestClosesThrough` 는 `test_close_date_guard.py` 로(A-1). `keeps_the_current_behaviour` 는 매일 테스트에 포함돼 지운다(A-2) |
| `tests/test_close_date_guard.py` | `closes_through` 테스트를 한 곳에 모으고 없는 날 예외 둘을 하나로(A-1), 시험 계열을 `date` 인덱스로(ST-3), **장 마감 전 수동 실행 테스트**(GUARD-2), **cli 보유 블록 조립 테스트**(A-6), 계수 함수 패치를 `github_runs.run_counter` 로, 사건 서술 docstring 정리(부록 B) |
| `tests/test_health_line.py` | 조회 구간 · 질의 테스트는 `github_runs` 대상으로, `count_success_runs` 실패 · `total_count` 누락 · `run_counter` 설정 유무 테스트 추가(A-6), 월요일 날짜 테스트를 공개 함수로(A-4), `no_positions` 삭제(BUG-2 fixture 가 대신), 사건 서술 정리 |
| `tests/test_alert_rendering.py` | `TestHealthLineFlowsIntoAlerts` 삭제(A-1 — `test_health_line` 종단 테스트에 포함), `TestFailure` 입력을 실제 형식으로(MIS-1), `render` 의 `health` 를 한 줄로 |
| `tests/test_yfinance_errors.py` | 0 이하 종가 테스트(GUARD-1), 인덱스가 `date` 인지(ST-3), `"Too Many Requests"` 고정을 `str(YFRateLimitError())` 포함 여부로(A-3), 같은 입력 두 테스트 합침(A-2), 사건 서술 정리 |
| `tests/test_usdkrw_calc.py` | 2/29 테스트(BUG-1), 창 시작 결손 테스트(GUARD-3), `window_line` 테스트, 같은 입력 두 테스트 합침(A-2), `mean_deviation` 빈 창 테스트 삭제(DEAD-4). `test_longer_window_holds_more_days` 는 시험 계열(2025-09-01 부터)이 3년 창을 못 채워 **GUARD-3 에 걸리므로** 계열을 3년 넘게 늘린다 — 정책 변화가 아니라 시험 데이터가 새 계약을 못 채운 것 |
| `tests/test_buffer_zone_calc.py` | `sma` 인자 · 빈 계열 테스트(A-2) · 가격 누락 테스트(DEAD-4) 정리 |
| `tests/test_state_loading.py` | 모르는 키 · 티커 형식 · 미국 밖 종목 거부와 실제 티커 8개 통과 테스트(GUARD-4 · GUARD-5 · BL-1) |
| `tests/test_trading_calendar.py` | 평일 · 주말(라이브러리 데이터) · 범위 밖(FB-1) 테스트 삭제, 노동절 유지(A-3) |
| `tests/test_cli_failure_path.py` | `build_message` 패치를 `monkeypatch.setitem(cli.ALERTS, …)` 로, `send_without_raising` 반환 `None` 에 맞춰 람다 정리(UF-3) |
| `tests/test_config_sources.py` | 설정 이름 상수 사용, `fetch_usdkrw` 새 시그니처, 사건 서술 정리 |
| `tests/test_credential_masking.py` | 「전에 `/bot` 접두사로」 서술을 현재 규칙으로 (부록 B) |

### 설정 · 워크플로

| 파일 | 변경 |
| --- | --- |
| `pyrightconfig.json` | 테스트 실행환경 블록 삭제(TI-2), `exclude` 의 `reference` 삭제 |
| `pytest.ini` | 쓰지 않는 마커 셋과 템플릿 설명 주석 삭제(UC-3), `norecursedirs` 의 `reference` 삭제 |
| `pyproject.toml` · `poetry.lock` | `freezegun` 삭제(UC-3) 후 `poetry lock`(`--regenerate` 없이 — 앞선 pykrx 제거와 같은 방식), black · ruff 의 `reference` 제외 삭제 |
| `.github/workflows/_run_alert.yml` | `python-version-file: .python-version`(CON-5), `dry_run` 입력 옆에 호출자의 `== true` 비교 이유 한 줄(PLAN-2), 머리 주석의 「매일 오던 알림 1」 정정(MIS-21) |
| `.github/workflows/buffer_zone.yml` · `usdkrw.yml` | 머리말 · 권한 주석을 DESIGN §6.2 · §6.3 포인터 한 줄씩으로(ST-5) |
| `.gitignore` | `state/` 주석을 한 줄 + 포인터로(ST-6) |

### 문서 — Phase 5 · 6 의 표

- `docs/COMMANDS.md`: **변경 있음** — cron-job.org 설정 · PAT 발급 절을 README 로 옮기고(D4), 「(마지막 Phase에서만)」 삭제(HIS-3). 실행 명령어 · CLI 옵션은 변화 없음(`--dry-run` · 알림 이름 그대로)
- 의존성: **dev 의존성 `freezegun` 하나 삭제** — 런타임 의존성 변화 없음

### 데이터/결과 영향

- **정상 알림 문구 변화 없음** — 정본 대조 테스트가 그대로 통과해야 한다
- **새로 실패 알림이 나가는 경우** — 0 이하 가격 · 장 마감 전 수동 실행 · 원달러 창 시작 결손 · 보유 파일의 모르는 키 · 잘못된 티커. 모두 지금은 **조용히 틀린 알림이 나가던** 경우다. 정시 실행(07:30 KST)은 미국 마감(서머타임 05:00 · 겨울 06:00 KST) 뒤라 GUARD-2 에 걸리지 않는다
- 저장하는 결과물 · CSV 없음

## 6) 단계별 계획(Phases)

### Phase 0 — 새 멈춤 조건과 실패 예시를 테스트로 먼저 고정(레드)

> 해당 사유: **에러 처리 정책 변경**(멈추는 조건이 다섯 생긴다) + 문구 정본(실패 예시) 수정.

**작업 내용**:

- [x] `tests/conftest.py` — 보유 차단 autouse fixture (BUG-2. 이것은 레드가 아니라 테스트 기반이다)
- [x] DESIGN §4.5 실패 알림 예시를 실제 형식 `ValueError: [QQQ] 시세 조회에 실패했습니다: YFRateLimitError: Too Many Requests. Rate limited. Try after a while.` 로, `test_alert_rendering.TestFailure` 입력도 같게 (MIS-1)
- [x] 레드 테스트 — 2/29 기준일(BUG-1) · 0 이하 종가(GUARD-1, `test_yfinance_errors.py`)와 0 이하 환율(GUARD-1, **`tests/test_ecos_errors.py` 를 이때 만든다**) · 장 마감 전 수동 실행이 조회 없이 멈춤(GUARD-2) · 첫 자료가 창 시작보다 늦음(GUARD-3) · 보유 파일의 모르는 최상위 키와 항목 키(GUARD-4) · 티커 형식과 미국 밖 종목 거부, 실제 티커 8개 통과(GUARD-5 · BL-1)

**Validation**:

- [x] `poetry run pytest` 로 새 테스트를 돌려 **새 멈춤 조건 테스트만** 실패하는지 본다(실제 티커 8개 통과 테스트와 MIS-1 은 통과가 맞다). 실패 목록을 진행 로그에 적는다
- [x] scratchpad 사본에 보유 한 줄을 넣고 전체 테스트 — `KeyError: 'QLD'` 3건이 사라진다(BUG-2)

---

### Phase 1 — data 계층 (그린)

**작업 내용**:

- [x] `yfinance_client.py` · `ecos_client.py` · `calendar.py` · `utils/config.py` · `utils/logger.py` · `notifier/telegram.py` — 5) 표대로
- [x] `data/github_runs.py` 신설과 `health.py` 에서 조회 코드 이동 (ST-2)
- [x] 각 모듈 docstring 을 「책임 한 줄 + 코드만으로 모르는 불변조건 + DESIGN · research 포인터」로 (ST-4). **DESIGN 이 정본인 근거는 코드에서 지운다**
- [x] 이 계층을 부르는 쪽(cli · health)과 테스트를 새 시그니처에 맞춘다 — 그린 유지에 필요한 만큼만

**Validation**:

- [x] `poetry run pytest tests/` — 실패가 **Phase 0 레드 중 판정 · 조립 계층 것(BUG-1 · GUARD-2 · GUARD-3 · GUARD-4 · GUARD-5)뿐**이다. GUARD-1 두 건은 그린이 되고, 그 밖의 실패는 0 이다. 실패 목록을 진행 로그에 적는다

---

### Phase 2 — 판정 · 조립 (그린)

**작업 내용**:

- [x] `health.py` · `buffer_zone.py` · `usdkrw.py` · `formatting.py` · `failure.py` · `positions.py` · `common_constants.py` · `cli.py` — 5) 표대로, docstring 은 Phase 1 과 같은 기준(ST-4)
- [x] 잔존 참조 0건 — `git grep -n -E "_index_date|request_json|build_payload|build_message|ALERT_NAMES|RunReport|lookup_failed|_detail\b|_weekly_slot|_run_counter|_health_counter|_previous_monday|_last_week_monday|RUN_WEEK_OFFSET|USDKRW_LOOKBACK_DAYS|is_trading_day\(|weekly_health\(|DEFAULT_PERIOD|DAILY_INTERVAL" -- src tests`

**Validation**:

- [x] `poetry run pytest tests/` failed=0 — Phase 0 레드 전부 그린, **정본 대조 테스트의 기대 문자열 무수정**(`git diff tests/test_alert_rendering.py` 에서 `TestBufferZone` · `TestUsdKrw` 의 기대값 줄이 바뀌지 않음)

---

### Phase 3 — 테스트 재편 (그린)

**작업 내용**:

- [x] 5) 「테스트」 표의 나머지 — 파일 합치기 · 중복 삭제 · 커버리지 공백 테스트 · 사건 서술 정리
- [x] 테스트 모듈 docstring 도 ST-4 기준 — DESIGN 이 정본인 근거(빨간 점 범위 · 분모 규칙 · UTC 조회 · 날짜로 집기 · `yf.download` 금지 · `.env` 경로 · 마스킹 이유)는 한 줄 + 포인터로
- [x] `pyrightconfig.json` 테스트 실행환경 블록 삭제 (TI-2)

**Validation**:

- [x] `poetry run pytest tests/` failed=0
- [x] `poetry run pytest --cov=src/notify --cov-report=term-missing tests/` — `ecos_client.py` · `cli.py` · `telegram.py` 커버리지가 기준선(33% · 79% · 65%)보다 오른다. 수치를 진행 로그에 적는다
- [x] `poetry run pyright` 0 errors (블록 삭제 확인 — 중간 확인이며 품질 검증은 마지막 Phase)

---

### Phase 4 — 설정 · 워크플로

**작업 내용**:

- [x] `pytest.ini` · `pyproject.toml` · `.gitignore` · 워크플로 셋 — 5) 표대로
- [x] `pyproject.toml` 에서 `freezegun` 을 지우고 `poetry lock` — 잠금 파일 diff 가 `freezegun` 관련 줄과 `content-hash` 뿐인지 눈으로 확인하고, 다른 변화가 있으면 멈춘다
- [x] **`poetry install` 은 돌리지 않는다** — 로컬 `.venv` 에 남은 `freezegun` 은 무해하다. 정리는 사용자가 판단한다 (전역 「환경 설치는 사용자가 직접 한다」)

**Validation**:

- [x] `poetry check --lock` 통과
- [x] 워크플로 YAML 문법 — `python -c "import yaml"` 이 없으면 `ruby -ryaml -e 'YAML.load_file(...)'` 등 이 기계에 있는 파서로 셋을 읽어 본다. 파서가 없으면 그 사실을 적고 diff 를 눈으로 대조한다

---

### Phase 5 — 문서 단일화 · 경량화

> 루트 `CLAUDE.md` 를 고치기 전에 `writing-for-agents` 스킬과 `~/.claude/docs/하네스_동작.md` 를 연다.

**작업 내용 — `docs/DESIGN.md`**

| 절 | 변경 |
| --- | --- |
| 머리말 | 작성일과 「그 문서는 이 저장소가 서면서 삭제됩니다」 삭제, 「§1 ~ §3 은 quant 설계서에서 옮긴 유일한 보관처」 한 줄 (HIS-2) |
| §1 · §3.1 | 폐기 파일 표와 줄 수를 한 문장으로 (HIS-2 · VOL-3) |
| §3.2 | `rolling(200).mean()` → 「최근 200개 평균」 (MIS-13) |
| §3.4 | 「처음에는 프라이빗」 표를 「퍼블릭이어도 잃지 않는 것」 현재형으로, 「월 2,000분」 삭제 (HIS-1 · VOL-2) |
| §4 | 표의 「침묵」 열 삭제(MIS-4), 화 ~ 토 이유는 §6.4 포인터로(ST-6). §4.1 의 원달러 행을 「지표 정의는 verify-lab `docs/조사/원달러_조달.md` §14.2 · 알림 형식은 §4.3」으로, 「규칙 문서 §1.5」→「옵션 만기일 규칙 §1.5」(MIS-20) |
| §4.5 → **§4.3** | 번호 당김(D5) · 목차. 「처음에는 `<pre>`」 · 「역방향 줄 75칸」을 현재형 근거로(HIS-1), 이모지 규칙 포인터를 전역 규칙으로(MIS-8), **3일 유지 문장을 「돌파일 다음 날부터 `매수선 위` 3일 — 돌파일 포함 4일째 매수」로**(BL-2 — quant `strategies/buffer_zone.py:379-412` 확인), 「두 비율은 테스트가 고정」을 옮겨 적은 값 넷으로(D7), 근접도 실측 표는 research 로(VOL-6), 빈 보유 문장은 §5.2 포인터로(ST-6). **원달러 절에 이 저장소가 쓰는 규칙을 옮긴다**(ST-7) — 평균대비 정의 · 네 창 · 양끝 포함 · 정규장 종가(ECOS 코드) · 소수 자리 · 판정 어휘와 말미 주의 문구를 붙이지 않는 이유, 그리고 「verify-lab 은 2026-09-15 정의를 조사 문서로 옮기며 알림 형식 결정을 뺐다 — 알림 형식의 정본은 이 절」. 「정본과 어긋난 상태」 문단 삭제 |
| §5.2 | 빈 보유 문장의 정본, **보유는 미국 상장 종목만(BL-1)** 한 줄 |
| §5.3 | 「달러 매수 기록」 행의 근거를 스냅샷 대신 「달러 보유가 0 이라 입력할 내역이 없다(2026-09-05 확정)」로 |
| §5.4 | 「한 모듈」→「`data/` 패키지」(MIS-14 — ST-2 로 사실이 됨) |
| §6.2 | 그림의 `.../workflow_dispatch` → `.../dispatches`(MIS-15), 「잡 개수 제한 없음(fair use)」 삭제(VOL-2), 「발급 설정은 COMMANDS.md」 → README(D4) |
| §6.4 | 화 ~ 토 이유의 정본. 잡 표는 README 설정 절 포인터로(D4 · VOL-1) |
| §7.2 | 「화 ~ 토 아침마다 오므로 즉시 티남」에 미국 휴장 다음 날 예외(MIS-21) |
| §7.3 | 역방향 시절 고장 경위를 한 문장 + research §7 포인터로, 「처음에는 거래일 여부로 셌고」를 현재형 근거로(HIS-1). 수동 · `dry_run` 실행도 센다는 한 줄(BL-3) |
| §7.4 | 「(§7.2)」→ research §2.4(MIS-12), 「조용히 깨지던 자리였습니다」 삭제(HIS-2). **추가** — 0 이하 가격에서 멈춤(GUARD-1) · 장 마감 전 실행에서 멈춤(GUARD-2) · 원달러 창 시작 결손에서 멈춤(GUARD-3) · 원달러에 날짜 가드를 두지 않는 이유와 평균 창 안 공백을 검증하지 않는 이유 · 200일 창 공백을 검증하지 않음(2026-09-09 확정, 최대 0.098%p — research §5.5) (PLAN-2) |
| §8 | 자동 재시도 행을 §7.4 포인터로(MIS-6), 옵션 만기일 행(MIS-20), pykrx 행을 한 줄 + `0e6b0f3` 판 research §4 포인터로(ST-8 — research §4 가 마지막으로 있는 판), YAML → TOML(MIS-7) |
| §9 | **겨울 첫 발송 2026-11-03(화) 관찰**을 「실측으로 확인해야 하는 것」에(MIS-3), 「해결된 것」 표 · 다른 저장소 할 일 · cron 메일 중복 삭제(HIS-2 · ST-6) |
| 확정 이력 | 표 삭제 (HIS-2) |

**작업 내용 — 그 밖의 문서**

| 문서 | 변경 |
| --- | --- |
| 루트 `CLAUDE.md` | reference 포인터 삭제(:6 · :56), 두 상태 표 · 시세 · 알림별 데이터를 DESIGN §5 포인터 한두 줄로, 기각 목록을 「DESIGN §5.3 · §7.4 · §8」 포인터로(MIS-5), verify-lab 행을 「원달러 지표 정의를 조사한 곳 — 알림 형식의 정본은 DESIGN §4.3」으로, SMA 문장 삭제, 「파일이 없거나 비어 있어도」 줄은 DESIGN §5.2 와 중복이라 삭제, 「§4.5 … §4 의 예시도」→ §4.3(MIS-17), 정렬 원칙 포인터 §4.3 |
| `README.md` | 화 ~ 토 이유 · 7시간 45분 · 64분을 DESIGN 포인터로(ST-6 · VOL-4), `reference/` 줄 삭제, **cron-job.org 설정 · PAT 발급 절 이동**(D4) |
| `docs/COMMANDS.md` | 설정 절을 README 로 옮기고 그 자리를 포인터로(D4), 「(마지막 Phase에서만)」 삭제(HIS-3), 「15회 연속」 · API 교체 경위 삭제(VOL-2 · HIS-3), 주간 수동 실행 안내를 한 줄 + DESIGN §7.3 |
| `docs/research/데이터소스_실측.md` | **지운 기능만의 측정 삭제**(ST-8) — §3.1 · §3.3 의 역방향 서술 · §4 전체 · §5.1 ~ §5.4 · §5.5 의 주간 요약 · §6.1 · §6.2 의 역방향 열 · §7 의 역방향 예시와 §7.4 · §8 전체. §3.2 달력 범위를 「실행 시점 기준 20년 전 ~ 1년 뒤」로(MIS-11), 죽은 참조 정리(MIS-18), 「값이 바뀌면 갱신」 · 「아직 모릅니다」 류 정리(HIS-6), 판 · run ID 를 「측정 당시」로(VOL-5), 스냅샷 포인터(§1.2 · §1.3 · §1.4)를 verify-lab 새 문서 §10.3 · §14.2 로, **DESIGN 의 근접도 실측 표를 새 절로 받음**(VOL-6) |
| `reference/` | **폴더 삭제**(ST-7) — `README.md` · `원달러_백분위_알림.md` |

**Validation**:

- [x] 끊긴 포인터 0건 — `git grep -n -E "§4\.5|4\.5 절|reference/|원달러_백분위_알림|역방향_매매_규칙" -- . ':!docs/plans' ':!docs/AUDIT_*'` 결과가 **허용 목록뿐**(DESIGN §8 의 역방향 · pykrx 행이 가리키는 git 판). 결과 전부를 진행 로그에 붙인다
- [x] DESIGN 목차 앵커와 절 제목 일치, `docs/research/` 의 절 번호를 가리키는 문서 포인터가 남은 절과 맞는다(`git grep -n "research" -- docs CLAUDE.md README.md src tests`)
- [x] 공백 없는 물결표 0건 — 이번에 쓴 문장에서 `화~토` 같은 표기가 취소선이 되지 않는다(코드 스팬 밖 `[^ ]~|~[^ ]` grep, 기존 문장은 일괄 치환하지 않는다)

---

### Phase 6 — 근거 승격 확인과 계획서 정리

**작업 내용**:

- [x] 계획서에만 있던 사실이 살아있는 문서에 있는지 확인 — 아래 표의 「옮길 곳」을 grep 으로 하나씩 대조

  | 사실 | 출처 | 옮길 곳 |
  | --- | --- | --- |
  | 호출자가 `dry_run` 을 `== true` 로 한 번 비교하는 이유 | PLAN_alerts_initial.md:691-695 | `_run_alert.yml` (Phase 4) |
  | 원달러에 날짜 가드를 두지 않는 이유 | PLAN_close_date_guard.md:51 · PLAN_weekly_window_precision.md:50 | DESIGN §7.4 (Phase 5) |
  | 원달러 평균 창 안의 공백을 검증하지 않는 이유 | PLAN_weekly_window_precision.md:51 | DESIGN §7.4 (Phase 5) |
  | 200일 창의 공백을 검증하지 않음(2026-09-09) | PLAN_close_date_guard.md:53 | DESIGN §7.4 (Phase 5) |
  | 보유는 미국 상장이라는 가정 | PLAN_close_date_guard.md:133 | DESIGN §5.2 + 로더 검증 (Phase 2 · 5) |
  | `read_config` 재파싱을 두는 이유 | PLAN_audit_priority_fixes.md:440 | **버린다** — 비용이 작고 되살릴 판단이 아니다 |

- [x] 끝난 계획서 11건 삭제 — `alerts_initial` · `yfinance_error_cause` · `remove_dead_validation` · `close_date_guard` · `weekly_window_precision` · `health_kst_window` · `rank_staleness_notice` · `audit_priority_fixes` · `buffer_zone_band_display` · `reverse_rank_cut` · `remove_reverse_rank`. `docs/plans/.gitkeep` 과 이 계획서는 남긴다

**Validation**:

- [x] `ls docs/plans` 가 `.gitkeep` 과 이 계획서뿐
- [x] 살아있는 문서가 지운 계획서를 가리키지 않는다 — `git grep -n "PLAN_" -- . ':!docs/plans'` 결과가 감사 문서뿐(마지막 Phase 에서 함께 지움)

---

### 마지막 Phase — 실제 조립 확인 · 감사 문서 삭제 · 최종 검증

**작업 내용**

> 🔴 **체크박스와 상태를 먼저 확정하고, `/commit` 은 맨 마지막에** — 이유는 `/impl-plan` 「5) Commit Messages」.

- [x] dry-run — `poetry run python -m notify buffer_zone --dry-run`. **목적: 바뀐 조립 경로(정규화한 인덱스 · 장 마감 가드 · 점검 줄)가 실제 시세로 같은 문구를 내는지 본다.** 외부 호출은 yfinance 일봉(버퍼존 티커 넷)뿐이다. 로컬은 `GITHUB_REPOSITORY` 가 없어 점검이 `이력 조회 실패` 인 것이 정상, 전날(KST)이 미국 휴장이면 출력이 비는 것이 정상이다. **KST 00:00 ~ 미국 마감(서머타임 05:00) 사이에 돌리면 GUARD-2 로 실패 문구가 나오는 것이 정상**이다 — 그때는 그 문구를 진행 로그에 적고, 마감 뒤에 한 번 더 돌린다
- [x] dry-run — `poetry run python -m notify usdkrw --dry-run`. **목적: `window_line` · 창 시작 검사 · 2/29 처리를 거친 주간 문구가 정상 조립되는지 본다.** 외부 호출은 ECOS 환율 조회 1회(인증키는 URL 경로에 들어가 로그에 남기지 않는다). 로컬에 인증키가 없으면 그 사실을 적고 단위 테스트로 갈음한다
- [x] 자동 포맷 적용 — `poetry run black .`
- [x] `docs/AUDIT_2026-09-26.md` · `docs/AUDIT_2026-10-07.md` 삭제 (사용자 요청 「완료 후 AUDIT 문서 전부 제거」 — 리뷰 · 품질 검증을 마친 뒤)
- [x] Validation 절에 `/code-review` 와 품질 검증 **실행 결과**를 적는다
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정
- [x] 🔴 **마지막에 `/commit` 을 실행하고 그 후보를 «이 계획서» 의 `#### Commit Messages` 절에 옮긴다** —
      대화에만 내면 그 절이 빈 채로 남는다. **커밋은 사용자가 한다 — 후보만 낸다**

**Validation**:

> 순서는 `/code-review` → 품질 검증이다. 고칠 것 · 회차 상한 · 수정분 검증은 `/impl-plan` 의 `review.md` 가 정한다.

- [x] `/code-review xhigh` **1회차** (발견 12건 — 버그 7 [무거움 2 · 가벼움 5] · 그 외 5 · 조치: 고칠 것(닿는 버그) 0 — 종료. 미조치 12건은 진행 로그 2026-10-08 23:14 에 거르는 기준과 함께)
- [x] 수정분 검증 (수정 0건 · 발견 0건 — 무거움 0 · 조치: 해당 없음 — 마지막 회차에 고친 것이 없음)
- [x] `poetry run python validate_project.py` (passed=149, failed=0, skipped=0 — Ruff 통과 · PyRight 통과)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

> **Done 직전에 `/commit` 을 실행해 이 절을 채운다. 그전에는 비워 둔다** — 추측으로 적은 줄은 그대로 나간다.

1. 알림 / 전수 분석 권장안 반영
2. 알림 / 조용히 틀리던 자리의 멈춤 조건 추가와 점검 로직 · 외부 조회 재배치
3. 알림 / 윤일 · 0 이하 가격 · 장 마감 전 실행 · 원달러 창 결손 · 보유 파일 오타에서의 멈춤 추가
4. 알림 / 한 사실 한 곳 원칙에 따른 docstring · 문서 중복 제거와 원달러 규칙의 설계서 이관
5. 알림 / 2026-10-07 전수 분석 반영 — 멈춤 조건 추가 · 점검 로직 health 집중 · 테스트 재편 · reference 와 끝난 계획서 · 감사 문서 삭제

## 7) 리스크(Risks)

- **변경 범위가 넓다** (소스 15 · 테스트 14 · 설정 6 · 문서 6 파일, 삭제 다수) → Phase 를 data → 판정 · 조립 → 테스트 → 설정 → 문서 순으로 나누고 Phase 마다 `pytest` 그린을 확인한다. 정상 문구는 정본 대조 테스트가 글자 단위로 지킨다
- **인덱스 정규화(ST-3)가 날짜를 하루 밀 수 있다** — tz 붙은 시각을 UTC 로 바꾼 뒤 날짜를 내면 뉴욕 자정 전후가 어긋난다 → **거래소 현지 시간대 그대로 `date` 를 낸다**(지금 `_index_date` 와 같은 결과). `test_yfinance_errors` 에 뉴욕 tz 프레임의 날짜가 그대로인지 테스트
- **새 가드가 정상을 실패로 볼 수 있다** — GUARD-2: 정시 실행은 마감 뒤라 해당 없음, 조기 마감일은 `session_close` 가 안다. GUARD-3: 조회를 가장 긴 창보다 1년 더 받아 첫 자료가 창 시작보다 약 1년 앞선다. GUARD-1: 조정 종가 · 환율은 0 이하가 될 수 없다. 티커 형식: 실제 티커 8개를 테스트로 통과시킨다(Context)
- **테스트를 지우며 정책이 빠질 수 있다** → 지우는 테스트마다 같은 계약을 고정하는 남는 테스트를 진행 로그에 짝지어 적는다(A-1 · A-2 · A-3)
- **문서를 대량으로 걷다 남길 근거를 잃을 수 있다** → Phase 6 의 대조 표, Phase 5 의 끊긴 포인터 grep. 지운 측정은 `0e6b0f3` 판에 남는다
- **스냅샷의 매수 규칙 · 비용 · 성적이 이 저장소 트리에서 사라진다** — 알림이 쓰지 않는 매매 규칙이고 verify-lab 이 「개인 운용 값」으로 뺀 부분이다 → git 이력(이 저장소 `0e6b0f3`, verify-lab `0746727`)에 남는다고 DESIGN §4.3 원달러 절에 적는다
- **`poetry lock` 이 무관한 패키지를 올릴 수 있다** → Poetry 2.4.1 은 `--regenerate` 없이 전면 재해석을 하지 않는다. diff 를 확인하고 freezegun 외 변화가 있으면 멈춘다
- **dry-run 은 외부 API 를 부른다** — 조회 한도가 있는 yfinance · ECOS 를 각 1회. 목적은 Phase 에 밝혔다. 발송은 하지 않는다

## 8) 메모(Notes)

- 근거: `docs/AUDIT_2026-10-07.md`(이 작업 끝에 삭제) — 항목 ID 와 재현 기록. 이 계획서는 그 문서 없이 읽히도록 Context 에 결정 · 재현 결과를 옮겼다
- 감사 문서가 그 이전 보고서 `docs/AUDIT_2026-09-26.md` 를 대체했다. 그 보고서의 열린 항목은 모두 이 계획서의 ID 로 이어진다

### 진행 로그 (KST)

- 2026-10-08 22:00: 계획서 작성 (Draft). 사용자 지시 「추천대로 진행」 · 「완료 후 AUDIT 문서 전부 제거」. 권장안이 없던 일곱 항목은 Context 「확인 필요」 표의 권장으로 썼다 — 승인 때 확인받는다
- 2026-10-08 22:00: 자체 검증 — 1회차(논리 · 누락) 5건: Phase 1 「그린」이 Phase 2 몫의 레드와 충돌 → 남는 레드 목록으로 판정, Phase 0 에 `test_ecos_errors.py` 생성 명시, CON-3 서술 구체화, pykrx 포인터 판 `e8968f2` → `0e6b0f3`, GUARD-3 에 걸리는 기존 시험 데이터 명시. 2회차(다른 로직 영향) 1건: DESIGN §6.2 의 COMMANDS 포인터. 3회차(남은 정리) 1건: 테스트 모듈 docstring 의 DESIGN 재서술. 4회차(DoD ↔ Phase 대조) 2건: Phase 번호 오기. 5회차(실행 시점) 1건: 자정 뒤 dry-run 은 GUARD-2 로 실패가 정상. 6 · 7 · 8회차(전역 파이썬 규칙 · 사용자 원칙 · 테스트 규칙) 개선 없음 — 종료
- 2026-10-08 22:22: 사용자 승인(「승인」) — 「확인 필요」 D1 ~ D7 모두 권장대로. Phase 0 착수. 실제 티커는 중복을 빼면 7개(`SPY` · `QQQ` · `GLD` · `TLT` · `SSO` · `QLD` · `BRK-B`)라 그 7개로 고정한다
- 2026-10-08 22:24: Phase 0 완료 — `12 failed, 136 passed`. 실패는 새 테스트 12건뿐이고 사유도 의도대로다: GUARD-2 1건(`AssertionError: 휴장일에는 시세를 받지 않는다` — 조회를 시도함), `DID NOT RAISE ValueError` 10건(GUARD-1 종가 · 환율, GUARD-3, GUARD-4 둘, GUARD-5 · BL-1 다섯), BUG-1 1건(`ValueError: day is out of range for month`). 실제 티커 7개 통과 테스트와 MIS-1 은 통과. 보유 한 줄을 넣은 scratchpad 사본에서도 같은 12건만 실패하고 `KeyError` 0건 — BUG-2 해소. GUARD-2 테스트가 빌려 쓴 `_forbid_fetch` 의 「휴장일에는」 문구는 Phase 3 에서 일반화한다
- 2026-10-08 22:29: Phase 1 완료 — `10 failed, 137 passed`. 실패는 판정 · 조립 몫의 레드 10건(GUARD-2 1 · GUARD-4 2 · GUARD-5 · BL-1 5 · BUG-1 1 · GUARD-3 1)뿐이고 GUARD-1 두 건은 그린. 총수가 148 → 147 인 것은 범위 밖 달력 테스트(`test_out_of_range_raises`)를 FB-1 과 함께 지웠기 때문이다(Phase 3 표의 항목을 당겨 함 — 범위 검사를 지우면 `match="갱신"` 이 깨져 그린을 유지할 수 없음). 그린 유지를 위해 당겨 고친 테스트: 시험 계열을 날짜 인덱스로(`test_close_date_guard` · `test_weekly_window` · `test_health_line`), 계수 함수 패치를 `github_runs.run_counter` 로, `fetch_usdkrw` 가짜의 시그니처, `test_health_line` 의 `no_positions` 삭제(conftest 가 대신). `cli.py` 는 import · 계수 함수 · ECOS 호출 · 설정 이름만 바꿨고 구조 정리는 Phase 2. `common_constants.py` 의 ECOS 코드 삭제로 빈 줄이 하나 겹친 것은 Phase 2 에서 정리
- 2026-10-08 22:35: Phase 2 완료 — `140 passed, 0 failed`. Phase 0 레드 12건 전부 그린. 잔존 참조 grep 의 결과 3건은 `weekly_health\(` 가 새 함수 `recent_weekly_health(` 에 부분 일치한 것으로 옛 심볼은 0건. 정본 대조 기대 문자열 무수정(`git diff` 에서 바뀐 것은 지운 테스트의 docstring 뿐). 그린 유지를 위해 Phase 3 표에서 당겨 한 것: `test_weekly_window.py` 해체(「지난주는 달력」 → `test_health_line.TestLastWeekIsIndependentOfTheRunDay` 가 공개 함수 `last_week_health` · `recent_weekly_health` 를 봄, `TestClosesThrough` → `test_close_date_guard.py` 로 합치며 없는 날 예외 둘 중 문구까지 보는 쪽만 남김), `TestHealthLineFlowsIntoAlerts` 삭제(종단 테스트 `test_block_ends_the_alert` 가 같은 두 줄을 봄), 지운 가드의 테스트 삭제(`render` 빈 근접도 · 보유 가격 누락 · `mean_deviation` 빈 창 · 지난주 시작 > 끝), `test_usdkrw_calc` 시험 계열을 2023-09-01 부터로 늘리고 창 시작 결손 테스트를 5년 창으로. 결정: `health` 의 발화 요일 상수를 `_US_ALERT_WEEKDAYS` → `_BUFFER_ZONE_WEEKDAYS` 로 이름을 바꿈(미국장 알림이 버퍼존 하나뿐). 실수 1건: 테스트 파일 삭제에 `git rm --cached` 를 섞어 권한 거부됨 — git 상태 변경은 사용자 몫이라 빼고 `rm` 만 했다
- 2026-10-08 22:39: Phase 3 완료 — `149 passed, 0 failed`, Ruff 통과(B023 1건 — 반복문 안 클로저를 헬퍼로 빼서 고침), PyRight `0 errors`(테스트 실행환경 블록을 지운 상태). 커버리지 85% → **96%** — `ecos_client.py` 33 → 98, `cli.py` 79 → 96, `telegram.py` 65 → 90. 추가한 테스트: ECOS 실패 경로 넷과 정상 경로 하나, 실행 이력 조회 실패 · `total_count` 누락, `run_counter` 설정 유무 둘, cli 보유 블록 조립, 거래소 현지 날짜 인덱스, 조기 마감 시각, 실패 알림용 조용한 발송, `window_line`. **지운 테스트와 그 계약을 지키는 남은 테스트**: `test_weekly_window` 의 월요일 결과 → 같은 클래스의 매일 테스트(offset 0) / 「가장 최근 월요일」 → `test_recent_weekly_points_to_this_weeks_monday`(월요일 분기는 DEAD-3 으로 사라짐) / 없는 날 예외 → `test_close_date_guard.test_message_names_the_ticker_and_both_days` · `TestHealthLineFlowsIntoAlerts` → `test_health_line.test_block_ends_the_alert` · `test_message_names_the_failed_ticker` → `test_one_failure_fails_the_whole_set`(같은 입력, `match` 를 옮김) · `test_matches_the_recorded_calculation` → `test_ratio_against_window_mean`(검산 단언을 합침) · `sma` 빈 계열 → `test_shorter_than_period_raises` · 달력 평일 · 주말(라이브러리 데이터) → 대응 없음, 노동절 테스트 유지 · 지운 가드의 테스트(빈 근접도 · 보유 가격 누락 · `mean_deviation` 빈 창 · 지난주 시작 > 끝 · 달력 범위) → 가드와 함께 소멸
- 2026-10-08 22:40: Phase 4 완료 — `pytest.ini`(마커 셋 · 템플릿 주석 삭제, `norecursedirs` 의 `reference` 삭제), `pyproject.toml`(`freezegun` · black · ruff 의 `reference` 제외 삭제), `pyrightconfig.json`(`exclude` 의 `reference` 삭제), `.gitignore`(state 주석 한 줄 + 포인터), 워크플로 셋(머리말 · 권한 주석을 DESIGN 포인터로, `python-version-file: .python-version`, `dry_run` 의 `== true` 이유를 `_run_alert.yml` 입력 옆에). `poetry lock`(Poetry 2.4.1, `--regenerate` 없음) — 잠금 파일 diff 는 freezegun 블록 삭제, 그 전이 의존성 `python-dateutil` · `six` 의 `groups` 에서 `dev` 가 빠진 것, `content-hash` 뿐이고 버전 변화 0. `poetry check --lock` 종료 코드 0(기존 `[tool.poetry]` 폐기 예정 경고만). YAML 세 파일 `ruby -ryaml` 로 파싱 통과. `poetry install` 은 돌리지 않았다 — 로컬 `.venv` 에 freezegun 이 남아 있고 무해하다
- 2026-10-08 22:54: Phase 5 완료 — DESIGN 을 표대로 다시 썼다(§4.5 → §4.3, 원달러 규칙 절 신설, §7.4 에 멈춤 조건 셋과 계획서에만 있던 결정 셋, §9 에 겨울 첫 발송, 확정 이력 삭제). research 는 지운 기능만의 측정을 걷고 **절 번호를 빈칸 없이 다시 매겼다** — §1 ECOS · §2 yfinance(옛 §5.5 → §2.5, 장중 일봉의 미확정 봉 관측을 거기에 한 줄로) · §3 달력(범위 서술 정정 · 캐시 · 경고) · §4 스케줄(cron-job.org 정시성 · 겨울 여유) · §5 GitHub API · §6 근접도 표시 범위(DESIGN 에서 옮김, 계획서 리뷰가 지적한 방법 서술 「데이터 시작일부터 재생하고 2016-01-04 이후 이벤트를 셈」을 반영). 다시 매긴 번호에 맞춰 DESIGN 포인터 여섯을 고쳤다. README 로 cron-job.org 잡 · PAT 발급 이동(D4), COMMANDS 는 그 자리를 머리말 한 줄로 두고 장 마감 전 수동 실행 안내 한 줄을 더함. 루트 `CLAUDE.md` 는 `writing-for-agents` 스킬과 `~/.claude/docs/하네스_동작.md` 를 연 뒤 다시 씀 — 두 상태 표 · 기각 목록 · SMA · 빈 보유 · reference 를 DESIGN 포인터로. `reference/` 삭제. 코드 · 테스트의 `§4.5` 포인터를 §4.3 으로 바꾸며 어긋난 조사 둘(「§4.3 다」 · 「§4.3 가」)을 고침. 검증: 끊긴 포인터 grep 결과는 허용 목록 둘뿐 — `docs/DESIGN.md:316`(`0e6b0f3` 의 `reference/` — 옮기지 않은 원달러 규칙의 git 판), `docs/DESIGN.md:636`(§8 역방향 행의 `e8968f2` 판 `reference/역방향_매매_규칙.md`). research 포인터 17건(DESIGN 11 · src 4 · tests 2)이 모두 새 절 번호와 맞고, `docs/DESIGN.md:638` 의 §4 는 옛 판 `0e6b0f3` 을 가리키는 pykrx 행이라 의도대로. 목차 앵커 9개 일치. 이번에 쓴 문서 다섯(DESIGN · README · COMMANDS · CLAUDE · research)의 코드 밖 공백 없는 물결표 0건
- 2026-10-08 22:56: Phase 6 완료 — 승격 대조 다섯 건 모두 확인: `_run_alert.yml:15`(`== true` 이유) · `docs/DESIGN.md:610`(원달러 날짜 가드 없음) · `:612-613`(창 안 공백 비검증, 200일 창 · 원달러 창 둘 다, 2026-09-09 확정) · `:374` + `positions.py:19`(미국 상장 한정). `read_config` 재파싱 근거는 버림. 끝난 계획서 11건 삭제 — `docs/plans/` 에는 `.gitkeep` 과 이 계획서만 남음. 살아있는 문서의 `PLAN_` 참조 0건(남은 참조는 마지막 Phase 에서 지울 `docs/AUDIT_2026-09-26.md` 뿐)
- 2026-10-08 23:14: 마지막 Phase. **dry-run** — `buffer_zone`(22:56, 판정 날짜 10-07 은 마감 뒤): 정본 형식대로 조립, 점검 줄은 로컬에 `GITHUB_REPOSITORY` 가 없어 「이력 조회 실패」 강조(정상), 종료 코드 0. `usdkrw`(22:57, `.env` 의 ECOS 키 채워짐 1 — 값은 보지 않음): 정상 조립, ECOS 가 `2015-10-08 ~ 2026-10-08` 2,702행을 돌려줘 10년 창 시작(2016-10-08)보다 첫 자료가 1년 앞섬 — 창 시작 검사가 여유 없이 통과함을 실데이터로 확인, 종료 코드 0. **black** 4개 파일 재포맷. **리뷰 1회차** 12건 — 닿는 버그 0 이라 종료. 워크플로의 `python-version-file` 지적은 운영 단절 위험부터 확인: setup-python 배포 목록(`actions/python-versions` 의 `versions-manifest.json`)에 `3.12.13` 이 리눅스 x64 22.04 · 24.04 · 26.04 로 있음 — 끊기지 않으므로 「그 외」(매 실행 내려받기 · 패치 자동 추종 안 함은 운영 선택). **품질 검증** `passed=149, failed=0, skipped=0`. **AUDIT 문서 둘 삭제**(사용자 요청), 남은 `AUDIT_` 참조 0건. 계획서 Validation 을 Bash 로 쓰다 이모지 차단 훅에 막힘(명령에 이모지와 코드 파일 이름이 함께 있었음, 실행되지 않음) — 마크다운 편집이라 Edit 도구로 다시 씀
- 2026-10-08 23:14: 미룬 지적 거르기 — 12건 모두 거름, 옮길 것 0건.
  - 기준 1(닿지 않는다): `health._measure_runs` 가 `ValueError` 만 잡아 계수 함수의 코드 버그는 본 알림을 실패시킴(가벼움 — 계수 함수 둘은 모든 조회 실패를 `ValueError` 로 내며, 다른 예외는 새 코드 실수가 있어야 생김. 코드 버그를 「이력 조회 실패」로 덮지 않는 것이 FB-2 의 의도) · 장 마감 「직후 몇 분」 안의 수동 실행이 공식 종가 확정 전 값을 받을 수 있음(무거운 모양 — 정시 실행은 마감 2시간 반 뒤라 해당 없고, 수동 재실행이 05:00 KST 직후 몇 분 안에 일어나야 함) · `mean_deviation` 이 빈 창에서 NaN(무거운 모양 — cli 는 늘 자료의 마지막 날을 창 끝으로 넘겨 창이 비지 않음, 새 호출이 있어야 함) · `position_weights` 의 가격 누락이 맨 `KeyError`(가벼움 — 조회 목록에 보유를 넣고 한 종목이라도 비면 전체 실패라 새 호출이 있어야 함) · `recent_weekly_health` 가 월요일에 그날을 가리킴(가벼움 — 월요일은 판정 날짜가 일요일이라 점검 줄 전에 끝남. 발화 요일 상수를 바꿔도 이 조기 종료는 달력이 정함)
  - 기준 2(막는 쪽으로만 틀린다): 0 이하 종가 · 환율 검사가 창 밖의 행까지 봄(가벼움 — 잘못된 값에서 멈출 뿐 틀린 값을 내지 않음. 오늘 실데이터 dry-run 둘 다 통과, 지금 산출물 0건) · 티커 정규식이 끝 · 겹 하이픈(`QLD-`)을 통과시킴(가벼움 — 그런 티커는 시세 조회에서 실패 알림으로 멈추고 문구만 덜 친절함. 지금 보유 파일 0줄)
  - 기준 3(그 외): `python-version-file` 의 패치 판 고정 · `window_line` 의 평균 두 번 계산 · 창 시작 검사의 「1년 앞섬」이 실측되지 않았다는 지적(이번 dry-run 과 research §1.5 의 11년치 조회로 확인됨) · `cli.py` 의 한 줄에 붙은 두 문자열 리터럴 · `calendar.py` docstring 의 범위 수치

---

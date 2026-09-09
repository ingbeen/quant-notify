# Implementation Plan: 판정이 읽는 종가의 날짜 검증

> 작성/운영 규칙(SoT): `/impl-plan` 스킬(`~/.claude/skills/impl-plan/SKILL.md`)을 반드시 참고하세요.  
> (이 템플릿을 수정하거나 새로운 양식의 계획서를 만들 때도 해당 스킬을 포인터로 두고 준수합니다.)

**상태**: ✅ Done

---

🚫 **이 영역은 삭제/수정 금지** 🚫

**상태 옵션**: 🟡 Draft / 🔄 In Progress / ✅ Done

**Done 처리 규칙**:

- ✅ Done 조건: DoD 모두 [x] + `skipped=0` + `failed=0`
- ⚠️ **스킵이 1개라도 존재하면 Done 처리 금지 + DoD 테스트 항목 체크 금지**
- 상세: `/impl-plan` 스킬의 "3) 스킵 및 완료 규칙" 참고
- 위 조건은 `~/.claude/hooks/plan_lint.py`가 저장 시 자동 검사합니다

---

**작성일**: 2026-09-09 09:30
**마지막 업데이트**: 2026-09-09 09:30
**관련 범위**: 데이터(`src/notify/data/`), 알림 진입점(`src/notify/cli.py`), 테스트
**관련 문서**: 루트 `CLAUDE.md`, `.claude/rules/python.md`, `docs/DESIGN.md`, `docs/research/데이터소스_실측.md`

---

## 0) 고정 규칙 (이 plan은 반드시 아래 규칙을 따른다)

> 🚫 **이 영역은 삭제/수정 금지** 🚫
> 이 섹션(0)은 지워지면 안 될 뿐만 아니라 **문구가 수정되면 안 됩니다.**
> 규칙의 상세 정의/예외는 반드시 `/impl-plan` 스킬을 따릅니다.

- 품질 검증 명령은 **마지막 Phase에서만 실행**한다. 실패하면 즉시 수정 후 재검증한다.
- Phase 0은 "레드(의도적 실패 테스트)" 허용, Phase 1부터는 **그린 유지**를 원칙으로 한다.
- 이미 생성된 plan은 **체크리스트 업데이트 외 수정 금지**한다.
- 스킵은 가능하면 **Phase 분해로 제거**한다.

---

## 1) 목표(Goal)

- [x] 목표 1: 일일 알림 셋(`buffer_zone` · `reverse_rank_us` · `reverse_rank_kr`)이 **판정에 직접 읽는 값(종가·장중 현재가)마다 그것이 의도한 거래일의 것인지** 확인하고, 아니면 `ValueError` 로 멈춘다
- [x] 목표 2: 멈춘 결과가 **텔레그램 실패 알림**으로 사용자에게 도달한다 (기존 `main()` 실패 경로 재사용 — 새 경로를 만들지 않는다)
- [x] 목표 3: 빈 종가가 `dropna()` 로 사라져 **하루 전 종가로 조용히 판정되는** 경로를 남기지 않는다

## 2) 비목표(Non-Goals)

- **`usdkrw` 알림에는 가드를 넣지 않는다.** 환율 기준일은 `as_of = series.index[-1]` 로 「받은 자료의 마지막 날」을 쓰고 **그 날짜를 화면에 표시**하므로, 낡으면 눈에 보인다. ECOS 는 정상적으로도 며칠 늦게 고시되어 가드를 걸면 정상 지연에도 실패한다
- **`usdkrw` 의 주간 역방향 창(지난주 월~금) 공백 검증**도 넣지 않는다 — 성격이 다른 「거래일 공백 검증」이다
- **200일 이동평균 창 전체의 거래일 공백 검증**을 넣지 않는다 (사용자 결정 2026-09-09). 창이 하루 밀릴 때 근접도 변화는 **최대 0.098%p** 로 실측됐고, `docs/DESIGN.md` §1 이 경계하는 공백 검증을 끌어들이지 않는다
- 자동 재시도 · 값 보간 · 부분 성공 — `docs/DESIGN.md` §7.4 · §8 의 기각 결정을 유지한다
- 알림 **문구 변경 없음.** 따라서 `docs/DESIGN.md` §4.5 의 예시는 손대지 않는다

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

**[실측] 2026-09-09 09:00~09:28 KST** — yfinance 가 `2026-09-08` 행을 주면서 **`Close` 만 `NaN`** 으로 보낸다. 4종목(SPY·QQQ·GLD·TLT) 모두 해당하고, KODEX 200(`069500.KS`)은 09-09 까지 정상이다. 미국 티커만의 현상이며 09:28 재조회에서도 지속됐다.

`_extract_close` ([yfinance_client.py:84](../../src/notify/data/yfinance_client.py#L84))가 `dropna()` 를 하므로 **그 행은 흔적 없이 사라진다.** 그리고 판정부는 남은 계열의 끝을 그대로 쓴다.

| 경로 | 지금 코드 | 빈 종가가 있을 때 |
| --- | --- | --- |
| `run_buffer_zone` ([cli.py:185](../../src/notify/cli.py#L185) · [194](../../src/notify/cli.py#L194)) | `closes[ticker].iloc[-1]` | 하루 전 종가로 근접도·비중을 낸다 |
| `_united_states_prices` ([cli.py:273-277](../../src/notify/cli.py#L273-L277)) | `closes.iloc[-2], closes.iloc[-1]` | 전일 종가와 당일 종가가 함께 밀린다 |
| `_korea_prices` ([cli.py:251](../../src/notify/cli.py#L251)) | `previous_close(closes, now.date())` | 「오늘 이전 마지막」을 고르므로 전일이 비면 그 전날을 쓴다 |

세 경우 모두 **예외도 로그도 없다.** 알림 형태로는 정상으로 보인다.

**오늘(09-09) 07:30 알림은 정상이었다.** 화면의 근접도에서 09-08 종가를 역산하면 SPY -0.55% · QQQ -0.09% · GLD -1.73% · TLT -0.01% 로 실제 장세와 맞고, 09-04 종가로는 재현되지 않는다(GLD 화면 -3.81% vs 09-04 기준 -2.09%, 차이 1.72%p — 창이 하루 밀려서 생길 수 있는 최대 변화 0.098%p 의 17배). 즉 **지금 코드가 오늘을 틀리게 낸 것이 아니라, 내일이 위험하다.**

**내일(09-10 07:30, target 09-09) 시나리오** — 09-08 이 비어 있는 채로 09-09 가 채워지면:

- `buffer_zone`: `iloc[-1]` = 09-09 로 **맞다**. SMA 창만 하루 밀린다 (영향 0.1%p 미만)
- `reverse_rank_us`: `iloc[-1]` = 09-09 로 맞지만 `iloc[-2]` 가 09-08 이 아닌 **09-04** 다. 전일 종가가 어긋나면 **신호 가격 전체가 어긋난다.** 조용히 틀린다

이것은 `docs/DESIGN.md` §7.4 의 「**보간하지 않습니다 — 값이 없으면 없다고 하고 멈춥니다**」와 「**침묵 알림의 실패도 실패 알림을 보냅니다**」에 이미 적힌 원칙이며, 지금 코드가 그 원칙을 지키지 못하는 자리다. ECOS 경로([ecos_client.py:142-143](../../src/notify/data/ecos_client.py#L142-L143))는 이미 `isna().any()` 로 멈추는데 yfinance 경로만 떨군다.

### 재사용 후보 검증 (전역 규칙 「기존 함수 재사용 전 검증」)

| 함수 | 프로덕션 직접 호출 | 테스트 호출 | 판정 |
| --- | --- | --- | --- |
| `previous_us_trading_day` ([calendar.py:94](../../src/notify/data/calendar.py#L94)) | **0건** | 4곳 | 이번 가드가 **첫 프로덕션 사용처**가 된다. `tests/test_trading_calendar.py:91` 이 이미 `previous_us_trading_day(2026-09-08) == 2026-09-04` 를 검증 중이라 동작은 고정돼 있다 |
| `previous_kr_trading_day` ([calendar.py:106](../../src/notify/data/calendar.py#L106)) | **0건** | 2곳 | 같음 |
| `previous_close` ([yfinance_client.py:145](../../src/notify/data/yfinance_client.py#L145)) | 1건 (cli.py:251) | 8곳 | 신규 선택자가 그 역할을 흡수하므로 **이 변경이 만드는 orphan** 이 된다. 전역 규칙에 따라 함께 정리한다 |
| `_index_date` ([yfinance_client.py:120](../../src/notify/data/yfinance_client.py#L120)) | 1건 (previous_close 내부) | — | 신규 선택자가 그대로 재사용한다 |

`previous_close` 를 남기고 그 안에 날짜 검증을 넣는 안은 택하지 않는다 — 「오늘 이전 마지막」과 「정확히 그 날짜」는 계약이 다르고, 이름이 뜻을 잃는다.

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- 루트 `CLAUDE.md` — 특히 「계획서 규약 — 이 프로젝트의 설정」 절
- `.claude/rules/python.md` — 명시적 검증 · 불가능 조건 처리 · 타입 힌트 · 로깅 정책
- `docs/DESIGN.md` — §1(계기), §4.5(알림 문구), §5.4(알림별 데이터), §7.2(층위별 감지), §7.4(예외처리 원칙), §8(채택하지 않은 안)
- `docs/research/데이터소스_실측.md` — 기존 실측 기록의 형식

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 `/impl-plan` 스킬)

- [x] 기능 요구사항 충족 — 일일 알림 셋이 판정에 읽는 모든 종가의 날짜를 검증하고, 어긋나면 실패 알림이 나간다
- [x] 회귀/신규 테스트 추가
- [x] `poetry run python validate_project.py` 통과 (failed=0, skipped=0; passed/failed/skipped 수 기록)
- [x] 자동 포맷 적용 완료 (마지막 Phase에서 실행)
- [x] 필요한 문서 업데이트(`docs/COMMANDS.md` / CLAUDE.md / plan 등 — 각각 변경 여부 명시)
- [x] 근거 승격 완료 — 이 계획서를 지금 삭제해도 잃을 정보가 없다
      (결정 근거·실측 수치를 루트 `CLAUDE.md` 의 프로젝트 설정 절이 정한 목적지로 이관.
      `/impl-plan` 스킬 "근거 승격" 참고)
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `src/notify/data/yfinance_client.py` — 신규 선택자 `close_on` 추가, `previous_close` 제거
- `src/notify/cli.py` — `run_buffer_zone` · `_united_states_prices` · `_korea_prices` 세 경로 교체, import 정리
- `tests/test_close_date_guard.py` — 신규
- `tests/test_intraday_price.py` · `tests/test_yfinance_errors.py` — `previous_close` 테스트를 `close_on` 기준으로 교체
- `docs/DESIGN.md` — §7.4 에 「받은 종가가 그 날짜의 것인지 확인한다」 원칙과 실측 근거 추가
- `docs/research/데이터소스_실측.md` — 2026-09-08 종가 NaN 실측 기록
- `docs/COMMANDS.md`: **변경 없음** (실행 명령어·CLI 옵션 변동 없음)

### 데이터/결과 영향

- **알림 문구 변경 없음.** 정상일 때 나가는 문구는 지금과 완전히 같다 → `docs/DESIGN.md` §4.5 예시 수정 불필요
- **동작이 바뀌는 경우는 하나뿐이다** — 지금은 조용히 낡은 값으로 발송되던 상황에서 이제 실패 알림이 나간다
- 실패 시 종료 코드 1 → GitHub Actions 실행이 빨간색으로 남는다 (의도된 결과, `docs/DESIGN.md` §7.2 표의 첫 줄)
- **가정**: `state/positions.toml` 의 보유 종목은 미국 상장이다 (현재 파일은 비어 있고 예시가 `QLD`). 한국 종목이 들어가면 target 거래일이 달라지므로 그때 재검토한다 — 지금은 만들지 않는다(YAGNI)

## 6) 단계별 계획(Phases)

### Phase 0 — 정책을 테스트로 먼저 고정(레드)

> 해당 사유: **에러 처리 정책 변경**(멈추는 조건이 새로 생긴다) + **판단 기준 변경 가능성**(전일 종가 선택 방식이 바뀐다).

**작업 내용**:

- [x] `tests/test_close_date_guard.py` 신설. `tests/test_yfinance_errors.py` 의 `_frame` · `_install` 관용(한 겹 컬럼 + 거래소 현지 tz, `yf.download` 동시 차단)을 따른다
- [x] `close_on` 계약 고정: 그 날짜 종가가 있으면 값을 돌려주고, 없으면 `ValueError` 에 **종목·요청 날짜·계열의 마지막 날짜**가 담긴다
- [x] 인덱스에 tz 가 붙은 경우와 순수 `date` 인 경우 모두 같게 동작함을 고정 (`_index_date` 재사용 확인)
- [x] `buffer_zone` 회귀: 09-08 종가가 빠진 계열 + target 09-08 → `ValueError`. 정상 계열 → 지금과 **같은 근접도**
- [x] `reverse_rank_us` 회귀: 09-08 이 빠지고 09-09 만 있는 계열 + target 09-09 → `ValueError` (전일 종가가 09-04 로 밀리는 것을 잡는다). 09-07 휴장 건너뛰기는 정상 통과해야 한다 — `previous_us_trading_day(2026-09-08) == 2026-09-04`
- [x] `reverse_rank_kr` 회귀: 전일(직전 한국 거래일) 종가가 없으면 `ValueError`. 장중 미확정 봉이 섞여 와도 그것을 전일 종가로 쓰지 않음을 고정 (`previous_close` 가 지키던 인바리언트를 승계)
- [x] `fetch_intraday_price` 회귀: 마지막 1분봉이 어제 것이면 `ValueError`, 오늘 것이면 통과
- [x] `usdkrw` 는 가드 대상이 아님을 고정하는 테스트를 **추가하지 않는다** (비목표를 테스트로 굳히지 않는다)

**Validation**: 새 테스트가 의도한 자리에서 실패하는지 확인 (레드)

---

### Phase 1 — 선택자 구현과 세 경로 교체(그린 유지)

**작업 내용**:

- [x] `yfinance_client.py` 에 `close_on(closes: pd.Series, day: date, ticker: str) -> float` 추가. `previous_close` 바로 옆에 두고 `_index_date` 를 재사용한다. docstring 에 **왜 멈추는지**(빈 종가가 `dropna()` 로 사라져 하루 전 값으로 판정된다)를 적는다
- [x] `_united_states_prices` 교체 — `prev = close_on(closes, previous_us_trading_day(target), TICKER_QQQ)`, `current = close_on(closes, target, TICKER_QQQ)`. 기존 `len(closes) < 2` 검사는 `close_on` 이 더 나은 메시지로 대체하므로 제거한다
- [x] `_korea_prices` 교체 — `close_on(closes, previous_kr_trading_day(now.date()), YF_TICKER_KODEX)`
- [x] `run_buffer_zone` 교체 — 종목별 `close_on(series, target, ticker)` 를 한 번 만들어 근접도(185행)와 보유 비중(194행) 양쪽에 같은 값을 쓴다
- [x] `fetch_intraday_price` 에 `today: date` 를 받아 **마지막 1분봉이 오늘 것인지** 확인한다. `reverse_rank_kr` 의 판정은 「전일 종가 대 현재가」이므로 현재가 쪽만 검증 없이 두면 형제 호출처가 깨진 채 남는다. 지금은 `period="1d"` 가 사실상 오늘로 묶어 주지만 그것을 검증하지는 않는다 (`docs/DESIGN.md` §7.4 「값이 없으면 없다고 하고 멈춥니다」)
- [x] `cli.py` import 정리 — `previous_close` 제거, `previous_us_trading_day` · `previous_kr_trading_day` 추가
- [x] Phase 0 테스트가 모두 그린인지 확인

**Validation**: Phase 0 테스트 그린 + 기존 테스트 무회귀 (해당 테스트 파일만 직접 실행)

---

### Phase 2 — orphan 정리(그린 유지)

**작업 내용**:

- [x] `previous_close` 제거 (이 변경이 만든 orphan — 프로덕션 호출 0건이 됨)
- [x] `tests/test_intraday_price.py` · `tests/test_yfinance_errors.py` 의 `previous_close` 테스트를 `close_on` 기준으로 옮긴다. **삭제가 아니라 이관이다** — 「장중 미확정 봉을 전일 종가로 쓰지 않는다」는 인바리언트는 계속 지켜져야 한다
- [x] `_index_date` 가 여전히 호출되는지 확인 (`close_on` 이 씀 — orphan 아님)

**Validation**: 전체 테스트 그린, `previous_close` 잔존 참조 0건 (`grep`)

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**

- [x] `docs/DESIGN.md` §7.4 에 원칙 추가 — 「**받은 종가가 그 날짜의 것인지 확인합니다**」 + 근거(2026-09-08 실측, `dropna()` 가 자취를 지운다는 점, 내일 시나리오)
- [x] `docs/research/데이터소스_실측.md` 에 실측 기록 — 4종목 09-08 `Close` NaN, KODEX 정상, 09:00/09:28 두 번 재현, 창 1일 밀림의 근접도 영향 0.098%p, 역산으로 확인한 09-08 실제 등락률
- [x] `docs/COMMANDS.md` — **변경 없음** (명시)
- [x] 루트 `CLAUDE.md` — 변경 없음 (명시)
- [x] 자동 포맷 적용: `poetry run black .`
- [x] 변경 기능 및 전체 플로우 최종 검증 — 세 알림 `--dry-run` 으로 문구가 이전과 같은지 확인 (미국 종가가 복구되지 않았다면 실패 알림 문구가 의도대로 나오는지 확인)
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=178, failed=0, skipped=0) — Ruff 통과 · PyRight 통과

#### Commit Messages (Final candidates) — 5개 중 1개 선택

> 기능명은 `데이터 /` 로 잡았다. 루트 `CLAUDE.md` 의 매핑 표에 `src/notify/cli.py` 가 없는데, 새 코드의 무게중심이 `src/notify/data/yfinance_client.py` 의 선택자이고 `cli.py` 변경은 그 호출부 교체이기 때문이다.

1. 데이터 / 판정이 읽는 종가가 그 날짜의 것인지 검증
2. 데이터 / 빈 종가가 조용히 하루 전 값으로 판정되던 경로 차단
3. 데이터 / 종가 날짜 가드 추가와 previous_close 이관
4. 데이터 / 일일 알림 셋에 종가 날짜 검증 추가 + 테스트 보강
5. 데이터 / yfinance 빈 종가를 실패로 다루도록 정책 변경

## 7) 리스크(Risks)

- **정상인데 실패로 판정할 위험**이 가장 크다. 미국 종가가 07:30 KST 시점에 아직 안 채워지는 날이 정기적으로 있다면 매일 실패 알림이 온다. → 오늘 07:30 실행은 09-08 종가를 정상적으로 받았으므로 그 시각에 데이터가 있는 것이 평시다. 이번 NaN 은 **채워졌다가 사라진** 사후 변형이다. 이 사실을 실측 문서에 남겨, 실패가 반복되면 「가드가 과하다」가 아니라 「업스트림이 불안정하다」로 읽히게 한다
- **휴장 판정과 가드가 겹쳐 이중으로 막을 위험** — `is_us_trading_day(target)` 이 먼저 걸러 휴장은 조용히 끝난다. 가드는 「거래일인데 종가가 없다」만 잡는다. Phase 0 에 09-07 휴장 통과 케이스를 넣어 고정한다
- **`previous_close` 제거가 인바리언트를 잃을 위험** — Phase 2 를 삭제가 아닌 이관으로 명시했다. 장중 미확정 봉 케이스를 `close_on` 기준으로 다시 고정한다
- **겨울(EST)에 여유가 1.5시간으로 줄어든다** — 서머타임(EDT)에는 미국 마감 16:00 ET = 05:00 KST 라 07:30 발송까지 2.5시간이지만, 겨울에는 06:00 KST 마감이라 **1.5시간**이다 (`docs/DESIGN.md` §8 의 「cron 을 더 앞당기기」 기각 사유와 같은 사실). yfinance 의 일봉 채움이 그보다 늦어지는 날이 있으면 **지금은 조용히 낡은 값으로 나가던 것이 매일 실패 알림으로 바뀐다.** 겨울 첫 주에 실제 발송을 지켜보고, 반복되면 발송 시각을 늦추는 쪽을 검토한다 (가드를 푸는 쪽이 아니다 — 낡은 값이 조용히 나가는 것이 더 나쁘다)
- **`exchange-calendars` 범위 밖 날짜** — `previous_us_trading_day` 는 범위를 벗어나면 `ValueError` 를 낸다. 실패 알림으로 드러나므로 추가 처리는 하지 않는다

## 8) 메모(Notes)

### 사용자 결정 (2026-09-09)

- 가드 범위: **일일 알림 셋만.** `usdkrw` 제외 — 다만 「원달러가 저번주 마지막 종가 기준인지」 확인 요청 → **확인 완료**: 09-07(월) 두 번의 실행 모두 ECOS 자료가 `2015-09-10 ~ 2026-09-04` 로 끝났다. 저번주 금요일 기준이 맞다. 코드가 「지난주 금요일」을 고른 것이 아니라 `as_of = series.index[-1]` 로 받은 자료의 마지막 날을 쓰고 그 날짜를 화면에 표시한다
- SMA 창: **판정이 읽는 종가만** 검증. 200일 창 공백 검증은 넣지 않는다

### 실측 원본 (근거 승격 대상)

- 2026-09-09 09:00·09:28 KST 재조회: `SPY/QQQ/GLD/TLT` 의 `2026-09-08` 행 존재, `Close` = `NaN`. `069500.KS` 는 09-07=110820 · 09-08=110335 · 09-09=110875 로 정상
- 09-04 종가 기준 근접도: SPY +8.50 / QQQ +9.47 / GLD -2.09 / TLT -2.81 (%)
- 09-09 07:30 알림 화면값: SPY +7.82 / QQQ +9.27 / GLD -3.81 / TLT -2.80 (%)
- SMA 창 1일 밀림 효과: SPY +0.0841 / QQQ +0.0980 / GLD +0.0414 / TLT -0.0206 (%p)
- 역산한 09-08 실제 등락률: SPY -0.55% / QQQ -0.09% / GLD -1.73% / TLT -0.01%
- 관련 Actions 실행: `34166888758`(09-08 07:30, 휴장 침묵) · `34286242544`(09-09 07:30, 신호 여유 밖) · `34064207064`·`34091183404`(usdkrw, ECOS ~09-04)

### 남긴 것 — 이 계획서 밖으로 이어지는 두 건

**① `run_usdkrw` 도 yfinance 로 종가를 받는다.** 이 계획서의 비목표 절은 usdkrw 제외 근거를
「ECOS 기준일을 화면에 표시하므로 낡으면 보인다」로 적었는데, 그것은 **환율 부분에만** 해당한다.
`run_usdkrw` 는 `fetch_closes([KODEX, QQQ])` 로 지난주 역방향 요약도 만들며(`cli.py:387`),
그 구간의 하루가 비면 `pct_change()` 가 **이틀치 등락률을 하루치로 이름 붙여** 낸다.
승인된 범위(일일 알림 셋) 밖이라 이번에 손대지 않았다. **별도 계획서로 다룰 사안이다.**

**② SMA 창은 여전히 계열 전체를 쓴다.** `run_buffer_zone` 은 종가를 `close_on(target)` 으로
집지만 이동평균은 `sma(closes[ticker])` 로 낸다. target 뒤에 더 최근 행이 붙어 오면 창이
그쪽으로 밀린다. **07:30 KST 는 미국장이 닫혀 있어 실제로 발생하지 않고**, 사용자가 창 검증을
비목표로 정했으므로 그대로 뒀다. 미국 장중 판정을 도입하면 그때 다시 본다.

### 진행 로그 (KST)

- 2026-09-09 09:30: 계획서 작성. 사용자 승인 대기
- 2026-09-09 09:36: 승인. `fetch_intraday_price` 검증도 포함하기로 확정 — 「현재날짜의 데이터가 없으면 실패」 원칙에 장중 현재가도 해당한다는 사용자 판단. Phase 0 착수
- 2026-09-09 11:25: **완료.** Ruff · PyRight · Pytest(178) 전부 통과. 라이브 dry-run 셋 확인 — `reverse_rank_us` 는 09-04·09-08 두 종가를 날짜로 집어 통과(휴장 09-07 건너뛰기 정상), `reverse_rank_kr` 은 전일 09-08 + 장중 마지막 봉 `2026-09-09 10:57`(약 20분 지연이나 날짜는 오늘)로 통과, `buffer_zone` 은 **오늘 아침 07:30 알림 화면값과 완전히 동일**한 문구를 냈다(SPY +7.82 · QQQ +9.27 · GLD -3.81 · TLT -2.80). 정상 경로의 출력이 바뀌지 않았다는 종단 확인이다
- 2026-09-09 10:47: **09-08 종가 NaN 이 복구됐다.** 10:40 조회까지 NaN, 10:47 조회에서 모든 조회 형태(`period` 1y·6mo·1mo·5d, `start/end`)가 값을 돌려준다. 즉 **약 1시간 40분 이상 지속된 일시적 결손**이었지 영구 결손이 아니다. 실제 09-08 종가는 SPY 765.96 · QQQ 718.36 · GLD 399.72 · TLT 82.20 이고, 이는 화면값에서 역산한 추정치(765.98 · 718.34 · 399.73 · 82.20)와 **소수 둘째 자리까지 일치**한다 — 오늘 07:30 알림이 09-08 종가로 계산됐다는 판정이 실측으로 확정됐다. 가드의 필요성은 그대로다(07:30 실행이 그 창 안에 걸렸다면 조용히 09-04 로 판정했을 것). 다만 「매일 거짓 실패」 리스크는 낮아졌다 — 결손은 상시가 아니라 간헐이다

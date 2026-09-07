# Implementation Plan: yfinance 조회 실패의 원인을 실패 알림에 담기

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

**작성일**: 2026-09-07 15:20
**마지막 업데이트**: 2026-09-07 15:28
**관련 범위**: `src/notify/data/yfinance_client.py`, `tests/`, `docs/`
**관련 문서**: 루트 `CLAUDE.md`, [docs/DESIGN.md](../DESIGN.md), `docs/research/데이터소스_실측.md`, `.claude/rules/python.md`

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

- [x] 목표 1: **조회 실패의 실제 원인이 실패 알림에 담긴다** — `YFRateLimitError` 인지 `YFPricesMissingError` 인지를 텔레그램만 보고 가른다
- [x] 목표 2: **원인을 삼키는 경로를 없앤다** — `yf.download` 는 종목별 예외를 삼키고 빈 프레임을 돌려준다. 예외를 그대로 올리는 호출로 바꾼다
- [x] 목표 3: **위 둘을 테스트로 고정한다** — 라이브러리 판이 바뀌어 다시 삼켜지면 테스트가 잡는다

## 2) 비목표(Non-Goals)

- **자동 재시도를 넣지 않는다** — [docs/DESIGN.md](../DESIGN.md) §7.4 의 「재시도하지 않습니다」를 유지한다.
  재시도가 429 를 뚫는다는 실측이 아직 없다. 이 계획서는 **재시도 여부를 판단할 근거를 쌓는 선행 작업**이다
- **429 빈도를 세거나 자동 대응하지 않는다** — 상태를 만들지 않는다는 축(루트 `CLAUDE.md`)에 어긋난다
- **1분봉 장중 지연 문제를 다루지 않는다** — 오늘 실측했으나(§8 메모) 판정 시각 조정은 별도 결정이다
- **`ensure_complete` 를 손대지 않는다** — `src/` 호출 0건인 데드 코드지만(§8 메모) 사전 존재분이라 언급만 한다
- **알림 문구 형식을 바꾸지 않는다** — §4.5 의 실패 알림 형식(`타입: 메시지`)은 그대로다. 메시지 **내용**만 길어진다
- **`scripts/probe_intraday.py` 를 바꾸지 않는다** — `yf.download` 를 쓰지만 실측용 스크립트이고
  알림 경로가 아니다. 두 경로가 같은 값을 준다고 §5 에서 확인했으므로 대조 근거도 그대로 유효하다

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

**2026-09-07 14:30 `reverse_rank_kr` 실행이 실패했다** (run `34087068444`).

- Actions 로그: `['069500.KS']: YFRateLimitError('Too Many Requests. Rate limited. Try after a while.')`
- 텔레그램 실패 알림: `ValueError: 시세를 받지 못했습니다: 069500.KS. 조회를 다시 실행하세요.`

**원인이 알림에서 사라졌다.** 경로는 이렇다.

1. `yf.download` 는 종목별로 `Ticker.history()` 를 부르고 **예외를 통째로 삼킨다.**
   빈 프레임을 넣고 실제 예외는 `shared._ERRORS` 에만 남긴다 (yfinance 0.2.66 `multi.py:289-293`)
2. 그래서 [yfinance_client.py:81-84](../../src/notify/data/yfinance_client.py#L81-L84) 의 `except` 는 **절대 걸리지 않는다.**
   실행은 항상 `frame.empty` 가지([:86-87](../../src/notify/data/yfinance_client.py#L86-L87))로 떨어진다
3. 그 가지의 문구에는 429 라는 사실이 없다

**결과**: 사용자는 「다시 돌리면 될 일」인지 「티커가 진짜 없어진 것」인지를 텔레그램만 보고 가를 수 없고,
GitHub Actions 로그를 열어야 안다. 장중 판정(12:00 · 14:30)은 시각이 의미 있어 그 몇 분이 회차를 가른다.

**이 실패는 §8 의 재시도 기각 사유에 해당하지 않는다.** 기각 사유는 「데이터 검증 실패는 재시도해도
**같은 자리에서 실패**한다」인데, 429 는 검증 실패가 아니고 실제로 같은 자리에서 실패하지 않았다 —
같은 시각 로컬에서는 같은 조회가 통과했다(243행 + 장중 354봉). 기각 사유의 전제가 실제보다 넓게 잡혀 있다.
**다만 재시도가 통한다는 근거도 없으므로 이 계획서는 재시도를 넣지 않는다.**

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- 루트 `CLAUDE.md` — 특히 「계획서 규약 — 이 프로젝트의 설정」 절
- 전역 `~/.claude/CLAUDE.md` — 수술적 변경 · 기존 함수 재사용 전 검증 · 코드 파일 이모지 금지
- `.claude/rules/python.md` — 타입 힌트 · Google 스타일 한글 docstring · 로깅 정책 · 불가능 조건 처리
- [docs/DESIGN.md](../DESIGN.md) — §4.5(문구 정본) · §7.2(실패 알림) · §7.4(예외처리 원칙) · §8(채택하지 않은 안)
- `docs/research/데이터소스_실측.md` — §2.2(응답 형태) · §5(장중 시세 소스)

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 `/impl-plan` 스킬)

- [x] 조회 실패 시 원인 예외의 **클래스명과 메시지**가 실패 알림 문구에 담긴다
- [x] 여러 종목 중 하나가 실패하면 **전체가 실패**한다 (§7.4 부분 성공 금지 유지)
- [x] 회귀/신규 테스트 추가 — 예외 전파 · 실패 종목 이름 · 조기 중단 · tz 인덱스 날짜 판정
- [x] `poetry run python validate_project.py` 통과 (failed=0, skipped=0; passed/failed/skipped 수 기록)
- [x] 자동 포맷 적용 완료 (마지막 Phase에서 실행)
- [x] 필요한 문서 업데이트 — `docs/COMMANDS.md` **변경 없음** / `docs/DESIGN.md` §7.4 갱신 / `docs/research/데이터소스_실측.md` §2.2 갱신
- [x] 근거 승격 완료 — 이 계획서를 지금 삭제해도 잃을 정보가 없다
      (2026-09-07 429 실측과 「원인을 담는 이유」를 살아있는 문서로 이관)
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `src/notify/data/yfinance_client.py` — `yf.download` → `yf.Ticker(...).history(..., raise_errors=True)`
- `tests/test_yfinance_errors.py` — **신규**. 예외 전파 정책을 고정
- `docs/DESIGN.md` — §7.4 에 「원인을 담는다」 원칙 한 줄 추가
- `docs/research/데이터소스_실측.md` — §2.2 응답 형태 갱신 + 429 실측 기록
- `docs/COMMANDS.md`: **변경 없음** — 실행 명령어도 CLI 옵션도 그대로다

### 데이터/결과 영향

**값은 바뀌지 않는다 — 실측했다** (2026-09-07 15:2x, `period="1y"`).

| 티커 | download 행 | history 행 | 종가 최대차 | SMA200 차이 |
| --- | ---: | ---: | ---: | ---: |
| QQQ | 252 | 252 | 0.0000610 | **0.0000043** |
| SPY | 252 | 252 | 0.0000000 | **0.0000000** |
| 069500.KS | 243 | 243 | 0.0156250 | **0.0002930** |

행 수가 모두 같으므로 **SMA200 계산이 깨지지 않는다.** 남는 차이는 `download` 가 concat 과정에서
float32 폭을 거치는 데서 오는 표현 차이이고, 크기가 float32 epsilon 과 맞는다(QQQ 656 에서 0.00006,
KODEX 92,961 에서 0.0078). **근접도는 소수 둘째 자리까지 낸다**(`데이터소스_실측.md` §2.1)—
차이는 그보다 다섯 자리 아래다. QQQ SMA200 은 양쪽 모두 **656.782** 로, §2.1 에 기록된 값과 일치한다.

장중 1분봉도 두 경로가 **같은 값을 준다** (2026-09-07 15:14:45, 양쪽 모두 354봉 · 마지막봉 14:53).

**바뀌는 것 둘.**

| | `yf.download` (현재) | `Ticker.history` (변경 후) |
| --- | --- | --- |
| 컬럼 | 두 겹 MultiIndex — `("Close", "QQQ")` | **한 겹** — `Close` |
| 인덱스 | tz 없음 (일봉은 `ignore_tz=True` 기본) | **tz 있음** — 거래소 현지 (`Asia/Seoul` · `America/New_York`) |

둘 다 위 대조 실행에서 직접 확인했다 — `download` 는 `tz=None`, `history` 는 미국 종목이 `America/New_York`,
KODEX 가 `Asia/Seoul` 이었다.

**인덱스 tz 변화가 판정을 바꾸지 않음을 확인했다.** 인덱스를 쓰는 곳은 셋뿐이고 모두 `.date()` 를 거친다.

| 위치 | 쓰는 방식 | 영향 |
| --- | --- | --- |
| [yfinance_client.previous_close](../../src/notify/data/yfinance_client.py#L129) | `_index_date(stamp) < today` | `2026-09-07 00:00+09:00`.date() = `2026-09-07`. 이전과 같다 |
| [cli._to_date_index](../../src/notify/cli.py#L403) | `stamp.date()` | 같다 |
| 나머지 (`iloc[-1]` · `iloc[-2]`) | 위치 기반 | 인덱스를 안 본다 |

**그래도 테스트로 고정한다.** 조용히 어긋나면 알림 형태로는 정상으로 보이는 종류의 변화다.

## 6) 단계별 계획(Phases)

### Phase 0 — 예외 전파 정책을 테스트로 먼저 고정(레드)

> 에러 처리 정책 변경이므로 Phase 0 을 둔다.

**작업 내용**:

- [x] `tests/test_yfinance_errors.py` 신규 작성. `notify.data.yfinance_client` 네임스페이스의 `yf.Ticker` 를 monkeypatch 한다
- [x] `test_fetch_closes_carries_the_cause` — `YFRateLimitError` 를 던지면 예외 메시지에 클래스명과 `Too Many Requests` 가 담긴다
- [x] `test_fetch_closes_names_the_failed_ticker` — 메시지에 실패한 티커가 담긴다
- [x] `test_fetch_closes_stops_at_first_failure` — 첫 종목이 실패하면 **뒤 종목을 조회하지 않는다** (호출 횟수로 확인)
- [x] `test_fetch_closes_empty_series_raises` — 예외는 없지만 종가가 빈 경우도 실패로 돌린다
- [x] `test_fetch_closes_returns_series_per_ticker` — 정상 경로. 한 겹 컬럼 프레임에서 `Close` 를 꺼낸다
- [x] `test_fetch_intraday_price_carries_the_cause` — 장중 경로도 같은 정책이다
- [x] `test_previous_close_reads_tz_aware_index` — `Asia/Seoul` tz 인덱스에서 전일 종가를 날짜로 올바로 고른다

---

### Phase 1 — `yfinance_client` 교체(그린 유지)

**작업 내용**:

- [x] `_history(ticker, period, interval)` 내부 헬퍼 추가 — `yf.Ticker(ticker).history(..., auto_adjust=True, raise_errors=True)` 를 부르고, 예외를 이 저장소의 문구로 감싸되 **원인을 그대로 담는다**
      - 문구: `f"[{ticker}] 시세 조회에 실패했습니다: {type(exc).__name__}: {exc}"`
      - **관용 이탈을 여기서 밝힌다** — 저장소의 기존 관용은 `{exc}` 만 담는다(`ecos_client.py:90` · `telegram.py:61`).
        여기만 `type(exc).__name__` 을 더하는 이유는 **429 를 이름으로 가리는 것이 이 변경의 목적**이기 때문이고,
        Actions 로그에서 grep 할 수 있는 고정 토큰이 하나 생긴다
      - `from None` 은 기존 관용대로 유지한다
- [x] `fetch_closes` 를 종목별 순차 루프로 바꾼다. **첫 실패에서 멈춘다**
      - 근거: 실제 실패는 429 이고, 그 상태에서 남은 종목을 부르면 **같은 실패를 더 만들 뿐**이다.
        §7.4 는 「하나가 실패하면 전체 실패」를 요구하지 실패 목록을 전부 모으라고 하지 않는다
      - 기존의 「빈 종목을 모아 한 번에 알린다」 동작은 이로써 사라진다. 메시지는 **실패한 그 종목**을 지목한다
- [x] `fetch_intraday_price` 를 같은 헬퍼 위로 옮긴다
- [x] `_extract_close` 에서 **MultiIndex 분기를 제거한다** — 이 변경으로 생긴 orphan 이다
- [x] `isinstance(frame, pd.DataFrame)` 가드의 거취를 PyRight 로 확인한다 — **제거했고 PyRight 통과**.
      그 가드는 `yf.download` 의 `Union[DataFrame, None]` 반환 때문이었고 `Ticker.history` 에는 필요 없다
- [x] `fetch_intraday_price` 의 debug 로그가 이제 KST 시각을 찍는다는 것을 확인한다 — **확인됨**.
      `마지막 2026-09-07 14:59:00+09:00` (이전에는 `05:59:00+00:00` 형태였다)
- [x] 모듈 docstring 갱신 — 「왜 `download` 가 아니라 `Ticker.history` 인가」를 적는다
- [x] Phase 0 테스트가 모두 통과하는지 확인 (`poetry run pytest tests/test_yfinance_errors.py`)

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**

- [x] `docs/research/데이터소스_실측.md` §2.2 「응답 형태」 갱신 — 컬럼이 **한 겹**임을 반영하고, MultiIndex 는 `download` 경로의 성질이었다고 남긴다
- [x] `docs/research/데이터소스_실측.md` 에 **2026-09-07 429 실측** 기록 — 러너에서 실패 · 같은 시각 로컬 통과 · yfinance 가 이미 쿠키 전략을 바꿔 1회 재시도한다는 사실(`data.py:420-432`)
- [x] [docs/DESIGN.md](../DESIGN.md) §7.4 에 원칙 한 줄 추가 — 「**재시도하지 않는 대신, 실패 알림은 재실행할 값어치가 있는 실패인지 말해야 한다**」
- [x] `docs/COMMANDS.md` — **변경 없음** 확인. 실행 명령어도 CLI 옵션도 그대로다
- [x] 실제 조회 경로 확인 — `reverse_rank_kr --dry-run` 정상(일봉 243행 + 장중 360봉). `buffer_zone` 은 09-06 미국 휴장이라 침묵했으므로 `fetch_closes` 4종목을 따로 불러 루프를 확인했다(1.59초)
- [x] 자동 포맷 적용 — `poetry run black .`
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=167, failed=0, skipped=0) — Ruff/PyRight/Pytest 모두 통과

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. `데이터 / yfinance 조회 실패의 원인을 실패 알림에 담기`
2. `데이터 / yf.download 가 삼키던 예외를 Ticker.history 로 전파 + 회귀 테스트`
3. `데이터 / 조회 실패 원인 표시 정책 반영 및 응답 형태 정리`
4. `데이터 / 종목별 순차 조회로 교체(값 동일) + MultiIndex 분기 제거`
5. `데이터 / 429 실측 기록과 예외 전파 구현 반영`

## 7) 리스크(Risks)

| 리스크 | 완화 |
| --- | --- |
| **인덱스가 tz-aware 로 바뀌어 날짜 비교가 조용히 어긋난다** | Phase 0 의 `test_previous_close_reads_tz_aware_index` 로 고정. §5 에 영향 분석 표를 남겼다 |
| **순차 조회로 응답 시간이 는다** | **실측 1.59초** (SPY·QQQ·GLD·TLT 순차. 병렬은 0.89초). 워크플로 제한 10분과 무관 |
| **실패 알림 문구가 길어져 모바일에서 접힌다** | 실패 알림은 원래 한 문단이고 정렬로 뜻을 나르지 않는다(§4.5). 접혀도 읽힌다 |
| **`raise_errors` 가 라이브러리 판에 따라 바뀐다** | 공개 파라미터이고 docstring 에 있다(`history.py:77`). Phase 0 테스트가 회귀를 잡는다 |
| **429 자체는 여전히 못 막는다** | 이 계획서의 목표가 아니다. 원인이 보이게 되는 것이 재시도 판단의 선행 조건이다 |

## 8) 메모(Notes)

### 실측 — 2026-09-07 429 실패

| 항목 | 값 |
| --- | --- |
| 실패 run | `34087068444` (`reverse_rank_kr`, 05:30 UTC = 14:30 KST) |
| 실패까지 | 스텝 시작 05:30:35 → 실패 05:30:40. **5초** |
| 실패 지점 | 첫 yfinance 호출 `fetch_closes`. `fetch_intraday_price` 까지 가지 못함 |
| 같은 시각 로컬 | **통과** — 243행 일봉 + 장중 354봉 |
| 빈도 | 실행 이력 14건 중 데이터 조회 실패 1건. **표본이 이틀치라 작다** |
| 09-06 `usdkrw` 실패 | 원인 다름 — `ECOS_API_KEY` 미설정. 현재 해결됨 |

**yfinance 는 이미 자체 재시도를 한다.** 429 를 받으면 쿠키 전략을 `basic` ↔ `csrf` 로 바꿔
크럼을 다시 받고 한 번 더 보낸다(`data.py:420-432`). 그래도 429 면 `YFRateLimitError` 를 낸다.
**즉시 재시도는 이미 해봤고 통하지 않았다** — 재시도를 넣는다면 지연 재시도여야 한다.

### 범위 밖 — 1분봉 장중 지연 (별도 결정 필요)

`docs/research/데이터소스_실측.md` §6 이 「평일 장중, 2026-09-07(월) 이후」로 미뤄둔 항목을
오늘 쟀다. **이 계획서에서 다루지 않는다.** 판정 시각 조정은 매매 규칙에 닿는 별도 결정이다.

| 조회 시각 | 마지막 봉 | 지연 | 봉 수 |
| --- | --- | --- | --- |
| 15:14:45 | 14:53 | **21.8분** | 354 |

`yf.download` 와 `Ticker.history` 가 **동일한 값**을 줬다. 즉 **14:30 판정은 사실상 14:08 가격을 본다.**

**아직 못 가린 것**: §5.2 의 「1분봉이 14:59 에서 끊긴다」가 이 지연으로 설명되는지다.
순수 지연이라면 마감(15:30) + 22분 = **15:52 이후 재조회하면 15:30 봉까지 나와야 한다.**
안 나오면 마지막 31분은 영구 누락이고, 그건 지연과 다른 문제다. **오늘 15:52 이후에만 가릴 수 있다.**

### 데드 코드 — `ensure_complete`

`src/notify/data/validation.py` 의 `ensure_complete` 는 **`src/` 에서 호출 0건**이다
(참조는 `tests/test_data_completeness.py` 9곳뿐). 시그니처가 `Mapping[str, float | None]` 이라
종가 **계열**을 다루는 `fetch_closes` 에는 애초에 맞지 않는다. **이 계획서는 손대지 않는다** —
사전에 존재하던 데드 코드는 사용자 요청 없이 삭제하지 않는다는 규칙에 따라 언급만 한다.

### 진행 로그 (KST)

- 2026-09-07 15:20: 계획서 작성. 승인 대기
- 2026-09-07 15:22: 승인. Phase 0 — 테스트 16개 작성, 11 failed / 5 passed 로 레드 확인 (네트워크 호출 없음)
- 2026-09-07 15:25: Phase 1 — `yfinance_client` 교체. 16개 전부 통과
- 2026-09-07 15:27: 문서 갱신 — `데이터소스_실측.md` §2.2·§2.3·§2.4·§5.4·§6, `DESIGN.md` §7.4
- 2026-09-07 15:28: 최종 검증 통과 (passed=167, failed=0, skipped=0). Done

---

# Implementation Plan: 전수 분석 우선순위 건 수정

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

**작성일**: 2026-09-11 18:02
**마지막 업데이트**: 2026-09-11 19:10
**관련 범위**: 발송(`notifier/`), 알림(`alerts/`), 데이터(`data/`), CLI, 스크립트, 의존성, 문서
**관련 문서**: 루트 `CLAUDE.md`, `docs/DESIGN.md`, `docs/research/데이터소스_실측.md`, `docs/COMMANDS.md`

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

- [x] 목표 1 — **텔레그램 봇 토큰이 로그·예외·트레이스백에 실리지 않는다.** 마스킹이 ECOS 인증키만 덮고 있던 것을 발송 토큰까지 넓힌다. **발송 실패가 예외로 올라가는 정책은 그대로 둔다**
- [x] 목표 2 — **주간 알림의 「지난주」가 실행 요일과 무관해진다.** 월요일이 아닌 날 수동으로 돌려도 직전 월~금을 낸다. 월요일 동작은 바뀌지 않는다
- [x] 목표 3 — **점검 줄의 분모가 조용히 0 이 되지 않는다.** 모르는 워크플로 이름은 내부 불변조건 위반으로 멈춘다
- [x] 목표 4 — **설정을 읽는 경로가 하나가 된다.** 과거에 워크플로 장애를 냈던 `load_api_key` 를 없애고 `ENV_FILE_PATH` 중복 정의를 걷는다
- [x] 목표 5 — **순위 파일의 날짜 오기입이 신호일에 숨지 않는다.** 일시적 데이터 공백과 사람이 고쳐야 하는 오기입을 **검증 자리로** 가른다 (값 검증은 로딩 시점)
- [x] 목표 6 — **`docs/DESIGN.md` 가 연 6~7회 바뀌는 값의 정본 행세를 하지 않는다.** 현재 값은 `state/reverse_rank.toml` 을 가리킨다
- [x] 목표 7 — **기각한 의존성이 실제로 사라진다.** 답을 이미 낸 프로브 스크립트 둘과 그것 때문에 남아 있던 pykrx 를 걷어, `docs/DESIGN.md` §8 의 「pykrx 를 쓰지 않는다」가 저장소 상태와 일치하게 한다

## 2) 비목표(Non-Goals)

아래는 **같은 전수 분석에서 나왔으나 이번 범위가 아니다.** 빠뜨린 것이 아니라 미룬 것이며, 필요하면 별도 계획서로 다룬다.

- **`window_slice` 의 윤일(2월 29일) 처리** · **한국 보유 종목이 한국 휴장일에 `buffer_zone` 을 깨뜨리는 문제** — 둘 다 잠복 상태이고 독립된 판단이 필요하다
- **`ecos_client.request_json` 의 도달 불가능한 `except ValueError`** · **`usdkrw._extreme_at` 의 인덱스 가드 불일치** — 동작에 영향이 없는 정리라 섞지 않는다
- **상수화·리팩토링 항목**(`"폭등"`/`"폭락"` 리터럴 중복 · KODEX 식별자 배치 · `window_slice` 이중 호출 등) — 동작이 바뀌지 않는 변경을 버그 수정과 같은 diff 에 넣지 않는다
- **`data_from` 이 정본보다 하루 늦은 것**(정본 `2002-10-14` vs 파일 `2002-10-15`) — **값을 건드리지 않고 남겨 둔다.** 판정에 쓰이지 않는 값이고, 확정하려면 verify-lab 을 봐야 한다. 무엇을 보면 되는지는 §8 메모에 적었다
- **`docs/DESIGN.md` §7.3 불릿이 「최근 주간」 줄을 빠뜨린 것** 등 나머지 문서 불일치 — 이번에 손대는 절만 고친다
- **완료된 계획서 7건 정리** — 이 계획서의 근거 승격과 함께 판단할 일이지만 별도 작업이다
- **알림 문구를 바꾸지 않는다.** 어느 항목도 사용자가 읽는 문자열을 바꾸지 않는다 (`docs/DESIGN.md` §4.5 불변)

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

저장소 전수 분석에서 나온 우선순위 건이다. **①~⑥ 은 모두 「에러 없이 조용히 틀리거나 새는」 부류**라 품질 검증(Ruff·PyRight·Pytest 236건 전부 통과)이 잡지 못한다. **⑦ 은 성격이 다르다** — 문서가 없앴다고 적은 의존성이 실제로는 남아 있는, 저장소와 설계서의 어긋남이다.

#### ① 텔레그램 봇 토큰이 마스킹을 빠져나간다 `[실측]`

`utils/logger.py` 의 `_KEY_IN_PATH` 는 `(?<=/)[A-Za-z0-9]{16,}(?=/|$)` 로 **영숫자만** 잡는다. 텔레그램 토큰은 `7123456789:AAF-...` 형태로 `:` 와 `-` 가 섞여 있어 경로 조각 전체가 이 패턴에 걸리지 않는다.

```
입력 : .../bot7123456789:AAF-abcdefGHIJKLmnopQRSTuvwx12345678/sendMessage
출력 : .../bot7123456789:AAF-abcdefGHIJKLmnopQRSTuvwx12345678/sendMessage   ← 그대로
비교 : ECOS 는 /api/StatisticSearch/***/json/... 으로 정상 마스킹된다
```

새는 경로가 둘이다.

| 경로 | 무엇 |
| --- | --- |
| `notifier/telegram.py:61` | `ValueError(f"텔레그램 발송에 실패했습니다: {exc}")` — `requests` 예외 문자열이 요청 주소를 담는다 |
| `notifier/telegram.py:83` | `logger.warning` — 마스킹 필터를 타지만 위 이유로 통과한다 |

`cli.py:644` 의 `telegram.send` 는 `try` 블록 밖이라, 발송이 실패하면 예외가 `sys.exit(main())` 까지 올라가 **스택 트레이스가 표준에러로 찍힌다.** 그 트레이스백의 마지막 줄이 위 메시지다.

> **그렇다고 `main()` 을 손대지 않는다.** `tests/test_cli_failure_path.py:119` 가 「발송이 실패하면 예외가 그대로 올라가 워크플로가 실패로 끝난다」를 **명시적으로 고정**해 두었고, 그것은 `docs/DESIGN.md` §7.2 의 「텔레그램이 죽으면 Actions 실패 메일이 맡는다」와 짝을 이룬다.
>
> **새는 것은 예외를 «올린다»는 사실이 아니라 그 «메시지»다.** 마스킹을 `telegram.send` 안으로 넣으면 트레이스백에서도 토큰이 사라진다 — 이미 `raise ... from None` 이라 원본 `requests` 예외가 연쇄로 노출되지 않기 때문이다 `[실측]`. **정책을 뒤집지 않고 고칠 수 있다.**

Actions 는 등록된 시크릿을 자동으로 `***` 처리하므로 실제 공개 로그에서는 가려질 공산이 크다. **그러나 로컬 dry-run·수동 실행에는 그 보호가 없고**, `docs/DESIGN.md` §3.4 는 마스킹을 GitHub 의 보호가 아니라 **이 저장소의 책임**으로 적어 두었다. 원칙이 ECOS 키에만 적용돼 있던 것이 문제다. `data/ecos_client.py` 가 이미 같은 방식을 쓴다(research §1.6: *"`requests` 예외를 그대로 올리지 않고 마스킹한 메시지로 바꿔 다시 냅니다"*) — **관용이 이미 있는데 한 모듈만 빠져 있었다.**

#### ② 주간 알림이 월요일에만 맞다 `[실측]`

`cli._last_monday` 를 **뜻이 다른 두 곳이 함께 쓴다.**

| 호출처 | 필요한 뜻 | 월요일에 | 화요일에 |
| --- | --- | --- | --- |
| `run_buffer_zone` → `_weekly_slot` | 가장 최근에 지나간 월요일 (주간 알림이 그날 돌았나) | 지난주 월 | **이번 주 월** |
| `run_usdkrw` → `week_start` | 지난주의 월요일 (그 주의 등락률을 낸다) | 지난주 월 | **지난주 월** |

**월요일에만 두 뜻이 겹쳐** 지금까지 드러나지 않았다. 화요일 이후에는 `run_usdkrw` 가 **이번 주** 월요일을 집고 `trading_week_end` 가 **미래 금요일**이 된다.

```
today 2026-09-08(화) → week_start 2026-09-07(월) · trading_week_end 2026-09-11(금)  ← 미래
→ _change_rates 가 미래 거래일 종가를 요구 → "[QQQ] 2026-09-11 종가를 받지 못했습니다"
→ weekly_health 도 미래 날짜를 분모에 넣어 🔴 0/5
```

`docs/DESIGN.md` §7.2 가 「cron-job.org 가 못 부름 → 수동 `Run workflow`」를 복구 경로로 명시했는데, **월요일에 놓친 것을 화요일에 눌러 복구하는 길이 이 함수에서 막혀 있다.**

#### ③ 점검 분모가 모르는 이름에 0 을 준다

`alerts/health.py:179` 의 `expected_runs` 는 모르는 워크플로에 `return 0` 한다. 분모가 0 이면 `actual < expected` 가 영원히 거짓이 되어 **`measure_runs` 의 🔴 강조가 통째로 꺼진다.** `docs/DESIGN.md` §7.3 이 *"덜 돌았을 때 강조하는 것이 핵심입니다"* 라고 적은 그 장치다.

워크플로 이름은 모듈 상수(`WORKFLOW_*`)로만 들어오므로 모르는 이름 = **코드 버그**다. 전역 `~/.claude/rules/python.md` 「불가능 조건 처리」가 `RuntimeError` 를 요구하는 자리다.

> **이것은 정책 변경이다.** `tests/test_health_line.py:290-292` 가 `expected_runs("nope.yml", FRIDAY) == 0` 을 「모르는 워크플로는 0 이다」라는 독스트링과 함께 **명시적으로 고정**해 두었다. 그래서 Phase 0(레드)에서 먼저 뒤집는다.

#### ④ 워크플로 장애를 냈던 함수가 프로덕션 모듈에 살아 있다

`tests/test_config_sources.py` 머리말이 사고를 기록한다.

> ECOS 인증키만 `.env` 를 직접 열고 있었고, 로컬에는 파일이 있어 **테스트도 dry-run 도 전부 통과했다.** Actions 에서만 드러났다.

당시 고친 방식은 `cli.py` 가 `_config` 로 가는 것이었는데, **원인이던 `data/ecos_client.load_api_key` 는 지우지 않았다.**

| 확인 | 값 |
| --- | --- |
| `load_api_key` 직접 호출 | **1건** — `scripts/probe_ecos.py:95` 뿐 |
| `ENV_FILE_PATH` 정의 | **2곳** — `cli.py:87` · `ecos_client.py:26` (같은 값) |
| `_config` 호출 | 6곳, 전부 `cli.py` 안 |

이름이 옳아 보이고 시그니처가 편해서, **쓰면 같은 장애가 재발한다.** 전역 `CLAUDE.md` 「기존 함수 재사용 전 검증 — Existence ≠ Endorsement」가 가리키는 함정 그대로다. 중복된 `ENV_FILE_PATH` 도 같은 사고의 구조적 잔재다 — 한쪽만 고치면 조용히 갈린다.

#### ⑤ `data_to` 미래 날짜 가드가 신호일에만 꺼진다

`alerts/reverse_rank.unreflected_window` 는 `data_to > last_confirmed` 면 `ValueError` 를 낸다. `docs/DESIGN.md` §5.2 가 그렇게 정했다 — *"사람이 손으로 적는 값이라 미래 날짜가 들어올 수 있고, 그것을 「검사할 날 없음」으로 처리하면 검사가 통째로 꺼진 채 알림은 정상으로 보입니다."*

그런데 `cli.py:422-428` 의 `except ValueError` 가 **신호가 있으면 그것까지 경고 로그로 넘긴다.**

| 실패 | 성격 | 지금 |
| --- | --- | --- |
| 창 안 종가 공백 | **일시적** — 다음 실행에 풀린다 | 넘기는 것이 옳다 (§5.2 의도) |
| `data_to` 오기입 | **영구적** — 사람이 파일을 고쳐야 한다 | 로그에만 남는다 |

두 실패가 같은 `ValueError` 로 뭉쳐 있다. **순위 파일이 깨진 사실을 가장 알아야 하는 날(신호일)에 숨는다.** 침묵하는 날에는 예외가 올라가 실패 알림이 나가므로 영원히 숨지는 않지만, 그 사이 신호일의 갱신 블록이 통째로 빠진다.

#### ⑥ 설계 정본이 연 6~7회 바뀌는 값을 들고 있다

`docs/DESIGN.md` §5.2 의 「참고 실측」 표가 순위 등락률 8개 값과 데이터 기간을 담는다. 같은 값의 정본은 `state/reverse_rank.toml` 이고 **연 6~7회 갱신**된다(정본 §1.5: KODEX 최근 5년 32회). 사용자가 verify-lab 에서 재계산해 TOML 만 커밋하면 DESIGN 은 조용히 낡는다.

표에 `(2026-08 기준)` 이 붙어 있어 완전한 오해는 막지만, **현재 값이 어디 있는지는 가리키지 않는다.** 전역 `CLAUDE.md` 「문서와 주석은 리팩토링을 견디게 쓴다 — 구체적 수치와 가변 정보를 직접 적지 않는다」에 걸린다.

다만 표에는 **다른 데 없는 정보**가 있다 — 1위 등락률이 나온 날짜(`2026-07-31`, `2001-01-03` 등)는 TOML 에도 정본 스냅샷에도 없다. **표를 지우면 그것을 잃는다.**

#### ⑦ 기각한 의존성이 실제로는 남아 있다

`docs/DESIGN.md` §8 이 pykrx 를 기각하며 이렇게 적었다.

> **가져오는 시점에 로그인하며 계정 아이디를 표준출력에 찍습니다** … yfinance 로 통일해 시크릿 두 개(`KRX_ID`·`KRX_PW`)와 그 문제를 함께 없앴습니다

그런데 `pyproject.toml` 의 **`[tool.poetry.dependencies]`**(dev 그룹이 아니다)에 `pykrx = "^1.0"` 이 그대로 있고, `scripts/probe_intraday.py` 가 여전히 `.env` 의 `KRX_*` 를 `os.environ` 으로 올린 뒤 pykrx 를 늦게 가져온다(`# noqa: E402` — 이 저장소의 유일한 `noqa`).

**두 프로브 모두 답을 이미 냈다.**

| 스크립트 | 답하려던 질문 | 지금 어디에 |
| --- | --- | --- |
| `probe_ecos.py` | 통계표·항목 코드 · 10년 응답 시간 | 코드는 `common_constants.py` 에 확정 · 응답 시간 0.76초는 §9 「해결된 것」 |
| `probe_intraday.py` | 장중 시세를 pykrx 와 yfinance 중 어디서 받나 | §9 「해결된 것」 — **`yfinance 069500.KS` 로 확정** |

§9 에 남은 미해결은 「장중 판정 시각을 조정할지」 하나인데, 그 근거인 **1분봉 지연 실측(research §5.4)은 `yf.download` 와 `Ticker.history` 를 직접 불러 잰 것**이라 pykrx 도 프로브도 필요하지 않다. 다시 재야 할 때도 마찬가지다.

**결과**: 워크플로의 `poetry install --without dev` 가 매 실행마다 쓰지 않는 pykrx 를 설치하고, **문서가 없앴다고 적은 것이 저장소에 남아 있다.**

### 확인된 사실 (조사 결과)

전부 이 저장소에서 실행해 확인했다.

| 확인 | 결과 |
| --- | --- |
| 품질 검증 기준선 | **passed=236 · failed=0 · skipped=0**, Ruff·PyRight 통과 |
| 텔레그램 토큰 마스킹 | **안 된다** (위 ①) |
| 제안 패턴 `(?<=/bot)[^/\s]+` | 두 예외 형태 모두 마스킹. **ECOS 4개 기존 케이스 전부 회귀 통과** |
| 그 패턴의 오염 | `/robots.txt` · `/robot/abc` · `경로 /bot 만 있음` **모두 그대로** (`(?<=/bot)` 이 직전 4글자를 요구) |
| `telegram.send` 안에서 메시지만 마스킹했을 때 | **트레이스백에서 토큰이 사라진다.** `from None` 이 원본 `requests` 예외 연쇄를 이미 막고 있어 프레임 수도 그대로다 |
| 발송 실패 정책을 고정한 테스트 | **1건** — `tests/test_cli_failure_path.py:119` 「예외가 그대로 올라간다」. **건드리지 않는다** |
| `_last_monday(2026-09-08 화)` | `2026-09-07` — 이번 주 월요일 |
| 제안 `last_week_monday = today - (weekday + 7)` | 월~토 어느 날에 돌려도 `2026-08-31`. **월요일 결과는 현행과 동일** |
| `expected_runs` 0 반환을 고정한 테스트 | **1건** — `tests/test_health_line.py:292` |
| `requests.exceptions.JSONDecodeError` MRO | `InvalidJSONError → RequestException → OSError → JSONDecodeError → ValueError` |
| `load_api_key` 호출처 | 정의부 제외 **1건** (`scripts/probe_ecos.py:95`) |
| `ecos_client` 에서 `load_api_key` 만 쓰는 것 | `Path` · `dotenv_values` · `PROJECT_ROOT` · `ENV_FILE_PATH` — 제거 시 함께 고아가 된다 |
| `src/` 의 `# type: ignore` | **0건** |
| `src/`·`tests/` 의 함수 내부 import | **0건** |
| `pykrx` 를 import 하는 파일 | **1건** — `scripts/probe_intraday.py:33` 뿐 |
| 저장소 전체의 `# noqa` | **1건** — 같은 줄 |
| `scripts/` 를 가리키는 비(非)계획서 문서 | **2건** — 루트 `CLAUDE.md:156` · `docs/research/데이터소스_실측.md:229` |
| `exchange_calendars` 달력 범위 | **XKRX·XNYS 모두 2006-09-11 ~ 2027-09-10** — `data_from` 의 2002·1999 를 **이 저장소에서는 셀 수 없다** |

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- 전역 `~/.claude/CLAUDE.md`
- 전역 `~/.claude/rules/python.md`
- 루트 `CLAUDE.md` — 특히 「계획서 규약 — 이 프로젝트의 설정」 절
- `docs/DESIGN.md` — 특히 §3.4(시크릿 취급) · §4.5(알림 문구 정본) · §5.2(두는 파일) · §7.2~§7.4(실패와 예외처리)
- `docs/research/데이터소스_실측.md` — 특히 §1.6(인증키 취급)
- `reference/역방향_매매_규칙.md` — 특히 §1.5

## 4) 완료 조건(Definition of Done)

- [x] 기능 요구사항 충족 (목표 1~7)
- [x] 회귀/신규 테스트 추가 — 특히 **「월요일 동작이 바뀌지 않는다」**, **「기존 ECOS 마스킹이 그대로다」** 두 회귀
- [x] 코드 리뷰 실행 및 결과 기록 (마지막 Phase 의 Validation 에 적는다)
- [x] 품질 검증 통과 (마지막 Phase 의 Validation 에 passed/failed/skipped 수를 적는다)
- [x] 자동 포맷 적용 완료 (마지막 Phase에서 실행)
- [x] 필요한 문서 업데이트 — `docs/DESIGN.md`(변경 있음) · `docs/research/데이터소스_실측.md`(변경 있음) · `docs/COMMANDS.md`(**변경 있음**) · 루트 `CLAUDE.md`(**변경 있음**)
- [x] **지운 파일을 가리키는 링크가 남지 않았다** — `scripts/` 참조 전수 재확인
- [x] 근거 승격 완료 — 이 계획서를 지금 삭제해도 잃을 정보가 없다
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

| 파일 | 무엇 | 목표 |
| --- | --- | --- |
| `src/notify/utils/logger.py` | 텔레그램 토큰 패턴 추가 | 1 |
| `src/notify/notifier/telegram.py` | 예외 메시지를 마스킹해 낸다 (`ecos_client` 와 같은 방식) | 1 |
| `src/notify/cli.py` | `_last_monday` 분리 · `_config` 제거 후 공용 함수 사용 · `RankDateError` 분기 | 2·4·5 |
| `src/notify/alerts/health.py` | `expected_runs` 가 모르는 워크플로에 `RuntimeError` | 3 |
| `src/notify/utils/config.py` | **신규** — 설정 읽기 한 경로 (`read_config`) | 4 |
| `src/notify/common_constants.py` | `ENV_FILE_PATH` 를 여기로 (경로 상수 자리) | 4 |
| `src/notify/data/ecos_client.py` | `load_api_key`·`ENV_FILE_PATH` 와 그로 인해 고아가 된 import 제거 | 4 |
| `src/notify/alerts/reverse_rank.py` | `RankDateError` 추가, `unreflected_window` 가 그것을 던진다 | 5 |
| `scripts/probe_ecos.py` | **삭제** — 답을 냈고, 남기면 4 의 단일 경로를 다시 갈라 놓는다 | 4·7 |
| `scripts/probe_intraday.py` | **삭제** — 답을 냈고, pykrx·늦은 import·`noqa` 의 유일한 근원이다 | 7 |
| `pyproject.toml` | `pykrx` 의존성 제거 | 7 |
| `poetry.lock` | `poetry lock` 으로 재생성 | 7 |
| `pyrightconfig.json` | `include` 와 `executionEnvironments` 에서 `scripts` 제거 | 7 |
| 루트 `CLAUDE.md` | 「스크립트 실행 규칙」 절에서 `scripts/` 와 `pykrx` 를 걷는다 | 7 |
| `tests/test_credential_masking.py` | 텔레그램 토큰 케이스 추가 + **발송 실패 예외에 토큰이 없다** | 1 |
| `tests/test_weekly_window.py` | 실행 요일과 무관한 「지난주」 | 2 |
| `tests/test_health_line.py` | 모르는 워크플로 기대값 교체 (`0` → `RuntimeError`) | 3 |
| `tests/test_config_sources.py` | 패치 대상 경로 조정 + `tmp_path: Path` 주석 정리 | 4 |
| `tests/test_rank_staleness_wiring.py` | 오기입은 신호일에도 멈춘다 | 5 |
| `docs/DESIGN.md` | §3.4 · §5.2 · §7.3 · §7.4 (아래 문서 절) | 1·3·5·6 |
| `docs/research/데이터소스_실측.md` | §1.6 에 「인증키를 읽는 경로는 하나다」 승격 · §4.1 의 `probe_intraday.py` 참조를 **지운 파일에 기대지 않는 서술로** 고침 | 4·7 |
| `docs/COMMANDS.md` | 수동 실행 절에 「주간 알림은 어느 요일에 돌려도 지난주를 낸다」 | 2 |

> **`tests/test_config_sources.py` 의 `# type: ignore[no-untyped-def]` 를 함께 없앤다.** 이번 변경으로 그 파일을 어차피 손대고, `tests/test_state_loading.py` 가 **이미 `tmp_path: Path` 관용을 12곳**에서 쓰고 있어 이쪽만 예외다. 게다가 `pyrightconfig.json` 이 tests 에 `reportMissingParameterType: none` 을 걸어 둬 **그 ignore 는 현재 아무 일도 하지 않는다.**

### 데이터/결과 영향

- **알림 문구는 한 글자도 바뀌지 않는다.** 여섯 건 모두 문구 밖의 층이다
- **월요일 `usdkrw` 결과는 현행과 비트 단위로 같다** — `last_week_monday(월요일)` 이 `_last_monday(월요일)` 과 같은 날을 준다 (실측 확인)
- **정상 경로의 `expected_runs` 값은 그대로다** — 상수 넷에 대한 반환값은 불변이고, 모르는 이름만 예외로 바뀐다
- `state/` 파일은 **읽지도 쓰지도 않게** 그대로 둔다
- **런타임 의존성이 하나 줄어든다** — 워크플로의 `poetry install --without dev` 가 pykrx 를 더 이상 설치하지 않는다. `src/` 는 pykrx 를 import 한 적이 없으므로 **알림 동작은 바뀌지 않는다**
- **`scripts/` 폴더가 사라진다.** `docs/plans/` 와 달리 이 폴더의 존재에 기대는 훅·설정이 없다 — `pytest.ini` 는 언급하지 않고, `pyrightconfig.json` 은 이번에 함께 고친다

## 6) 단계별 계획(Phases)

### Phase 0 — 정책과 인바리언트를 테스트로 먼저 고정(레드)

> 세 가지가 **정책 변경**이라 레드를 둔다 — ③ 은 기존 테스트가 반대 동작을 고정하고 있고, ① 과 ⑤ 는 「무엇을 숨기지 않을 것인가」를 새로 정한다.

**작업 내용**:

- [x] `tests/test_credential_masking.py` — 텔레그램 봇 토큰(`bot<id>:<secret>`)이 경로에서 가려진다. **기존 ECOS 케이스 4건이 그대로 통과하는지 함께 확인**하고, `/robots.txt` 처럼 `bot` 이 낱말 안에 든 문자열은 건드리지 않는다
- [x] `tests/test_credential_masking.py` — **`telegram.send` 가 올리는 예외 메시지에 토큰이 없다.** 마스킹이 로거가 아니라 **발송 모듈 안**에서 되어야 트레이스백까지 덮인다
- [x] `tests/test_weekly_window.py` — 「지난주」 구간이 **월·화·금·토 어느 날에 계산해도 같은 직전 월~금**이다. **월요일 값이 현행과 같다는 회귀**를 명시적으로 둔다
- [x] `tests/test_health_line.py` — `expected_runs` 가 모르는 워크플로에 `RuntimeError` 를 낸다. **기존 `== 0` 테스트를 교체**하고 독스트링도 새 정책으로 고친다
- [x] `tests/test_rank_staleness_wiring.py` — `data_to` 가 마지막 확정 종가일보다 뒤면 **신호가 있어도** 예외가 올라간다 (지금은 경고 로그로 삼켜진다)
- [x] `tests/test_config_sources.py` — ECOS 인증키가 **`.env` 없이 환경 변수만으로** 읽히는 기존 테스트가 새 경로에서도 성립한다

---

### Phase 1 — 발송 경로에서 토큰이 새지 않게 한다 (목표 1)

**작업 내용**:

- [x] `utils/logger.py` — 텔레그램 토큰 패턴을 추가한다. **경로 패턴보다 먼저 적용**한다(가린 뒤에는 `***` 가 섞여 영숫자 패턴에 걸리지 않는다). 「자격증명이 URL 에 들어가는 API 가 둘이고 형태가 다르다」는 것을 주석의 근거로 남긴다 — ECOS 는 영숫자 한 조각, 텔레그램은 `:` 와 `-` 가 섞인다
- [x] `notifier/telegram.py` — `send` 가 올리는 `ValueError` 메시지를 **마스킹해서** 만든다. `data/ecos_client.py` 가 쓰는 방식 그대로다
- [x] **`cli.main()` 을 건드리지 않는다.** 발송 실패가 예외로 올라가 워크플로를 실패시키는 것은 `docs/DESIGN.md` §7.2 의 설계이고 테스트가 고정하고 있다. 메시지가 이미 가려졌으므로 트레이스백도 안전하다
- [x] `send_without_raising` 의 경고는 **이미 가려진 메시지**를 받는다. 로거 필터가 2차 방어로 남는다

---

### Phase 2 — 주간 알림의 「지난주」를 실행 요일과 분리한다 (목표 2)

**작업 내용**:

- [x] `cli.py` — `_last_monday` 를 **뜻이 다른 두 함수로 가른다**
  - `_previous_monday(today)` — 가장 최근에 지나간 월요일. `_weekly_slot`(버퍼존 점검)이 쓴다. **현행 로직 그대로**
  - `_last_week_monday(today)` — 지난주의 월요일(`today - (weekday + 7)`). `run_usdkrw` 가 쓴다
- [x] 각 독스트링에 **그 호출처가 왜 그 뜻을 필요로 하는지**를 적는다. 지금 한 함수의 독스트링이 버퍼존 관점만 설명하고 있어, 주간 알림이 왜 같은 것을 쓰는지가 드러나지 않았다
- [x] `run_usdkrw` 의 `week_start` 를 새 함수로 바꾼다. `trading_week_end`·`weekly_health` 구간은 그 값에서 그대로 파생되므로 **추가 변경이 없다**

---

### Phase 3 — 점검 분모의 조용한 0 을 없앤다 (목표 3)

**작업 내용**:

- [x] `alerts/health.py` — `expected_runs` 가 모르는 워크플로에 `RuntimeError("내부 불변조건 위반: ...")` 를 낸다. 메시지에 **받은 이름**을 담는다
- [x] 독스트링의 `Returns` 에서 "모르는 워크플로면 0" 을 걷고 `Raises` 를 적는다
- [x] **`measure_runs` 의 `try` 범위를 넓히지 않는다.** 그 `try` 는 `count_runs`(이력 조회)만 감싸고 있고, 조회 실패와 코드 버그는 다르게 다뤄야 한다 — 조회 실패는 「이력 조회 실패」로 적고 본 알림을 살리지만, 모르는 워크플로 이름은 **알림을 멈춰 즉시 드러내야** 한다

---

### Phase 4 — 답을 낸 프로브와 기각한 의존성을 걷는다 (목표 7)

> **Phase 5 보다 먼저 한다.** `load_api_key` 의 유일한 호출처가 `scripts/probe_ecos.py` 이므로,
> 프로브를 먼저 걷으면 그 함수가 **호출 0건**이 되어 Phase 5 에서 그냥 지우면 된다.
> 순서를 뒤집으면 중간에 깨진 스크립트가 남는다.

**작업 내용**:

- [x] `scripts/probe_ecos.py` · `scripts/probe_intraday.py` 를 지우고 **`scripts/` 폴더를 없앤다**
  - 근거는 §3 ⑦ 의 표다. 둘 다 답을 냈고, 그 답은 `common_constants.py` 와 `docs/DESIGN.md` §9 · `docs/research/데이터소스_실측.md` 에 이미 살아 있다
  - **`.gitkeep` 을 남기지 않는다** — `docs/plans/` 와 달리 이 폴더의 존재에 기대는 훅이 없다
- [x] `pyproject.toml` — `pykrx` 를 의존성에서 지운다
- [x] `poetry lock` 으로 잠금 파일을 맞춘다. **Poetry 2.4.1 은 무관한 패키지를 함께 올리지 않는다** (`--regenerate` 를 쓰지 않는다)
- [x] `pyrightconfig.json` — `include` 와 `executionEnvironments` 에서 `scripts` 항목을 지운다
- [x] 루트 `CLAUDE.md` 「스크립트 실행 규칙」 — `scripts/` 와 `pykrx` 를 걷는다. **남은 규칙은 살린다**: `validate_project.py` 직접 실행 · 실제 발송은 사용자가 결정 · 외부 API(yfinance·ECOS) 호출 시 목적을 밝히고 URL 을 로그에 남기지 않는다
- [x] `docs/research/데이터소스_실측.md` §4.1 — `scripts/probe_intraday.py` 를 가리키는 문장을 **지운 파일에 기대지 않는 서술로** 고친다. 「pykrx 는 자격증명을 환경 변수에서만 읽는다」는 실측 사실 자체는 남긴다
- [x] `scripts/` 참조가 저장소에 남지 않았는지 전수 확인 (계획서 폴더 제외)

---

### Phase 5 — 설정을 읽는 경로를 하나로 모은다 (목표 4)

**작업 내용**:

- [x] `common_constants.py` — `ENV_FILE_PATH` 를 경로 상수 자리에 둔다 (`POSITIONS_PATH`·`REVERSE_RANK_PATH` 옆)
- [x] `utils/config.py` **신규** — `read_config(name, required=True)`. `cli._config` 의 동작을 그대로 옮긴다(환경 변수 먼저, 없으면 `.env`). `utils/logger.py` 와 같은 자리에 두는 이유는 **알림 도메인이 아니라 실행 환경을 다루기 때문**이다
- [x] `cli.py` — `_config` 와 `ENV_FILE_PATH` 정의를 지우고 `read_config` 를 쓴다 (호출 6곳)
- [x] `data/ecos_client.py` — `load_api_key` 와 `ENV_FILE_PATH` 를 지운다 (Phase 4 뒤에는 **호출 0건**이다). **그로 인해 고아가 되는 import 만** 함께 정리한다 (`Path` · `dotenv_values` · `PROJECT_ROOT`). `ENV_ECOS_API_KEY` 는 남긴다 — 환경 변수 **이름**이고 `cli` 가 쓴다
- [x] `tests/test_config_sources.py` — 패치 대상을 새 모듈로 바꾸고, `tmp_path: Path` 주석을 붙여 `# type: ignore` 를 없앤다

---

### Phase 6 — 순위 파일 오기입이 신호일에 숨지 않게 한다 (목표 5)

> ⚠️ **이 Phase 는 코드 리뷰 뒤 설계가 바뀌었다.** 원안(`RankDateError` 를 만들어 `cli` 에서
> 골라 다시 던지기)은 **정상 파일을 실패로 만드는 회귀**였다. 무엇이 왜 달라졌는지는 §8 의
> 「코드 리뷰 결과」에 있다. 아래는 **실제로 한 것**이다.

**작업 내용**:

- [x] `state/reverse_rank.py` — `_check_period` 를 두고 **파일을 읽는 자리에서** 검증한다.
      `data_to` 가 **KST 오늘**보다 뒤면, `data_from` 이 `data_to` 보다 뒤면 예외다
- [x] **「마지막 확정 종가일보다 뒤인가」로 재지 않는다.** 장중 판정은 그 값이 전일이라,
      마감 뒤 재계산해 오늘로 올린 **정상 파일**이 걸린다 (리뷰 finding 1)
- [x] `unreflected_window` 에서 그 예외를 걷고 **검사할 날이 없으면 `None`** 으로 돌린다.
      이 함수는 이제 「검사할 날이 있나」만 본다
- [x] `cli._run_reverse` — 특별 분기가 필요 없다. `_load_rank` 가 **`try` 밖**이라 값 오류는
      구조적으로 삼켜질 수 없다. 주석에 그 근거를 적는다
- [x] `RankDateError` 를 만들지 않는다 — 자리로 갈리므로 타입이 필요 없고, 다른 검증이 전부
      `ValueError` 를 쓰는 관용과도 어긋나지 않는다

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**

- [x] `docs/DESIGN.md` §3.4 — 마스킹 대상이 ECOS 인증키만이 아님을 적는다. **URL 에 자격증명이 들어가는 API 가 둘**이고 둘 다 가린다
- [x] `docs/DESIGN.md` §7.3 「예정 횟수는 요일로만 셉니다」 — 모르는 워크플로 이름은 멈춘다는 정책과 **그 근거**(분모 0 이면 강조가 꺼진다)를 적는다
- [x] `docs/DESIGN.md` §7.4 — 「검사 실패가 신호 알림을 삼키지 못하게 합니다」 문단에 **예외**를 적는다. 사람이 고쳐야 하는 오기입은 신호일에도 멈춘다
- [x] `docs/DESIGN.md` §5.2 「참고 실측」 표 — **현재 값의 정본이 `state/reverse_rank.toml` 임을 가리킨다.** 표는 남긴다(1위 발생일이 다른 곳에 없다). 「이 표는 스냅샷이고 파일이 현재다」가 드러나게 한다
- [x] `docs/DESIGN.md` §4.4 또는 §7.2 — 주간 알림의 「지난주」가 실행 요일과 무관하다는 사실과 **그 근거**(수동 복구가 다음 날 이후에 이뤄진다)를 적는다
- [x] `docs/research/데이터소스_실측.md` §1.6 — **「인증키를 읽는 경로는 하나다」와 그렇게 된 사고 근거**를 승격한다. 지금 그 근거는 `docs/plans/PLAN_alerts_initial.md` 에만 있어 계획서를 지우면 사라진다
- [x] `docs/COMMANDS.md` 「워크플로 수동 실행」 — 주간 알림을 다른 요일에 돌려도 지난주를 낸다는 한 줄
- [x] `docs/DESIGN.md` §8 pykrx 기각 행 — **기각이 저장소 상태와 일치하게 됐음**을 한 마디로 확정한다. 기각 근거(계정 아이디 표준출력 · 일봉 종가 동일)는 그대로 둔다
- [x] 자동 포맷 적용 — `poetry run black .`
- [x] 변경 기능 및 전체 플로우 최종 검증 — 알림 넷을 `--dry-run` 으로 돌려 **문구가 바뀌지 않았는지** 눈으로 대조한다 (실제 발송은 하지 않는다)
- [x] **pykrx 잔재 확인** — `poetry check` 로 `pyproject.toml`/`poetry.lock` 정합성을 보고, `src/`·`tests/` 에 pykrx import 가 0건임을 재확인한다
  - **`poetry install --without dev` 는 돌리지 않는다.** 로컬 `.venv` 에서 dev 의존성(pytest·pyright·ruff)을 걷어내 이어지는 품질 검증이 깨진다. 워크플로 재현이 필요하면 **사용자가 판단해 실행**한다 (전역 `CLAUDE.md` 「환경 설치는 사용자가 직접 한다」)
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

> 순서를 지킨다 — 리뷰에서 고치면 코드가 바뀌므로 품질 검증이 마지막 관문이어야 한다.

- [x] `/code-review xhigh` (발견 **11건** · 조치: **7건 수정 · 4건 미조치**, 상세는 §8)
- [x] `poetry run python validate_project.py` (passed=254, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 알림 / 조용히 새거나 꺼지던 자리를 막고 기각한 의존성 걷어내기
2. 알림 / 토큰 마스킹·주간 구간·점검 분모·설정 경로·순위 날짜 가드 수정
3. 발송 / 텔레그램 토큰 노출을 막고 실패가 트레이스백으로 새지 않게 하기
4. 알림 / 전수 분석 우선순위 건 수정과 회귀 테스트 보강
5. 알림 / 무증상 결함 수정 · pykrx 제거 · 설계 문서 동기화

## 7) 리스크(Risks)

| 리스크 | 완화 |
| --- | --- |
| **마스킹 패턴이 과하게 가린다** — `/bot` 뒤를 통째로 지우므로 엉뚱한 경로가 걸릴 수 있다 | `(?<=/bot)` 이 **직전 네 글자를 정확히 요구**해 `/robots.txt`·`/robot/abc` 는 안 걸리는 것을 실측했다. Phase 0 에 그 케이스를 테스트로 박는다 |
| **`_last_monday` 분리가 버퍼존 점검을 건드린다** | 버퍼존 쪽은 **함수 본문을 그대로 옮기기만** 한다. Phase 0 에 「월요일 값이 현행과 같다」 회귀를 둔다 |
| **`expected_runs` 예외가 알림 전체를 멈춘다** | 그것이 의도다 — 상수로만 들어오므로 정상 경로에서는 발생할 수 없고, 발생하면 코드 버그다. 다만 **`measure_runs` 의 조회 실패 처리와 섞이지 않게** `try` 범위를 넓히지 않는다 |
| **`utils/config.py` 신설이 과한 추상화** | 함수 하나·상수 참조 하나다. 대안(‎`cli` 의 private 함수를 스크립트가 가져다 쓰기)은 **진입점에서 헬퍼를 끌어오는 역방향 의존**이라 더 나쁘다 |
| **`RankDateError` 도입이 새 개념을 늘린다** | 저장소에 사용자 정의 예외가 아직 없다. 다만 전역 `python.md` 의 `ValueError`/`RuntimeError` 구분을 유지한 채(하위형) **삼킬지 말지만 가르는** 최소 형태다 |
| **일곱 건이 한 diff 에 섞여 리뷰가 어려워진다** | Phase 를 항목별로 끊어 각 Phase 가 독립적으로 읽히게 한다. 필요하면 사용자가 Phase 단위 커밋을 요청할 수 있다 |
| **문서만 고치고 코드가 뒤처지거나 반대가 된다** | 마지막 Phase 에서 알림 넷을 `--dry-run` 으로 돌려 문구 불변을 눈으로 확인한다 |
| **프로브를 지운 뒤 「그때 어떻게 쟀나」를 잃는다** | 측정 **결과와 방법**은 이미 `docs/research/데이터소스_실측.md` §1·§4·§5 에 남아 있다. 스크립트는 그 결과를 낸 도구이지 근거 자체가 아니다. **근거를 지우는 것이 아니라 도구를 지우는 것**이다 |
| **`poetry lock` 이 무관한 패키지를 함께 올린다** | Poetry 2.4.1 은 `poetry lock` 에서 전면 재해석을 하지 않는다(`--regenerate` 가 그 역할). 잠금 파일 diff 를 **눈으로 확인**하고, pykrx 와 그 전이 의존성 외의 변화가 있으면 멈춘다 |
| **`scripts/` 를 지워 하네스·설정이 깨진다** | 이 폴더를 가리키는 것은 `pyrightconfig.json` 과 루트 `CLAUDE.md` 둘뿐이고 **둘 다 같은 Phase 에서 고친다.** `pytest.ini` 는 언급하지 않고, 계획서 게이트 훅이 보는 것은 `docs/plans/` 다 |

## 8) 메모(Notes)

### 코드 리뷰 결과 (11건 · 7건 조치)

**조치한 것 — 내가 넣은 회귀 둘이 섞여 있었다.**

| # | 무엇 | 왜 고쳤나 |
| --- | --- | --- |
| 1 | **`data_to` 가드가 정상 파일을 실패로 만든다** | 장중 판정은 `last_confirmed` 가 **전일**이라, 마감 뒤 재계산해 오늘로 올린 파일이 걸린다 — 정본 §1.5 가 말하는 갱신 방식이 정확히 그 모양이다. **가드를 로딩 시점으로 옮기고 「KST 오늘보다 뒤인가」로 바꿨다.** 원안의 `RankDateError` 는 필요 없어져 지웠다 |
| 2 | **마스킹 패턴이 멀쩡한 경로를 지운다** | `(?<=/bot)[^/\s]+` 가 `.../repos/owner/bot-alerts/...` 를 `bot***` 로 만들고 `bot.py",` 의 따옴표까지 먹었다. **주소 모양 대신 토큰 모양**(`\d{6,}:[A-Za-z0-9_-]{30,}`)으로 바꿨다 |
| 3 | **접두사 없이 찍힌 토큰은 못 잡는다** | 같은 패턴 교체로 함께 닫혔다. `chat_id=... 7123456789:AAF-...` 가 이제 가려진다 |
| 4 | `health.py` 독스트링이 새 정책과 어긋난다 | 「조회가 실패해도 예외를 내보내지 않는다」가 그대로 남아 있었다. 다음 사람이 그 말을 믿고 `try` 를 넓히면 분모 0 구멍이 되살아난다 |
| 5 | 구간 검증이 주간 알림을 덮지 못한다 | 1의 조치로 함께 닫혔다. `data_from > data_to` 는 **아무 데서도 검사되지 않고 있었다** |
| 7 | `count_success_runs` 만 마스킹을 안 한다 | 지금 그 주소엔 자격증명이 없지만, **예외를 만드는 자리에서 가린다**는 관용이 이번에 저장소 규칙이 됐다. 셋 중 하나만 빠져 있으면 다음 사람이 의도인지 누락인지 가릴 수 없다 |
| 8 | 일요일이 테스트에 없다 | `_last_week_monday(일)` 은 13일을 되짚는다. 한국에서 일요일을 주의 시작으로 보는 관습 때문에 **가장 의심받을 경계인데** `range(6)` 이라 안 걸렸다. `range(7)` 로 넓히고 근거를 독스트링에 적었다 |
| 9 | 가드보다 `first_change_day` 가 먼저 평가된다 | 1의 조치로 함께 닫혔다 — 검증이 조회보다 앞선 자리로 갔다 |

**조치하지 않은 것 — 근거와 함께 남긴다.**

| # | 무엇 | 왜 두나 |
| --- | --- | --- |
| 6 | `read_config` 가 호출마다 `.env` 를 다시 판다 | 실행당 4~5회이고 그 실행은 **네트워크 조회로 초 단위**를 쓴다. 캐시를 두면 모듈 전역을 monkeypatch 하는 테스트와 얽히는 상태가 생긴다 — 얻는 것보다 비싸다. **동작은 이전과 같다**(옮겨 온 코드다) |
| 10 | 두 「월요일」 함수가 각자 요일 산술을 쓴다 | 공용 `_monday_of_week` 를 두자는 제안. 한 줄짜리 둘이고 **독스트링이 「월요일에는 두 뜻이 같다」를 명시**하며 테스트가 양쪽을 못 박았다. 헬퍼를 더하면 읽을 것이 하나 늘 뿐이다 |
| — | `main()` 의 `telegram.send` 를 `try` 로 감싸기 | **원안에서 이미 뺐다.** 정책을 고정한 테스트가 있고, 메시지 마스킹만으로 트레이스백이 안전해진다 |
| — | 나머지 전수 분석 항목 | §2 Non-Goals 그대로 |

### `data_from` 하루 차이 — 무엇을 보고 판단하나

**먼저 알아야 할 것: 이 값은 판정에 쓰이지 않는다.** `RankEntry.data_from` 은 파싱·검증되지만 **프로덕션 호출 0건**이다(`data_to` 만 낡음 판정에 쓰인다). 어느 쪽이 맞든 **알림은 한 글자도 달라지지 않는다.** 급한 결정이 아니다.

#### 숫자가 말하는 것

| | 정본 `reference/역방향_매매_규칙.md` | `state/reverse_rank.toml` + `docs/DESIGN.md` |
| --- | --- | --- |
| KODEX 200 | **2002-10-14** ~ 2026-08-26 · **5,891** | **2002-10-15** ~ 2026-08-26 · **5,890** |
| QQQ | **1999-03-10** ~ 2026-08-25 · **6,908** | **1999-03-11** ~ 2026-08-25 · **6,907** |

**시작일이 하루, 개수가 하나씩 어긋나고 `data_to` 는 같다.** 두 종목 모두 정확히 1이다.

정본 §1.5 는 20위 등락률을 **"판정일 이전까지의 «일간 등락률» 중 K번째"** 로 정의한다. 등락률 n개는 시세 n+1개에서 나오므로 `5,891 시세 → 5,890 등락률`, `6,908 시세 → 6,907 등락률` 이다. **어긋난 값이 정확히 이 관계다.**

> **가설**: 정본은 **시세 구간**을, 파일은 **줄 세우기에 실제로 들어간 등락률 구간**을 적었다.
> 그렇다면 둘 다 맞고 세는 대상이 다를 뿐이다. 다만 **그 사실이 어디에도 적혀 있지 않다.**

#### 확정하려면 이것을 본다 (위에서부터, 하나만 맞으면 끝)

1. **verify-lab 의 산출물** `storage/results/20260831_105540_reverse_trading/` — 정본 머리말이 「근거 산출물」로 지목한 폴더다. **줄 세우기에 들어간 행 수가 5,890 인지 5,891 인지** 본다. 5,890 이면 파일이 맞다(가설 성립)
2. **verify-lab 의 `studies/index_extreme/extreme_move.py`** — 정본 §1.5 가 지목한 산출 코드다. 등락률을 낸 뒤 **첫 행을 떨구는지**(`pct_change()` 뒤의 `dropna()` 또는 `[1:]`) 본다. 떨구면 가설 확정
3. 둘 다 볼 수 없으면 — **2002-10-14 와 1999-03-10 이 각 종목의 «첫 거래일»인지** 확인한다. 첫 거래일이면 그날은 견줄 전일 종가가 없어 **등락률이 존재할 수 없으므로** 파일 쪽(하루 뒤)이 등락률 첫날로 맞다

#### 이 저장소에서는 왜 확인할 수 없나

- `exchange_calendars` 달력이 **2006-09-11 ~ 2027-09-10** 뿐이라 2002·1999 의 거래일을 셀 수 없다 `[실측]`
- 이 저장소는 **전체 히스토리를 갖지 않는다** — `DEFAULT_PERIOD = "1y"` 이고, 그것이 `docs/DESIGN.md` §3.2 의 설계다

#### 어느 쪽으로 결론이 나든 할 일

| 결론 | 조치 |
| --- | --- |
| 가설이 맞다 (파일 = 등락률 구간) | **값은 그대로 두고** `state/reverse_rank.toml` 머리말에 「`data_from`·`data_to` 는 등락률 구간이다」 한 줄. 정본과 하루 차이 나는 이유가 그 줄로 닫힌다 |
| 가설이 틀리다 (단순 오기입) | `data_from` 두 줄을 정본 값으로 고친다. **판정은 여전히 바뀌지 않는다** |

### 진행 로그 (KST)

- 2026-09-11 18:02: 저장소 전수 분석 결과 중 우선순위 6건으로 계획서 작성. 착수 전 여섯 건의 전제를 전부 실행으로 확인했다 — 마스킹 미동작·`_last_monday` 화요일 값·제안 패턴의 회귀 무해성·`expected_runs` 0 을 고정한 테스트 위치·`load_api_key` 호출 1건
- 2026-09-11 19:10: **최종 검증 통과** — `/code-review xhigh` 11건 중 7건 조치(§8), `validate_project.py` passed=254 · failed=0 · skipped=0. 알림 넷을 `--dry-run` 으로 돌려 문구 불변을 확인했고, 금요일에 `usdkrw` 를 돌려 **지난주 08-31~09-04 가 정상 산출**되는 것을 실데이터로 확인했다(ECOS 만 대체). 리뷰가 **내가 넣은 회귀 둘**을 잡았다 — `data_to` 가드가 정상 파일을 실패로 만드는 것과 마스킹 패턴이 멀쩡한 경로를 지우는 것. **Phase 6 은 그 지적으로 설계가 바뀌었다**(§8 · Phase 6 머리말)
- 2026-09-11 18:40: **목표 1 의 해법을 줄였다.** 착수 직전 `tests/test_cli_failure_path.py:119` 가 「발송 실패는 예외가 그대로 올라간다」를 고정하고 있는 것을 발견했다. `main()` 을 `try` 로 감싸려던 원안은 **그 정책을 뒤집는 변경**이었다. 실측해 보니 `telegram.send` 안에서 **메시지만 마스킹하면 트레이스백에서도 토큰이 사라진다** — `raise ... from None` 이 원본 예외 연쇄를 이미 막고 있다. 정책을 건드리지 않고 고칠 수 있어 `cli.py` 변경과 테스트 수정을 범위에서 뺐다
- 2026-09-11 18:32: **승인 전 범위 조정.** 사용자가 「프로브 스크립트가 쓰이지 않으면 삭제」를 지시해 목표 7(pykrx·프로브 제거)을 Non-Goals 에서 끌어올렸다. 두 프로브가 답하려던 질문이 모두 닫혀 있음을 확인했고(§3 ⑦), 남은 미해결(장중 판정 시각)의 근거인 research §5.4 실측이 **pykrx 없이** 이뤄진 것도 확인했다. `load_api_key` 의 유일한 호출처가 `probe_ecos.py` 라 **프로브 제거를 설정 통합보다 앞(Phase 4)** 에 두어 호출 0건 상태에서 지우게 했다. `data_from` 은 값을 건드리지 않고 **판단 근거를 §8 에 정리**했다

---

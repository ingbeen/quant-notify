# Implementation Plan: 데드 코드 `ensure_complete` 제거

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

**작성일**: 2026-09-07 15:32
**마지막 업데이트**: 2026-09-07 16:02
**관련 범위**: `src/notify/data/validation.py`, `tests/test_data_completeness.py`
**관련 문서**: 루트 `CLAUDE.md`, [docs/DESIGN.md](../DESIGN.md), `.claude/rules/python.md`

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

- [x] 목표 1: **`ensure_complete` 와 그 테스트를 지운다** — 프로덕션 호출 0건인 데드 코드다
- [x] 목표 2: **그 함수가 지키던 정책은 그대로 지켜지는지 확인한다** — 「부분 성공을 만들지 않는다」는 코드가 아니라 **설계**다

## 2) 비목표(Non-Goals)

- **§7.4 「부분 성공을 만들지 않습니다」를 폐기하지 않는다** — 정책은 유지된다. 지우는 것은 그 정책을
  구현했다고 **주장만 하고 아무도 부르지 않던 함수**다
- **다른 데드 코드를 찾아 지우지 않는다** — 이번 요청은 이 하나다
- **`docs/DESIGN.md` 를 고치지 않는다** — 이 함수를 가리키는 문장이 없다 (전수 확인함)

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

`src/notify/data/validation.py` 의 `ensure_complete` 는 **`src/` 에서 호출이 0건**이다.
`PLAN_yfinance_error_cause` 작업 중 「기존 함수 재사용 전 검증」 절차로 발견했고, 그때는
사전 존재 데드 코드라 언급만 했다. **사용자가 제거를 지시했다.**

**전수 조사 결과** (2026-09-07):

| 대상 | 참조 |
| --- | --- |
| `src/` 프로덕션 | **0건** |
| `scripts/` | **0건** |
| `tests/test_data_completeness.py` | 9건 (이 함수만 테스트하는 전용 파일) |
| `src/notify/data/__init__.py` | 비어 있음 — 재수출하지 않는다 |
| `docs/DESIGN.md` · `reference/` · `CLAUDE.md` | **0건** |

`validation.py` 는 36줄이고 **`ensure_complete` 하나만 들어 있다.** 파일째 사라진다.

**왜 쓰이지 않았나**: 시그니처가 `Mapping[str, float | None]` 으로 **스칼라 가격**을 받는다.
실제 조회 계층(`fetch_closes`)이 다루는 것은 **종가 계열(`pd.Series`)** 이라 애초에 맞지 않았다.

### 지워도 정책이 남는가 — 이것이 유일한 실질 쟁점

`tests/test_data_completeness.py` 는 [docs/DESIGN.md](../DESIGN.md) §7.4 의
**「부분 성공을 만들지 않습니다」**를 고정하는 테스트다. 지우면 그 정책이 무방비가 되는가?

**아니다. 이미 살아있는 경로에서 고정돼 있다.** `tests/test_yfinance_errors.py` 의
`TestFetchClosesFailsWhole` 이 같은 정책을 **실제로 도는 코드**에 대해 검사한다.

| 정책 | 지워질 테스트 (죽은 함수 대상) | 남는 테스트 (살아있는 경로 대상) |
| --- | --- | --- |
| 하나 실패 = 전체 실패 | `test_one_failure_fails_the_whole_set` | `TestFetchClosesFailsWhole::test_one_failure_fails_the_whole_set` |
| 빈 값이면 실패 | `test_none_value_raises` · `test_no_interpolation` | `TestFetchClosesFailsWhole::test_empty_series_is_a_failure` |
| 실패한 종목을 지목 | `test_error_names_the_missing_ticker` | `TestFetchClosesCarriesTheCause::test_message_names_the_failed_ticker` |

**커버리지가 오히려 올라간다** — 아무도 부르지 않는 함수 대신 실제 알림이 타는 경로를 지킨다.

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- 루트 `CLAUDE.md` — 특히 「계획서 규약 — 이 프로젝트의 설정」 절
- 전역 `~/.claude/CLAUDE.md` — 수술적 변경 · 단순화하지 않을 것
- `.claude/rules/python.md` — 품질 검증 절차
- [docs/DESIGN.md](../DESIGN.md) §7.4 — 예외처리 원칙

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 `/impl-plan` 스킬)

- [x] `src/notify/data/validation.py` 삭제
- [x] `tests/test_data_completeness.py` 삭제
- [x] 남은 참조가 0건임을 재확인 — `src/`·`tests/`·`scripts/`·`docs/`(계획서 제외) 모두 0건
- [x] `poetry run python validate_project.py` 통과 (passed=159, failed=0, skipped=0)
- [x] 자동 포맷 적용 완료 (마지막 Phase에서 실행)
- [x] 필요한 문서 업데이트 — `docs/COMMANDS.md` **변경 없음** / `docs/DESIGN.md` **변경 없음**
- [x] 근거 승격 완료 — 이 계획서를 지금 삭제해도 잃을 정보가 없다
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `src/notify/data/validation.py` — **파일 삭제**
- `tests/test_data_completeness.py` — **파일 삭제**
- `docs/COMMANDS.md`: **변경 없음** — 실행 명령어와 무관하다

### 데이터/결과 영향

**없다.** 실행되지 않는 코드라 알림 문구도 판정도 바뀌지 않는다.
테스트 수가 줄어드는 것이 유일한 관측 가능한 변화다 — **실측 167 → 159 (8개 감소)**.
작성 시 「9개」로 적었던 것은 `grep` 적중 수(임포트 1 + 사용 8)를 테스트 수로 잘못 센 것이다.
실제 테스트 함수는 8개였다.

> `passed` 의 절대값은 기준선이 아니다 — 코드를 지우면 테스트도 주는 것이 정상이다
> (`docs/COMMANDS.md`). 판단은 `failed=0 skipped=0` 으로 한다.

## 6) 단계별 계획(Phases)

> Phase 0 을 두지 않는다. 인바리언트가 **바뀌지 않고**, 그 인바리언트를 지키는 테스트가
> 이미 `test_yfinance_errors.py` 에 있다 (§3 의 대응표). 새로 고정할 것이 없다.

### Phase 1 — 삭제(그린 유지)

**작업 내용**:

- [x] `src/notify/data/validation.py` 삭제
- [x] `tests/test_data_completeness.py` 삭제
- [x] `grep -rn "ensure_complete\|data.validation"` 로 남은 참조 0건 확인

---

### 마지막 Phase — 최종 검증

**작업 내용**

- [x] 문서 변경 필요 없음을 확인한다 (`docs/COMMANDS.md` · [docs/DESIGN.md](../DESIGN.md) 둘 다 이 함수를 가리키지 않는다)
- [x] 자동 포맷 적용 — `poetry run black .`
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=159, failed=0, skipped=0) — Ruff/PyRight/Pytest 모두 통과

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. `데이터 / 호출되지 않던 ensure_complete 와 전용 테스트 제거`
2. `데이터 / 데드 코드 validation 모듈 삭제 (정책은 조회 경로 테스트가 지킨다)`
3. `데이터 / 부분 성공 금지 검증을 살아있는 경로로 일원화`
4. `데이터 / 미사용 validation.py 정리`
5. `데이터 / ensure_complete 제거 + 참조 전수 확인`

## 7) 리스크(Risks)

| 리스크 | 완화 |
| --- | --- |
| **§7.4 정책의 테스트 근거가 사라진다** | 사라지지 않는다. §3 의 대응표대로 `TestFetchClosesFailsWhole` 이 **살아있는 경로**에서 같은 정책을 검사한다 |
| **나중에 스칼라 완전성 검사가 다시 필요해진다** | 그때 필요한 형태로 다시 쓴다. 지금 형태는 계열을 못 받아 **어차피 쓸 수 없었다** |
| **다른 곳에서 동적으로 참조한다** | 파이썬 동적 임포트를 쓰지 않는 저장소다. `grep` 전수 결과 0건이고 `__init__.py` 도 비어 있다 |

## 8) 메모(Notes)

- 발견 경로: `PLAN_yfinance_error_cause` 작업 중 「기존 함수 재사용 전 검증」 절차. 그 계획서는
  사전 존재 데드 코드라 **언급만** 하고 손대지 않았고, 사용자가 이번에 제거를 지시했다
- 남길 근거가 없다 — 「호출 0건이라 지웠다」는 사실은 삭제된 코드와 함께 무의미해진다.
  정책(§7.4)은 [docs/DESIGN.md](../DESIGN.md) 에 이미 있고 테스트가 지킨다

### 진행 로그 (KST)

- 2026-09-07 15:32: 계획서 작성. 승인 대기
- 2026-09-07 16:02: 승인. 두 파일 삭제 후 검증 통과 (passed=159 · failed=0 · skipped=0).
  테스트 감소는 8개로, 계획서의 「9개」 예상은 grep 적중 수를 잘못 센 것이었다. Done

---

# Implementation Plan: quant-notify 알림 셋 초기 구현

> 작성/운영 규칙(SoT): `/impl-plan` 스킬(`~/.claude/skills/impl-plan/SKILL.md`)을 반드시 참고하세요.  
> (이 템플릿을 수정하거나 새로운 양식의 계획서를 만들 때도 해당 스킬을 포인터로 두고 준수합니다.)

**상태**: 🟡 Draft

---

🚫 **이 영역은 삭제/수정 금지** 🚫

**상태 옵션**: 🟡 Draft / 🔄 In Progress / ✅ Done

**Done 처리 규칙**:

- ✅ Done 조건: DoD 모두 [x] + `skipped=0` + `failed=0`
- ⚠️ **스킵이 1개라도 존재하면 Done 처리 금지 + DoD 테스트 항목 체크 금지**
- 상세: `/impl-plan` 스킬의 "3) 스킵 및 완료 규칙" 참고
- 위 조건은 `~/.claude/hooks/plan_lint.py`가 저장 시 자동 검사합니다

---

**작성일**: 2026-09-05 18:32
**마지막 업데이트**: 2026-09-05 18:32
**관련 범위**: `src/notify/` 전체, `.github/workflows/`, `state/`, `tests/`
**관련 문서**: 루트 `CLAUDE.md`, [docs/DESIGN.md](../DESIGN.md), [reference/README.md](../../reference/README.md), `.claude/rules/python.md`

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

- [ ] 목표 1: **알림 4종을 구현한다** — `buffer_zone` · `reverse_rank_kr` · `reverse_rank_us` · `usdkrw`
- [ ] 목표 2: **사람이 쓰는 파일 2종을 로딩·검증한다** — `state/positions.yaml` · `state/reverse_rank.yaml`
- [ ] 목표 3: **cron-job.org 가 부를 워크플로 4개를 만든다** — `workflow_dispatch` 전용, `schedule` 없음
- [ ] 목표 4: **실패와 침묵을 구분 가능하게 한다** — 실패 알림 + `점검` 줄

## 2) 비목표(Non-Goals)

- **역방향 청산 추적** — 알림은 그날 신호 발생 여부만 낸다. 진입가·D+2·손절 판정을 하지 않는다
- **평균단가·손익** — 보유 알림은 보유량과 비중만 낸다
- **옵션 만기일 알림** — 규칙 문서 §1.5 의 「알림 없음」 결정을 유지한다
- **시세 CSV 저장** — 매 실행마다 받는다. 정본을 두지 않는다
- **`schedule` 백업 트리거** — 중복 발송을 부른다 ([docs/DESIGN.md](../DESIGN.md) §6.3)
- **cron-job.org 계정 설정** — 사용자가 웹 UI 에서 직접 한다. 이 계획서는 워크플로까지만 만든다
- **quant 저장소 정리** — 별도 계획서로 다룬다

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- 이 저장소는 **비어 있다.** 골격 파일과 문서만 있고 `src/notify/` 에 코드가 없다
- 전신인 quant `src/live/` 는 **누적 상태 때문에 거래일 하나를 영구히 잃었다.**
  cron 이 7시간 45분 밀려 처리 대상 날짜가 하루 건너뛰었고, 그 공백이 이후 실행을 전부 막았다
- 그래서 이 저장소는 **무상태로 다시 짓는다.** 실행이 하루 빠지거나 몇 시간 밀려도 다음 날 오면 그만이다
- **판정 규격은 이미 확정돼 있다** — `reference/` 의 매매 규칙 문서와 [docs/DESIGN.md](../DESIGN.md) 가
  무엇을 언제 어떤 문구로 알릴지까지 정해두었다. 이 계획서는 그것을 코드로 옮긴다

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- 루트 `CLAUDE.md` — 특히 「무상태」 절과 「계획서 규약 — 이 프로젝트의 설정」 절
- [docs/DESIGN.md](../DESIGN.md) — **설계 근거의 정본.** §4 알림 문구 예시, §5 저장 정책, §7 실패 처리
- [reference/README.md](../../reference/README.md) 와 그 폴더의 매매 규칙 두 건 — 판정 규격
- `.claude/rules/python.md` — 구현 원칙·코딩 표준·로깅 정책
- `~/.claude/CLAUDE.md` — 전역 규칙

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 `/impl-plan` 스킬)

- [ ] 알림 4종이 **dry-run 으로 [docs/DESIGN.md](../DESIGN.md) §4 의 문구와 일치하는 출력**을 낸다
- [ ] `state/` 파일 2종의 로딩·스키마 검증이 동작하고, 파일이 없어도 알림이 발송된다
- [ ] 워크플로 4개가 `workflow_dispatch` 로 실행되고 실패 시 실패 알림이 나간다
- [ ] 회귀/신규 테스트 추가
- [ ] `poetry run python validate_project.py` 통과 (failed=0, skipped=0; passed/failed/skipped 수 기록)
- [ ] 자동 포맷 적용 완료 (마지막 Phase에서 실행)
- [ ] 필요한 문서 업데이트(`docs/COMMANDS.md` / `docs/DESIGN.md` — 각각 변경 여부 명시)
- [ ] 근거 승격 완료 — 이 계획서를 지금 삭제해도 잃을 정보가 없다
      (데이터 소스 실측 결과 → `docs/research/`, 설계 변경 → [docs/DESIGN.md](../DESIGN.md))
- [ ] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

**신규**

- `src/notify/common_constants.py` — 티커·경로·컬럼명·타임존
- `src/notify/utils/logger.py`
- `src/notify/data/` — `yfinance_client.py` · `pykrx_client.py` · `ecos_client.py` · `calendar.py`
- `src/notify/state/` — `positions.py` · `reverse_rank.py`
- `src/notify/alerts/` — `buffer_zone.py` · `reverse_rank.py` · `usdkrw.py` · `health.py`(점검 줄)
- `src/notify/notifier/telegram.py`
- `src/notify/__main__.py` · `cli.py` — 알림별 서브커맨드 + `--dry-run`
- `.github/workflows/` — `buffer_zone.yml` · `reverse_rank_kr.yml` · `reverse_rank_us.yml` · `usdkrw.yml`
- `state/positions.yaml` · `state/reverse_rank.yaml` — 초기값과 스키마 주석
- `tests/` — 위 모듈별 테스트, `conftest.py`
- `scripts/probe_intraday.py` — 장중 시세 소스 실측용
- `docs/research/데이터소스_실측.md` — 실측 결과

**수정**

- `docs/COMMANDS.md`: **변경 있음** — 「알림 실행」 절에 dry-run·발송 명령을 채운다
- `docs/DESIGN.md`: **변경 있음** — §9 미해결 사항의 실측 항목을 결과로 대체한다

### 데이터/결과 영향

- **외부 API 를 호출한다** — yfinance · pykrx · ECOS. 조회 한도와 응답 시간을 실측해 기록한다
- **텔레그램으로 실제 발송이 일어난다** — 개발 중에는 `--dry-run` 으로 표준출력만 확인하고,
  실제 발송은 사용자가 확인한 뒤 한다
- **기존 결과 비교 불필요** — 이 저장소에 이전 산출물이 없다

## 6) 단계별 계획(Phases)

### Phase 0 — 판정 인바리언트를 테스트로 먼저 고정(레드)

> 판정 산식이 틀리면 **알림이 조용히 거짓말을 한다.** 틀린 값도 알림 형태로는 정상으로 보이므로
> 사람이 알아차릴 수 없다. 그래서 산식을 먼저 테스트로 고정한다.

**작업 내용**:

- [ ] 신호 가격 산식 고정 — `전일 종가 × (1 ± 순위 등락률)`, **부등호 방향이 폭등·폭락에서 반대**임을 검증
- [ ] **방향별 독립 순위** 고정 — 폭등·폭락 순위를 절대값으로 합치지 않음을 검증
      (합치면 신호가 절반이 되고 한쪽 방향이 구조적으로 묻힌다)
- [ ] 근접 판정 고정 — 여유 **1%p**, 도달(동률 포함)과 근접의 경계값 테스트
- [ ] 백분위 정의 고정 — `(과거 종가 < 현재 종가).mean() × 100`, 1·3·5·10년 창
- [ ] MA 근접도 고정 — `(종가 − SMA200) / SMA200`, 워밍업 구간(200일 미만) 처리
- [ ] **부분 성공 금지** 고정 — 티커 하나가 실패하면 전체가 실패함을 검증
- [ ] **침묵 조건** 고정 — 신호가 여유 밖이면 발송하지 않음을 검증
- [ ] `state/` 파일 스키마 검증 — 잘못된 값에서 예외가 나고, 파일 부재는 예외가 아님을 검증

---

### Phase 1 — 기반 계층과 데이터 소스 실측(그린 유지)

**작업 내용**:

- [ ] `common_constants.py` — 티커·MA 기간·여유 폭·타임존·경로. 매직넘버를 코드에 흩지 않는다
- [ ] `utils/logger.py` — `.claude/rules/python.md` 의 로깅 정책을 따른다
- [ ] `data/yfinance_client.py` — SPY·QQQ·GLD·TLT 1년치, QQQ 전일 종가
- [ ] **`scripts/probe_intraday.py` 로 KODEX 200 장중 시세 소스를 실측한다**
      — pykrx 와 yfinance `069500.KS` 를 같은 시각에 호출해 값과 지연을 비교하고,
      결과를 `docs/research/데이터소스_실측.md` 에 남긴다
- [ ] `data/pykrx_client.py` — 실측 결과로 고른 소스를 구현
- [ ] `data/ecos_client.py` — USDKRW 10년치. **인증키가 URL 경로에 들어가므로 마스킹 없이 로깅하지 않는다**
      (예외 메시지에도 URL 이 담기므로 함께 막는다)
- [ ] `data/calendar.py` — 미국·한국 휴장 판정. 휴장이면 알림이 조용히 종료된다
- [ ] `state/positions.py` · `state/reverse_rank.py` — 로딩과 스키마 검증
- [ ] Phase 0 테스트를 그린으로 만든다

---

### Phase 2 — 알림 계산과 문구(그린 유지)

**작업 내용**:

- [ ] `alerts/buffer_zone.py` — MA 근접도 4종 + 보유량·비중.
      **비중은 `수량 × 현재가` 의 비율**이며 평가액은 표시하지 않는다
- [ ] `alerts/reverse_rank.py` — 한국·미국 공용 판정. 침묵 조건 포함
- [ ] `alerts/usdkrw.py` — 원달러 평균대비 4창 + **지난주 역방향 방향별 양끝**
      (가장 오른 날 · 가장 내린 날. 절대값으로 합치지 않는다)
- [ ] `alerts/health.py` — `점검` 줄. GitHub Actions REST API 로 실행 이력을 읽는다.
      **조회가 실패해도 본 알림은 정상 발송한다**
- [ ] 문구 포맷 — [docs/DESIGN.md](../DESIGN.md) §4 의 예시와 **문자열 단위로 일치**시킨다.
      자릿수·정렬·제목의 날짜 요일 표기를 테스트로 고정한다

---

### Phase 3 — 발송과 CLI(그린 유지)

**작업 내용**:

- [ ] `notifier/telegram.py` — 발송. **알림 채널 자체의 실패는 로그로만 남긴다**
      (실패 알림이 실패했다고 다시 알림을 보내면 무한 루프가 된다)
- [ ] 실패 알림 — 제목과 예외 메시지만. 안내 문구를 붙이지 않는다
- [ ] `cli.py` · `__main__.py` — 알림별 서브커맨드와 `--dry-run`
- [ ] dry-run 으로 4종 문구를 뽑아 §4 예시와 대조한다

---

### Phase 4 — 워크플로(그린 유지)

**작업 내용**:

- [ ] 워크플로 4개 — **`workflow_dispatch` 만 둔다. `schedule` 을 두지 않는다**
- [ ] `concurrency` 그룹으로 워크플로당 동시 실행 1개
- [ ] `if: failure()` 잡 — 텔레그램 실패 알림
- [ ] `permissions: actions: read` — `점검` 줄이 실행 이력을 읽는 데 필요
- [ ] 시크릿 셋 확인 — `TELEGRAM_BOT_TOKEN` · `TELEGRAM_CHAT_ID` · `ECOS_API_KEY`

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**

- [ ] `docs/COMMANDS.md` 의 「알림 실행」 절을 채운다 (**변경 있음**)
- [ ] `docs/DESIGN.md` §9 의 실측 항목을 결과로 대체한다 (**변경 있음**)
- [ ] `docs/research/데이터소스_실측.md` 완성 — 근거 승격 목적지
- [ ] 자동 포맷 적용 — `poetry run black .`
- [ ] 변경 기능 및 전체 플로우 최종 검증
- [ ] DoD 체크리스트 최종 업데이트 및 체크 완료
- [ ] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [ ] `poetry run python validate_project.py` (passed=\_\_, failed=\_\_, skipped=\_\_)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 알림 / quant-notify 알림 4종 초기 구현 — 무상태 판정과 텔레그램 발송
2. 알림 / 버퍼존·역방향·원달러 알림 구현 + 판정 인바리언트 테스트 고정
3. 데이터 / 시세·환율 조회 계층과 알림 판정 구현
4. 워크플로 / workflow_dispatch 기반 알림 4종과 실패 감지 구성
5. 문서 / 설계 근거 승격 + 알림 구현 및 실행 명령 정리

## 7) 리스크(Risks)

| 리스크 | 완화 |
| --- | --- |
| **KODEX 200 장중 시세를 못 받는다** — pykrx 는 장중 미확정 값을 반환한 관측만 있고 「현재가」로 검증된 바 없다. yfinance `069500.KS` 도 미검증 | Phase 1 에서 **먼저 실측**한다. 둘 다 안 되면 `reverse_rank_kr` 은 **종가 판정으로 축소**하고(집행이 지난 알림), 그 사실을 §4.3 처럼 명시한다 |
| **알림 문구가 코드와 문서로 갈라진다** | 문구를 테스트로 고정하고, 루트 `CLAUDE.md` 가 「문구를 바꾸면 §4 예시도 함께 고친다」를 규칙으로 둔다 |
| **`점검` 줄이 본 알림을 막는다** | 조회 실패를 잡아 `점검 조회 실패` 로 표시하고 본문은 정상 발송한다. Phase 0 테스트로 고정 |
| **ECOS 인증키가 로그에 남는다** | 키가 URL 경로에 들어간다. `mask_api_key` 를 통과한 문자열만 로깅하고 **예외 메시지도 마스킹**한다 |
| **개발 중 실제 발송이 나간다** | 기본을 `--dry-run` 으로 두고, 발송은 사용자가 확인한 뒤 한다 |
| **`state/reverse_rank.yaml` 이 낡는다** | 낡으면 **안전한 방향으로 틀린다**(임계가 느슨해져 거짓 알림만 늘고 진짜 신호는 안 놓친다). 알림에 기준일을 함께 싣는 것은 다음 계획서로 미룬다 |

## 8) 메모(Notes)

### 확정된 설계 결정 (근거는 [docs/DESIGN.md](../DESIGN.md))

- 알림 4종 · 저장 파일 2종 · `schedule` 없는 단일 트리거
- 데이터는 알림마다 따로 받는다 — 캐시 공유는 결합과 신선도 검증을 부른다
- 지난주 역방향 요약은 **방향별 양끝**(해석 A)

### 실측으로 채워야 하는 값

Phase 1·4 에서 재고 `docs/research/데이터소스_실측.md` 에 남긴다.

- KODEX 200 장중 시세 소스 — pykrx 대 yfinance `069500.KS`
- yfinance QQQ 장중 지연 폭
- ECOS 10년 조회 응답 시간 (약 2,600행)
- cron-job.org 실제 발화 정시성
- 한국 휴장 달력 — pykrx 거래일 조회로 충분한지

### 순위 등락률 참고값 (2026-08 기준, `state/reverse_rank.yaml` 초기값)

| 대상 | 폭등 1위 | 폭등 20위 | 폭락 1위 | 폭락 20위 |
| --- | --- | --- | --- | --- |
| KODEX 200 | +24.17% (2026-07-31) | **+6.10%** | −12.46% (2026-03-04) | **−6.31%** |
| QQQ | +16.84% (2001-01-03) | **+7.42%** | −11.98% (2020-03-16) | **−6.87%** |

데이터 기간: KODEX 200 2002-10-15 ~ 2026-08-26 (5,890 거래일) · QQQ 1999-03-11 ~ 2026-08-25 (6,907 거래일).
20위 값은 `reference/역방향_매매_규칙.md` §1.5 와 일치함을 확인했다 — 계산 경로가 검증됐다는 뜻이다.

### 진행 로그 (KST)

- 2026-09-05 18:32: 계획서 작성. 저장소 골격·문서(`CLAUDE.md`·`DESIGN.md`·`COMMANDS.md`·`README.md`·`reference/`)는 이미 배치 완료

---

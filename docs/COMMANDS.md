# quant-notify 실행 명령어 레퍼런스

> 이 파일은 실행 명령어의 **단일 SoT(Source of Truth)** 입니다.
> README.md · CLAUDE.md 등 다른 문서에는 실행 명령어를 기재하지 않으며, 필요 시 이 문서를 참조합니다.
> 설치처럼 한 번만 쓰는 일회성 명령어는 기재하지 않습니다. **평상시 반복 실행하는 명령어만** 관리합니다.
> cron-job.org 잡 설정과 PAT 발급(한 번 하는 설정)은 [README](../README.md) 에 있습니다.

---

## 품질 검증

```bash
# 전체 검증 (Ruff + PyRight + Pytest)
poetry run python validate_project.py

# 개별 실행
poetry run python validate_project.py --only-lint
poetry run python validate_project.py --only-pyright
poetry run python validate_project.py --only-tests

# 커버리지 포함 테스트
poetry run python validate_project.py --cov

# 포맷 자동 적용
poetry run black .
```

> **`failed=0 skipped=0` 이 통과 기준입니다.** `passed` 의 절대값을 기준선으로 삼지 않습니다 —
> 코드를 지우면 테스트도 줄어드는 것이 정상인데, 숫자를 문서에 박아 두면 정상 상태가 고장으로 읽힙니다.
> 판단이 필요하면 **직전 실행과 비교**합니다.

> 세 항목이 **모두** `Command not found` 로 실패하면 코드 문제가 아니라 실행 환경 문제입니다.
> `poetry env info --path` 가 이 저장소의 `.venv` 를 가리키는지 확인합니다.
> **다른 저장소에서 세션을 시작했다면** `env -u VIRTUAL_ENV` 를 앞에 붙입니다.

---

## 알림 실행

**보내지 않고 문구만 확인합니다.** 표준출력으로 문구가 나오고 로그는 표준에러로 갈립니다.

```bash
poetry run python -m notify buffer_zone --dry-run
poetry run python -m notify usdkrw --dry-run
```

**실제로 보냅니다.** `--dry-run` 을 빼면 텔레그램으로 나갑니다.

```bash
poetry run python -m notify buffer_zone
```

> **휴장이면 조용히 끝납니다.** 이동평균 알림은 한국 기준 어제가 미국 거래일이
> 아니면 볼 새 종가가 없어 그대로 종료합니다.

> **한국 자정 뒤 미국 마감 전에 버퍼존을 돌리면 실패로 멈춥니다.** 판정할 종가가 아직
> 확정 전이기 때문입니다 ([DESIGN.md](DESIGN.md) §7.4). 마감 뒤에 다시 돌립니다.

> `점검` 줄은 `GITHUB_REPOSITORY` 와 `GITHUB_TOKEN` 이 있어야 채워집니다. 로컬에서는
> 보통 없으므로 **`이력 조회 실패` 로 나오고, 본문은 그대로 나옵니다.**

---

## 워크플로 수동 실행

정시 트리거가 실패했거나 원인 확인 후 다시 돌릴 때 씁니다.

GitHub 웹 → **Actions** → 워크플로 선택 → **Run workflow**

> **주간 알림은 월요일이 아닌 날에 돌려도 됩니다** — 점검 줄의 「지난주」는 실행 요일이 아니라
> 달력이 정합니다 ([DESIGN.md](DESIGN.md) §7.3).

### 보내지 않고 확인하기 (`dry_run`)

워크플로 둘 모두 **`dry_run` 입력**을 받습니다. 참이면 문구를 **실행 로그에만 찍고
텔레그램으로 보내지 않습니다.** 웹에서는 `Run workflow` 를 누를 때 나오는 체크박스입니다.

REST API 로 부를 때는 본문에 넣습니다. 값은 **문자열** 이어야 합니다.

```bash
curl -X POST \
  -H "Authorization: Bearer $GITHUB_TOKEN" \
  -H "Accept: application/vnd.github+json" \
  -H "X-GitHub-Api-Version: 2026-03-10" \
  https://api.github.com/repos/ingbeen/quant-notify/actions/workflows/buffer_zone.yml/dispatches \
  -d '{"ref":"main","inputs":{"dry_run":"true"}}'
```

**cron-job.org 는 `inputs` 를 보내지 않습니다.** 기본값이 `false` 라 그대로 발송됩니다.

`gh` CLI 를 쓴다면:

```bash
gh workflow run buffer_zone.yml -f dry_run=true
gh workflow run usdkrw.yml
```

---

## 실행 이력 조회

`점검` 줄이 무엇을 보고 있는지 직접 확인할 때 씁니다.

```bash
# 특정 날짜(KST)의 성공 실행 수 — 점검 줄과 같은 구간으로 묻습니다
gh api -X GET repos/ingbeen/quant-notify/actions/workflows/buffer_zone.yml/runs \
  -f created="2026-09-09T15:00:00Z..2026-09-10T14:59:59Z" -f status=success \
  --jq '{total_count, runs: [.workflow_runs[] | .created_at]}'

# 최근 실패만
gh run list --status=failure --limit=10
```

> 🔴 **`--created=2026-09-04` 같은 날짜 하나로 묻지 마세요. 그 필터는 UTC 기준입니다.**
> 아침 알림(버퍼존 07:30 · 주간 월 07:30)은 UTC 로 **전날 22:30**
> 이라 하루 어긋난 결과가 나오고, **에러는 나지 않습니다.** 위 예시의 `전날 15:00:00Z..당일 14:59:59Z` 가
> KST 하루입니다. 근거는 [DESIGN.md](DESIGN.md) §7.3 에 있습니다.

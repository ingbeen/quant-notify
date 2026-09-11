# quant-notify 실행 명령어 레퍼런스

> 이 파일은 실행 명령어의 **단일 SoT(Source of Truth)** 입니다.
> README.md · CLAUDE.md 등 다른 문서에는 실행 명령어를 기재하지 않으며, 필요 시 이 문서를 참조합니다.
> 설치처럼 한 번만 쓰는 일회성 명령어는 기재하지 않습니다. **평상시 반복 실행하는 명령어만** 관리합니다.

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

# 포맷 자동 적용 (마지막 Phase에서만)
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
poetry run python -m notify reverse_rank_kr --dry-run
poetry run python -m notify reverse_rank_us --dry-run
poetry run python -m notify usdkrw --dry-run
```

**실제로 보냅니다.** `--dry-run` 을 빼면 텔레그램으로 나갑니다.

```bash
poetry run python -m notify buffer_zone
```

> **역방향 알림은 신호가 멀면 아무것도 내지 않습니다.** 출력이 비어 있는 것이 정상이며,
> 그때는 로그(표준에러)에 「신호가 여유 밖이라 보내지 않습니다」가 남습니다.

> **휴장이면 조용히 끝납니다.** 이동평균과 미국 역방향은 한국 기준 어제가 미국 거래일이
> 아니면 볼 새 종가가 없어 그대로 종료합니다.

> `점검` 줄은 `GITHUB_REPOSITORY` 와 `GITHUB_TOKEN` 이 있어야 채워집니다. 로컬에서는
> 보통 없으므로 **`이력 조회 실패` 로 나오고, 본문은 그대로 나옵니다.**

---

## cron-job.org 정시 트리거 설정

워크플로는 `workflow_dispatch` 뿐이라 **누가 불러주지 않으면 돌지 않습니다.**
cron-job.org 에 아래 잡 다섯 개를 만듭니다. 요일 근거는 [DESIGN.md](DESIGN.md) 6.4 절에 있습니다.

**공통 설정** — 잡마다 URL 의 워크플로 파일명만 다릅니다.

```
Method    POST
URL       https://api.github.com/repos/ingbeen/quant-notify/actions/workflows/<파일명>/dispatches
Headers   Authorization: Bearer <PAT>
          Accept: application/vnd.github+json
          X-GitHub-Api-Version: 2026-03-10
          Content-Type: application/json
Body      {"ref":"main"}
Timezone  Asia/Seoul
```

**URL 끝의 `/dispatches` 가 「실행시켜라」입니다.** 빼면 워크플로 정보를 조회하는 주소가 됩니다.

| 잡 | 크론탭 | 시각 (KST) | 워크플로 파일 |
| --- | --- | --- | --- |
| 역방향 US | `20 7 * * 2-6` | 화~토 **07:20** | `reverse_rank_us.yml` |
| 버퍼존 | `30 7 * * 2-6` | 화~토 07:30 | `buffer_zone.yml` |
| 역방향 KR | `0 12 * * 1-5` | 월~금 12:00 | `reverse_rank_kr.yml` |
| 역방향 KR | `30 14 * * 1-5` | 월~금 14:30 | `reverse_rank_kr.yml` |
| 주간 | `30 7 * * 1` | 월 07:30 | `usdkrw.yml` |

> 🔴 **역방향 US 를 버퍼존보다 늦추지 마세요.** 버퍼존이 찍는 점검 줄이 **오늘 아침 US 가
> 돌았는지**를 담습니다. 순서가 뒤집히면 매일 `🔴 역방향 US 0/1` 이 뜹니다.
> 근거는 [DESIGN.md](DESIGN.md) 6.4 절에 있습니다.

**API 버전은 `2026-03-10` 을 씁니다.** `2022-11-28` 은 2026-03-10 부로 deprecated 되었고
2028-03-10 에 끊깁니다. 새 버전은 응답도 낫습니다 — `204 No Content` 대신 **`200 OK` 와 함께
`workflow_run_id`·`html_url` 을 돌려주어** 방금 만든 실행을 바로 찾을 수 있습니다.

**실패 알림 이메일을 켭니다.** PAT 가 만료되거나 무효가 되면 cron 이 401 을 받고 워크플로가
아예 돌지 않는데, **알림이 안 오니 점검 줄도 오지 않습니다.** 이 메일이 그것을 잡는 유일한
장치입니다. cron-job.org 는 15회 연속 실패하면 잡을 끄고 알려줍니다.

### PAT 발급

https://github.com/settings/personal-access-tokens/new 에서 만듭니다.

| 항목 | 값 |
| --- | --- |
| Expiration | `No expiration` — 만료는 위 「조용한 죽음」을 부릅니다 |
| Repository access | `Only select repositories` → `ingbeen/quant-notify` |
| Permissions | **Actions: Read and write** 하나만. dispatch(write)와 점검 줄의 이력 조회(read)를 겸합니다 |

토큰은 **생성 직후 한 번만** 보입니다. cron-job.org 헤더와 로컬 `.env` 의 `GITHUB_TOKEN` 에 넣습니다.

---

## 워크플로 수동 실행

정시 트리거가 실패했거나 원인 확인 후 다시 돌릴 때 씁니다.

GitHub 웹 → **Actions** → 워크플로 선택 → **Run workflow**

> **주간 알림은 월요일이 아닌 날에 돌려도 됩니다.** 「지난주」는 실행 요일이 아니라
> 달력이 정하므로, 화요일에 복구 실행해도 직전 월~금 구간을 그대로 냅니다.
> 근거는 [DESIGN.md](DESIGN.md) 4.4 절에 있습니다.

### 보내지 않고 확인하기 (`dry_run`)

워크플로 넷 모두 **`dry_run` 입력**을 받습니다. 참이면 문구를 **실행 로그에만 찍고
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
gh workflow run reverse_rank_kr.yml
gh workflow run reverse_rank_us.yml
gh workflow run usdkrw.yml
```

---

## 실행 이력 조회

`점검` 줄이 무엇을 보고 있는지 직접 확인할 때 씁니다.

```bash
# 특정 날짜(KST)의 성공 실행 수 — 점검 줄과 같은 구간으로 묻습니다
gh api -X GET repos/ingbeen/quant-notify/actions/workflows/reverse_rank_us.yml/runs \
  -f created="2026-09-09T15:00:00Z..2026-09-10T14:59:59Z" -f status=success \
  --jq '{total_count, runs: [.workflow_runs[] | .created_at]}'

# 최근 실패만
gh run list --status=failure --limit=10
```

> 🔴 **`--created=2026-09-04` 같은 날짜 하나로 묻지 마세요. 그 필터는 UTC 기준입니다.**
> 아침 알림(역방향 US 07:20 · 버퍼존 07:30 · 주간 월 07:30)은 UTC 로 **전날 22:20~22:30**
> 이라 하루 어긋난 결과가 나오고, **에러는 나지 않습니다.** 한국 역방향(12:00·14:30)만
> UTC 로도 날짜가 같아 우연히 맞습니다. 위 예시의 `전날 15:00:00Z..당일 14:59:59Z` 가
> KST 하루입니다. 근거는 [DESIGN.md](DESIGN.md) 7.3 절과
> `research/데이터소스_실측.md` §7 에 있습니다.

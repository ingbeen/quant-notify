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
> 보통 없으므로 **`조회 실패` 로 나오고, 본문은 그대로 나옵니다.**

---

## 워크플로 수동 실행

정시 트리거가 실패했거나 원인 확인 후 다시 돌릴 때 씁니다.

GitHub 웹 → **Actions** → 워크플로 선택 → **Run workflow**

CLI 를 쓴다면:

```bash
gh workflow run buffer_zone.yml
gh workflow run reverse_rank_kr.yml
gh workflow run reverse_rank_us.yml
gh workflow run usdkrw.yml
```

---

## 실행 이력 조회

`점검` 줄이 무엇을 보고 있는지 직접 확인할 때 씁니다.

```bash
# 특정 날짜의 성공 실행 수
gh run list --workflow=reverse_rank_kr.yml --status=success --created=2026-09-04

# 최근 실패만
gh run list --status=failure --limit=10
```

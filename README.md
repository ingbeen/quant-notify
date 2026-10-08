# quant-notify

quant 와 verify-lab 의 매매 규칙이 내는 신호를 **텔레그램으로 알리는** 시스템입니다.
GitHub Actions 에서 돌고, **매일 갱신되는 누적 상태를 갖지 않습니다.**

## 알림

| 알림 | 시각 (KST) | 내용 |
| --- | --- | --- |
| `buffer_zone` | 화 ~ 토 07:30 | SPY · QQQ · GLD · TLT 의 200일 이동평균 근접도 + 보유 종목과 비중 |
| `usdkrw` | 월 07:30 | 원달러가 1·3·5·10년 평균 대비 어디인지 |

요일 근거는 [docs/DESIGN.md](docs/DESIGN.md) §6.4, 문구는 §4.3 에 있습니다.

## 왜 이렇게 생겼나

전신인 quant `src/live/` 가 **누적 상태 때문에 거래일 하나를 영구히 잃었습니다.**
cron 이 몇 시간 밀려 처리 대상 날짜가 하루 건너뛰었고, 그 공백이 이후 실행을 전부 막았습니다.

그래서 이 저장소는 상태를 갖지 않습니다. 실행이 하루 빠지거나 몇 시간 밀려도 **다음 날 오면 그만**입니다.
설계 근거 전체는 [docs/DESIGN.md](docs/DESIGN.md) 에 있습니다.

## 구조

```
docs/DESIGN.md     왜 이렇게 생겼는지 — 설계의 정본
src/notify/        알림 구현
state/             사람이 손으로 쓰는 파일 (보유 종목)
```

실행 명령은 [docs/COMMANDS.md](docs/COMMANDS.md) 를 봅니다.

## 필요한 것

- Python 3.12 · Poetry
- GitHub 시크릿 셋 — `TELEGRAM_BOT_TOKEN` · `TELEGRAM_CHAT_ID` · `ECOS_API_KEY`
- 정시 트리거 — 아래 cron-job.org 잡 둘. 워크플로는 `workflow_dispatch` 뿐이라
  **누가 불러주지 않으면 돌지 않습니다** (GitHub `schedule` 을 쓰지 않는 이유는 [docs/DESIGN.md](docs/DESIGN.md) §6)

### cron-job.org 잡

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
| 버퍼존 | `30 7 * * 2-6` | 화 ~ 토 07:30 | `buffer_zone.yml` |
| 주간 | `30 7 * * 1` | 월 07:30 | `usdkrw.yml` |

**실패 알림 이메일을 켭니다.** PAT 가 만료되거나 무효가 되면 cron 이 401 을 받고 워크플로가
아예 돌지 않는데, **알림이 안 오니 점검 줄도 오지 않습니다.** 이 메일이 그것을 잡는 유일한 장치입니다.

### PAT 발급

https://github.com/settings/personal-access-tokens/new 에서 **fine-grained PAT** 를 만듭니다.

| 항목 | 값 |
| --- | --- |
| Expiration | `No expiration` — 만료되면 위처럼 알림과 점검 줄이 함께 끊깁니다 |
| Repository access | `Only select repositories` → `ingbeen/quant-notify` |
| Permissions | **Actions: Read and write** 하나만. dispatch(write)와 점검 줄의 이력 조회(read)를 겸합니다 |

토큰은 **생성 직후 한 번만** 보입니다. cron-job.org 헤더와 로컬 `.env` 의 `GITHUB_TOKEN` 에 넣습니다.

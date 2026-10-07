# quant-notify

quant 와 verify-lab 의 매매 규칙이 내는 신호를 **텔레그램으로 알리는** 시스템입니다.
GitHub Actions 에서 돌고, **매일 갱신되는 누적 상태를 갖지 않습니다.**

## 알림

| 알림 | 시각 (KST) | 내용 |
| --- | --- | --- |
| `buffer_zone` | 화~토 아침 | SPY · QQQ · GLD · TLT 의 200일 이동평균 근접도 + 보유 종목과 비중 |
| `usdkrw` | 월요일 아침 | 원달러가 1·3·5·10년 평균 대비 어디인지 |

`buffer_zone` 이 화~토인 것은 한국 아침에 **전날 미국 종가**를 보기 때문입니다 — 금요일 종가는
토요일 아침에 보고, 일·월에는 볼 새 종가가 없습니다.

## 왜 이렇게 생겼나

전신인 quant `src/live/` 가 **누적 상태 때문에 거래일 하나를 영구히 잃었습니다.**
cron 이 7시간 45분 밀려 처리 대상 날짜가 하루 건너뛰었고, 그 공백이 이후 실행을 전부 막았습니다.

그래서 이 저장소는 상태를 갖지 않습니다. 실행이 하루 빠지거나 몇 시간 밀려도 **다음 날 오면 그만**입니다.
설계 근거 전체는 [docs/DESIGN.md](docs/DESIGN.md) 에 있습니다.

## 구조

```
docs/DESIGN.md     왜 이렇게 생겼는지 — 설계의 정본
reference/         verify-lab 매매 규칙 스냅샷 (판정 근거)
src/notify/        알림 구현
state/             사람이 손으로 쓰는 파일 (보유 종목)
```

실행 명령은 [docs/COMMANDS.md](docs/COMMANDS.md) 를 봅니다.

## 필요한 것

- Python 3.12 · Poetry
- 시크릿 셋 — `TELEGRAM_BOT_TOKEN` · `TELEGRAM_CHAT_ID` · `ECOS_API_KEY`
- 정시 트리거 — cron-job.org 가 GitHub `workflow_dispatch` 를 호출합니다
  (GitHub 의 `schedule` 은 중앙값 64분 밀립니다 — [docs/DESIGN.md](docs/DESIGN.md) §6)
- 그 호출에 쓸 **fine-grained PAT** — 이 저장소의 `Actions: Read and write` 하나면 됩니다.
  발급과 cron 설정은 [docs/COMMANDS.md](docs/COMMANDS.md) 에 있습니다

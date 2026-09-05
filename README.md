# quant-notify

quant 와 verify-lab 의 매매 규칙이 내는 신호를 **텔레그램으로 알리는** 시스템입니다.
GitHub Actions 에서 돌고, **매일 갱신되는 누적 상태를 갖지 않습니다.**

## 알림

| 알림 | 시각 (KST) | 내용 |
| --- | --- | --- |
| `buffer_zone` | 매 거래일 아침 | SPY · QQQ · GLD · TLT 의 200일 이동평균 근접도 + 보유 종목과 비중 |
| `reverse_rank_kr` | 평일 12:00 · 14:30 | KODEX 200 이 역대 상위 20위 등락률에 접근하면 알림. **멀면 침묵** |
| `reverse_rank_us` | 매 거래일 아침 | QQQ 에 대해 같은 판정. **멀면 침묵** |
| `usdkrw` | 월요일 아침 | 원달러가 1·3·5·10년 평균 대비 어디인지 + 지난주 역방향 요약 |

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
state/             사람이 손으로 쓰는 파일 (보유 종목, 순위 등락률)
```

실행 명령은 [docs/COMMANDS.md](docs/COMMANDS.md) 를 봅니다.

## 필요한 것

- Python 3.12 · Poetry
- 시크릿 셋 — `TELEGRAM_BOT_TOKEN` · `TELEGRAM_CHAT_ID` · `ECOS_API_KEY`
- 정시 트리거 — cron-job.org 가 GitHub `workflow_dispatch` 를 호출합니다
  (GitHub 의 `schedule` 은 중앙값 64분 밀려 장중 알림에 쓸 수 없습니다)

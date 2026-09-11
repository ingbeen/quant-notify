"""실패했을 때 알림이 나가는지 고정한다.

워크플로에 `if: failure()` 잡을 두지 않으므로, 실패를 알리는 책임은 전적으로 여기에 있다.
이 경로가 끊기면 알림이 조용히 죽는다.

**발송 자체가 실패한 경우는 여기서 알리지 않는다.** 텔레그램이 죽었으면 텔레그램으로
알릴 수 없다. 그때는 GitHub Actions 실패 메일이 마지막 보루다.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from notify import cli
from notify.alerts.formatting import RED_DOT


def _fail(alert: str, now: datetime) -> str | None:
    """알림 조립이 실패하는 상황을 흉내 낸다.

    Args:
        alert: 알림 이름.
        now: 실행 시각.

    Raises:
        RuntimeError: 항상.
    """
    del alert, now
    raise RuntimeError("yfinance 조회 실패 — QQQ")


class TestFailureIsAnnounced:
    """알림 조립이 실패했을 때."""

    def test_sends_a_failure_alert(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """실패 알림이 텔레그램으로 나간다."""
        sent: list[str] = []

        monkeypatch.setattr(cli, "build_message", _fail)
        monkeypatch.setattr(cli, "read_config", lambda name, required=True: "dummy")
        monkeypatch.setattr(
            cli.telegram,
            "send_without_raising",
            lambda token, chat_id, text: bool(sent.append(text)) or True,
        )

        assert cli.main(["buffer_zone"]) == 1
        assert len(sent) == 1
        assert sent[0].startswith(f"{RED_DOT} <b>실패 · buffer_zone</b>")
        assert "RuntimeError: yfinance 조회 실패 — QQQ" in sent[0]

    def test_uses_the_quiet_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """실패 알림은 예외를 올리지 않는 경로로 보낸다.

        여기서 예외가 올라가면 실패를 알리다 다시 실패하고, 그 실패를 또 알리려 든다.
        """
        monkeypatch.setattr(cli, "build_message", _fail)
        monkeypatch.setattr(cli, "read_config", lambda name, required=True: "dummy")

        def _boom(token: str, chat_id: str, text: str) -> None:
            del token, chat_id, text
            raise AssertionError("실패 알림은 send() 가 아니라 send_without_raising() 로 나가야 한다")

        monkeypatch.setattr(cli.telegram, "send", _boom)
        monkeypatch.setattr(cli.telegram, "send_without_raising", lambda token, chat_id, text: True)

        assert cli.main(["buffer_zone"]) == 1

    def test_dry_run_prints_instead_of_sending(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """dry-run 에서는 보내지 않고 표준출력으로 찍는다."""
        monkeypatch.setattr(cli, "build_message", _fail)

        def _never(token: str, chat_id: str, text: str) -> bool:
            del token, chat_id, text
            raise AssertionError("dry-run 은 보내지 않는다")

        monkeypatch.setattr(cli.telegram, "send_without_raising", _never)

        assert cli.main(["buffer_zone", "--dry-run"]) == 1
        assert f"{RED_DOT} <b>실패 · buffer_zone</b>" in capsys.readouterr().out

    def test_missing_secrets_do_not_crash(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """시크릿이 없으면 보내지 못하고 끝난다. 그 자리에서 다시 죽지 않는다."""
        monkeypatch.setattr(cli, "build_message", _fail)
        monkeypatch.setattr(cli, "read_config", lambda name, required=True: "")

        def _never(token: str, chat_id: str, text: str) -> bool:
            del token, chat_id, text
            raise AssertionError("시크릿이 없으면 발송을 시도하지 않는다")

        monkeypatch.setattr(cli.telegram, "send_without_raising", _never)

        assert cli.main(["buffer_zone"]) == 1


class TestSilenceIsNotFailure:
    """보낼 것이 없는 경우."""

    def test_silent_run_sends_nothing_and_succeeds(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """침묵은 실패가 아니다. 아무것도 보내지 않고 정상 종료한다."""
        monkeypatch.setattr(cli, "build_message", lambda alert, now: None)

        def _never(*args: object, **kwargs: object) -> None:
            raise AssertionError("침묵일 때는 보내지 않는다")

        monkeypatch.setattr(cli.telegram, "send", _never)
        monkeypatch.setattr(cli.telegram, "send_without_raising", _never)

        assert cli.main(["reverse_rank_us"]) == 0


class TestSendFailureIsNotRetried:
    """발송 자체가 실패한 경우."""

    def test_send_failure_propagates(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """발송이 실패하면 예외가 그대로 올라가 워크플로가 실패로 끝난다.

        텔레그램이 죽었으면 텔레그램으로 알릴 수 없다. GitHub Actions 실패 메일이 맡는다.
        """
        monkeypatch.setattr(cli, "build_message", lambda alert, now: "본문")
        monkeypatch.setattr(cli, "read_config", lambda name, required=True: "dummy")

        def _fail_send(token: str, chat_id: str, text: str) -> None:
            del token, chat_id, text
            raise ValueError("텔레그램 발송에 실패했습니다")

        monkeypatch.setattr(cli.telegram, "send", _fail_send)

        with pytest.raises(ValueError, match="텔레그램 발송"):
            cli.main(["buffer_zone"])

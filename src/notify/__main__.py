"""`python -m notify` 로 실행하는 진입점."""

from __future__ import annotations

import sys

from notify.cli import main

if __name__ == "__main__":
    sys.exit(main())

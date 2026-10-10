"""Language-neutral CLI failures; agents localize errorCode for the user."""
from __future__ import annotations

import json
import sys


def failure(exc: Exception, code: str, *, stream=None) -> None:
    diagnostic = str(exc)[:1000]
    print(json.dumps({"ok": False, "errorCode": code, "diagnostic": diagnostic},
                     ensure_ascii=False), file=stream or sys.stderr)

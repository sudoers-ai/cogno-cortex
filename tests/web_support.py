"""Helpers for the web-skill tests — INVENTED data only. Not a test module.

``LocalServer`` starts ``tests/web_server_app.py`` as a SUBPROCESS on a disposable port and kills
it by PID when the session ends; ``resolver`` maps invented host names to fixed addresses, so the
SSRF guard is exercised without any DNS lookup leaving the box.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
from pathlib import Path
from typing import Mapping, Sequence

import httpx

APP = Path(__file__).with_name("web_server_app.py")


class LocalServer:
    def __init__(self) -> None:
        self.proc = subprocess.Popen([sys.executable, "-I", str(APP)], stdout=subprocess.PIPE,
                                     stderr=subprocess.DEVNULL, text=True)
        line = self.proc.stdout.readline() if self.proc.stdout else ""
        if not line.strip().isdigit():
            self.stop()
            raise RuntimeError("the local test server did not start")
        self.port = int(line.strip())
        self.pid = self.proc.pid

    def count(self) -> int:
        """Requests that reached the server — read directly, never through the skill."""
        return int(httpx.get(f"http://127.0.0.1:{self.port}/_count", trust_env=False).text)

    def stop(self) -> None:
        if self.proc.poll() is None:
            os.kill(self.proc.pid, signal.SIGTERM)
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.kill(self.proc.pid, signal.SIGKILL)
                self.proc.wait(timeout=5)
        if self.proc.stdout:
            self.proc.stdout.close()


def resolver(table: Mapping[str, Sequence[str]]):
    async def resolve(host: str, port: int) -> "list[str]":
        if host not in table:
            raise OSError(f"unknown test host {host}")
        return list(table[host])
    return resolve


def valid_cpf(nine: str) -> str:
    """An INVENTED CPF that passes the checksum: nine digits + the two check digits."""
    digits = [int(c) for c in nine]
    for weight in (10, 11):
        total = sum(d * w for d, w in zip(digits, range(weight, 1, -1)))
        rest = (total * 10) % 11
        digits.append(0 if rest == 10 else rest)
    s = "".join(map(str, digits))
    return f"{s[:3]}.{s[3:6]}.{s[6:9]}-{s[9:]}"

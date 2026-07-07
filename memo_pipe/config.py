"""Configuration for memo-pipe.

All settings come from environment variables (optionally loaded from a
chmod-600 env file at ~/.memo-pipe/env) or the macOS Keychain.
"""

from __future__ import annotations

import os
import stat
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

HOME = Path.home()
STATE_DIR = HOME / ".memo-pipe"
ENV_FILE = STATE_DIR / "env"

DEFAULT_RECORDINGS_DIR = (
    HOME
    / "Library/Group Containers/group.com.apple.VoiceMemos.shared/Recordings"
)

KEYCHAIN_SERVICE = "memo-pipe-devin-api-key"


def _load_env_file(path: Path) -> None:
    """Load KEY=VALUE lines from an env file into os.environ (no overwrite).

    Refuses to load the file if it is readable by group/other.
    """
    if not path.exists():
        return
    mode = stat.S_IMODE(path.stat().st_mode)
    if mode & 0o077:
        print(
            f"ERROR: {path} must be chmod 600 (found {oct(mode)}); refusing to load.",
            file=sys.stderr,
        )
        raise SystemExit(1)
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _keychain_get(service: str) -> str | None:
    """Read a generic password from the macOS Keychain via `security`."""
    try:
        result = subprocess.run(
            ["security", "find-generic-password", "-s", service, "-w"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


@dataclass
class Config:
    recordings_dir: Path = DEFAULT_RECORDINGS_DIR
    state_dir: Path = STATE_DIR
    ledger_path: Path = STATE_DIR / "ledger.db"
    log_path: Path = STATE_DIR / "memo-pipe.log"

    whisper_bin: str = "whisper-cli"
    whisper_model: Path = STATE_DIR / "models" / "ggml-medium.en.bin"

    devin_api_base: str = "https://api.devin.ai/v1"
    devin_api_key: str = ""

    playbook_path: Path = field(default_factory=lambda: Path(__file__).resolve().parent.parent / "playbook.md")

    # File-stability check: size must be unchanged across two checks this far apart.
    stability_interval_secs: int = 10

    retries: int = 3
    retry_backoff_secs: int = 5

    @classmethod
    def load(cls) -> "Config":
        _load_env_file(ENV_FILE)
        cfg = cls()
        env = os.environ
        if env.get("MEMO_PIPE_RECORDINGS_DIR"):
            cfg.recordings_dir = Path(env["MEMO_PIPE_RECORDINGS_DIR"]).expanduser()
        if env.get("MEMO_PIPE_WHISPER_BIN"):
            cfg.whisper_bin = env["MEMO_PIPE_WHISPER_BIN"]
        if env.get("MEMO_PIPE_WHISPER_MODEL"):
            cfg.whisper_model = Path(env["MEMO_PIPE_WHISPER_MODEL"]).expanduser()
        if env.get("MEMO_PIPE_PLAYBOOK"):
            cfg.playbook_path = Path(env["MEMO_PIPE_PLAYBOOK"]).expanduser()
        if env.get("DEVIN_API_BASE"):
            cfg.devin_api_base = env["DEVIN_API_BASE"].rstrip("/")

        # API key: env var first, then macOS Keychain.
        cfg.devin_api_key = (
            env.get("DEVIN_API_KEY") or _keychain_get(KEYCHAIN_SERVICE) or ""
        )
        return cfg

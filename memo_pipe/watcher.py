"""Main watcher loop.

Designed to be invoked by launchd on WatchPaths events and on a 5-minute
StartInterval polling fallback. Each invocation scans the recordings folder,
processes any new stable .m4a files, and exits. A lock file prevents
overlapping runs.
"""

from __future__ import annotations

import fcntl
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from .config import Config
from .devin_client import build_prompt, create_session
from .ledger import Ledger, file_sha256
from .transcribe import transcribe

log = logging.getLogger("memo-pipe")


def setup_logging(cfg: Config) -> None:
    cfg.state_dir.mkdir(parents=True, exist_ok=True)
    handlers = [
        logging.FileHandler(cfg.log_path),
        logging.StreamHandler(sys.stderr),
    ]
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=handlers,
    )


def is_stable(path: Path, interval_secs: int) -> bool:
    """True if the file size is unchanged across two checks `interval_secs` apart.

    Avoids grabbing files still being written by iCloud sync.
    """
    try:
        size1 = path.stat().st_size
        time.sleep(interval_secs)
        size2 = path.stat().st_size
    except FileNotFoundError:
        return False
    return size1 == size2 and size1 > 0


def recording_timestamp(path: Path) -> str:
    """Best-effort recording time: the file's mtime, in local time + UTC."""
    mtime = path.stat().st_mtime
    local = datetime.fromtimestamp(mtime).astimezone()
    utc = datetime.fromtimestamp(mtime, tz=timezone.utc)
    return f"{local.isoformat()} (UTC: {utc.isoformat()})"


def process_file(cfg: Config, ledger: Ledger, path: Path) -> None:
    log.info("file detected: %s", path)

    if not is_stable(path, cfg.stability_interval_secs):
        log.info("file not yet stable (still syncing?), skipping for now: %s", path)
        return

    sha = file_sha256(path)
    if ledger.is_processed(sha):
        log.info("already processed (sha256=%s): %s", sha[:12], path)
        return

    last_error: Exception | None = None
    for attempt in range(1, cfg.retries + 1):
        try:
            log.info("transcribing (attempt %d/%d): %s", attempt, cfg.retries, path)
            transcript = transcribe(cfg, path)
            log.info("transcribed %d chars: %s", len(transcript), path)

            playbook = cfg.playbook_path.read_text()
            prompt = build_prompt(playbook, transcript, recording_timestamp(path))
            session_id, session_url = create_session(cfg, prompt)
            log.info("session created: %s (%s)", session_id, session_url)

            ledger.mark_processed(sha, path, session_id, session_url)
            log.info("done: %s", path)
            return
        except Exception as e:  # noqa: BLE001 - log and retry any failure
            last_error = e
            log.error("attempt %d/%d failed for %s: %s", attempt, cfg.retries, path, e)
            if attempt < cfg.retries:
                backoff = cfg.retry_backoff_secs * (2 ** (attempt - 1))
                time.sleep(backoff)

    attempts = ledger.record_failure(sha, path, str(last_error))
    log.error(
        "giving up for now (total failed attempts: %d); will retry on next run: %s",
        attempts,
        path,
    )


def scan(cfg: Config, ledger: Ledger) -> None:
    if not cfg.recordings_dir.is_dir():
        log.error("recordings dir not found: %s", cfg.recordings_dir)
        return
    for path in sorted(cfg.recordings_dir.glob("*.m4a")):
        process_file(cfg, ledger, path)


def main() -> int:
    cfg = Config.load()
    setup_logging(cfg)

    lock_path = cfg.state_dir / "watcher.lock"
    with open(lock_path, "w") as lock_file:
        try:
            fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            log.info("another run is in progress; exiting")
            return 0

        ledger = Ledger(cfg.ledger_path)
        try:
            scan(cfg, ledger)
        finally:
            ledger.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

import threading
import time
from pathlib import Path
from unittest import mock

from memo_pipe.config import Config
from memo_pipe.devin_client import build_prompt
from memo_pipe.ledger import Ledger
from memo_pipe.watcher import is_stable, process_file


def make_cfg(tmp_path: Path) -> Config:
    cfg = Config()
    cfg.recordings_dir = tmp_path / "recordings"
    cfg.state_dir = tmp_path / "state"
    cfg.ledger_path = cfg.state_dir / "ledger.db"
    cfg.log_path = cfg.state_dir / "memo-pipe.log"
    cfg.playbook_path = tmp_path / "playbook.md"
    cfg.playbook_path.write_text("PLAYBOOK CONTENT")
    cfg.stability_interval_secs = 0
    cfg.retries = 2
    cfg.retry_backoff_secs = 0
    cfg.state_dir.mkdir(parents=True)
    cfg.recordings_dir.mkdir(parents=True)
    return cfg


def test_is_stable_rejects_growing_file(tmp_path: Path):
    f = tmp_path / "grow.m4a"
    f.write_bytes(b"a" * 10)

    def grow():
        time.sleep(0.2)
        f.write_bytes(b"a" * 20)

    t = threading.Thread(target=grow)
    t.start()
    assert is_stable(f, 1) is False
    t.join()
    assert is_stable(f, 0) is True


def test_build_prompt_contains_all_parts():
    p = build_prompt("PLAYBOOK", "the transcript", "2026-07-07T09:30")
    assert "PLAYBOOK" in p
    assert "the transcript" in p
    assert "2026-07-07T09:30" in p


def test_process_file_success_marks_ledger(tmp_path: Path):
    cfg = make_cfg(tmp_path)
    f = cfg.recordings_dir / "memo.m4a"
    f.write_bytes(b"fake audio")
    ledger = Ledger(cfg.ledger_path)

    with mock.patch("memo_pipe.watcher.transcribe", return_value="hi") as tr, \
         mock.patch("memo_pipe.watcher.create_session", return_value=("s1", "u1")) as cs:
        process_file(cfg, ledger, f)
        process_file(cfg, ledger, f)  # second run: already processed

    assert tr.call_count == 1
    assert cs.call_count == 1
    ledger.close()


def test_process_file_failure_retries_then_leaves_unprocessed(tmp_path: Path):
    cfg = make_cfg(tmp_path)
    f = cfg.recordings_dir / "memo.m4a"
    f.write_bytes(b"fake audio")
    ledger = Ledger(cfg.ledger_path)

    with mock.patch("memo_pipe.watcher.transcribe", side_effect=RuntimeError("boom")) as tr:
        process_file(cfg, ledger, f)

    assert tr.call_count == cfg.retries
    from memo_pipe.ledger import file_sha256
    assert not ledger.is_processed(file_sha256(f))

    # Next run retries and can succeed (kill-mid-transcription acceptance test).
    with mock.patch("memo_pipe.watcher.transcribe", return_value="ok"), \
         mock.patch("memo_pipe.watcher.create_session", return_value=("s2", "u2")):
        process_file(cfg, ledger, f)
    assert ledger.is_processed(file_sha256(f))
    ledger.close()

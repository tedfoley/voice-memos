import hashlib
from pathlib import Path

from memo_pipe.ledger import Ledger, file_sha256


def test_sha256(tmp_path: Path):
    f = tmp_path / "a.m4a"
    f.write_bytes(b"hello audio")
    assert file_sha256(f) == hashlib.sha256(b"hello audio").hexdigest()


def test_exactly_once(tmp_path: Path):
    ledger = Ledger(tmp_path / "ledger.db")
    sha = "x" * 64
    assert not ledger.is_processed(sha)
    ledger.mark_processed(sha, tmp_path / "a.m4a", "sess-1", "https://app.devin.ai/sessions/1")
    assert ledger.is_processed(sha)
    ledger.close()

    # Ledger survives restarts.
    ledger2 = Ledger(tmp_path / "ledger.db")
    assert ledger2.is_processed(sha)
    ledger2.close()


def test_failures_retryable(tmp_path: Path):
    ledger = Ledger(tmp_path / "ledger.db")
    sha = "y" * 64
    assert ledger.record_failure(sha, tmp_path / "b.m4a", "boom") == 1
    assert ledger.record_failure(sha, tmp_path / "b.m4a", "boom2") == 2
    # A failed file is NOT marked processed, so next run retries it.
    assert not ledger.is_processed(sha)
    ledger.mark_processed(sha, tmp_path / "b.m4a", "sess-2", "url")
    assert ledger.is_processed(sha)
    row = ledger.conn.execute("SELECT COUNT(*) FROM failures").fetchone()
    assert row[0] == 0
    ledger.close()

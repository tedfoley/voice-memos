"""Devin API client: creates one session per memo transcript."""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from .config import Config


class DevinAPIError(RuntimeError):
    pass


def build_prompt(playbook: str, transcript: str, recorded_at: str) -> str:
    return (
        f"{playbook.strip()}\n\n"
        "---\n\n"
        f"Recording timestamp: {recorded_at}\n\n"
        "Transcript of the voice memo:\n\n"
        f'"""\n{transcript.strip()}\n"""\n'
    )


def create_session(cfg: Config, prompt: str) -> tuple[str, str]:
    """POST /v1/sessions; returns (session_id, session_url)."""
    if not cfg.devin_api_key:
        raise DevinAPIError(
            "No Devin API key found (set DEVIN_API_KEY in ~/.memo-pipe/env "
            "or store it in the Keychain under 'memo-pipe-devin-api-key')."
        )
    body = json.dumps({"prompt": prompt, "idempotent": False}).encode()
    req = urllib.request.Request(
        f"{cfg.devin_api_base}/sessions",
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {cfg.devin_api_key}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        raise DevinAPIError(f"Devin API HTTP {e.code}: {e.read().decode()[:500]}") from e
    except urllib.error.URLError as e:
        raise DevinAPIError(f"Devin API unreachable: {e.reason}") from e

    session_id = data.get("session_id", "")
    session_url = data.get("url", "")
    if not session_id:
        raise DevinAPIError(f"Unexpected Devin API response: {data}")
    return session_id, session_url

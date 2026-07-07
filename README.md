# memo-pipe

Apple Voice Memos → local Whisper transcription → Devin session that organizes
each brain dump per [`playbook.md`](playbook.md) and commits it to a private
`brain-dumps` repo. Zero manual steps after you hit stop on the recording.

## How it works

```
iPhone Voice Memo
   └─ iCloud sync ─▶ ~/Library/Group Containers/group.com.apple.VoiceMemos.shared/Recordings/*.m4a
        └─ launchd LaunchAgent (WatchPaths + 5-min StartInterval fallback)
             └─ memo_pipe.watcher
                  1. wait until file size is stable across two checks 10s apart
                  2. sha256 → skip if already in ~/.memo-pipe/ledger.db
                  3. transcribe LOCALLY with whisper.cpp (medium.en) — audio never leaves the Mac
                  4. POST https://api.devin.ai/v1/sessions with prompt = playbook.md + transcript + timestamp
                  5. mark processed in ledger (only after success → exactly-once)
                       └─ Devin session classifies + commits to brain-dumps repo + notifies you
```

## Install (on the always-on Mac)

```bash
git clone <this repo> && cd memo-pipe
./scripts/install.sh
```

The installer:
- installs `whisper-cpp` and `ffmpeg` via Homebrew
- downloads the `medium.en` model (~1.5 GB) to `~/.memo-pipe/models/`
- prompts for your Devin API key and stores it in the **macOS Keychain**
  (service `memo-pipe-devin-api-key`); alternatively put `DEVIN_API_KEY=...`
  in `~/.memo-pipe/env` and `chmod 600` it — the watcher refuses to load a
  group/other-readable env file
- installs and starts the LaunchAgent `com.memo-pipe.watcher`

## Configuration (all optional, via env or `~/.memo-pipe/env`)

| Variable | Default |
|---|---|
| `DEVIN_API_KEY` | (Keychain `memo-pipe-devin-api-key`) |
| `DEVIN_API_BASE` | `https://api.devin.ai/v1` |
| `MEMO_PIPE_RECORDINGS_DIR` | Voice Memos iCloud recordings dir |
| `MEMO_PIPE_WHISPER_BIN` | `whisper-cli` |
| `MEMO_PIPE_WHISPER_MODEL` | `~/.memo-pipe/models/ggml-medium.en.bin` |
| `MEMO_PIPE_PLAYBOOK` | `playbook.md` in this repo |

## Privacy guarantee

Raw audio never leaves the Mac. Transcription runs entirely locally with
whisper.cpp; the only outbound request is the transcript text POSTed to the
Devin API. Verify from the logs (`~/.memo-pipe/memo-pipe.log`): the only
network event logged is `session created`, and you can additionally confirm
with e.g. `nettop`/Little Snitch that only api.devin.ai is contacted with a
payload the size of the transcript.

## Reliability

- **Exactly-once:** a memo is marked processed in the SQLite ledger
  (`~/.memo-pipe/ledger.db`, keyed by file sha256) only after the Devin
  session is successfully created. Kill the watcher mid-transcription and
  restart — the memo is retried and processed exactly once.
- **Retries:** each failure retries 3x with exponential backoff, then the
  file is left unprocessed so the next run (≤5 min later) retries.
- **Logs:** all events (file detected, transcribed, session created, errors)
  go to `~/.memo-pipe/memo-pipe.log` with timestamps.

## Output

The Devin session (driven by `playbook.md`) commits one dated markdown file
per memo per bucket to the private `brain-dumps` repo:
`/prompts`, `/essays`, `/anki`, `/todo` — `YYYY-MM-DD-HHMM-<slug>.md` — then
sends a short Slack DM or email with the classification and file link.

## Running tests

```bash
python3 -m pytest tests/
```

## Uninstall

```bash
launchctl bootout gui/$(id -u)/com.memo-pipe.watcher
rm ~/Library/LaunchAgents/com.memo-pipe.watcher.plist
rm -rf ~/.memo-pipe   # ledger, logs, model, env
```

## Non-goals (v1)

- No parsing of Apple's internal CloudRecordings database or Apple-generated
  transcripts (fragile, undocumented). Whisper is the transcription source.
- No iOS-side automation (no reliable trigger exists for new Voice Memos).

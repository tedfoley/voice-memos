#!/usr/bin/env bash
# One-time setup of memo-pipe on the always-on Mac.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STATE_DIR="$HOME/.memo-pipe"
MODEL_DIR="$STATE_DIR/models"
MODEL="$MODEL_DIR/ggml-medium.en.bin"
PLIST_SRC="$REPO_DIR/launchd/com.memo-pipe.watcher.plist"
PLIST_DST="$HOME/Library/LaunchAgents/com.memo-pipe.watcher.plist"
LABEL="com.memo-pipe.watcher"

echo "==> memo-pipe install"
mkdir -p "$STATE_DIR" "$MODEL_DIR"

# 1. Dependencies (whisper.cpp + ffmpeg) via Homebrew.
if ! command -v brew >/dev/null; then
  echo "ERROR: Homebrew is required (https://brew.sh)"; exit 1
fi
for pkg in whisper-cpp ffmpeg; do
  brew list "$pkg" >/dev/null 2>&1 || brew install "$pkg"
done

# 2. Whisper medium.en model (~1.5 GB), downloaded once.
if [ ! -f "$MODEL" ]; then
  echo "==> downloading whisper medium.en model to $MODEL"
  curl -L --fail -o "$MODEL" \
    "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-medium.en.bin"
fi

# 3. Devin API key: Keychain preferred, chmod-600 env file as fallback.
if ! security find-generic-password -s memo-pipe-devin-api-key -w >/dev/null 2>&1 \
   && ! grep -qs '^DEVIN_API_KEY=' "$STATE_DIR/env" 2>/dev/null; then
  echo "==> No Devin API key found."
  read -r -s -p "Paste your Devin API key (stored in macOS Keychain): " KEY; echo
  security add-generic-password -s memo-pipe-devin-api-key -a "$USER" -w "$KEY"
  unset KEY
fi
if [ -f "$STATE_DIR/env" ]; then chmod 600 "$STATE_DIR/env"; fi

# 4. Install the LaunchAgent with paths substituted.
mkdir -p "$HOME/Library/LaunchAgents"
sed -e "s|__MEMO_PIPE_DIR__|$REPO_DIR|g" -e "s|__HOME__|$HOME|g" \
  "$PLIST_SRC" > "$PLIST_DST"

launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST_DST"
launchctl kickstart "gui/$(id -u)/$LABEL"

echo "==> installed. Logs: $STATE_DIR/memo-pipe.log"

#!/usr/bin/env bash
# Installs or updates voice-readout for Antigravity CLI (agy).
#
#   ./install.sh    copy the plugin into agy's plugin folder and link the `readout` command
#
# agy runs the installed copy, not this repo, so re-run this after pulling or editing.
# Override the locations with VOICE_READOUT_PLUGIN_DIR and VOICE_READOUT_BIN_DIR.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_DIR="${VOICE_READOUT_PLUGIN_DIR:-$HOME/.gemini/config/plugins/voice-readout}"
BIN_DIR="${VOICE_READOUT_BIN_DIR:-$HOME/.local/bin}"
COMPONENTS=(plugin.json hooks.json README.md commands skills scripts)

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  sed -n '2,7p' "$0" | sed 's/^# \{0,1\}//'
  exit 0
fi

if [[ -e "$PLUGIN_DIR" && "$REPO_DIR" -ef "$PLUGIN_DIR" ]]; then
  echo "Running from the installed copy at $PLUGIN_DIR; nothing to copy."
else
  mkdir -p "$PLUGIN_DIR"
  for item in "${COMPONENTS[@]}"; do
    rm -rf "${PLUGIN_DIR:?}/$item"
    cp -R "$REPO_DIR/$item" "$PLUGIN_DIR/$item"
  done
  find "$PLUGIN_DIR/scripts" -name __pycache__ -type d -prune -exec rm -rf {} +
  echo "✔ Plugin copied to $PLUGIN_DIR"
  if [[ -d "$PLUGIN_DIR/.git" ]]; then
    echo "  (that folder is a git clone; 'git status' there will now show this repo's changes)"
  fi
fi

chmod +x "$PLUGIN_DIR"/scripts/*.py
mkdir -p "$BIN_DIR"
ln -sfn "$PLUGIN_DIR/scripts/toggle.py" "$BIN_DIR/readout"
echo "✔ 'readout' command linked at $BIN_DIR/readout"

# Warn about anything that would make playback fall back to the robotic system voice.
missing=()
python3 -c "import edge_tts" 2>/dev/null || missing+=("edge-tts")
python3 -c "import gtts" 2>/dev/null || missing+=("gTTS")
if ((${#missing[@]})); then
  echo "! Missing Python packages: ${missing[*]}. Install with: python3 -m pip install --user ${missing[*]}"
fi
if ! command -v ffplay >/dev/null && ! command -v mpv >/dev/null && ! command -v cvlc >/dev/null; then
  echo "! No audio player found. Install ffmpeg (for ffplay), mpv or vlc to hear neural voices."
fi
case ":$PATH:" in
  *":$BIN_DIR:"*) ;;
  *) echo "! $BIN_DIR is not on your PATH, so the 'readout' command won't be found until you add it." ;;
esac

echo "Done. Hook scripts update on the next agy turn; restart agy to reload commands and skills."

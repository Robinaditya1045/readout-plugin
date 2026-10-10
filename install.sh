#!/usr/bin/env bash
# Installs, updates or removes voice-readout for your coding agents.
#
#   ./install.sh                     install for every supported agent found on this machine
#   ./install.sh agy claude codex    install for the agents you name
#   ./install.sh uninstall [agents]  remove it again (all agents by default)
#
# Re-run after pulling or editing this repo. Locations can be overridden with
# VOICE_READOUT_SHARE_DIR, VOICE_READOUT_PLUGIN_DIR (agy), VOICE_READOUT_BIN_DIR and CODEX_HOME.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SHARE_DIR="${VOICE_READOUT_SHARE_DIR:-$HOME/.local/share/voice-readout}"
AGY_PLUGIN_DIR="${VOICE_READOUT_PLUGIN_DIR:-$HOME/.gemini/config/plugins/voice-readout}"
BIN_DIR="${VOICE_READOUT_BIN_DIR:-$HOME/.local/bin}"
CODEX_DIR="${CODEX_HOME:-$HOME/.codex}"
AGENTS=(agy claude codex)

usage() { sed -n '2,9p' "$0" | sed 's/^# \{0,1\}//'; }

# copy_into <dest> <repo items...>: replace those items in dest with the repo's copies.
copy_into() {
  local dest="$1"
  shift
  if [[ -e "$dest" && "$REPO_DIR" -ef "$dest" ]]; then
    return
  fi
  mkdir -p "$dest"
  for item in "$@"; do
    rm -rf "${dest:?}/$item"
    cp -R "$REPO_DIR/$item" "$dest/$item"
  done
  find "$dest" -name __pycache__ -type d -prune -exec rm -rf {} +
  chmod +x "$dest"/scripts/*.py
}

# codex_hook <add|remove>: edit the voice-readout Stop hook in Codex's hooks.json, keeping everything else.
codex_hook() {
  python3 - "$1" "$CODEX_DIR/hooks.json" "python3 \"$SHARE_DIR/scripts/readout.py\"" <<'PY'
import json, os, sys
action, path, command = sys.argv[1:]
data = {}
if os.path.exists(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
stop = data.setdefault("hooks", {}).setdefault("Stop", [])
for group in stop:
    group["hooks"] = [h for h in group.get("hooks", []) if "scripts/readout.py" not in h.get("command", "")]
stop[:] = [g for g in stop if g.get("hooks")]
if action == "add":
    stop.append({"hooks": [{"type": "command", "command": command, "timeout": 30}]})
if not stop:
    del data["hooks"]["Stop"]
os.makedirs(os.path.dirname(path), exist_ok=True)
with open(path, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2)
    f.write("\n")
PY
}

install_runtime() {
  copy_into "$SHARE_DIR" scripts bin
  mkdir -p "$BIN_DIR"
  ln -sfn "$SHARE_DIR/scripts/toggle.py" "$BIN_DIR/readout"
  echo "✔ Runtime installed to $SHARE_DIR, 'readout' command linked at $BIN_DIR/readout"
}

install_agent() {
  case "$1" in
    agy)
      copy_into "$AGY_PLUGIN_DIR" plugin.json hooks.json README.md commands skills scripts
      echo "✔ agy: plugin copied to $AGY_PLUGIN_DIR (restart agy to reload commands and skills)"
      ;;
    claude)
      # A marketplace added from a local path loads the plugin in place from this repo.
      claude plugin marketplace add "$REPO_DIR" >/dev/null
      claude plugin install voice-readout@voice-readout >/dev/null
      echo "✔ Claude Code: plugin installed from $REPO_DIR (run /reload-plugins or start a new session)"
      ;;
    codex)
      codex_hook add
      echo "✔ Codex: Stop hook added to $CODEX_DIR/hooks.json"
      echo "  → Open Codex and run /hooks once to trust it; Codex skips new hooks until you do."
      ;;
  esac
}

uninstall_agent() {
  case "$1" in
    agy)
      if grep -qs '"name": "voice-readout"' "$AGY_PLUGIN_DIR/plugin.json" && ! [[ "$REPO_DIR" -ef "$AGY_PLUGIN_DIR" ]]; then
        rm -rf "$AGY_PLUGIN_DIR"
        echo "✔ agy: removed $AGY_PLUGIN_DIR"
      fi
      ;;
    claude)
      if command -v claude >/dev/null; then
        claude plugin uninstall voice-readout@voice-readout >/dev/null 2>&1 || true
        claude plugin marketplace remove voice-readout >/dev/null 2>&1 || true
        echo "✔ Claude Code: plugin and marketplace removed"
      fi
      ;;
    codex)
      if [[ -f "$CODEX_DIR/hooks.json" ]]; then
        codex_hook remove
        echo "✔ Codex: Stop hook removed from $CODEX_DIR/hooks.json"
      fi
      ;;
  esac
}

agent_present() {
  case "$1" in
    agy) command -v agy >/dev/null || [[ -d "$HOME/.gemini/config/plugins" ]] ;;
    claude) command -v claude >/dev/null ;;
    codex) command -v codex >/dev/null ;;
  esac
}

check_dependencies() {
  local missing=()
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
}

mode=install
if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
elif [[ "${1:-}" == "uninstall" ]]; then
  mode=uninstall
  shift
fi

targets=("$@")
for agent in ${targets[@]+"${targets[@]}"}; do
  if [[ ! " ${AGENTS[*]} " == *" $agent "* ]]; then
    echo "Unknown agent '$agent'. Choose from: ${AGENTS[*]}" >&2
    exit 1
  fi
done

if [[ "$mode" == uninstall ]]; then
  ((${#targets[@]})) || targets=("${AGENTS[@]}")
  for agent in "${targets[@]}"; do uninstall_agent "$agent"; done
  if [[ "$#" -eq 0 ]]; then
    rm -f "$BIN_DIR/readout"
    [[ "$REPO_DIR" -ef "$SHARE_DIR" ]] || rm -rf "${SHARE_DIR:?}"
    echo "✔ Removed $SHARE_DIR and $BIN_DIR/readout (your settings in ~/.config/voice-readout are kept)"
  fi
  exit 0
fi

if ! ((${#targets[@]})); then
  for agent in "${AGENTS[@]}"; do
    if agent_present "$agent"; then targets+=("$agent"); fi
  done
  if ! ((${#targets[@]})); then
    echo "No supported agent found (agy, claude or codex). Name one explicitly: ./install.sh agy" >&2
    exit 1
  fi
fi

install_runtime
for agent in "${targets[@]}"; do install_agent "$agent"; done
check_dependencies
echo "Done. Try it with: readout test"

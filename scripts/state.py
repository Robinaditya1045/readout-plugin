#!/usr/bin/env python3
"""
state.py - Where voice-readout keeps its config and runtime state.

Shared by every supported agent (agy, Claude Code, Codex), so one config and one
player PID file apply everywhere: a new readout from any agent cancels the previous one.
Set VOICE_READOUT_HOME to use a different directory.
"""

import json
import os
from pathlib import Path

STATE_DIR = Path(os.environ.get("VOICE_READOUT_HOME") or Path.home() / ".config" / "voice-readout")
CONFIG_PATH = STATE_DIR / "config.json"
PID_FILE = STATE_DIR / "player.pid"
LAST_TEXT_FILE = STATE_DIR / "last.txt"  # the last text spoken, for `readout replay`
LAST_RESPONSE_FILE = STATE_DIR / "last_response.md"  # the last raw response, even when readout is off
LOG_FILE = STATE_DIR / "hook.log"

# Versions before 2.0 kept the config under agy's own directory.
LEGACY_CONFIG_PATH = Path.home() / ".gemini" / "antigravity-cli" / "voice_readout_config.json"

DEFAULT_CONFIG = {
    "enabled": True,
    "mode": "explain",  # "explain" (conversational brief) or "direct" (verbatim readout)
    "voice": "en-US-AvaNeural",  # the "siri" preset
    "speech_rate": "+0%",
    "max_chars": 2000,
    "include_code_notice": True,
}


def load_config() -> dict:
    config = dict(DEFAULT_CONFIG)
    for path in (CONFIG_PATH, LEGACY_CONFIG_PATH):
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    config.update(json.load(f))
            except Exception:
                pass
            break
    return config


def save_config(config: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)

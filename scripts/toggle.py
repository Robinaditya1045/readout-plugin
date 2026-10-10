#!/usr/bin/env python3
"""
CLI helper to toggle and configure the voice-readout plugin for Antigravity CLI.
Usage:
  python3 scripts/toggle.py on
  python3 scripts/toggle.py off
  python3 scripts/toggle.py status
  python3 scripts/toggle.py test
"""

import json
import sys
from pathlib import Path

CONFIG_PATH = Path.home() / ".gemini" / "antigravity-cli" / "voice_readout_config.json"


def load_config() -> dict:
    default_config = {
        "enabled": True,
        "max_chars": 2000,
        "cancel_previous": True,
        "include_code_notice": True,
        "speech_rate": 0,
        "engine": "auto",
    }
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                saved = json.load(f)
                default_config.update(saved)
        except Exception:
            pass
    return default_config


def save_config(config: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)


def main():
    args = sys.argv[1:]
    action = args[0].lower() if args else "status"

    config = load_config()

    if action in ("on", "enable", "start"):
        config["enabled"] = True
        save_config(config)
        print("🔊 Voice readout ENABLED. Model responses will be read aloud.")
    elif action in ("off", "disable", "stop"):
        config["enabled"] = False
        save_config(config)
        print("🔇 Voice readout DISABLED. Responses will remain silent.")
    elif action == "status":
        state = "ENABLED" if config.get("enabled", True) else "DISABLED"
        symbol = "🔊" if config.get("enabled", True) else "🔇"
        print(f"{symbol} Voice readout status: {state}")
        print(f"   Config file: {CONFIG_PATH}")
        print(f"   Engine: {config.get('engine', 'auto')}")
        print(f"   Max chars: {config.get('max_chars', 2000)}")
        print(f"   Speech rate: {config.get('speech_rate', 0)}")
    elif action == "test":
        from readout import speak_text
        print("Testing TTS engine...")
        speak_text("Antigravity voice readout is working properly.", config)
        print("Spoken audio triggered!")
    else:
        print("Usage: toggle.py [on|off|status|test]")
        sys.exit(1)


if __name__ == "__main__":
    main()

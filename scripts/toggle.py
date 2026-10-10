#!/usr/bin/env python3
"""
CLI helper to toggle, configure, switch modes and voices for the voice-readout plugin.
Usage:
  python3 scripts/toggle.py on
  python3 scripts/toggle.py off
  python3 scripts/toggle.py mode [explain|direct]
  python3 scripts/toggle.py voice [name]
  python3 scripts/toggle.py status
  python3 scripts/toggle.py test
"""

import json
import sys
from pathlib import Path

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from player import VOICE_ALIASES

CONFIG_PATH = Path.home() / ".gemini" / "antigravity-cli" / "voice_readout_config.json"


def load_config() -> dict:
    default_config = {
        "enabled": True,
        "mode": "explain",  # "explain" (conversational brief) or "direct" (verbatim)
        "voice": "en-US-AvaNeural",
        "speech_rate": "+0%",
        "max_chars": 2000,
        "include_code_notice": True,
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


def print_available_voices():
    print("Available natural neural voice presets:")
    print("  - siri / ava      : en-US-AvaNeural (Natural female, modern assistant)")
    print("  - emma            : en-US-EmmaNeural (Warm conversational female)")
    print("  - aria            : en-US-AriaNeural (Expressive female)")
    print("  - jenny           : en-US-JennyNeural (Clear female)")
    print("  - andrew          : en-US-AndrewNeural (Natural conversational male)")
    print("  - brian           : en-US-BrianNeural (Professional male)")
    print("  - guy             : en-US-GuyNeural (Casual male)")
    print("  - google          : gtts (Classic Google Assistant / Translate voice)")
    print("\nTo set: python3 scripts/toggle.py voice <name>")


def print_mode_info(current_mode: str):
    print(f"Current mode: {current_mode.upper()}")
    print("\nAvailable modes:")
    print("  - explain (Default) : Conversational companion. Summarizes the key takeaway,")
    print("                        explains choices, announces commands naturally,")
    print("                        and highlights closing questions.")
    print("  - direct            : Verbatim readout. Reads the full response directly")
    print("                        (with markdown syntax cleaned).")
    print("\nTo switch mode:")
    print("  python3 scripts/toggle.py mode explain")
    print("  python3 scripts/toggle.py mode direct")


def main():
    args = sys.argv[1:]
    action = args[0].lower() if args else "status"

    config = load_config()

    if action in ("on", "enable", "start"):
        config["enabled"] = True
        save_config(config)
        print("🔊 Voice readout ENABLED. Model responses will be spoken aloud.")

    elif action in ("off", "disable", "stop"):
        config["enabled"] = False
        save_config(config)
        print("🔇 Voice readout DISABLED. Responses will remain silent.")

    elif action == "mode":
        if len(args) > 1:
            target_mode = args[1].lower()
            if target_mode in ("explain", "brief", "summary", "companion"):
                config["mode"] = "explain"
                save_config(config)
                print("🧠 Mode set to: EXPLAIN (Conversational brief with command announcements)")
            elif target_mode in ("direct", "verbatim", "readout", "full"):
                config["mode"] = "direct"
                save_config(config)
                print("📖 Mode set to: DIRECT (Verbatim readout of full response)")
            else:
                print(f"Unknown mode '{args[1]}'. Choose 'explain' or 'direct'.")
        else:
            print_mode_info(config.get("mode", "explain"))

    elif action == "voice":
        if len(args) > 1:
            voice_choice = args[1].lower()
            resolved = VOICE_ALIASES.get(voice_choice, args[1])
            config["voice"] = resolved
            save_config(config)
            print(f"🎙️ Voice updated to: {resolved}")
        else:
            print_available_voices()

    elif action == "status":
        state = "ENABLED" if config.get("enabled", True) else "DISABLED"
        symbol = "🔊" if config.get("enabled", True) else "🔇"
        mode = config.get("mode", "explain").upper()
        voice = config.get("voice", "en-US-AvaNeural")
        print(f"{symbol} Voice readout status: {state}")
        print(f"   Mode: {mode}")
        print(f"   Voice: {voice}")
        print(f"   Speech rate: {config.get('speech_rate', '+0%')}")
        print(f"   Config file: {CONFIG_PATH}")

    elif action == "test":
        from readout import prepare_speech_content, speak_text
        test_markdown = """
The configuration has been updated successfully.
To apply changes, run:
```bash
agy plugin list
```
Would you like to test another voice?
"""
        spoken = prepare_speech_content(test_markdown, config)
        print(f"Testing [{config.get('mode', 'explain').upper()} mode]: \"{spoken}\"")
        speak_text(spoken, config)
        print("Audio playback triggered!")

    else:
        print("Usage: toggle.py [on|off|mode [explain|direct]|voice [name]|status|test]")
        sys.exit(1)


if __name__ == "__main__":
    main()

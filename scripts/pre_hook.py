#!/usr/bin/env python3
"""
pre_hook.py - PreInvocation hook for voice-readout.

Intercepts /readout commands before the model generates reasoning or tool calls.
Executes the toggle/configuration action instantly in <1ms and injects the result
so the model confirms it in a single quick step without wasting time on deliberation
or tool invocation round-trips.
"""

import json
import os
import re
import sys
from pathlib import Path

# Add scripts directory to path
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import toggle


def parse_readout_command(prompt: str):
    """Detects if prompt is a /readout command and extracts arguments."""
    prompt = prompt.strip()
    match = re.search(r"(?:/readout|/voice-readout:readout)\s*(.*)", prompt, re.IGNORECASE)
    if not match:
        return None
    arg_str = match.group(1).strip()
    return arg_str.split() if arg_str else []


def execute_toggle_action(args):
    action = args[0].lower() if args else "status"
    config = toggle.load_config()

    if action in ("on", "enable", "start"):
        config["enabled"] = True
        toggle.save_config(config)
        return "🔊 Voice readout ENABLED. Model responses will be spoken aloud."

    elif action in ("off", "disable", "stop"):
        config["enabled"] = False
        toggle.save_config(config)
        return "🔇 Voice readout DISABLED. Responses will remain silent."

    elif action == "mode":
        if len(args) > 1:
            target_mode = args[1].lower()
            if target_mode in ("explain", "brief", "summary", "companion"):
                config["mode"] = "explain"
                toggle.save_config(config)
                return "🧠 Mode set to: EXPLAIN (Conversational brief with command announcements)"
            elif target_mode in ("direct", "verbatim", "readout", "full"):
                config["mode"] = "direct"
                toggle.save_config(config)
                return "📖 Mode set to: DIRECT (Verbatim readout of full response)"
            else:
                return f"Unknown mode '{args[1]}'. Choose 'explain' or 'direct'."
        else:
            return f"Current mode: {config.get('mode', 'explain').upper()}"

    elif action == "voice":
        if len(args) > 1:
            voice_choice = args[1].lower()
            resolved = toggle.VOICE_ALIASES.get(voice_choice, args[1])
            config["voice"] = resolved
            toggle.save_config(config)
            return f"🎙️ Voice updated to: {resolved}"
        else:
            return f"Current voice: {config.get('voice', 'en-US-AvaNeural')}"

    elif action == "status":
        state = "ENABLED" if config.get("enabled", True) else "DISABLED"
        symbol = "🔊" if config.get("enabled", True) else "🔇"
        mode = config.get("mode", "explain").upper()
        voice = config.get("voice", "en-US-AvaNeural")
        return f"{symbol} Voice readout status: {state} | Mode: {mode} | Voice: {voice}"

    return None


def main():
    hook_output = {"injectSteps": []}

    try:
        raw_input = sys.stdin.read()
        if not raw_input.strip():
            sys.stdout.write(json.dumps(hook_output) + "\n")
            return

        payload = json.loads(raw_input)
        transcript_path_str = payload.get("transcriptPath")

        if transcript_path_str and os.path.exists(transcript_path_str):
            with open(transcript_path_str, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()

            latest_user_prompt = ""
            for line in reversed(lines):
                line = line.strip()
                if not line:
                    continue
                try:
                    step = json.loads(line)
                    if step.get("type") == "USER_INPUT":
                        latest_user_prompt = step.get("content", "")
                        break
                except Exception:
                    continue

            # Strip XML tags like <USER_REQUEST> if present
            clean_prompt = re.sub(r"<[^>]+>", "", latest_user_prompt).strip()
            args = parse_readout_command(clean_prompt)

            if args is not None:
                result_msg = execute_toggle_action(args)
                if result_msg:
                    hook_output["injectSteps"].append({
                        "ephemeralMessage": (
                            f"[Voice Readout System]: The command has already been executed instantly:\n"
                            f"{result_msg}\n\n"
                            f"CRITICAL: Do NOT call run_command or any tool. Output the exact confirmation message above directly."
                        )
                    })

    except Exception:
        pass
    finally:
        sys.stdout.write(json.dumps(hook_output) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()

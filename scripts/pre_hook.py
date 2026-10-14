#!/usr/bin/env python3
"""
pre_hook.py - Instant /readout handling, before the model runs.

- agy (PreInvocation): executes the action and injects the result so the model
  confirms it in a single quick step without tool calls.
- Claude Code (UserPromptExpansion): executes the action and blocks the command's
  expansion, so it never costs a model turn; the result is shown to the user.
"""

import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

# Add scripts directory to path
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import state
import toggle

def log_event(message: str):
    try:
        state.LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(state.LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().isoformat()}] {message}\n")
    except Exception:
        pass


def parse_readout_command(prompt: str):
    """Detects if prompt is a /readout command and extracts arguments.

    Only a request that starts with the command counts, so a prompt that merely
    mentions /readout (or metadata appended after the request) never toggles anything.
    """
    request = re.search(r"<USER_REQUEST>(.*?)</USER_REQUEST>", prompt, re.DOTALL)
    text = request.group(1) if request else re.sub(r"<[^>]+>", "", prompt)
    match = re.match(r"\s*/(?:voice-readout:)?readout\b[ \t]*([^\n]*)", text, re.IGNORECASE)
    if not match:
        return None
    arg_str = match.group(1).strip()
    return arg_str.split() if arg_str else []


def execute_toggle_action(args, payload=None):
    action = args[0].lower() if args else "status"
    config = toggle.load_config()

    if action in ("on", "enable", "start"):
        config["enabled"] = True
        toggle.save_config(config)
        return "🔊 Voice readout ENABLED. Model responses will be spoken aloud."

    elif action in toggle.OFF_ACTIONS:
        config["enabled"] = False
        toggle.save_config(config)
        toggle.stop_playback()
        return "🔇 Voice readout DISABLED. Responses will remain silent."

    elif action in toggle.STOP_ACTIONS:
        return toggle.stop_speech()

    elif action in toggle.REPLAY_ACTIONS:
        return toggle.replay_last(config)

    elif action in toggle.LAST_ACTIONS:
        return toggle.read_last(config, payload)

    elif action == "test":
        return toggle.speak_test(config)

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
        status = "ENABLED" if config.get("enabled", True) else "DISABLED"
        symbol = "🔊" if config.get("enabled", True) else "🔇"
        mode = config.get("mode", "explain").upper()
        voice = config.get("voice", "en-US-AvaNeural")
        return f"{symbol} Voice readout status: {status} | Mode: {mode} | Voice: {voice}"

    return None


def handle_agy(payload: dict, start_time: float) -> dict:
    hook_output = {"injectSteps": []}
    transcript_path_str = payload.get("transcriptPath")
    if not transcript_path_str or not os.path.exists(transcript_path_str):
        return hook_output

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

    args = parse_readout_command(latest_user_prompt)
    clean_prompt = re.sub(r"<[^>]+>", "", latest_user_prompt).strip().split("\n")[0]

    if args is not None:
        result_msg = execute_toggle_action(args, payload)
        elapsed_ms = (time.time() - start_time) * 1000
        log_event(f"Intercepted '{clean_prompt}' -> Executed {args} in {elapsed_ms:.2f}ms -> Result: '{result_msg}'")

        if result_msg:
            hook_output["injectSteps"].append({
                "ephemeralMessage": (
                    f"[Voice Readout System]: The command has already been executed instantly:\n"
                    f"{result_msg}\n\n"
                    f"CRITICAL: Do NOT call run_command or any tool. Output the exact confirmation message above directly."
                )
            })
    return hook_output


def handle_claude_expansion(payload: dict, start_time: float):
    """Runs `/readout <action>` and blocks the expansion. Unknown actions fall through to the skill."""
    name = (payload.get("command_name") or "").lstrip("/").split(":")[-1]
    if name != "readout":
        return None
    args = (payload.get("command_args") or "").split()
    result_msg = execute_toggle_action(args, payload)
    elapsed_ms = (time.time() - start_time) * 1000
    log_event(f"Claude Code /readout {' '.join(args)} -> {elapsed_ms:.2f}ms -> Result: '{result_msg}'")
    if not result_msg:
        return None
    return {
        "decision": "block",
        "reason": result_msg,
        "hookSpecificOutput": {"hookEventName": "UserPromptExpansion", "suppressOriginalPrompt": True},
    }


def main():
    start_time = time.time()
    hook_output = {"injectSteps": []}  # agy expects this shape even when nothing happens

    try:
        raw_input = sys.stdin.read()
        if not raw_input.strip():
            return  # the finally block writes the (empty) hook output exactly once

        payload = json.loads(raw_input)
        if payload.get("hook_event_name") == "UserPromptExpansion":
            hook_output = None  # Claude Code: print nothing unless we handle the command
            hook_output = handle_claude_expansion(payload, start_time)
        else:
            hook_output = handle_agy(payload, start_time)

    except Exception as e:
        log_event(f"Error in pre_hook: {e}")
    finally:
        if hook_output is not None:
            sys.stdout.write(json.dumps(hook_output) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()

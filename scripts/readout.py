#!/usr/bin/env python3
"""
voice-readout hook script for Google Antigravity CLI (agy).
Executed automatically on the 'Stop' lifecycle event.

Supports two reading modes:
1. 'direct'  : Reads the full model response directly (with markdown cleaned).
2. 'explain' : Intelligently summarizes and explains the response on the go,
               highlighting key takeaways, options, and commands naturally.
"""

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

# Add scripts directory to path
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from explainer import explain_response
from markdown_speech import parse_markdown, render_full, strip_thinking

CONFIG_PATH = Path.home() / ".gemini" / "antigravity-cli" / "voice_readout_config.json"

DEFAULT_CONFIG = {
    "enabled": True,
    "mode": "explain",  # "explain" (conversational brief) or "direct" (verbatim readout)
    "voice": "en-US-AvaNeural",  # Natural assistant voice
    "speech_rate": "+0%",
    "max_chars": 2000,
    "include_code_notice": True,
}


def load_config() -> dict:
    config = dict(DEFAULT_CONFIG)
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                user_config = json.load(f)
                config.update(user_config)
        except Exception:
            pass
    return config


def clean_markdown_for_speech(text: str, include_code_notice: bool = True, max_chars: int = 2000) -> str:
    """Verbatim mode cleaner: strips markdown noise while preserving full text."""
    if not text:
        return ""

    blocks = parse_markdown(strip_thinking(text))
    text = render_full(blocks, include_code_notice=include_code_notice)

    if max_chars and len(text) > max_chars:
        cut_text = text[:max_chars]
        last_punct = max(cut_text.rfind("."), cut_text.rfind("!"), cut_text.rfind("?"))
        if last_punct > max_chars // 2:
            text = cut_text[: last_punct + 1] + " Response truncated."
        else:
            text = cut_text.rstrip() + "... Response truncated."

    return text


def content_text(content) -> str:
    """Step content is normally a string, but tolerate a list of text parts."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [p if isinstance(p, str) else (p.get("text") or "") for p in content if isinstance(p, (str, dict))]
        return "\n".join(p for p in parts if p)
    return ""


def extract_model_response(hook_input: dict) -> str:
    # 1. Environment variable fallback
    env_text = os.environ.get("ANTIGRAVITY_RESPONSE_TEXT")
    if env_text:
        return env_text

    # 2. Extract from transcriptPath passed in hook JSON
    transcript_path_str = hook_input.get("transcriptPath")
    if not transcript_path_str:
        return ""

    transcript_path = Path(transcript_path_str)
    full_path = transcript_path.parent / "transcript_full.jsonl"
    target_path = full_path if full_path.exists() else transcript_path

    if not target_path.exists():
        return ""

    try:
        with open(target_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        for line in reversed(lines):
            line = line.strip()
            if not line:
                continue
            try:
                step = json.loads(line)
            except Exception:
                continue

            # Stop at the turn boundary so a turn without a final message never
            # re-reads the previous turn's answer.
            if step.get("type") == "USER_INPUT":
                break
            if step.get("source") == "MODEL" and step.get("type") == "PLANNER_RESPONSE":
                content = content_text(step.get("content"))
                if content.strip():
                    return content
    except Exception:
        pass

    return ""


def normalize_rate(rate) -> str:
    """edge-tts only accepts signed percentages like '+10%'; accept 10, '10', '10%' too."""
    if isinstance(rate, (int, float)):
        return f"{int(rate):+d}%"
    m = re.fullmatch(r"\s*([+-]?)(\d+)\s*%?\s*", str(rate))
    if not m:
        return "+0%"
    return f"{m.group(1) or '+'}{m.group(2)}%"


def speak_text(text: str, config: dict) -> None:
    if not text:
        return

    voice = config.get("voice", "en-US-AvaNeural")
    rate = normalize_rate(config.get("speech_rate", "+0%"))

    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write(text)
            txt_path = f.name

        player_script = SCRIPT_DIR / "player.py"

        cmd = [
            sys.executable,
            str(player_script),
            "--voice",
            str(voice),
            "--rate",
            str(rate),
            "--file",
            txt_path,
        ]

        # Spawn detached player process
        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except Exception:
        pass


def prepare_speech_content(response_text: str, config: dict) -> str:
    mode = config.get("mode", "explain").lower()

    if mode in ("explain", "brief", "summary", "companion"):
        return explain_response(response_text, config)
    else:
        # "direct" / "verbatim"
        return clean_markdown_for_speech(
            response_text,
            include_code_notice=config.get("include_code_notice", True),
            max_chars=config.get("max_chars", 2000),
        )


def main():
    hook_output = "{}"

    try:
        raw_input = sys.stdin.read()
        hook_input = {}
        if raw_input.strip():
            try:
                hook_input = json.loads(raw_input)
            except Exception:
                pass

        config = load_config()

        if config.get("enabled", True):
            err = hook_input.get("error")
            if not err:
                response_text = extract_model_response(hook_input)
                spoken_content = prepare_speech_content(response_text, config)
                if spoken_content:
                    speak_text(spoken_content, config)

    except Exception:
        pass
    finally:
        sys.stdout.write(hook_output + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()

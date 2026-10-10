#!/usr/bin/env python3
"""
voice-readout audio player.
Handles neural synthesis (edge-tts / gTTS) and non-blocking playback,
with automatic fallback to system TTS if offline.
"""

import argparse
import asyncio
import os
import signal
import subprocess
import sys
import tempfile
from pathlib import Path

PID_FILE = Path.home() / ".gemini" / "antigravity-cli" / "voice_readout_player.pid"

VOICE_ALIASES = {
    "siri": "en-US-AvaNeural",
    "assistant": "en-US-AvaNeural",
    "ava": "en-US-AvaNeural",
    "emma": "en-US-EmmaNeural",
    "andrew": "en-US-AndrewNeural",
    "brian": "en-US-BrianNeural",
    "aria": "en-US-AriaNeural",
    "jenny": "en-US-JennyNeural",
    "guy": "en-US-GuyNeural",
    "google": "gtts",
}


def _is_player_process(pid: int) -> bool:
    """Guards against a stale PID file pointing at a reused, unrelated process."""
    try:
        with open(f"/proc/{pid}/cmdline", "rb") as f:
            return b"player.py" in f.read()
    except FileNotFoundError:
        if os.path.isdir("/proc"):
            return False  # Linux and the process is gone
    except Exception:
        pass
    try:
        out = subprocess.run(["ps", "-p", str(pid), "-o", "command="], capture_output=True, text=True)
        return "player.py" in out.stdout
    except Exception:
        return False


def kill_previous_playback():
    """Cancel any ongoing speech playback to prevent overlapping voices."""
    if not PID_FILE.exists():
        return
    try:
        with open(PID_FILE, "r") as f:
            old_pid = int(f.read().strip())
        if old_pid != os.getpid() and _is_player_process(old_pid):
            try:
                # The player runs in its own session (see readout.speak_text), so killing
                # its process group also stops the ffplay/mpv child that is producing sound.
                if hasattr(os, "killpg"):
                    os.killpg(old_pid, signal.SIGTERM)
                else:
                    os.kill(old_pid, signal.SIGTERM)
            except (ProcessLookupError, PermissionError):
                pass
    except Exception:
        pass
    finally:
        try:
            PID_FILE.unlink(missing_ok=True)
        except Exception:
            pass


def save_current_pid():
    PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))


def release_pid_file():
    """Remove the PID file only if it is still ours; a newer player may have replaced it."""
    try:
        with open(PID_FILE, "r") as f:
            if int(f.read().strip()) != os.getpid():
                return
        PID_FILE.unlink(missing_ok=True)
    except Exception:
        pass


def find_audio_player():
    """Find an available CLI audio player."""
    for player in ["ffplay", "mpv", "cvlc"]:
        if subprocess.run(["which", player], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0:
            return player
    return None


async def synthesize_edge_tts(text: str, voice: str, output_path: str, rate_str: str = "+0%") -> bool:
    try:
        import edge_tts

        resolved_voice = VOICE_ALIASES.get(voice.lower(), voice)
        communicate = edge_tts.Communicate(text, resolved_voice, rate=rate_str)
        await communicate.save(output_path)
        return os.path.exists(output_path) and os.path.getsize(output_path) > 0
    except Exception:
        return False


def synthesize_gtts(text: str, output_path: str) -> bool:
    try:
        from gtts import gTTS

        tts = gTTS(text=text, lang="en")
        tts.save(output_path)
        return os.path.exists(output_path) and os.path.getsize(output_path) > 0
    except Exception:
        return False


def fallback_system_tts(text: str):
    """Fallback to system TTS (spd-say on Linux, say on macOS, powershell on Windows)."""
    platform = sys.platform
    if platform.startswith("linux"):
        subprocess.run(["spd-say", text], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    elif platform == "darwin":
        subprocess.run(["say", text], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    elif platform in ("win32", "cygwin"):
        escaped = text.replace("'", "''")
        ps_code = f"Add-Type -AssemblyName System.Speech; (New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak('{escaped}')"
        subprocess.run(["powershell", "-NoProfile", "-Command", ps_code], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def play_audio_file(player: str, file_path: str):
    if player == "ffplay":
        cmd = ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", file_path]
    elif player == "mpv":
        cmd = ["mpv", "--no-video", "--really-quiet", file_path]
    elif player == "cvlc":
        cmd = ["cvlc", "--play-and-exit", "--quiet", file_path]
    else:
        return

    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main():
    parser = argparse.ArgumentParser(description="Voice readout audio player")
    parser.add_argument("--voice", default="en-US-AvaNeural", help="Voice name or alias")
    parser.add_argument("--rate", default="+0%", help="Speech rate offset (e.g. +10%, -10%)")
    parser.add_argument("--file", help="Path to text file containing speech content")
    args = parser.parse_args()

    # Exit through SystemExit when a newer player cancels us, so cleanup still runs.
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    kill_previous_playback()
    save_current_pid()

    text = ""
    if args.file and os.path.exists(args.file):
        with open(args.file, "r", encoding="utf-8") as f:
            text = f.read().strip()
        try:
            os.remove(args.file)  # temp file written by readout.speak_text
        except Exception:
            pass
    else:
        text = sys.stdin.read().strip()

    if not text:
        release_pid_file()
        return

    player = find_audio_player()
    played = False

    if player:
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            mp3_path = f.name

        try:
            # 1. Try edge-tts neural voice (unless explicitly set to google)
            if args.voice.lower() != "google":
                success = asyncio.run(synthesize_edge_tts(text, args.voice, mp3_path, args.rate))
                if success:
                    play_audio_file(player, mp3_path)
                    played = True

            # 2. Try gTTS (Google voice)
            if not played:
                success = synthesize_gtts(text, mp3_path)
                if success:
                    play_audio_file(player, mp3_path)
                    played = True
        finally:
            if os.path.exists(mp3_path):
                try:
                    os.remove(mp3_path)
                except Exception:
                    pass

    # 3. Fallback to offline system TTS if neural audio failed
    if not played:
        fallback_system_tts(text)

    release_pid_file()


if __name__ == "__main__":
    main()

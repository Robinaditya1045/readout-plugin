#!/usr/bin/env python3
"""
voice-readout audio player.
Streams neural speech (edge-tts / gTTS) into an audio player as it is synthesized,
so playback starts after the first chunk instead of after the whole response.
Falls back to system TTS if offline.
"""

import argparse
import asyncio
import os
import shutil
import signal
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import state

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

# Each player reads an MP3 stream from stdin and exits when it ends.
STREAM_COMMANDS = {
    "ffplay": ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", "-i", "pipe:0"],
    "mpv": ["mpv", "--no-video", "--really-quiet", "-"],
    "cvlc": ["cvlc", "--play-and-exit", "--quiet", "-"],
}

_system_tts_running = False


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


def stop_playback() -> bool:
    """Cancel any ongoing speech playback. Returns True if something was playing."""
    if not state.PID_FILE.exists():
        return False
    stopped = False
    try:
        with open(state.PID_FILE, "r") as f:
            old_pid = int(f.read().strip())
        if old_pid != os.getpid() and _is_player_process(old_pid):
            try:
                # The player runs in its own session (see readout.speak_text), so killing
                # its process group also stops the ffplay/mpv child that is producing sound.
                if hasattr(os, "killpg"):
                    os.killpg(old_pid, signal.SIGTERM)
                else:
                    os.kill(old_pid, signal.SIGTERM)
                stopped = True
            except (ProcessLookupError, PermissionError):
                pass
    except Exception:
        pass
    finally:
        try:
            state.PID_FILE.unlink(missing_ok=True)
        except Exception:
            pass
    return stopped


def save_current_pid():
    state.PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(state.PID_FILE, "w") as f:
        f.write(str(os.getpid()))


def release_pid_file():
    """Remove the PID file only if it is still ours; a newer player may have replaced it."""
    try:
        with open(state.PID_FILE, "r") as f:
            if int(f.read().strip()) != os.getpid():
                return
        state.PID_FILE.unlink(missing_ok=True)
    except Exception:
        pass


def save_last_text(text: str):
    """Remember what was read so `readout replay` can say it again."""
    try:
        state.LAST_TEXT_FILE.parent.mkdir(parents=True, exist_ok=True)
        state.LAST_TEXT_FILE.write_text(text, encoding="utf-8")
    except Exception:
        pass


def find_audio_player():
    """Find an available CLI audio player."""
    for player in STREAM_COMMANDS:
        if shutil.which(player):
            return player
    return None


class PlayerPipe:
    """Feeds MP3 bytes to an audio player's stdin, starting it on the first chunk."""

    def __init__(self, player: str):
        self.command = STREAM_COMMANDS[player]
        self.proc = None

    @property
    def started(self) -> bool:
        return self.proc is not None

    def write(self, data: bytes):
        if self.proc is None:
            self.proc = subprocess.Popen(
                self.command, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
        self.proc.stdin.write(data)
        self.proc.stdin.flush()

    def finish(self):
        """Close the stream and wait for the player to finish speaking it."""
        if self.proc is None:
            return
        try:
            self.proc.stdin.close()
        except Exception:
            pass
        self.proc.wait()


async def stream_edge_tts(text: str, voice: str, rate: str, pipe: PlayerPipe):
    import edge_tts

    resolved_voice = VOICE_ALIASES.get(voice.lower(), voice)
    async for chunk in edge_tts.Communicate(text, resolved_voice, rate=rate).stream():
        if chunk["type"] == "audio":
            pipe.write(chunk["data"])


def stream_gtts(text: str, pipe: PlayerPipe):
    from gtts import gTTS

    for data in gTTS(text=text, lang="en").stream():
        pipe.write(data)


def fallback_system_tts(text: str):
    """Fallback to system TTS (spd-say on Linux, say on macOS, powershell on Windows)."""
    global _system_tts_running
    _system_tts_running = True
    platform = sys.platform
    if platform.startswith("linux"):
        # -w keeps spd-say (and so this player) alive until speech ends, so it can be stopped.
        subprocess.run(["spd-say", "-w", text], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    elif platform == "darwin":
        subprocess.run(["say", text], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    elif platform in ("win32", "cygwin"):
        escaped = text.replace("'", "''")
        ps_code = f"Add-Type -AssemblyName System.Speech; (New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak('{escaped}')"
        subprocess.run(["powershell", "-NoProfile", "-Command", ps_code], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    _system_tts_running = False


def _on_sigterm(*_):
    if _system_tts_running and sys.platform.startswith("linux"):
        # speech-dispatcher keeps talking after its client dies; cancel it explicitly.
        subprocess.run(["spd-say", "-C"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    sys.exit(0)  # exit through SystemExit so cleanup in finally blocks still runs


def speak(text: str, voice: str, rate: str) -> bool:
    """Streams neural speech to an audio player. Returns False if nothing could be played."""
    player = find_audio_player()
    if not player:
        return False
    pipe = PlayerPipe(player)
    try:
        if voice.lower() != "google":
            try:
                asyncio.run(stream_edge_tts(text, voice, rate, pipe))
            except Exception:
                pass
        # Only fall back to gTTS if edge-tts produced nothing; otherwise we'd repeat ourselves.
        if not pipe.started:
            try:
                stream_gtts(text, pipe)
            except Exception:
                pass
    finally:
        pipe.finish()
    return pipe.started


def main():
    parser = argparse.ArgumentParser(description="Voice readout audio player")
    parser.add_argument("--voice", default="en-US-AvaNeural", help="Voice name or alias")
    parser.add_argument("--rate", default="+0%", help="Speech rate offset (e.g. +10%, -10%)")
    parser.add_argument("--file", help="Path to text file containing speech content")
    args = parser.parse_args()

    signal.signal(signal.SIGTERM, _on_sigterm)
    stop_playback()
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

    try:
        if text:
            save_last_text(text)
            if not speak(text, args.voice, args.rate):
                fallback_system_tts(text)
    finally:
        release_pid_file()


if __name__ == "__main__":
    main()

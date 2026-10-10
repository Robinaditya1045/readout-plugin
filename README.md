# Antigravity Voice Readout Plugin (`voice-readout`)

An open-source plugin for **Google Antigravity CLI (`agy`)** that reads out or explains agent responses as natural, high-definition spoken audio using neural voices (Siri / Google Assistant quality).

---

## Features & Two Operating Modes

The plugin supports two speech modes:

### 1. 🧠 `explain` Mode (Default / Conversational Companion)
Instead of reading 50 lines of technical markdown verbatim, this mode explains the answer on the go:
- **Core Takeaway**: Summarizes the diagnosis, root cause, or direct answer in 1-2 sentences.
- **Multiple Options/Methods**: Identifies high-level approaches (e.g. *"Method 1: Enroll Key, or Method 2: Disable Secure Boot"*).
- **Spoken Terminal Commands**: Instead of ignoring code or droning through punctuation, it naturally announces actionable commands (e.g. *"First run: `sudo mokutil ...`, then: `sudo reboot`"*).
- **Code Snippets**: Informs you naturally when code or scripts are provided (e.g. *"A Python snippet is provided to implement the helper function"*).
- **Next Steps & Questions**: Highlights follow-up questions so you can answer immediately.

### 2. 📖 `direct` Mode (Verbatim Readout)
Reads out the full text of the response word-for-word, stripping out markdown formatting and code fences so speech flows cleanly.

---

## Audio & Voice Quality

- 🎙️ **Studio Neural Voices**: Powered by Edge Neural TTS and Google TTS (`en-US-AvaNeural`, `en-US-AndrewNeural`, `en-US-EmmaNeural`, `gTTS`).
- ⚡ **Non-Blocking Background Playback**: Synthesizes and plays audio asynchronously via `ffplay` without delaying or freezing the CLI.
- 🛑 **Instant Cancellation**: Interrupts and cancels previous speech as soon as a new response turn completes.
- 🌐 **Offline Fallback**: Automatically falls back to system TTS (`spd-say` on Linux, `say` on macOS, PowerShell on Windows) if offline.

---

## Directory Structure

```
voice_readout_plugin/
├── plugin.json              # Plugin manifest
├── hooks.json               # PreInvocation & Stop lifecycle hooks
├── commands/
│   └── readout.md           # Slash command definition (/readout)
├── skills/
│   └── readout/
│       └── SKILL.md         # Fast zero-deliberation skill definition
├── scripts/
│   ├── readout.py           # Stop hook entry point and mode router
│   ├── pre_hook.py          # PreInvocation hook for instant toggle handling
│   ├── explainer.py         # Conversational summary and command extractor
│   ├── player.py            # Neural TTS synthesis and audio playback
│   └── toggle.py            # CLI toggle, mode switcher, and voice selector
├── tests/
│   └── test_readout.py      # Unit test suite
└── README.md
```

---

## Ultra-Fast Control (Zero Deliberation)

You have multiple ways to toggle or configure voice readout:

### 1. Instant Shell Command (Fastest: < 50ms, Zero AI Thinking)
Installed to `~/.local/bin/readout`:
- From terminal:
  ```bash
  readout off              # Instant mute
  readout on               # Instant unmute
  readout mode explain     # Switch to explain mode
  readout mode direct      # Switch to direct mode
  readout voice siri       # Switch voice
  readout status           # View status
  ```
- Inside `agy` session: Prefix with `!` to execute immediately without calling the AI model:
  ```text
  !readout off
  !readout on
  ```

### 2. Slash Command (`/readout`) with PreInvocation Acceleration
When using `/readout off` or `/readout on` in `agy`, the plugin's `PreInvocation` hook executes the configuration change instantly in <1ms and bypasses unnecessary tool-use planning, responding in a single quick turn.

---

## Configuration

Settings are saved in `~/.gemini/antigravity-cli/voice_readout_config.json`:

```json
{
  "enabled": true,
  "mode": "explain",
  "voice": "en-US-AvaNeural",
  "speech_rate": "+0%",
  "max_chars": 2000,
  "include_code_notice": true
}
```

---

## Running Tests

```bash
python3 -m unittest discover tests
```

---

## License

MIT

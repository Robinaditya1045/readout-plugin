# Antigravity Voice Readout Plugin (`voice-readout`)

An open-source plugin for **Google Antigravity CLI (`agy`)** that automatically reads out agent responses as natural, high-definition spoken audio using neural voices (similar to Google Assistant and Siri).

---

## Features

- 🎙️ **Natural Neural Voices**: Uses state-of-the-art neural speech synthesis (via Microsoft Edge Neural TTS and Google TTS). No more robotic or cracked audio!
- ⚡ **Non-Blocking Playback**: Spawns synthesis and audio playback in a detached background process via `ffplay`/`mpv`, so `agy` turns finish instantly without hanging the terminal.
- 🧹 **Intelligent Markdown Cleaner**: Strips out code blocks, markdown links, asterisks, headers, and noisy syntax so speech flows naturally like conversation.
- 🛑 **Automatic Speech Interruption**: Cancels any previous speech as soon as a new response arrives to prevent overlapping audio.
- 🎛️ **Slash Command & Voice Selector**: Choose your favorite assistant voice (`siri`, `ava`, `andrew`, `emma`, `brian`, `google`) or mute/unmute at will.
- 🌐 **Offline Fallback**: Automatically falls back to local system TTS (`spd-say` / `say` / PowerShell) if internet is unavailable.

---

## How It Works (Antigravity Lifecycle Hooks)

When the agent finishes generating a response turn, Antigravity CLI triggers the **`Stop`** lifecycle hook defined in `hooks.json`. 

- The hook script receives turn metadata via **JSON on `stdin`**, including `transcriptPath`.
- It reads the latest model output from `transcript_full.jsonl`.
- It cleans the markdown and passes the plain text to the neural audio player.
- It returns `{}` immediately on `stdout` to satisfy Antigravity's hook contract.

---

## Directory Structure

```
voice_readout_plugin/
├── plugin.json              # Plugin manifest
├── hooks.json               # Stop lifecycle hook definition
├── commands/
│   └── readout.md           # Slash command definition (/readout)
├── scripts/
│   ├── readout.py           # Hook entry point and text cleaning
│   ├── player.py            # Neural TTS synthesis and audio playback
│   └── toggle.py            # CLI toggle and voice switcher
├── tests/
│   └── test_readout.py      # Unit tests
└── README.md
```

---

## Installation & Setup

### 1. Requirements

- Python 3.8+
- Audio player (`ffplay` or `mpv`):
  ```bash
  sudo apt install ffmpeg  # provides ffplay
  ```
- Neural TTS packages:
  ```bash
  pip install --user edge-tts gtts
  ```

### 2. Install the Plugin in Antigravity CLI

From this directory:

```bash
agy plugin install .
```

Verify that it appears in your plugin list:

```bash
agy plugin list
```

---

## Voice Selection & Commands

### Changing Voices

Choose from several high-quality natural voices:

```bash
python3 scripts/toggle.py voice siri     # Female assistant (en-US-AvaNeural)
python3 scripts/toggle.py voice andrew   # Male assistant (en-US-AndrewNeural)
python3 scripts/toggle.py voice emma     # Warm conversational female (en-US-EmmaNeural)
python3 scripts/toggle.py voice brian    # Professional male (en-US-BrianNeural)
python3 scripts/toggle.py voice google   # Classic Google voice (gTTS)
```

List all available presets:
```bash
python3 scripts/toggle.py voice
```

### Toggling & Testing

- **Disable voice**: `python3 scripts/toggle.py off`
- **Enable voice**: `python3 scripts/toggle.py on`
- **Check status**: `python3 scripts/toggle.py status`
- **Test audio**: `python3 scripts/toggle.py test`

---

## Configuration

Settings are saved in `~/.gemini/antigravity-cli/voice_readout_config.json`:

```json
{
  "enabled": true,
  "max_chars": 2000,
  "voice": "en-US-AvaNeural",
  "speech_rate": "+0%",
  "include_code_notice": true
}
```

---

## License

MIT

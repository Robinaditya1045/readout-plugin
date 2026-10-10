# Antigravity Voice Readout Plugin (`voice-readout`)

An open-source plugin for **Google Antigravity CLI (`agy`)** that automatically reads out agent responses as spoken audio via your operating system's Text-to-Speech (TTS) engine.

---

## Features

- 🎙️ **Hands-Free Readout**: Speaks the final model response automatically at the end of each turn.
- 🧹 **Intelligent Markdown Cleaner**: Strips out code blocks, markdown links, asterisks, headers, and noisy syntax so the voice audio sounds natural and clean.
- ⚡ **Non-Blocking & Asynchronous**: Spawns TTS in a detached background process so Antigravity CLI responses and commands never freeze or wait on speech completion.
- 🎛️ **Slash Command & Toggle Support**: Easily toggle speech on or off with `/readout on` and `/readout off` or inspect state with `/readout status`.
- 🌐 **Cross-Platform**:
  - **Linux**: Uses `spd-say` (speech-dispatcher) with fallback to `espeak-ng` or `espeak`.
  - **macOS**: Uses native `say`.
  - **Windows**: Uses PowerShell SAPI (`System.Speech.Synthesis`).

---

## How It Works (Antigravity Lifecycle Hooks)

Antigravity CLI plugins execute lifecycle hooks defined in `hooks.json`. When a turn completes, Antigravity fires the **`Stop`** hook. 

Unlike older or hypothetical documentation snippets:
- Context is passed to hook scripts via **JSON on `stdin`** (including `transcriptPath`, `conversationId`, etc.).
- The hook must output a JSON object (`{}`) on `stdout`.
- The plugin inspects the conversation log (`transcript_full.jsonl`) to retrieve the model's final response, formats the text, and feeds it to your system TTS engine.

---

## Directory Structure

```
voice_readout_plugin/
├── plugin.json              # Plugin manifest
├── hooks.json               # Stop lifecycle hook definition
├── commands/
│   └── readout.md           # Slash command definition (/readout)
├── scripts/
│   ├── readout.py           # Hook handler and speech pipeline
│   └── toggle.py            # CLI toggle and configuration utility
├── tests/
│   └── test_readout.py      # Unit tests
└── README.md
```

---

## Installation

### 1. Install via Antigravity CLI

From this repository directory, install the plugin into your global Antigravity configuration:

```bash
agy plugin install .
```

Verify that the plugin is installed:

```bash
agy plugin list
```

### 2. Verify Your System TTS Engine

- **Linux (Ubuntu/Debian)**:
  Ensure `speech-dispatcher` or `espeak-ng` is installed:
  ```bash
  sudo apt install speech-dispatcher
  spd-say "TTS is configured"
  ```
- **macOS**:
  `say` is built-in.
- **Windows**:
  PowerShell SAPI is built-in.

---

## Usage

Once installed, simply chat with `agy`:

```bash
agy -p "Summarize how neural networks learn in 2 sentences"
```

The response text will be displayed in the terminal and spoken aloud simultaneously.

### Slash Commands & Toggling

You can control voice readout at any time:

- **Inside `agy`**: Type `/readout on` or `/readout off`.
- **From terminal**:
  ```bash
  python3 scripts/toggle.py off    # Silence voice readout
  python3 scripts/toggle.py on     # Re-enable voice readout
  python3 scripts/toggle.py status # Check current configuration
  python3 scripts/toggle.py test   # Play a test speech sample
  ```

---

## Configuration

Preferences are stored in `~/.gemini/antigravity-cli/voice_readout_config.json`:

```json
{
  "enabled": true,
  "max_chars": 2000,
  "cancel_previous": true,
  "include_code_notice": true,
  "speech_rate": 0,
  "engine": "auto"
}
```

- **`enabled`**: Set `false` to mute readout.
- **`max_chars`**: Maximum number of characters to read before truncating.
- **`cancel_previous`**: Cancel any ongoing speech when a new response arrives.
- **`include_code_notice`**: Replaces code blocks with `"code block omitted"` instead of reading raw code.
- **`speech_rate`**: Speed modifier for `spd-say` (-100 to 100).
- **`engine`**: Force a specific engine (`"spd-say"`, `"espeak-ng"`, `"say"`, or `"auto"`).

---

## Running Tests

Run the test suite using `unittest`:

```bash
python3 -m unittest discover tests
```

---

## License

MIT

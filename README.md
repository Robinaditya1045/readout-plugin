# Antigravity Voice Readout Plugin (`voice-readout`)

An open-source plugin for **Google Antigravity CLI (`agy`)** that reads out or explains agent responses as natural, high-definition spoken audio using neural voices (Siri / Google Assistant quality).

---

## Features & Two Operating Modes

The plugin supports two speech modes:

### 1. 🧠 `explain` Mode (Default / Conversational Companion)
Instead of reading 50 lines of technical markdown verbatim, this mode explains the answer on the go. Short replies are read in full; longer ones are walked section by section:
- **Core Takeaway**: Summarizes the diagnosis, root cause, or direct answer in 1-2 sentences.
- **Sections, Steps & Options**: Gives each section's gist, reads numbered steps in order (*"first, ...; then, ...; and finally, ..."*) and announces alternatives (*"There are 2 options. Method 1: Enroll Key ... Method 2: Disable Secure Boot"*).
- **Every Terminal Command**: Reads every command from every code block (not just the first), next to the step or option it belongs to (e.g. *"Step 2: Install tmux: run sudo apt update, and then sudo apt install -y tmux"*). Console output, comments, heredoc bodies and test logs are skipped; `&&`, `|` and `;` are spoken naturally.
- **Lists & Tables**: Reads the highlights of change reports and key/value tables (*"Total URLs: 5 / 5; Status: 100% Succeeded"*) and summarizes wide tables.
- **Code Snippets**: Tells you what is on screen instead of reading it (e.g. *"there's a Python snippet for handler.py on screen"*).
- **Warnings, Next Steps & Questions**: Always reads `> [!WARNING]`-style callouts and the closing question, including offered choices, so you can answer immediately.

Long responses are kept to roughly `explain_max_chars` characters of prose (default `1000`); commands and warnings are never cut, and skipped sections are named (*"It also covers ..."*).

### 2. 📖 `direct` Mode (Verbatim Readout)
Reads out the full text of the response word-for-word, stripping out markdown formatting and code fences so speech flows cleanly.

---

## Audio & Voice Quality

- 🎙️ **Studio Neural Voices**: Powered by Edge Neural TTS and Google TTS (`en-US-AvaNeural`, `en-US-AndrewNeural`, `en-US-EmmaNeural`, `gTTS`).
- ⚡ **Streaming, Non-Blocking Playback**: Audio is streamed into `ffplay` (or `mpv` / `cvlc`) while it is still being synthesized, so speech starts about a second after a turn ends instead of after the whole response has been generated. It runs in the background without freezing the CLI.
- 🛑 **Instant Cancellation**: Interrupts previous speech as soon as a new response turn completes, or whenever you run `readout stop`.
- 🔁 **Replay**: `readout replay` reads the last response again.
- 🌐 **Offline Fallback**: Automatically falls back to system TTS (`spd-say` on Linux, `say` on macOS, PowerShell on Windows) if offline.

---

## Installation

```bash
git clone git@github.com:Robinaditya1045/readout-plugin.git
cd readout-plugin
./install.sh
```

`install.sh` copies the plugin into `~/.gemini/config/plugins/voice-readout`, links the `readout` command into `~/.local/bin`, and warns if anything needed for neural voices is missing (`edge-tts`, `gTTS`, and an audio player such as `ffplay`). agy runs that installed copy, so **re-run `./install.sh` after pulling or editing** the repo. Override the locations with `VOICE_READOUT_PLUGIN_DIR` and `VOICE_READOUT_BIN_DIR`.

---

## Directory Structure

```
voice_readout_plugin/
├── install.sh               # Installs/updates the plugin and the readout command
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
│   ├── markdown_speech.py   # Markdown parser and speech cleanup shared by both modes
│   ├── player.py            # Neural TTS synthesis and audio playback
│   └── toggle.py            # CLI toggle, mode switcher, and voice selector
├── tests/
│   ├── test_readout.py      # Modes, transcript parsing, hooks
│   ├── test_explainer.py    # Explain-mode response shapes and command extraction
│   └── test_player.py       # Streaming playback and engine fallback
└── README.md
```

---

## Ultra-Fast Control (Zero Deliberation)

You have multiple ways to toggle or configure voice readout:

### 1. Instant Shell Command (Fastest: < 50ms, Zero AI Thinking)
Installed to `~/.local/bin/readout`:
- From terminal:
  ```bash
  readout off              # Instant mute (also stops current speech)
  readout on               # Instant unmute
  readout stop             # Stop the current speech, keep readout on
  readout replay           # Read the last response again
  readout mode explain     # Switch to explain mode
  readout mode direct      # Switch to direct mode
  readout voice siri       # Switch voice
  readout status           # View status
  ```
- Inside `agy` session: Prefix with `!` to execute immediately without calling the AI model:
  ```text
  !readout stop
  !readout replay
  ```

### 2. Slash Command (`/readout`) with PreInvocation Acceleration
When using `/readout off`, `/readout stop`, `/readout replay` and the other `/readout` commands in `agy`, the plugin's `PreInvocation` hook executes the action instantly and bypasses unnecessary tool-use planning, responding in a single quick turn. The model's confirmation after `stop`, `replay` and `test` is not read aloud, so it never talks over (or cuts off) what you asked for.

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

Optional keys:
- `explain_max_chars` (default `1000`): soft limit on spoken prose in `explain` mode. `max_chars` limits `direct` mode.
- `use_llm` + `gemini_api_key` (or the `GEMINI_API_KEY` env var): have Gemini 2.5 Flash write the `explain` summary, falling back to the built-in explainer on any error.

---

## Running Tests

```bash
python3 -m unittest discover tests
```

---

## License

MIT

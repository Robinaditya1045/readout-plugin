# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A plugin that speaks coding-agent responses aloud with neural TTS, for **three agents from one repo**: Google Antigravity CLI (`agy`), Claude Code and Codex CLI. It is plain Python 3 with no build step. The TTS and LLM libraries (`edge_tts`, `gtts`, `google.genai`) are imported lazily inside `try` blocks, so every script runs without them and falls back gracefully.

The repo root is two plugins at once, and the two agents ignore each other's files (verified with both validators):
- **agy:** root `plugin.json` + root `hooks.json` (PreInvocation, Stop), plus `commands/` and `skills/`. agy does **not** read `hooks/hooks.json`.
- **Claude Code:** `.claude-plugin/plugin.json` + `.claude-plugin/marketplace.json` (`source: "./"`), `hooks/hooks.json` (Stop, UserPromptExpansion), `skills/`, and `bin/readout`, which goes on the Bash tool's PATH. The manifest sets `"commands": []` so agy's `commands/readout.md` doesn't register a second `readout` next to the skill.
- **Codex:** no plugin. `install.sh` merges a Stop hook into `~/.codex/hooks.json`. Codex **skips new or changed hooks until the user trusts them with `/hooks`** (trust is per hash), so keep the hook command string stable.

How each copy is loaded:
- **agy** runs its own **copy** in `~/.gemini/config/plugins/voice-readout/`, so changes only reach agy after `./install.sh agy`. The installer copies because it's unverified whether agy follows a symlinked plugin folder.
- **Claude Code** loads the repo **in place** when it's installed from a local-path marketplace (`./install.sh claude`); changes apply after `/reload-plugins`.
- **Codex and the `readout` CLI** use the shared runtime copy in `~/.local/share/voice-readout/`.

## Commands

```bash
python3 -m unittest discover tests                                    # all tests (silent, temp state)
python3 -m unittest tests.test_explainer.TestCommands.test_every_command_in_one_block_is_read   # single test
claude plugin validate . && agy plugin validate .                     # both manifests
./install.sh [agy] [claude] [codex]                                   # install/update (default: every agent found)
./install.sh uninstall [agents]
python3 scripts/toggle.py status|on|off|stop|replay|last|mode <explain|direct>|voice <name>|test
echo '{"hook_event_name": "Stop", "last_assistant_message": "Hi"}' | python3 scripts/readout.py   # simulate a Stop hook
claude -p "/voice-readout:readout status" --plugin-dir . --output-format json   # live check: num_turns 0, cost 0
```

To rehearse installs safely, point everything at scratch dirs: `VOICE_READOUT_SHARE_DIR`, `VOICE_READOUT_PLUGIN_DIR`, `VOICE_READOUT_BIN_DIR`, `CODEX_HOME`, `CLAUDE_CONFIG_DIR`.

For a live Codex check without editing `~/.codex`, pass the hook inline:

```bash
codex exec --skip-git-repo-check --dangerously-bypass-hook-trust \
  -c 'hooks.Stop=[{hooks=[{type="command",command="python3 <repo>/scripts/readout.py"}]}]' '<prompt>'
```

**Silent testing:**
- Tests set `VOICE_READOUT_HOME` to a temp dir at import time. `TestVoiceReadout.setUp` also patches `state.CONFIG_PATH`, `state.LEGACY_CONFIG_PATH`, `state.LAST_TEXT_FILE` and `state.PID_FILE`, and stubs `readout.speak_text`. New tests that call toggle/pre_hook actions must do the same.
- `test_player.py` swaps the player command for `cat > file`.
- For live runs, set `SDL_AUDIODRIVER=dummy` and `VOICE_READOUT_HOME=<scratch>`. If you change `HOME`, also set `PYTHONUSERBASE=~/.local`; otherwise `edge_tts`/`gtts` disappear and the player falls back to `spd-say`, which **does** speak out loud.

Real agy transcripts to test against live in `~/.gemini/antigravity-cli/brain/*/.system_generated/logs/transcript_full.jsonl`.

## Architecture

Every hook script swallows exceptions and must exit 0 with the output its agent expects. Keep it that way:
- `readout.py` prints `{}`. Codex's Stop hook *requires* JSON on stdout.
- `pre_hook.py` prints `{"injectSteps": []}` for agy, and **nothing** for Claude Code unless it blocks.

**State: `scripts/state.py`.** Config is at `~/.config/voice-readout/config.json` (or `$VOICE_READOUT_HOME`), alongside `player.pid`, `last.txt`, `last_response.md` and `hook.log`, shared by all agents. `load_config` falls back to the pre-2.0 agy path `~/.gemini/antigravity-cli/voice_readout_config.json` until the first save. Modules read `state.X` at call time, so patching `state` attributes works.

**Turn-complete hook: `scripts/readout.py`** (agy, Claude Code and Codex Stop hooks, and Codex `notify`)
1. `read_event` reads the payload. Codex `notify` passes it as the **last argv** item; every hook passes it on stdin.
2. `turn_from_event` returns `(user request, final response)`:
   - Codex notify (`type == "agent-turn-complete"`): uses `last-assistant-message` and `input-messages`.
   - Claude Code and Codex hooks (`hook_event_name == "Stop"`): use `last_assistant_message`.
   - agy: `read_current_turn` walks the transcript backwards to the last non-empty `MODEL`/`PLANNER_RESPONSE` step. It stops at the turn's `USER_INPUT`, so it never re-reads an older answer. A turn usually has several PLANNER_RESPONSE steps; the last is the final answer. `ANTIGRAVITY_RESPONSE_TEXT` overrides the transcript.
3. `is_audio_command` skips turns whose request was `/readout stop|replay|last|test`. Those make or stop audio themselves, and reading the confirmation would cut them off. This matters for agy only; in Claude Code they never reach the model.
4. `prepare_speech_content` picks the text by mode. Both modes start from `markdown_speech.parse_markdown`, which produces blocks: heading, paragraph, list (items carry their nested code), code, table and quote/alert.
   - `explain` → `explainer.explain_response`. If the full rendering is ≤ 320 chars, it's read in full. Otherwise the explainer walks the heading sections: lead sentences, list item titles, table rows and alerts, with **all** shell commands in place. Prose stops at `explain_max_chars` (default 1000); after that, sections contribute only their commands, and skipped titles are named. Commands are capped at 15. With `use_llm` and a Gemini key, it tries Gemini 2.5 Flash first.
   - `direct` → `render_full`, which reads every block, replaces code with a notice, and truncates at `max_chars`.
5. Every response is also saved to `last_response.md`, even while readout is off, as the fallback for `readout last`.
6. `speak_text` spawns `player.py` **detached** (`start_new_session=True`), so the hook returns immediately.

**`scripts/player.py`** (detached process)
- Stops previous playback by killing the old player's whole **process group** (`killpg`); the sound comes from its ffplay/mpv child. It first checks that the PID really is a `player.py`.
- `PlayerPipe` streams edge-tts chunks into `ffplay`/`mpv`/`cvlc` stdin as they arrive: about 1.3 s to first audio, versus 4–19 s when synthesizing the whole file first.
- gTTS is tried only if edge-tts produced **no** audio. System TTS (`spd-say -w`/`say`/PowerShell) is the last resort. On SIGTERM it runs `spd-say -C`, because speech-dispatcher keeps talking after its client dies.
- Saves the text it reads to `last.txt` for `readout replay`.

**Instant `/readout`: `scripts/pre_hook.py`**
- **agy PreInvocation:** finds the latest `USER_INPUT`, which is wrapped as `<USER_REQUEST>…</USER_REQUEST><ADDITIONAL_METADATA>…`. Only a request that *starts* with `/readout` or `/voice-readout:readout` counts, with arguments from its first line. It runs the action and injects an `ephemeralMessage` telling the model to echo the result without tools.
- **Claude Code UserPromptExpansion:** fires for every prompt-type slash command (no matcher), so it filters on `command_name` ending in `readout`. It runs the action and returns `decision: block` with the result as `reason` and `suppressOriginalPrompt`. Unknown actions return nothing, so the skill expands and the model handles them.
- The skill (`skills/readout/SKILL.md`) is the fallback for both: the model runs `readout <args>`.

### Logic to keep in sync

- **Action handling:** `toggle.py` `main()` (prints) and `pre_hook.py` `execute_toggle_action()` (returns strings). Action names live in `toggle.py` (`OFF_ACTIONS`, `STOP_ACTIONS`, `REPLAY_ACTIONS`, `LAST_ACTIONS`, `AUDIO_ACTIONS`). stop/replay/last/test are shared helpers in `toggle.py` (`stop_speech`, `replay_last`, `read_last`, `speak_test`); reuse them. `replay` repeats `last.txt` (what was spoken); `last` re-renders the previous response via `readout.previous_response`: the Claude Code transcript (`transcript_path`), the agy transcript (skipping the current `USER_INPUT`), else `last_response.md`. It must never change `enabled`. `stop` means "stop current speech"; `off`/`disable`/`mute` disable readout and also stop speech. Mode aliases also appear in `readout.prepare_speech_content`.
- **Voice aliases:** defined once in `player.VOICE_ALIASES`. The lists in `toggle.print_available_voices`, `commands/readout.md`, `skills/readout/SKILL.md` and `README.md` are written by hand.
- **Version:** `plugin.json` (agy) and `.claude-plugin/plugin.json`, plus `CHANGELOG.md`.

All markdown parsing, inline cleanup (`clean_inline`), shell command extraction and speech phrasing live in `markdown_speech.py`. Put new cleanup rules there, not in `readout.py` or `explainer.py`.

Every script imports its siblings by putting `scripts/` on `sys.path`, and the tests do the same. Keep modules flat in `scripts/`.

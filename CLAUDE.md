# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A plugin for **Google Antigravity CLI (`agy`)**, not for Claude Code. It speaks agent responses aloud using neural TTS. It is plain Python 3 with no build step, no packaging and no requirements file. The TTS and LLM libraries (`edge_tts`, `gtts`, `google.genai`) are imported lazily inside `try` blocks, so every script runs without them and falls back gracefully.

When installed, the plugin lives at `~/.gemini/config/plugins/voice-readout/`. `commands/readout.md` and `skills/readout/SKILL.md` hardcode that path. agy runs that **copy**, not this repo, so changes only take effect after `./install.sh`. The installer copies files instead of symlinking because it's unverified whether agy follows a symlinked plugin folder. `~/.local/bin/readout` is a symlink to the installed `scripts/toggle.py`.

## Commands

```bash
./install.sh                                                           # copy plugin into ~/.gemini/config/plugins/voice-readout + link ~/.local/bin/readout
python3 -m unittest discover tests                                    # all tests
python3 -m unittest tests.test_explainer.TestCommands.test_every_command_in_one_block_is_read   # single test
python3 scripts/toggle.py status|on|off|stop|replay|mode <explain|direct>|voice <name>|test   # manual control; `test` speaks a sample
echo '{"transcriptPath": "/path/to/transcript.jsonl"}' | python3 scripts/readout.py      # simulate the Stop hook
```

`TestVoiceReadout.setUp` points `toggle.CONFIG_PATH`, `toggle.LAST_TEXT_FILE` and `player.PID_FILE` at temp files and stubs `readout.speak_text`. Any new test that calls toggle/pre_hook actions must stay in that class (or do the same), or it will rewrite real state in `~/.gemini/antigravity-cli/` or start audio. `test_player.py` swaps the player command for `cat > file`.

To run the real player silently, set `SDL_AUDIODRIVER=dummy` (ffplay then makes no sound). If you also point `HOME` at a scratch dir, set `PYTHONUSERBASE=~/.local`; otherwise the user-installed `edge_tts`/`gtts` disappear, and the player falls back to `spd-say`, which **does** speak out loud.

To check explain/direct output against real responses, local agy transcripts live at `~/.gemini/antigravity-cli/brain/*/.system_generated/logs/transcript_full.jsonl`.

## Architecture

`hooks.json` registers two `agy` lifecycle hooks. Each one reads a JSON payload on stdin that contains `transcriptPath`. Both hooks swallow every exception and **always** write valid JSON to stdout, so a failure never blocks the CLI. Keep it that way.

**Stop hook → `scripts/readout.py`** (30s timeout, prints `{}`)
1. `extract_model_response` checks the `ANTIGRAVITY_RESPONSE_TEXT` env var first. Otherwise it reads the transcript JSONL, preferring a sibling `transcript_full.jsonl`, and walks backwards to the last non-empty `source == "MODEL"`, `type == "PLANNER_RESPONSE"` step. It stops at the turn's `USER_INPUT`, so it never re-reads an older answer. A turn usually has several PLANNER_RESPONSE steps ("Checking the logs…" plus tool calls); the last one is the final answer.
2. `prepare_speech_content` picks the speech text by mode. Both modes start from `markdown_speech.parse_markdown`, which turns the response into blocks (heading, paragraph, list with items that carry their nested code, code, table, quote/alert):
   - `explain` (aliases: brief/summary/companion) → `explainer.explain_response`. If the fully rendered text is ≤ 320 chars, it reads it in full. Otherwise it groups blocks into heading sections and speaks each section's gist (lead sentences, list item titles, table rows, alerts) with **all** shell commands in place. Prose stops at `explain_max_chars` (default 1000); after that, sections contribute only their commands, and skipped titles are named ("It also covers…"). Commands are capped at 15. When the config has `use_llm: true` and either `gemini_api_key` or `GEMINI_API_KEY` is set, it tries Gemini 2.5 Flash first.
   - anything else → `clean_markdown_for_speech` → `render_full`, which reads every block, replaces code with a notice, and truncates at `max_chars`.
3. `speak_text` writes the text to a temp file and spawns `player.py` **detached** (`start_new_session=True`), so the hook returns immediately.

**`scripts/player.py`** (detached process)
- Cancels the previous playback through a PID file at `~/.gemini/antigravity-cli/voice_readout_player.pid`. It kills the old player's whole **process group** (`killpg`), because the sound comes from its ffplay/mpv child. This only works because `readout.speak_text` spawns the player with `start_new_session=True`. It also checks that the PID really is a `player.py` before killing.
- **Streams**: `PlayerPipe` starts `ffplay`/`mpv`/`cvlc` reading MP3 from stdin on the first audio chunk and feeds it edge-tts chunks as they arrive. Measured: about 1.2–1.6 s to first audio, versus 4 s (short) to 19 s (long explanation) when synthesizing the whole file first. gTTS is tried only if edge-tts produced **no** audio, so a mid-stream failure never repeats speech. System TTS (`spd-say -w` / `say` / PowerShell) is the last resort. On SIGTERM it runs `spd-say -C`, because speech-dispatcher keeps talking after its client dies.
- Saves the text it reads to `voice_readout_last.txt` for `readout replay`.

**PreInvocation hook → `scripts/pre_hook.py`** (5s timeout, prints `{"injectSteps": [...]}`)
- Finds the latest `USER_INPUT` step in the transcript. Its content is wrapped as `<USER_REQUEST>…</USER_REQUEST><ADDITIONAL_METADATA>…`. Only a request that *starts* with `/readout` or `/voice-readout:readout` counts, and arguments come from that first line only. The hook then applies the config change itself before the model runs. It then injects an `ephemeralMessage` telling the model to echo the result without calling any tools. `skills/readout/SKILL.md` covers the fallback case where the hook did not fire: the model runs `toggle.py` through `run_command`.
- Logs timing to `~/.gemini/antigravity-cli/voice_readout_hook.log`.

### Duplicated logic to keep in sync

Some logic is copied rather than shared. A change to one copy usually needs the others updated too:
- **Default config dict**: `readout.py` (`DEFAULT_CONFIG`) and `toggle.py` (`load_config`).
- **on/off/mode/voice/status handling and mode aliases**: `toggle.py` `main()`, which prints, and `pre_hook.py` `execute_toggle_action()`, which returns strings. Mode aliases also appear in `readout.prepare_speech_content`. stop/replay/test are shared helpers in `toggle.py` (`stop_speech`, `replay_last`, `speak_test`). Reuse them rather than adding a third copy.
- **Voice aliases**: defined once in `player.VOICE_ALIASES` and imported by `toggle.py`. The voice list printed by `toggle.print_available_voices` and the lists in `commands/readout.md` and `skills/readout/SKILL.md` are written by hand.

All markdown parsing, inline cleanup (`clean_inline`), shell command extraction and speech phrasing live in `markdown_speech.py`. Put new cleanup rules there, not in `readout.py` or `explainer.py`.

Every script imports its siblings by putting `scripts/` on `sys.path`, and the tests do the same. Keep modules flat in `scripts/`.

`/readout stop|replay|test` produce or stop audio themselves. `readout.is_audio_command` makes the Stop hook skip those turns; otherwise it would read the model's confirmation and cut the replay off. Note that `stop` means "stop current speech"; `off`/`disable`/`mute` disable readout and also stop speech. The action names live in `toggle.py` (`OFF_ACTIONS`, `STOP_ACTIONS`, `REPLAY_ACTIONS`, `AUDIO_ACTIONS`).

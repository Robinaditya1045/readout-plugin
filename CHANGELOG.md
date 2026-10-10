# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project uses
[Semantic Versioning](https://semver.org/).

## [2.0.0] - 2026-10-11

### Added
- **Claude Code support:** the repo is now also a Claude Code plugin and marketplace. A `Stop` hook speaks `last_assistant_message`, and a `UserPromptExpansion` hook runs `/voice-readout:readout …` without a model turn.
- **Codex CLI support:** a `Stop` hook in `~/.codex/hooks.json`, and a `notify` payload alternative for older versions.
- `install.sh` installs for every detected agent (or the ones you name), and `./install.sh uninstall` removes it again.
- `readout stop` stops the current speech and `readout replay` reads the last response again.
- Streaming playback: speech starts after the first audio chunk (about 1.3 s) instead of after synthesizing the whole response (4 to 19 s before).
- Explain mode reads every command in a response, next to the step or option it belongs to. It also handles lists, tables, callouts, console transcripts, code descriptions and closing questions, and stays within `explain_max_chars`.
- LICENSE, CONTRIBUTING.md, `requirements.txt`, CI workflow, and tests for explain mode, playback and every agent integration.

### Changed
- Settings moved to `~/.config/voice-readout/config.json`, shared by all agents. The old agy config path is still read when the new file doesn't exist yet.
- `readout stop` now stops the current speech. Use `readout off` (or `disable`, `mute`) to turn readout off, which now also stops current speech.
- The `/readout` skill and command use the `readout` command instead of agy-specific paths.

### Fixed
- Explain mode only read the first command of a response.
- Cancelling speech left the audio player running, so voices overlapped.
- A turn without a final message re-read the previous turn's answer.
- `/readout` matched prompts that merely mentioned it, and a bare `/readout` used the metadata line after it as arguments.
- The PreInvocation hook printed its JSON twice on empty input.
- Headings with no blank line after them lost their text. Sentences were split inside file names like `readout.py`, and `snake_case` identifiers lost their underscores.
- Fenced code with info strings, `~~~` fences, unclosed fences and tables leaked into speech.
- The tests overwrote the user's real config.

## [1.0.0] - 2026-10-10

### Added
- Voice readout plugin for Google Antigravity CLI with neural voices (edge-tts, gTTS, system fallback).
- `explain` and `direct` modes.
- Instant `/readout` handling through a PreInvocation hook, and the `readout` shell command.

[2.0.0]: https://github.com/Robinaditya1045/readout-plugin/compare/468cf0e...HEAD
[1.0.0]: https://github.com/Robinaditya1045/readout-plugin/commits/468cf0e

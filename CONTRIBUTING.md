# Contributing to Voice Readout

Thanks for helping! Bug reports, new response shapes the explainer gets wrong, and support for more agents are all welcome.

## Development setup

```bash
git clone https://github.com/Robinaditya1045/readout-plugin.git
cd readout-plugin
python3 -m pip install --user -r requirements.txt
python3 -m unittest discover tests
```

The tests never play audio and never touch your real settings. They run with a temporary `VOICE_READOUT_HOME` and a stand-in audio player.

To try your changes in an agent, re-run `./install.sh <agent>`. In Claude Code you can also load the plugin for one session with `claude --plugin-dir .`.

## Guidelines

- **Never break the agent.** Hook scripts must always exit 0 and print what their agent expects: `{}` from the Stop hook, `{"injectSteps": [...]}` from agy's PreInvocation hook, and nothing (or a block decision) for Claude Code's UserPromptExpansion. Wrap new logic so a failure means silence, not a broken turn.
- **Return fast.** Hooks run on every turn. Anything slow, like speech synthesis, belongs in the detached `player.py`.
- **Explainer changes need a test** in `tests/test_explainer.py`, built from the shape of a real agent response (with personal details removed).
- **Keep shared logic in one place.** Markdown parsing and speech cleanup go in `markdown_speech.py`. Config and state paths go in `state.py`. Actions shared by `toggle.py` and `pre_hook.py` (stop, replay, last, test) are helpers in `toggle.py`.
- **Keep `scripts/` flat.** Every script imports its siblings by putting `scripts/` on `sys.path`.
- **Validate both manifests** before opening a PR: `claude plugin validate .` and `agy plugin validate .`.

## Testing audio by hand

```bash
SDL_AUDIODRIVER=dummy VOICE_READOUT_HOME=/tmp/vr readout test   # silent run with throwaway settings
```

If you change `HOME` for a test run, also set `PYTHONUSERBASE=~/.local`. Otherwise user-installed `edge-tts`/`gTTS` disappear and the player falls back to `spd-say`, which speaks out loud.

## Pull requests

- Keep each PR focused, and update `CHANGELOG.md` under an `Unreleased` heading.
- Describe how you tested it, including the agent and version if you ran it live.
- Make sure CI passes.

---
name: readout
description: Instantly toggle or configure voice readout text-to-speech without deliberation.
---

# Voice Readout (`/readout`)

> [!IMPORTANT]
> **ZERO DELIBERATION RULE**:
> If the hook already executed the action (see system notice), DO NOT call any tools. Output the confirmation directly.
> Otherwise, immediately call `run_command` in Step 1 without multi-step planning or deliberation.

## Direct Command Map

- `/readout on` -> `python3 ~/.gemini/config/plugins/voice-readout/scripts/toggle.py on`
- `/readout off` -> `python3 ~/.gemini/config/plugins/voice-readout/scripts/toggle.py off`
- `/readout mode explain` -> `python3 ~/.gemini/config/plugins/voice-readout/scripts/toggle.py mode explain`
- `/readout mode direct` -> `python3 ~/.gemini/config/plugins/voice-readout/scripts/toggle.py mode direct`
- `/readout voice <name>` -> `python3 ~/.gemini/config/plugins/voice-readout/scripts/toggle.py voice <name>`
- `/readout status` -> `python3 ~/.gemini/config/plugins/voice-readout/scripts/toggle.py status`
- `/readout test` -> `python3 ~/.gemini/config/plugins/voice-readout/scripts/toggle.py test`

Return the single-line command result directly to the user.

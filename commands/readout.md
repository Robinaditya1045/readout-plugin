---
name: readout
description: Control the voice readout plugin (toggle on/off, switch between explain/direct modes, or change voices).
---

# Voice Readout Command

Use `/readout` to control spoken audio in Antigravity:

- Switch to conversational explain mode:
  `python3 ~/.gemini/config/plugins/voice-readout/scripts/toggle.py mode explain`

- Switch to verbatim direct readout mode:
  `python3 ~/.gemini/config/plugins/voice-readout/scripts/toggle.py mode direct`

- Toggle readout on:
  `python3 ~/.gemini/config/plugins/voice-readout/scripts/toggle.py on`

- Toggle readout off:
  `python3 ~/.gemini/config/plugins/voice-readout/scripts/toggle.py off`

- Switch neural voice:
  `python3 ~/.gemini/config/plugins/voice-readout/scripts/toggle.py voice <siri|andrew|emma|brian|google|ava>`

- Check status and current mode:
  `python3 ~/.gemini/config/plugins/voice-readout/scripts/toggle.py status`

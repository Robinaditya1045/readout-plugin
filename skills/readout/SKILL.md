---
name: readout
description: Control voice readout text-to-speech (toggle on/off, switch between explain and direct modes, change neural voices, test audio).
---

# Voice Readout (`/readout`)

Control spoken audio playback and AI companion voice explanations for Antigravity responses.

## Actions

- **Turn On Voice**:
  Run: `python3 ~/.gemini/config/plugins/voice-readout/scripts/toggle.py on`

- **Turn Off Voice**:
  Run: `python3 ~/.gemini/config/plugins/voice-readout/scripts/toggle.py off`

- **Switch to Conversational Explain Mode**:
  Run: `python3 ~/.gemini/config/plugins/voice-readout/scripts/toggle.py mode explain`

- **Switch to Verbatim Direct Mode**:
  Run: `python3 ~/.gemini/config/plugins/voice-readout/scripts/toggle.py mode direct`

- **Change Voice**:
  Run: `python3 ~/.gemini/config/plugins/voice-readout/scripts/toggle.py voice <siri|andrew|emma|brian|google|ava>`

- **Check Current Status**:
  Run: `python3 ~/.gemini/config/plugins/voice-readout/scripts/toggle.py status`

- **Test Audio**:
  Run: `python3 ~/.gemini/config/plugins/voice-readout/scripts/toggle.py test`

---
name: readout
description: Control the voice readout text-to-speech plugin (toggle on/off, change neural voice, or status).
---

# Voice Readout Command

When the user types `/readout`, execute the corresponding command:

- Toggle on: `python3 ~/.gemini/config/plugins/voice-readout/scripts/toggle.py on`
- Toggle off: `python3 ~/.gemini/config/plugins/voice-readout/scripts/toggle.py off`
- Check status: `python3 ~/.gemini/config/plugins/voice-readout/scripts/toggle.py status`
- Switch voice: `python3 ~/.gemini/config/plugins/voice-readout/scripts/toggle.py voice <siri|andrew|emma|brian|google|ava>`
- Test audio: `python3 ~/.gemini/config/plugins/voice-readout/scripts/toggle.py test`

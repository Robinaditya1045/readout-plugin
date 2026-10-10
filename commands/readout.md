---
name: readout
description: Control voice readout (toggle on/off, stop or replay speech, switch between explain/direct modes, or change voices).
---

# Voice Readout Command

Use `/readout` to control spoken audio. Run the matching command and return its output:

- `readout on` / `readout off` (off also stops current speech)
- `readout stop`: stop the current speech, keep readout on
- `readout replay`: read the last response again
- `readout mode explain` / `readout mode direct`
- `readout voice <siri|ava|emma|andrew|brian|aria|jenny|guy|google>`
- `readout status`
- `readout test`

If `readout` is not on the PATH, run `python3 ~/.local/share/voice-readout/scripts/toggle.py` with the same arguments.

---
name: readout
description: Control voice readout (spoken agent responses) - turn it on or off, stop or replay the current speech, read the last response on demand, switch between explain and direct modes, change the voice, or show status.
---

# Voice Readout (`/readout`)

> [!IMPORTANT]
> **ZERO DELIBERATION RULE**:
> If a system notice says the command was already executed, DO NOT call any tools. Output that confirmation directly.
> Otherwise run the matching command below in ONE step, without planning, and return its output to the user.

## Direct Command Map

| `/readout ...` | Run |
|---|---|
| `on` / `off` | `readout on` / `readout off` |
| `stop` | `readout stop` (stop the current speech, keep readout on) |
| `replay` | `readout replay` (repeat the last readout) |
| `last` | `readout last` (read the last response once, even while readout is off; it stays off) |
| `mode explain` / `mode direct` | `readout mode explain` / `readout mode direct` |
| `voice <name>` | `readout voice <name>` (siri, ava, emma, andrew, brian, aria, jenny, guy, google) |
| `status` | `readout status` |
| `test` | `readout test` |

If `readout` is not on the PATH, run `python3 ~/.local/share/voice-readout/scripts/toggle.py` with the same arguments.

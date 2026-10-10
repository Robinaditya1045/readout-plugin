#!/usr/bin/env python3
"""
Unit tests for voice_readout_plugin (modes, explainer, cleaner, transcript parsing, pre_hook).
"""

import json
import tempfile
import unittest
from pathlib import Path

# Add scripts directory to sys.path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from explainer import explain_response
from readout import clean_markdown_for_speech, extract_model_response, prepare_speech_content
from pre_hook import parse_readout_command, execute_toggle_action


class TestVoiceReadout(unittest.TestCase):
    def test_direct_mode_cleans_markdown(self):
        raw = "Here is the code:\n```python\nprint('hello world')\n```\nLet me know if this helps!"
        cleaned = clean_markdown_for_speech(raw, include_code_notice=True)
        self.assertNotIn("print('hello world')", cleaned)
        self.assertIn("code block omitted", cleaned)
        self.assertIn("Let me know if this helps!", cleaned)

    def test_explain_mode_with_shell_commands(self):
        raw = """
Dependencies are installed.
To launch the server, run:
```bash
npm run dev
```
"""
        explained = explain_response(raw)
        self.assertIn("Dependencies are installed", explained)
        self.assertIn("npm run dev", explained)
        self.assertNotIn("```", explained)

    def test_explain_mode_with_multiple_methods_and_questions(self):
        raw = """
The issue is that UEFI Secure Boot is blocking the NVIDIA driver.

### Method 1: Enroll Key
Run:
```bash
sudo mokutil --import /var/lib/mok.der
```

### Method 2: Disable Secure Boot
Disable Secure Boot in BIOS.

Would you like me to walk you through Method 1?
"""
        explained = explain_response(raw)
        self.assertIn("UEFI Secure Boot is blocking", explained)
        self.assertIn("Method 1: Enroll Key", explained)
        self.assertIn("Method 2: Disable Secure Boot", explained)
        self.assertIn("sudo mokutil", explained)
        self.assertIn("Would you like me to walk you through Method 1?", explained)

    def test_prepare_speech_content_mode_selection(self):
        raw = "Sentence one. Sentence two.\n```bash\ngit status\n```"
        explain_res = prepare_speech_content(raw, {"mode": "explain"})
        direct_res = prepare_speech_content(raw, {"mode": "direct"})

        self.assertIn("git status", explain_res)
        self.assertIn("code block omitted", direct_res)

    def test_pre_hook_parser_and_execution(self):
        args_off = parse_readout_command("/readout off")
        self.assertEqual(args_off, ["off"])
        msg = execute_toggle_action(args_off)
        self.assertIn("DISABLED", msg)

        args_on = parse_readout_command("/voice-readout:readout on")
        self.assertEqual(args_on, ["on"])
        msg2 = execute_toggle_action(args_on)
        self.assertIn("ENABLED", msg2)

    def test_extract_model_response_from_transcript(self):
        with tempfile.TemporaryDirectory() as td:
            transcript_file = Path(td) / "transcript_full.jsonl"
            steps = [
                {"step_index": 0, "source": "USER_EXPLICIT", "type": "USER_INPUT", "content": "hello"},
                {"step_index": 1, "source": "MODEL", "type": "PLANNER_RESPONSE", "content": "Hello Robin! How are you?"},
            ]
            with open(transcript_file, "w", encoding="utf-8") as f:
                for step in steps:
                    f.write(json.dumps(step) + "\n")

            hook_input = {"transcriptPath": str(transcript_file)}
            extracted = extract_model_response(hook_input)
            self.assertEqual(extracted, "Hello Robin! How are you?")


if __name__ == "__main__":
    unittest.main()

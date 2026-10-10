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

import player
import readout
import toggle
from explainer import explain_response
from readout import (
    clean_markdown_for_speech,
    extract_model_response,
    is_audio_command,
    normalize_rate,
    prepare_speech_content,
    read_current_turn,
)
from pre_hook import parse_readout_command, execute_toggle_action


class TestVoiceReadout(unittest.TestCase):
    def setUp(self):
        # Never touch the real ~/.gemini state: config, PID and last-text files live in a temp dir.
        self._tmp = tempfile.TemporaryDirectory()
        tmp = Path(self._tmp.name)
        self._saved = (toggle.CONFIG_PATH, toggle.LAST_TEXT_FILE, player.PID_FILE, readout.speak_text)
        toggle.CONFIG_PATH = tmp / "voice_readout_config.json"
        toggle.LAST_TEXT_FILE = tmp / "voice_readout_last.txt"
        player.PID_FILE = tmp / "voice_readout_player.pid"
        self.spoken = []
        readout.speak_text = lambda text, config: self.spoken.append(text)

    def tearDown(self):
        toggle.CONFIG_PATH, toggle.LAST_TEXT_FILE, player.PID_FILE, readout.speak_text = self._saved
        self._tmp.cleanup()

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

    def _write_transcript(self, td, steps):
        path = Path(td) / "transcript_full.jsonl"
        with open(path, "w", encoding="utf-8") as f:
            for step in steps:
                f.write(json.dumps(step) + "\n")
        return {"transcriptPath": str(path)}

    def test_extract_model_response_uses_last_message_of_current_turn(self):
        with tempfile.TemporaryDirectory() as td:
            hook_input = self._write_transcript(td, [
                {"source": "USER_EXPLICIT", "type": "USER_INPUT", "content": "fix it"},
                {"source": "MODEL", "type": "PLANNER_RESPONSE", "content": "Checking the logs.", "tool_calls": [{}]},
                {"source": "MODEL", "type": "GENERIC", "content": None},
                {"source": "MODEL", "type": "PLANNER_RESPONSE", "content": "Fixed the bug in readout.py."},
                {"source": "MODEL", "type": "PLANNER_RESPONSE", "content": None, "tool_calls": [{}]},
            ])
            self.assertEqual(extract_model_response(hook_input), "Fixed the bug in readout.py.")

    def test_extract_model_response_never_rereads_previous_turn(self):
        with tempfile.TemporaryDirectory() as td:
            hook_input = self._write_transcript(td, [
                {"source": "USER_EXPLICIT", "type": "USER_INPUT", "content": "first question"},
                {"source": "MODEL", "type": "PLANNER_RESPONSE", "content": "Old answer."},
                {"source": "USER_EXPLICIT", "type": "USER_INPUT", "content": "second question"},
                {"source": "MODEL", "type": "PLANNER_RESPONSE", "content": None, "tool_calls": [{}]},
            ])
            self.assertEqual(extract_model_response(hook_input), "")

    def test_extract_model_response_accepts_content_parts(self):
        with tempfile.TemporaryDirectory() as td:
            hook_input = self._write_transcript(td, [
                {"source": "USER_EXPLICIT", "type": "USER_INPUT", "content": "hi"},
                {"source": "MODEL", "type": "PLANNER_RESPONSE", "content": [{"text": "Part one."}, "Part two."]},
            ])
            self.assertEqual(extract_model_response(hook_input), "Part one.\nPart two.")

    def test_pre_hook_only_matches_requests_that_start_with_the_command(self):
        wrapped = (
            "<USER_REQUEST>\n/readout\n</USER_REQUEST>\n<ADDITIONAL_METADATA>\n"
            "The current local time is: 2026-10-11T00:49:33+05:30.\n</ADDITIONAL_METADATA>"
        )
        self.assertEqual(parse_readout_command(wrapped), [])
        self.assertEqual(parse_readout_command("<USER_REQUEST>\n/readout mode direct\n</USER_REQUEST>"), ["mode", "direct"])
        self.assertIsNone(parse_readout_command("<USER_REQUEST>\nHow does /readout off work?\n</USER_REQUEST>"))
        self.assertIsNone(parse_readout_command("explain the /readout command"))
        self.assertIsNone(parse_readout_command("/readouts are great"))

    def test_toggle_actions_write_to_isolated_config(self):
        execute_toggle_action(["mode", "direct"])
        saved = json.loads(toggle.CONFIG_PATH.read_text())
        self.assertEqual(saved["mode"], "direct")

    def test_normalize_rate(self):
        self.assertEqual(normalize_rate("+10%"), "+10%")
        self.assertEqual(normalize_rate("10%"), "+10%")
        self.assertEqual(normalize_rate("-5"), "-5%")
        self.assertEqual(normalize_rate(15), "+15%")
        self.assertEqual(normalize_rate("fast"), "+0%")

    def test_direct_mode_handles_fence_variants_and_identifiers(self):
        raw = (
            "Call `load_config` and save_config from readout.py.\n\n"
            "```python title=\"app.py\"\nsecret_code()\n```\n\n"
            "~~~\nmore_hidden()\n~~~\n\n"
            "| Key | Value |\n|---|---|\n| Mode | explain |\n\n"
            "```bash\nunclosed_fence_command"
        )
        cleaned = clean_markdown_for_speech(raw)
        self.assertIn("load_config and save_config from readout.py", cleaned)
        self.assertIn("Mode: explain", cleaned)
        for leaked in ("secret_code", "more_hidden", "unclosed_fence_command", "```", "|"):
            self.assertNotIn(leaked, cleaned)

    def test_stop_stops_speech_without_disabling_readout(self):
        self.assertEqual(execute_toggle_action(["stop"]), "Nothing is being read out right now.")
        self.assertTrue(toggle.load_config()["enabled"])

    def test_off_also_stops_current_speech(self):
        calls = []
        real_stop = toggle.stop_playback
        toggle.stop_playback = lambda: calls.append("stop")
        try:
            self.assertIn("DISABLED", execute_toggle_action(["off"]))
        finally:
            toggle.stop_playback = real_stop
        self.assertEqual(calls, ["stop"])
        self.assertFalse(toggle.load_config()["enabled"])

    def test_replay_reads_the_last_text_again(self):
        self.assertEqual(execute_toggle_action(["replay"]), "Nothing to replay yet.")
        toggle.LAST_TEXT_FILE.write_text("Run: npm test.", encoding="utf-8")
        self.assertEqual(execute_toggle_action(["replay"]), "🔁 Replaying the last readout.")
        self.assertEqual(self.spoken, ["Run: npm test."])

    def test_stop_hook_stays_silent_after_audio_commands(self):
        for request in ("/readout stop", "/readout replay", "/readout test", "/voice-readout:readout skip"):
            self.assertTrue(is_audio_command(f"<USER_REQUEST>\n{request}\n</USER_REQUEST>"), request)
        for request in ("/readout mode direct", "/readout on", "please stop the server", ""):
            self.assertFalse(is_audio_command(f"<USER_REQUEST>\n{request}\n</USER_REQUEST>"), request)

    def test_read_current_turn_returns_the_request_too(self):
        with tempfile.TemporaryDirectory() as td:
            hook_input = self._write_transcript(td, [
                {"source": "USER_EXPLICIT", "type": "USER_INPUT", "content": "<USER_REQUEST>\n/readout stop\n</USER_REQUEST>"},
                {"source": "MODEL", "type": "PLANNER_RESPONSE", "content": "Stopped the current readout."},
            ])
            user_input, response = read_current_turn(hook_input)
            self.assertIn("/readout stop", user_input)
            self.assertEqual(response, "Stopped the current readout.")


if __name__ == "__main__":
    unittest.main()

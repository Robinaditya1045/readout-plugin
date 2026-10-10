#!/usr/bin/env python3
"""
Unit tests for voice_readout_plugin.
"""

import json
import tempfile
import unittest
from pathlib import Path

# Add scripts directory to sys.path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from readout import clean_markdown_for_speech, extract_model_response
import toggle


class TestVoiceReadout(unittest.TestCase):
    def test_clean_markdown_strips_code_blocks(self):
        raw = "Here is the code:\n```python\nprint('hello world')\n```\nLet me know if this helps!"
        cleaned = clean_markdown_for_speech(raw, include_code_notice=True)
        self.assertNotIn("print('hello world')", cleaned)
        self.assertIn("code block omitted", cleaned)
        self.assertIn("Let me know if this helps!", cleaned)

    def test_clean_markdown_strips_links_and_formatting(self):
        raw = "Check [our documentation](https://example.com) for **important** details and `var_name`."
        cleaned = clean_markdown_for_speech(raw)
        self.assertNotIn("https://example.com", cleaned)
        self.assertIn("Check our documentation for important details and var_name.", cleaned)

    def test_clean_markdown_strips_headers_and_lists(self):
        raw = "## Next Steps\n* Step 1: Install packages\n* Step 2: Run tests"
        cleaned = clean_markdown_for_speech(raw)
        self.assertNotIn("##", cleaned)
        self.assertNotIn("*", cleaned)
        self.assertIn("Next Steps", cleaned)
        self.assertIn("Step 1: Install packages", cleaned)

    def test_clean_markdown_truncates_long_text(self):
        raw = "Sentence one. " * 200
        cleaned = clean_markdown_for_speech(raw, max_chars=100)
        self.assertTrue(len(cleaned) <= 150)
        self.assertIn("Response truncated", cleaned)

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

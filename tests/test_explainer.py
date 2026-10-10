#!/usr/bin/env python3
"""
Explain-mode tests covering the response shapes agy produces: step guides, option
guides, change reports, status tables, console transcripts, callouts and questions.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from explainer import explain_response, heuristic_explain
from markdown_speech import clean_inline, extract_commands, parse_markdown, speak_command, split_sentences, CodeBlock

FILLER = (
    "This paragraph adds enough detail that the response is clearly long, so the explainer "
    "has to summarize it instead of reading every word out loud to the user."
)


class TestCommands(unittest.TestCase):
    def test_every_command_in_one_block_is_read(self):
        raw = f"{FILLER}\n\nRun these:\n```bash\nnpm install\nnpm run build\nnpm test\nnpm run deploy\n```\n\n{FILLER}"
        explained = explain_response(raw)
        for cmd in ("npm install", "npm run build", "npm test", "npm run deploy"):
            self.assertIn(cmd, explained)

    def test_commands_from_every_step_section_are_read(self):
        steps = "\n\n".join(
            f"### Step {n}: Do part {n}\n{FILLER}\n```bash\ntool-{n} --flag\n```" for n in range(1, 6)
        )
        explained = explain_response(f"Here is the full setup.\n\n{steps}")
        self.assertIn("There are 5 steps", explained)
        for n in range(1, 6):
            self.assertIn(f"tool-{n} --flag", explained)
        # Commands stay in document order.
        positions = [explained.index(f"tool-{n}") for n in range(1, 6)]
        self.assertEqual(positions, sorted(positions))

    def test_commands_nested_under_numbered_items_are_attached_to_the_step(self):
        raw = (
            f"{FILLER}\n\n{FILLER}\n\n"
            "1. Start the web assistant:\n   ```bash\n   ./run.sh web\n   ```\n"
            "2. Open the dashboard in your browser.\n"
            "3. Run the tests:\n   ```bash\n   ./run.sh test\n   ```\n   You should see:\n   ```text\n   16 passed\n   ```\n"
        )
        explained = explain_response(raw)
        self.assertIn("Start the web assistant: run ./run.sh web", explained)
        self.assertIn("Run the tests: ./run.sh test", explained)
        self.assertNotIn("You should see", explained.split("Run the tests")[0])

    def test_console_transcript_reads_only_prompted_lines(self):
        code = CodeBlock(lang="console", body="$ git status\nOn branch main\nnothing to commit\n$ git push\nEverything up-to-date")
        self.assertEqual(extract_commands(code), ["git status", "git push"])

    def test_continuations_heredocs_and_comments(self):
        body = (
            "# Install the runtime\n"
            "docker run -d \\\n  -p 8080:80 \\\n  nginx  # web server\n"
            "cat > ~/.ssh/config <<'EOF'\nHost oracle\n  User opc\nEOF\n"
            "chmod 600 ~/.ssh/config"
        )
        cmds = extract_commands(CodeBlock(lang="bash", body=body))
        self.assertEqual(cmds[0], "docker run -d -p 8080:80 nginx")
        self.assertEqual(cmds[1], "cat > ~/.ssh/config with the content shown")
        self.assertEqual(cmds[2], "chmod 600 ~/.ssh/config")
        self.assertEqual(len(cmds), 3)

    def test_output_labelled_as_bash_is_not_read_as_commands(self):
        code = CodeBlock(lang="bash", body="test parser::parses_json ... ok\ntest parser::parses_reply ... ok")
        self.assertEqual(extract_commands(code), [])

    def test_shell_operators_are_spoken_but_quoted_pipes_are_kept(self):
        self.assertEqual(speak_command("cd app && npm i"), "cd app, and then npm i")
        self.assertEqual(
            speak_command("curl -s localhost:8080/api | jq '.[] | {pair}'"),
            "curl -s localhost:8080/api, piped to jq '.[] | {pair}'",
        )
        self.assertEqual(speak_command("ssh robin@<LAPTOP_IP>"), "ssh robin@laptop ip")
        self.assertEqual(speak_command("make build > /dev/null 2>&1"), "make build")

    def test_inline_run_commands_are_read_but_bare_mentions_are_not(self):
        raw = (
            f"{FILLER}\n\n{FILLER} {FILLER}\n\n{FILLER}\n\n"
            "Enter your `sudo` password when prompted. When it finishes, run `systemctl restart nginx` to apply it."
        )
        explained = heuristic_explain(raw, budget=200)
        self.assertIn("systemctl restart nginx", explained)
        self.assertNotIn("Run: sudo", explained)


class TestResponseShapes(unittest.TestCase):
    def test_short_answers_are_read_in_full(self):
        self.assertEqual(explain_response("Hello! How can I help you today?"), "Hello! How can I help you today?")
        self.assertEqual(
            explain_response("🔇 Voice readout status: DISABLED | Mode: EXPLAIN | Voice: en-US-AvaNeural"),
            "Voice readout status: DISABLED, Mode: EXPLAIN, Voice: en-US-AvaNeural.",
        )

    def test_heading_without_blank_line_keeps_its_text(self):
        raw = f"### Root Cause\nYour laptop runs Wayland, which blocks synthetic key events.\n\n{FILLER}\n\n{FILLER}"
        explained = explain_response(raw)
        self.assertIn("Root Cause: Your laptop runs Wayland", explained)

    def test_change_report_lists_bold_item_titles(self):
        raw = (
            "The bot now supports multi-item carts.\n\n"
            "### What Was Fixed\n"
            "1. **Full Multi-Item Cart Building**:\n   - The agent iterates through all items.\n"
            "2. **Phonetic & Stem Matching**:\n   - Handles misheard dish names.\n"
            "3. **Combined Discount Calculation**:\n   - Applies the best coupon.\n\n"
            f"{FILLER}"
        )
        explained = explain_response(raw)
        self.assertIn(
            "first, Full Multi-Item Cart Building; then, Phonetic & Stem Matching; and finally, Combined Discount Calculation",
            explained,
        )

    def test_option_list_items_are_joined_with_or(self):
        raw = (
            f"{FILLER}\n\n{FILLER}\n\nYou can pay in one tap:\n\n"
            "1. **Option 1: Mobile App**\n   * Open the app.\n2. **Option 2: Payment Link**\n   * Open the link.\n"
        )
        self.assertIn("Option 1: Mobile App; or Option 2: Payment Link", explain_response(raw))

    def test_option_sections_are_announced(self):
        raw = (
            f"{FILLER}\n\n### Method 1: Enroll Key\n```bash\nsudo mokutil --import key.der\n```\n\n"
            f"### Method 2: Disable Secure Boot\nDisable it in the BIOS. {FILLER}"
        )
        explained = explain_response(raw)
        self.assertIn("There are 2 options.", explained)
        self.assertIn("Method 1: Enroll Key: Run: sudo mokutil --import key.der.", explained)

    def test_key_value_tables_are_read_and_wide_tables_summarized(self):
        raw = (
            "The batch download finished.\n\n### Summary\n\n| Metric | Result |\n| :--- | :--- |\n"
            "| **Total URLs** | 5 / 5 |\n| **Status** | 100% Succeeded |\n\n"
            "### Services\n\n| Service | Port | Status | Description |\n|---|---|---|---|\n"
            "| Backend | 8080 | Running | API |\n| Frontend | 5173 | Running | UI |\n\n"
            f"{FILLER}"
        )
        explained = explain_response(raw)
        self.assertIn("Total URLs: 5 / 5; Status: 100% Succeeded", explained)
        self.assertIn("a table of 2 rows with columns Service, Port, Status, and Description", explained)

    def test_callout_with_code_inside(self):
        raw = (
            f"{FILLER}\n\n> [!TIP]\n> **Shortcut alias:**\n> In your ~/.bashrc, add:\n"
            "> ```bash\n> alias laptop='ssh -t robin@100.70.6.46'\n> ```\n\n"
            "> [!WARNING]\n> This deletes all local data. Back up first.\n\n"
            f"{FILLER}"
        )
        explained = explain_response(raw)
        self.assertIn("Tip: Shortcut alias: In your ~/.bashrc, add: alias laptop=", explained)
        self.assertIn("Warning: This deletes all local data.", explained)
        self.assertEqual(explained.count("Shortcut alias"), 1)

    def test_closing_question_with_choices(self):
        raw = (
            f"Phase 9 is complete.\n\n### Details\n{FILLER}\n\n{FILLER}\n\n"
            "Which would you like to do next?\n\n1. **Review the changes**\n2. **Start Phase 10**\n"
        )
        explained = explain_response(raw)
        self.assertTrue(explained.endswith("Which would you like to do next: Review the changes; or Start Phase 10?"))

    def test_non_shell_code_is_described(self):
        raw = (
            f"{FILLER}\n\nUpdate the handler:\n```python:src/handler.py\nitems = parse(text)\n```\n\n"
            f"Then this config:\n```yaml\nport: 8080\nhost: 0.0.0.0\n```\n\n```mermaid\ngraph TD; A-->B\n```\n\n{FILLER}"
        )
        explained = explain_response(raw)
        self.assertIn("Update the handler: there's a Python snippet for handler.py on screen.", explained)
        self.assertIn("Then this config: there's a YAML snippet on screen.", explained)
        self.assertNotIn("items = parse", explained)

    def test_long_responses_stay_within_budget_but_keep_commands(self):
        sections = "\n\n".join(f"### Topic {n}\n{FILLER} {FILLER}" for n in range(1, 9))
        raw = f"{sections}\n\n### Quick Start\n```bash\ncargo run -p server\n```"
        explained = heuristic_explain(raw, budget=600)
        self.assertIn("cargo run -p server", explained)
        self.assertIn("It also covers", explained)
        self.assertLess(len(explained), 1000)

    def test_thinking_is_never_spoken(self):
        raw = "<thought>secret plan</thought>The fix is applied.\n<thinking>more secret"
        self.assertEqual(explain_response(raw), "The fix is applied.")


class TestSpeechCleanup(unittest.TestCase):
    def test_file_names_and_versions_do_not_split_sentences(self):
        self.assertEqual(
            split_sentences("I fixed readout.py in v1.2.3 today. See e.g. Chrome. Done!"),
            ["I fixed readout.py in v1.2.3 today.", "See e.g. Chrome.", "Done!"],
        )

    def test_inline_cleanup(self):
        cleaned = clean_inline(
            "✅ Updated [`batchd.py`](file:///home/robin/batchd.py) — see https://github.com/org/repository-name/pull/123 "
            "and run `load_config`; state goes WaitingForEntry → Active. Use <kbd>Ctrl</kbd> with snake_case_names."
        )
        self.assertEqual(
            cleaned,
            "Updated batchd.py — see github.com and run load_config; state goes WaitingForEntry to Active. "
            "Use Ctrl with snake_case_names.",
        )

    def test_space_is_kept_before_dotfiles(self):
        self.assertEqual(clean_inline("Created a venv at `.venv` and ran `./run.sh`."), "Created a venv at .venv and ran ./run.sh.")

    def test_parser_handles_indented_code_in_lists(self):
        blocks = parse_markdown("1. Install:\n   ```bash\n   npm i\n   ```\n2. Start it.\n")
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0].kind, "list")
        self.assertEqual(blocks[0].items[0].code[0].body, "npm i")


if __name__ == "__main__":
    unittest.main()

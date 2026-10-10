#!/usr/bin/env python3
"""
explainer.py - Intelligent conversational explainer for Google Antigravity responses.

Transforms long, markdown-heavy agent responses into concise, spoken explanations.
Instead of reading every line verbatim, it extracts:
1. Core diagnosis / direct takeaway
2. High-level choices or solution methods
3. Key actionable terminal commands (spoken naturally)
4. Modified files or code snippets
5. Closing questions or next steps
"""

import os
import re
from typing import Dict, List, Optional, Tuple


def is_shell_language(lang: str, code: str) -> bool:
    lang = lang.lower().strip()
    if lang in ("bash", "sh", "zsh", "shell", "terminal", "console", "cmd", "powershell"):
        return True
    first_line = code.strip().split("\n")[0].strip() if code.strip() else ""
    if first_line.startswith(("$", ">", "sudo ", "npm ", "git ", "pip ", "python3 ", "apt ", "docker ", "cargo ", "yarn ", "pnpm ")):
        return True
    return False


def extract_commands_from_code(code: str) -> List[str]:
    lines = [line.strip() for line in code.split("\n")]
    cmds = []
    for line in lines:
        if not line or line.startswith("#"):
            continue
        clean_line = re.sub(r"^[$>]\s+", "", line).strip()
        if clean_line:
            cmds.append(clean_line)
    return cmds


def clean_command_for_speech(cmd: str) -> str:
    cmd = re.sub(r"^sudo\s+", "sudo ", cmd)
    cmd = cmd.replace("&&", "and then").replace("||", "or")
    cmd = re.sub(r"\s+", " ", cmd).strip()
    return cmd


def clean_markdown_inline(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)
    text = re.sub(r"!\[([^\]]*)\]\([^\)]+\)", "", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\*([^*]+)\*", r"\1", text)
    text = re.sub(r"__([^_]+)__", r"\1", text)
    text = re.sub(r"_([^_]+)_", r"\1", text)
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^[>\s*+-]+\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\d+\.\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^[ \t]*[-*_]{3,}[ \t]*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"[ \t]+", " ", text).strip()
    return text


def split_sentences(text: str) -> List[str]:
    # Split by standard sentence terminators OR newlines
    tokens = re.split(r"(?:(?<=[.!?])|\n+)\s*", text.strip())
    return [s.strip() for s in tokens if s.strip()]


def extract_closing_question(text_no_code: str) -> Optional[str]:
    """Finds if the response ends with an actionable question for the user."""
    clean = clean_markdown_inline(text_no_code)
    sentences = split_sentences(clean)
    if sentences:
        last_s = sentences[-1]
        if last_s.endswith("?") or any(last_s.lower().startswith(q) for q in ["would you like", "let me know", "should i", "do you want"]):
            # Avoid picking up giant multi-sentence blocks
            if len(last_s) < 140:
                return last_s
    return None


def extract_methods_or_options(headers: List[str]) -> List[str]:
    """Extracts high-level methods like 'Method 1: Enroll Key', 'Option 2: Disable Secure Boot'."""
    options = []
    pattern = re.compile(r"^(Method|Option|Approach|Step|Solution)\s+(\d+[:.-]?\s*.*)", re.IGNORECASE)
    for h in headers:
        clean_h = clean_markdown_inline(h)
        match = pattern.match(clean_h)
        if match:
            title = re.sub(r"\s*\([^)]*\)", "", clean_h).strip()
            options.append(title)
    return options


def summarize_commands(commands: List[str]) -> Optional[str]:
    if not commands:
        return None

    unique_cmds = []
    for c in commands:
        c_clean = clean_command_for_speech(c)
        if c_clean and c_clean not in unique_cmds:
            unique_cmds.append(c_clean)

    if not unique_cmds:
        return None

    if len(unique_cmds) == 1:
        cmd = unique_cmds[0]
        if len(cmd) < 70:
            return f"Run the command: {cmd}."
        else:
            first_word = cmd.split()[0]
            return f"Run the {first_word} command provided."

    if len(unique_cmds) == 2:
        c1, c2 = unique_cmds[0], unique_cmds[1]
        if len(c1) < 50 and len(c2) < 50:
            return f"First run: {c1}, then: {c2}."
        else:
            return f"Run the suggested commands, starting with: {c1.split()[0]}."

    c1 = unique_cmds[0]
    return f"There are {len(unique_cmds)} suggested commands, starting with: {c1}."


def heuristic_explain(raw_text: str) -> str:
    """Intelligently creates a 2-4 sentence conversational spoken brief."""
    if not raw_text or not raw_text.strip():
        return ""

    text = re.sub(r"<thought>.*?</thought>", "", raw_text, flags=re.DOTALL)
    text = re.sub(r"<thinking>.*?</thinking>", "", text, flags=re.DOTALL)

    # 1. Parse code blocks and shell commands
    code_blocks = re.findall(r"```([a-zA-Z0-9_-]*)\n([\s\S]*?)```", text)
    shell_commands = []
    other_code_langs = []

    for lang, code in code_blocks:
        if is_shell_language(lang, code):
            cmds = extract_commands_from_code(code)
            shell_commands.extend(cmds)
        else:
            lang_label = lang.strip().lower() or "code"
            if lang_label not in other_code_langs:
                other_code_langs.append(lang_label)

    # 2. Strip code blocks to extract pure prose
    text_no_code = re.sub(r"```[\s\S]*?```", "", text)
    cleaned_prose = clean_markdown_inline(text_no_code)

    # If the response is pure short text without code or headers, just read it directly
    prose_sentences = split_sentences(cleaned_prose)
    if not code_blocks and len(prose_sentences) <= 2 and len(cleaned_prose) < 200:
        return cleaned_prose

    # 3. Extract section headers
    headers = re.findall(r"^#{1,4}\s+(.*)$", text, flags=re.MULTILINE)
    options = extract_methods_or_options(headers)

    # 4. Extract opening lead paragraph / diagnosis
    blocks = [b.strip() for b in text_no_code.split("\n\n") if b.strip()]
    lead_sentence = ""
    for b in blocks:
        if b.startswith("#") or b.startswith("---"):
            continue
        clean_b = clean_markdown_inline(b)
        s_list = split_sentences(clean_b)
        if s_list:
            lead_sentence = s_list[0]
            if len(lead_sentence) < 40 and len(s_list) > 1:
                lead_sentence += " " + s_list[1]
            break

    # If lead sentence ends with a colon (e.g. "To start the development server, run:"),
    # clean that up so it flows nicely into the command
    if lead_sentence.endswith(":"):
        lead_sentence = lead_sentence[:-1] + "."

    # 5. Extract closing question or next step
    closing_q = extract_closing_question(text_no_code)

    # 6. Extract command summary
    cmd_summary = summarize_commands(shell_commands)

    # 7. Compose spoken summary
    parts = []
    if lead_sentence:
        parts.append(lead_sentence)

    if options:
        if len(options) == 2:
            parts.append(f"There are two approaches: {options[0]}, or {options[1]}.")
        elif len(options) > 2:
            parts.append(f"Options include: {options[0]}, {options[1]}, and {options[2]}.")
        else:
            parts.append(f"Recommended approach: {options[0]}.")

    if cmd_summary:
        parts.append(cmd_summary)
    elif other_code_langs:
        langs_str = ", ".join(other_code_langs)
        parts.append(f"A {langs_str} code snippet is provided.")

    if closing_q:
        if closing_q.lower() not in lead_sentence.lower():
            parts.append(closing_q)

    if not parts:
        parts = prose_sentences[:2]

    result = " ".join(parts).strip()
    result = re.sub(r"\s+", " ", result)
    return result


def try_llm_explain(text: str, api_key: str) -> Optional[str]:
    """Optionally calls Gemini 2.5 Flash if an API key is configured."""
    try:
        from google import genai

        client = genai.Client(api_key=api_key)
        prompt = (
            "You are a spoken voice assistant companion for an AI coding terminal. "
            "Convert the following AI assistant message into a natural, conversational, 2-to-3 sentence spoken summary. "
            "Highlight the core takeaway, actions taken, any commands to run (phrase them clearly for speech), "
            "and any questions asked. Do not include markdown, bullet symbols, or code blocks.\n\n"
            f"Message:\n{text}"
        )
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        if response and response.text:
            return response.text.strip()
    except Exception:
        pass
    return None


def explain_response(raw_text: str, config: Optional[dict] = None) -> str:
    """Main entry point to explain an Antigravity response on the go."""
    if not raw_text:
        return ""

    config = config or {}
    api_key = config.get("gemini_api_key") or os.environ.get("GEMINI_API_KEY")

    if config.get("use_llm", False) and api_key:
        llm_result = try_llm_explain(raw_text, api_key)
        if llm_result:
            return llm_result

    return heuristic_explain(raw_text)

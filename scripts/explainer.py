#!/usr/bin/env python3
"""
explainer.py - Intelligent conversational explainer for Google Antigravity responses.

Transforms long, markdown-heavy agent responses into concise, spoken explanations.
Short responses are read in full. Longer ones are walked section by section:
1. The opening takeaway / diagnosis
2. Each section's gist: its lead sentences, list highlights, or table rows
3. Every terminal command, in order, next to the step or option it belongs to
4. Code snippets, diagrams and output that only make sense on screen
5. Warnings, and the closing question or next step
"""

import os
import re
from typing import List, Optional, Tuple

from markdown_speech import (
    Block,
    ListItem,
    clean_inline,
    describe_code,
    end_sentence,
    extract_commands,
    is_inline_command,
    is_shell_block,
    parse_markdown,
    render_full,
    shorten,
    single_line_value,
    speak_command,
    split_sentences,
    strip_thinking,
)

SHORT_RESPONSE_CHARS = 320  # spoken length below which a response is read in full
DEFAULT_BUDGET = 1000  # soft cap on spoken prose; commands and warnings are never cut by it
MAX_COMMANDS = 15

OPTION_RE = re.compile(r"^(?i:method|option|approach|solution|alternative|fix|workaround|way|plan)\s+(?:\d+|[A-Z])\b")
STEP_RE = re.compile(r"^(?i:step|part|phase|stage)\s+\d+\b")
GENERIC_TITLES = {
    "summary", "overview", "details", "tl;dr", "tldr", "result", "results", "response", "answer", "explanation",
}
ALERT_PREFIX_RE = re.compile(r"^(note|tip|important|warning|caution|heads up)\s*[:\-—]\s*", re.IGNORECASE)
RUN_VERB_RE = re.compile(
    r"\b(run|running|execute|executing|type|typing|enter|paste|use|using|add|append)\b", re.IGNORECASE
)
INLINE_RUN_RE = re.compile(r"\b(?:run|running|execute|type|enter)\b[^`\n]{0,30}`([^`\n]+)`", re.IGNORECASE)
QUESTION_RE = re.compile(r"\b(would you|should i|do you|which|what|shall i|want me|prefer)\b", re.IGNORECASE)
CLOSING_PREFIXES = (
    "would you like", "let me know", "should i", "do you want", "shall i", "want me to", "if you'd like",
    "if you want", "next,",
)


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _join_and(items: List[str]) -> str:
    if len(items) <= 2:
        return " and ".join(items)
    return ", ".join(items[:-1]) + ", and " + items[-1]


class _Brief:
    """Accumulates spoken parts while tracking the prose budget and the command cap."""

    def __init__(self, budget: int):
        self.budget = budget
        self.parts: List[str] = []
        self.commands_seen: List[str] = []
        self.commands_skipped = 0
        self.also_covers: List[str] = []

    def add(self, text: str) -> None:
        if text:
            self.parts.append(text)

    def length(self) -> int:
        return sum(len(p) for p in self.parts)

    def over_budget(self) -> bool:
        return self.length() >= self.budget

    def contains(self, text: str) -> bool:
        return _norm(text) in _norm(" ".join(self.parts))

    def take_commands(self, raw_commands: List[str]) -> List[str]:
        """Speakable versions of commands not already said, within the overall cap."""
        taken: List[str] = []
        for raw in raw_commands:
            cmd = speak_command(raw)
            key = _norm(cmd)
            if not key or key in self.commands_seen:
                continue
            self.commands_seen.append(key)
            if len(self.commands_seen) > MAX_COMMANDS:
                self.commands_skipped += 1
                continue
            taken.append(cmd)
        return taken

    def text(self) -> str:
        return re.sub(r"\s+", " ", " ".join(self.parts)).strip()


def _commands_phrase(cmds: List[str], label: str = "") -> str:
    if not cmds:
        return ""
    joined = "; then ".join(cmds)
    if label:
        return end_sentence(f"{label}: {joined}" if RUN_VERB_RE.search(label) else f"{label}: run {joined}")
    return end_sentence(f"Run: {joined}")


def _item_title(raw: str) -> str:
    """'**Mode**: `explain`' -> 'Mode: explain'; long bold-led items keep just their bold title."""
    m = re.match(r"^\*\*(.+?)\*\*\s*[:\-–—]?\s*(.*)$", raw.strip())
    if m:
        title = clean_inline(m.group(1)).rstrip(":").strip()
        desc = clean_inline(m.group(2))
        if not desc:
            return title
        if len(title.split()) <= 3 or len(desc) <= 40:
            return f"{title}: {shorten(split_sentences(desc)[0], 100)}"
        return title
    text = clean_inline(raw)
    sentences = split_sentences(text)
    return shorten(sentences[0], 150) if sentences else ""


def _shell_commands(code) -> List[str]:
    return extract_commands(code) if is_shell_block(code) else []


def _inline_commands(raw: str) -> List[str]:
    return [c for c in INLINE_RUN_RE.findall(raw) if is_inline_command(c)]


def _item_phrase(item: ListItem, brief: _Brief) -> Tuple[str, bool]:
    title = _item_title(item.text).rstrip(".:; ")
    raw_cmds: List[str] = []
    value = None
    for code in item.code:
        found = _shell_commands(code)
        raw_cmds.extend(found)
        if not found and value is None:
            value = single_line_value(code)
    cmds = brief.take_commands(raw_cmds)
    if cmds:
        joined = "; then ".join(cmds)
        if not title:
            return f"run {joined}", True
        return (f"{title}: {joined}" if RUN_VERB_RE.search(title) else f"{title}: run {joined}"), True
    if value and title:
        return f"{title}: {value}", False
    return title, False


def _speak_list(block: Block, label: str, brief: _Brief, commands_only: bool) -> str:
    cap = 5 if block.ordered else 4
    phrases: List[str] = []
    hidden = 0
    for idx, item in enumerate(block.items):
        phrase, has_cmd = _item_phrase(item, brief)
        if not phrase:
            continue
        # Items past the cap are only spoken when they carry a command.
        if (commands_only and not has_cmd) or (idx >= cap and not has_cmd):
            hidden += 0 if commands_only else 1
            continue
        phrases.append(phrase)
    if not phrases:
        return ""

    titles = [_item_title(it.text) for it in block.items]
    if len(phrases) >= 2 and all(OPTION_RE.match(t) for t in titles):
        body = "; or ".join(phrases)
    elif block.ordered and len(phrases) >= 2 and not commands_only:
        steps = [f"first, {phrases[0]}"] + [f"then, {p}" for p in phrases[1:-1]]
        last = "and finally" if len(phrases) > 2 and not hidden else "then"
        steps.append(f"{last}, {phrases[-1]}")
        body = "; ".join(steps)
    elif len(phrases) >= 3:
        body = "; ".join(phrases[:-1]) + "; and " + phrases[-1]
    else:
        body = "; ".join(phrases)
    if hidden:
        body += f"; plus {hidden} more"
    return end_sentence(f"{label}: {body}" if label else body)


def _speak_table(block: Block, label: str) -> str:
    header, body = block.rows[0], block.rows[1:]
    if not body:
        return ""
    if len(header) <= 3:
        rows = []
        for row in body[:4]:
            cells = [clean_inline(c) for c in row]
            text = f"{cells[0]}: {', '.join(c for c in cells[1:] if c)}" if len(cells) > 1 else cells[0]
            rows.append(shorten(text, 90))
        text = "; ".join(r for r in rows if r)
        if len(body) > 4:
            text += f"; plus {len(body) - 4} more rows"
        return end_sentence(f"{label}: {text}" if label else text)
    cols = [clean_inline(h) for h in header if clean_inline(h)]
    summary = f"a table of {len(body)} rows with columns {_join_and(cols)}"
    return end_sentence(f"{label}: {summary}" if label else f"There's {summary}")


def _alert_kind(block: Block, sentences: List[str], label: str) -> Tuple[str, List[str], str]:
    """Detects a callout ([!WARNING] quote or 'Note:' paragraph) and strips its prefix."""
    kind = block.alert
    if not kind:
        first = sentences[0] if sentences else label
        m = ALERT_PREFIX_RE.match(first)
        if not m:
            return "", sentences, label
        kind = m.group(1)
        if sentences:
            sentences = [first[m.end():]] + sentences[1:]
        else:
            label = first[m.end():]
    return kind.capitalize(), sentences, label


def _speak_section(blocks: List[Block], brief: _Brief, commands_only: bool, prose_heavy: bool) -> str:
    out: List[str] = []
    paragraphs = lists = tables = notes = 0
    label = ""
    unspoken_cmds: List[str] = []  # inline `commands` whose sentence we didn't read

    def keep_unspoken(cmds: List[str], spoken: str) -> None:
        unspoken_cmds.extend(c for c in cmds if clean_inline(f"`{c}`") not in spoken)

    for k, b in enumerate(blocks):
        nxt = blocks[k + 1] if k + 1 < len(blocks) else None
        if b.kind in ("paragraph", "quote"):
            sentences = split_sentences(clean_inline(b.text))
            label = ""
            if sentences and sentences[-1].endswith(":") and nxt is not None and nxt.kind in ("list", "code", "table"):
                label = sentences.pop()[:-1].strip()
            kind, sentences, label = _alert_kind(b, sentences, label)
            if kind:
                # Callouts are always read, but only their first sentence.
                if sentences:
                    alert = end_sentence(f"{kind}: {shorten(sentences[0], 200)}")
                    out.append(alert)
                    keep_unspoken(_inline_commands(b.text), alert)
                elif label:
                    label = f"{kind}: {label}"
                continue
            spoken = ""
            if not commands_only and sentences and paragraphs < (4 if prose_heavy else 3):
                chosen = sentences[:1]
                if paragraphs == 0 and len(sentences) > 1 and len(chosen[0]) < 90:
                    chosen.append(sentences[1])
                # Intros that lead into something we don't read ("Here's what changed:") add nothing.
                chosen = [s for s in chosen if not s.endswith(":")] or chosen[:1]
                spoken = " ".join(end_sentence(shorten(s, 220)) for s in chosen)
                out.append(spoken)
                paragraphs += 1
            keep_unspoken(_inline_commands(b.text), spoken)
        elif b.kind == "list":
            spoken = _speak_list(b, label, brief, commands_only=commands_only or lists >= 2)
            out.append(spoken)
            lists += 1
            for item in b.items:
                keep_unspoken(_inline_commands(item.text), spoken)
            label = ""
        elif b.kind == "table":
            if not commands_only and tables < 2 and b.rows:
                out.append(_speak_table(b, label))
                tables += 1
            label = ""
        elif b.kind == "code":
            cmds = _shell_commands(b.code)
            if cmds:
                out.append(_commands_phrase(brief.take_commands(cmds), label))
            elif not commands_only:
                value = single_line_value(b.code)
                if value and label:
                    out.append(end_sentence(f"{label}: {value}"))
                elif notes < 2 and not value:
                    desc = describe_code(b.code)
                    out.append(f"{label}: there's {desc} on screen." if label else f"There's {desc} on screen.")
                    notes += 1
            label = ""

    if unspoken_cmds:
        out.append(_commands_phrase(brief.take_commands(unspoken_cmds)))
    return " ".join(p for p in out if p).strip()


def _clean_title(raw: str) -> str:
    title = clean_inline(raw)
    title = re.sub(r"^\d+[.)]\s*", "", title)
    return title.strip().rstrip(":").strip()


def _group_sections(blocks: List[Block]) -> List[Tuple[str, List[Block]]]:
    sections: List[Tuple[str, List[Block]]] = [("", [])]
    for b in blocks:
        if b.kind == "heading":
            sections.append((_clean_title(b.text), []))
        else:
            sections[-1][1].append(b)
    return [s for s in sections if s[0] or s[1]]


def _closing_sentence(blocks: List[Block]) -> Optional[str]:
    """The question or next step the response ends on, if any."""
    content = [b for b in blocks if b.kind != "heading"]
    if not content:
        return None
    last = content[-1]
    if last.kind == "list" and len(content) >= 2 and content[-2].kind == "paragraph":
        intro = split_sentences(clean_inline(content[-2].text))
        if intro and (intro[-1].endswith("?") or (intro[-1].endswith(":") and QUESTION_RE.search(intro[-1]))):
            choices = [_item_title(it.text).rstrip(".:;?") for it in last.items[:4]]
            return f"{intro[-1].rstrip(':?').strip()}: {'; or '.join(c for c in choices if c)}?"
    if last.kind not in ("paragraph", "quote"):
        return None
    sentences = split_sentences(clean_inline(last.text))
    for s in reversed(sentences):
        if s.endswith("?") and len(s) <= 220:
            return s
    for s in reversed(sentences):
        if s.lower().startswith(CLOSING_PREFIXES) and len(s) <= 220:
            return end_sentence(s)
    if sentences and len(sentences[0]) <= 160 and not sentences[0].endswith(":"):
        return end_sentence(sentences[0])
    return None


def heuristic_explain(raw_text: str, budget: int = DEFAULT_BUDGET) -> str:
    """Creates a conversational spoken brief that scales with the response."""
    text = strip_thinking(raw_text or "").strip()
    if not text:
        return ""
    blocks = parse_markdown(text)

    full = render_full(blocks, speak_code=True)
    if len(full) <= SHORT_RESPONSE_CHARS:
        return full

    sections = _group_sections(blocks)
    prose_heavy = not any(b.kind in ("list", "table", "code") for b in blocks)
    n_options = sum(1 for title, _ in sections if OPTION_RE.match(title))
    n_steps = sum(1 for title, _ in sections if STEP_RE.match(title))
    announced = set()
    brief = _Brief(budget)

    for title, sblocks in sections:
        if not sblocks:
            if title and not brief.parts:
                brief.add(end_sentence(title))  # a title-only heading opening the response
            continue
        if OPTION_RE.match(title) and n_options >= 2 and "options" not in announced:
            brief.add(f"There are {n_options} options.")
            announced.add("options")
        if STEP_RE.match(title) and n_steps >= 2 and "steps" not in announced:
            brief.add(f"There are {n_steps} steps.")
            announced.add("steps")

        over = brief.over_budget()
        body = _speak_section(sblocks, brief, commands_only=over, prose_heavy=prose_heavy)
        if not body:
            if over and title:
                brief.also_covers.append(title)
            continue
        if title and title.lower() not in GENERIC_TITLES:
            sep = " " if title[-1] in ".!?" else ": "
            brief.add(title + sep + body)
        else:
            brief.add(body)

    if brief.also_covers:
        brief.add(end_sentence("It also covers " + _join_and(brief.also_covers[:4])))
    if brief.commands_skipped:
        brief.add(f"Plus {brief.commands_skipped} more commands, shown on screen.")

    closing = _closing_sentence(blocks)
    if closing and not brief.contains(closing):
        brief.add(closing)

    return brief.text() or full


def try_llm_explain(text: str, api_key: str) -> Optional[str]:
    """Optionally calls Gemini 2.5 Flash if an API key is configured."""
    try:
        from google import genai

        client = genai.Client(api_key=api_key)
        prompt = (
            "You are a spoken voice assistant companion for an AI coding terminal. "
            "Convert the following AI assistant message into a natural, conversational, 2-to-3 sentence spoken summary. "
            "Highlight the core takeaway, actions taken, every command to run (phrase them clearly for speech), "
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
        llm_result = try_llm_explain(strip_thinking(raw_text), api_key)
        if llm_result:
            return llm_result

    try:
        budget = int(config.get("explain_max_chars", DEFAULT_BUDGET))
    except (TypeError, ValueError):
        budget = DEFAULT_BUDGET
    return heuristic_explain(raw_text, budget)

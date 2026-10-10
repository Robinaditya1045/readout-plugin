#!/usr/bin/env python3
"""
markdown_speech.py - Shared markdown parsing and speech cleanup for voice-readout.

Turns agent markdown into structured blocks (headings, paragraphs, lists, code,
tables, quotes) and provides helpers that make prose and shell commands sound
natural when spoken by a TTS engine. Used by both explain and direct modes.
"""

import os
import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple


# ---------------------------------------------------------------------------
# Block model
# ---------------------------------------------------------------------------

@dataclass
class CodeBlock:
    lang: str
    body: str
    title: str = ""  # file name from the fence info string, if any


@dataclass
class ListItem:
    text: str
    children: List[str] = field(default_factory=list)
    code: List[CodeBlock] = field(default_factory=list)


@dataclass
class Block:
    kind: str  # heading | paragraph | list | code | table | quote
    text: str = ""
    level: int = 0
    ordered: bool = False
    items: List[ListItem] = field(default_factory=list)
    rows: List[List[str]] = field(default_factory=list)
    code: Optional[CodeBlock] = None
    alert: str = ""


FENCE_RE = re.compile(r"^(\s*)(`{3,}|~{3,})\s*(.*)$")
HEADING_RE = re.compile(r"^\s{0,3}(#{1,6})\s+(.*?)\s*#*\s*$")
LIST_RE = re.compile(r"^(\s*)([-*+]|\d{1,3}[.)])\s+(.*)$")
HR_RE = re.compile(r"^\s{0,3}([-*_])(\s*\1){2,}\s*$")
TABLE_SEP_RE = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$")
QUOTE_RE = re.compile(r"^\s{0,3}>\s?(.*)$")
ALERT_RE = re.compile(r"^\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]\s*", re.IGNORECASE)
BOLD_LINE_RE = re.compile(r"^\s*\*\*([^*]+?)\*\*\s*:?\s*$")


def strip_thinking(text: str) -> str:
    text = re.sub(r"<(thought|thinking)>.*?</\1>", "", text or "", flags=re.DOTALL)
    # An unclosed thinking tag means the rest is still internal reasoning.
    return re.sub(r"<(thought|thinking)>.*", "", text, flags=re.DOTALL)


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _is_fence(line: str) -> bool:
    m = FENCE_RE.match(line)
    return bool(m) and not (m.group(2).startswith("`") and "`" in m.group(3))


def _is_table_line(line: str) -> bool:
    s = line.strip()
    return s.startswith("|") and s.count("|") >= 2


def _starts_block(line: str) -> bool:
    return bool(
        _is_fence(line)
        or HEADING_RE.match(line)
        or HR_RE.match(line)
        or LIST_RE.match(line)
        or QUOTE_RE.match(line)
        or _is_table_line(line)
    )


def _parse_info(info: str) -> Tuple[str, str]:
    """Splits a fence info string like 'python title="app.py"' into (lang, title)."""
    info = info.strip().strip("{}").lstrip(".")
    if not info:
        return "", ""
    title = ""
    m = re.search(r"(?:title|filename|file)=[\"']?([^\"'\s]+)", info)
    if m:
        title = m.group(1)
    lang = info.split()[0]
    if ":" in lang:
        lang, _, path = lang.partition(":")
        title = title or path
    if "." in lang and "=" not in lang:
        # A bare file name used as the info string, e.g. ```app.py
        title = title or lang
        lang = lang.rsplit(".", 1)[-1]
    return lang.lower(), title


def _parse_fence(lines: List[str], i: int) -> Tuple[CodeBlock, int]:
    m = FENCE_RE.match(lines[i])
    indent, fence = len(m.group(1)), m.group(2)
    lang, title = _parse_info(m.group(3))
    close_re = re.compile(r"^\s*" + re.escape(fence[0]) + "{" + str(len(fence)) + r",}\s*$")
    body = []
    i += 1
    # An unclosed fence (e.g. a truncated response) runs to the end of the text.
    while i < len(lines) and not close_re.match(lines[i]):
        line = lines[i]
        body.append(line[min(indent, _indent(line)):])
        i += 1
    return CodeBlock(lang=lang, body="\n".join(body), title=title), i + 1


def _parse_table(lines: List[str], i: int) -> Tuple[Block, int]:
    rows = []
    while i < len(lines) and _is_table_line(lines[i]):
        line = lines[i].strip()
        i += 1
        if TABLE_SEP_RE.match(line):
            continue
        cells = [c.strip() for c in re.split(r"(?<!\\)\|", line.strip("|"))]
        rows.append(cells)
    return Block(kind="table", rows=rows), i


def _parse_quote(lines: List[str], i: int) -> Tuple[List[Block], int]:
    inner = []
    while i < len(lines) and QUOTE_RE.match(lines[i]):
        inner.append(QUOTE_RE.match(lines[i]).group(1))
        i += 1
    alert = ""
    m = ALERT_RE.match(inner[0].strip()) if inner else None
    if m:
        alert = m.group(1).upper()
        inner[0] = inner[0].strip()[m.end():]
    # Parse the quoted text as markdown so code and lists inside callouts keep their structure.
    blocks = parse_markdown("\n".join(inner))
    for k, b in enumerate(blocks):
        if b.kind == "paragraph":
            blocks[k] = Block(kind="quote", text=b.text, alert=alert)
            break
    return blocks, i


def _parse_list(lines: List[str], i: int) -> Tuple[Block, int]:
    first = LIST_RE.match(lines[i])
    base = len(first.group(1))
    ordered = first.group(2)[0].isdigit()
    items: List[ListItem] = []
    cur: Optional[ListItem] = None
    n = len(lines)

    while i < n:
        line = lines[i]
        if not line.strip():
            # A blank line continues the list only if what follows belongs to it.
            j = i + 1
            while j < n and not lines[j].strip():
                j += 1
            if j >= n:
                break
            m = LIST_RE.match(lines[j])
            same_list = m and _indent(lines[j]) <= base + 1 and m.group(2)[0].isdigit() == ordered
            if same_list or _indent(lines[j]) > base + 1:
                i = j
                continue
            break

        m = LIST_RE.match(line)
        if m and _indent(line) <= base + 1 and not HR_RE.match(line):
            if m.group(2)[0].isdigit() != ordered:
                break  # bullets switched to numbers (or back): that's a new list
            cur = ListItem(text=m.group(3).strip())
            items.append(cur)
            i += 1
            continue
        if cur is None:
            break

        if _indent(line) > base + 1:
            if _is_fence(line):
                code, i = _parse_fence(lines, i)
                cur.code.append(code)
                continue
            child = LIST_RE.match(line)
            if child or (cur.code and not cur.children):
                cur.children.append(child.group(3).strip() if child else line.strip())
            elif cur.children:
                cur.children[-1] += " " + line.strip()
            else:
                cur.text += " " + line.strip()
            i += 1
            continue

        if not _starts_block(line) and not BOLD_LINE_RE.match(line):
            cur.text += " " + line.strip()  # lazy continuation line
            i += 1
            continue
        break

    return Block(kind="list", ordered=ordered, items=items), i


def _join_lines(lines: List[str]) -> str:
    """Joins paragraph lines; "**Key:** value" lines become separate sentences."""
    text = lines[0]
    for prev, line in zip(lines, lines[1:]):
        separate = line.startswith("**") or BOLD_LINE_RE.match(prev)
        text += (". " if separate and prev.rstrip("*")[-1:] not in ".!?:;," else " ") + line
    return text


def parse_markdown(text: str) -> List[Block]:
    lines = (text or "").expandtabs(4).splitlines()
    blocks: List[Block] = []
    i, n = 0, len(lines)
    while i < n:
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        if _is_fence(line):
            code, i = _parse_fence(lines, i)
            blocks.append(Block(kind="code", code=code))
            continue
        m = HEADING_RE.match(line)
        if m:
            blocks.append(Block(kind="heading", text=m.group(2), level=len(m.group(1))))
            i += 1
            continue
        if HR_RE.match(line):
            i += 1
            continue
        if _is_table_line(line):
            block, i = _parse_table(lines, i)
            blocks.append(block)
            continue
        if QUOTE_RE.match(line):
            quoted, i = _parse_quote(lines, i)
            blocks.extend(quoted)
            continue
        if LIST_RE.match(line):
            block, i = _parse_list(lines, i)
            blocks.append(block)
            continue

        para = [line.strip()]
        i += 1
        while i < n and lines[i].strip() and not _starts_block(lines[i]):
            para.append(lines[i].strip())
            i += 1
        bold = BOLD_LINE_RE.match(para[0]) if len(para) == 1 else None
        if bold:
            # A bold-only line ("**Option 1: Use Docker**") works as a heading.
            blocks.append(Block(kind="heading", text=bold.group(1).strip().rstrip(":"), level=6))
        else:
            blocks.append(Block(kind="paragraph", text=_join_lines(para)))
    return blocks


# ---------------------------------------------------------------------------
# Inline speech cleanup
# ---------------------------------------------------------------------------

HTML_TAGS = (
    "a|abbr|b|blockquote|br|center|code|del|details|div|em|font|h[1-6]|hr|i|img|ins|kbd|li|mark|ol|p|pre|"
    "s|samp|small|span|strong|sub|summary|sup|table|tbody|td|th|thead|tr|u|ul"
)
HTML_TAG_RE = re.compile(r"</?(?:%s)\b[^<>]*/?>" % HTML_TAGS, re.IGNORECASE)
PLACEHOLDER_RE = re.compile(r"<([A-Za-z][\w-]*)>")
URL_RE = re.compile(r"\b(?:https?|file)://[^\s<>()\[\]`]+[^\s<>()\[\]`.,;:!?'\"]")
EMOJI_RE = re.compile(
    "[\U0001F000-\U0001FAFF☀-➿⬀-⯿■-◿️‍⃣]"
)


def speak_url(url: str) -> str:
    """Reads a URL as its host (plus a short path) instead of spelling every character."""
    if url.lower().startswith("file://"):
        path = url[len("file://"):].split("#")[0].rstrip("/")
        return os.path.basename(path) or path
    m = re.match(r"https?://([^/?#]+)([^?#]*)", url, re.IGNORECASE)
    if not m:
        return url
    host, path = m.group(1), m.group(2).rstrip("/")
    if host.startswith("www."):
        host = host[4:]
    return host + path if path and len(path) <= 25 else host


def _speak_placeholder(m: re.Match) -> str:
    return m.group(1).replace("_", " ").replace("-", " ").lower()


def clean_inline(text: str) -> str:
    """Strips inline markdown, HTML, URLs and emoji so a sentence reads naturally."""
    if not text:
        return ""
    codes: List[str] = []

    def stash(m: re.Match) -> str:
        code = PLACEHOLDER_RE.sub(_speak_placeholder, m.group(2).strip())
        codes.append(URL_RE.sub(lambda u: speak_url(u.group(0)), code))
        return "\x00%d\x00" % (len(codes) - 1)

    # Inline code is protected so identifiers like load_config keep their underscores.
    text = re.sub(r"(`+)(.+?)\1", stash, text)
    text = re.sub(r"!\[([^\]]*)\]\([^)]*\)", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"<((?:https?|file)://[^>]+)>", r"\1", text)
    text = URL_RE.sub(lambda m: speak_url(m.group(0)), text)
    text = HTML_TAG_RE.sub(" ", text)
    text = PLACEHOLDER_RE.sub(_speak_placeholder, text)
    text = re.sub(r"(\*\*|__)(?=\S)(.+?)(?<=\S)\1", r"\2", text)
    text = re.sub(r"(?<![\w*])\*(?=\S)([^*\n]+?)(?<=\S)\*(?![\w*])", r"\1", text)
    text = re.sub(r"(?<!\w)_(?=\S)([^_\n]+?)(?<=\S)_(?!\w)", r"\1", text)
    text = re.sub(r"~~(.+?)~~", r"\1", text)
    text = re.sub(r"\$?\\(?:rightarrow|Rightarrow|longrightarrow|to)\$?|\s*(?:→|->|⟶|=>)\s*", " to ", text)
    text = EMOJI_RE.sub("", text)
    text = re.sub(r"\s+\|\s+", ", ", text)
    text = re.sub(r"<([^<>\s]{1,40})>", r"\1", text)  # leftover <a|b> style choices
    text = re.sub(r"\x00(\d+)\x00", lambda m: codes[int(m.group(1))], text)
    text = re.sub(r"\s+", " ", text).strip()
    # Drop spaces left before punctuation, but not before names like ".venv" or "./run.sh".
    text = re.sub(r"\s+([,.;:!?])(?=\s|$)", r"\1", text)
    text = re.sub(r"(?<!\.)\.\.(?!\.)", ".", text)
    return text.lstrip(",;: ")


ABBREVIATIONS = ("e.g.", "i.e.", "etc.", "vs.", "approx.", "incl.", "no.", "fig.")


def split_sentences(text: str) -> List[str]:
    # Only split on terminators followed by whitespace, so "readout.py" or "v1.2" stay whole.
    raw = [s.strip() for s in re.split(r"(?<=[.!?])\s+(?=[^a-z\s])|\n+", text.strip()) if s.strip()]
    merged: List[str] = []
    for s in raw:
        if merged and merged[-1].lower().endswith(ABBREVIATIONS):
            merged[-1] += " " + s
        else:
            merged.append(s)
    return merged


def shorten(text: str, limit: int) -> str:
    """Cuts text at a clause or word boundary near the limit."""
    text = text.strip()
    if len(text) <= limit:
        return text
    cut = text[:limit]
    for sep in ("; ", ", ", " — ", " - ", " ("):
        pos = cut.rfind(sep)
        if pos > limit // 2:
            cut = cut[:pos]
            break
    else:
        cut = cut.rsplit(" ", 1)[0]
    if cut.count("(") > cut.count(")"):
        cut = cut[: cut.rfind("(")]  # don't end inside a parenthetical
    return cut.rstrip(" ,;:(-—")


def end_sentence(text: str) -> str:
    text = text.strip().rstrip(",;")
    if text.endswith(":"):
        text = text[:-1]
    if text and text[-1] not in ".!?":
        text += "."
    return text


# ---------------------------------------------------------------------------
# Code and shell commands
# ---------------------------------------------------------------------------

SHELL_LANGS = {
    "bash", "sh", "zsh", "fish", "shell", "terminal", "console", "shell-session", "shellsession",
    "sh-session", "cmd", "bat", "batch", "powershell", "ps1", "pwsh", "ps",
}
OUTPUT_LANGS = {"", "text", "txt", "plaintext", "plain", "output", "log", "logs", "none"}
COMMAND_WORDS = {
    "sudo", "npm", "npx", "pnpm", "yarn", "bun", "node", "deno", "git", "gh", "pip", "pip3", "pipx",
    "python", "python3", "uv", "poetry", "pytest", "apt", "apt-get", "brew", "dnf", "yum", "pacman",
    "snap", "pkg", "docker", "docker-compose", "podman", "kubectl", "helm", "cargo", "rustup", "go",
    "make", "cmake", "curl", "wget", "cd", "ls", "cat", "cp", "mv", "rm", "mkdir", "chmod", "chown",
    "ssh", "scp", "rsync", "mosh", "tmux", "export", "source", "systemctl", "journalctl", "agy",
    "claude", "echo", "tailscale", "proot-distro", "ollama", "terraform", "gcloud", "aws", "az",
    "ffmpeg", "java", "mvn", "gradle", "dotnet", "flutter", "code", "open", "xdg-open", "kill",
    "pkill", "touch", "tar", "unzip", "which", "readout", "grep", "sed", "awk", "find", "head", "tail",
    "less", "nano", "vim", "ps", "df", "du", "ping", "lsof", "ip", "ln", "pwd", "tee", "xargs", "jq",
    "openssl", "base64", "sleep", "watch", "nohup", "crontab", "service", "ufw", "mount", "umount",
    "lsblk", "reboot", "mokutil", "modprobe", "dmesg", "flatpak", "zip", "gzip", "ssh-keygen",
    "ssh-copy-id", "ssh-add", "sftp", "dig", "nslookup", "gcc", "g++", "clang", "rustc", "javac",
    "tsc", "eslint", "prettier", "ruff", "black", "mypy", "flake8", "alembic", "uvicorn", "gunicorn",
    "flask", "django-admin", "psql", "mysql", "mongosh", "sqlite3", "redis-cli", "vercel", "netlify",
    "firebase", "supabase", "wrangler", "heroku", "adb", "fastboot", "bundle", "gem", "rails", "rake",
    "composer", "php", "swift", "xcodebuild", "pod", "dart", "expo", "vite", "next", "set", "alias",
    "unset", "env", "nvm", "pyenv", "conda", "pnpx", "bunx", "chsh", "passwd", "usermod", "visudo",
    "update-grub", "useradd", "su", "rsync", "7z", "rclone",
}
PROMPT_RE = re.compile(r"^\s*(?:[\w.-]+@[\w.-]+(?::[^$#\n]*)?[$#]|\$|%|❯|PS(?: [^>\n]*)?>)\s+")
HEREDOC_RE = re.compile(r"<<-?\s*['\"]?([A-Za-z_]\w*)['\"]?")
CONTINUATION_CHARS = ("\\", "`", "^")
OUTPUT_LINE_RE = re.compile(
    r"\.\.\.\s*(ok|FAILED|failed|passed|PASSED|ignored|done)\s*$|^(running \d+ tests?|test result:|"
    r"Requirement already satisfied|Successfully installed|Collecting |PASSED|FAILED|\d+ passed)"
)


def looks_like_command(line: str) -> bool:
    tokens = PROMPT_RE.sub("", line.strip()).split()
    while tokens and re.match(r"^[A-Za-z_]\w*=", tokens[0]):
        tokens = tokens[1:]  # FOO=bar cmd
    if not tokens:
        return False
    first = tokens[0]
    return first in COMMAND_WORDS or first.startswith(("./", "~/", "/")) or (
        "/" in first and "://" not in first and not first.endswith("/")
    )


def is_inline_command(code: str) -> bool:
    """Inline code worth reading as a command: `npm run dev` yes, a bare `sudo` no."""
    code = code.strip()
    return looks_like_command(code) and (len(code.split()) >= 2 or code.startswith(("./", "~/")))


def is_shell_block(code: CodeBlock) -> bool:
    if code.lang in SHELL_LANGS:
        return True
    if code.lang not in OUTPUT_LANGS:
        return False
    lines = [l for l in code.body.splitlines() if l.strip() and not l.strip().startswith("#")]
    return bool(lines) and all(looks_like_command(l) for l in lines[:3])


def _strip_trailing_comment(line: str) -> str:
    pos = line.find(" #")
    while pos != -1:
        before = line[:pos]
        if before.count("'") % 2 == 0 and before.count('"') % 2 == 0:
            return before.rstrip()
        pos = line.find(" #", pos + 1)
    return line


def extract_commands(code: CodeBlock) -> List[str]:
    """Pulls every runnable command out of a shell block, in order."""
    lines = code.body.splitlines()
    prompted = any(PROMPT_RE.match(l) for l in lines)
    commands: List[str] = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        i += 1
        if prompted:
            # Console transcripts: only prompted lines are commands, the rest is output.
            if not PROMPT_RE.match(line):
                continue
            line = PROMPT_RE.sub("", line)
        if not line or line.startswith(("#", "REM ", "::")):
            continue
        while line.endswith(CONTINUATION_CHARS) and i < len(lines):
            line = line[:-1].rstrip() + " " + lines[i].strip()
            i += 1
        heredoc = HEREDOC_RE.search(line)
        if heredoc:
            # Skip the heredoc body; it is file content, not commands.
            while i < len(lines) and lines[i].strip() != heredoc.group(1):
                i += 1
            i += 1
            line = HEREDOC_RE.sub("", line).strip() + " with the content shown"
        line = _strip_trailing_comment(line)
        if line and line not in ("do", "done", "then", "fi", "else", "{", "}", "end") and not OUTPUT_LINE_RE.search(line):
            commands.append(line)
    if not prompted and len(commands) >= 2:
        # A "bash" block that is mostly program output (test results, logs): keep only real commands.
        known = [c for c in commands if looks_like_command(c)]
        if not known or (len(commands) >= 3 and len(known) * 2 < len(commands)):
            return known
    return commands


def _speak_command_part(part: str) -> str:
    part = re.sub(r"\s+", " ", part).strip()
    if len(part) <= 90:
        return part
    tokens = part.split()
    name = tokens[0]
    if len(tokens) > 1 and re.match(r"^[a-z][\w-]*$", tokens[1]) and (name == "sudo" or len(tokens[1]) > 2):
        name += " " + tokens[1]
    return f"a long {name} command"


def _split_shell(cmd: str) -> Tuple[List[str], List[str]]:
    """Splits on &&, ||, ; and | outside quotes. Returns (segments, operators between them)."""
    segs, ops, buf, quote, i = [], [], "", None, 0
    while i < len(cmd):
        ch = cmd[i]
        if quote:
            quote = None if ch == quote else quote
        elif ch in "'\"":
            quote = ch
        elif cmd[i:i + 2] in ("&&", "||"):
            segs.append(buf)
            ops.append(cmd[i:i + 2])
            buf, i = "", i + 2
            continue
        elif ch in ";|":
            segs.append(buf)
            ops.append(ch)
            buf, i = "", i + 1
            continue
        buf += ch
        i += 1
    segs.append(buf)
    return segs, ops


def speak_command(cmd: str) -> str:
    cmd = PLACEHOLDER_RE.sub(_speak_placeholder, cmd)
    cmd = URL_RE.sub(lambda m: re.sub(r"^\w+://", "", m.group(0)), cmd)
    cmd = re.sub(r"\s*\d?>\s*/dev/null", "", cmd)
    cmd = re.sub(r"\s*2>&1", "", cmd)
    segs, ops = _split_shell(cmd)
    joiners = {"&&": ", and then ", "||": ", or else ", ";": ", then ", "|": ", piped to "}
    out = ""
    for k, seg in enumerate(segs):
        if not seg.strip():
            continue
        if out:
            out += joiners[ops[k - 1]]
        out += _speak_command_part(seg)
    return out.strip()


LANG_NAMES = {
    "py": "Python", "python": "Python", "python3": "Python", "js": "JavaScript", "javascript": "JavaScript",
    "mjs": "JavaScript", "jsx": "JSX", "ts": "TypeScript", "typescript": "TypeScript", "tsx": "TSX",
    "json": "JSON", "jsonc": "JSON", "json5": "JSON", "yaml": "YAML", "yml": "YAML", "toml": "TOML",
    "ini": "config", "cfg": "config", "conf": "config", "env": "environment", "dotenv": "environment",
    "html": "HTML", "css": "CSS", "scss": "SCSS", "sql": "SQL", "go": "Go", "rust": "Rust", "rs": "Rust",
    "java": "Java", "kotlin": "Kotlin", "kt": "Kotlin", "swift": "Swift", "c": "C", "h": "C",
    "cpp": "C++", "c++": "C++", "cc": "C++", "hpp": "C++", "cs": "C#", "csharp": "C#", "rb": "Ruby",
    "ruby": "Ruby", "php": "PHP", "lua": "Lua", "dockerfile": "Dockerfile", "docker": "Dockerfile",
    "makefile": "Makefile", "make": "Makefile", "xml": "XML", "graphql": "GraphQL", "proto": "Protobuf",
    "nginx": "Nginx config", "ssh-config": "SSH config", "sshconfig": "SSH config", "vue": "Vue",
    "svelte": "Svelte", "dart": "Dart", "r": "R", "scala": "Scala", "elixir": "Elixir", "hcl": "Terraform",
    "terraform": "Terraform", "tf": "Terraform", "md": "Markdown", "markdown": "Markdown", "csv": "CSV",
}
DIAGRAM_LANGS = {"mermaid", "plantuml", "dot", "graphviz"}


def _with_article(name: str) -> str:
    vowel_sound = name[0] in "AEIOUaeiou" or (name.split()[0].isupper() and name[0] in "FHLMNRSX")
    return ("an " if vowel_sound else "a ") + name


def describe_code(code: CodeBlock) -> str:
    """A short spoken description of a non-shell code block, e.g. 'a Python snippet for app.py'."""
    lang = code.lang
    target = f" for {os.path.basename(code.title)}" if code.title else ""
    if lang in ("diff", "patch"):
        return "a diff" + target
    if lang in DIAGRAM_LANGS:
        return "a diagram"
    if lang in OUTPUT_LANGS or lang in SHELL_LANGS:
        if re.search(r"[├└]──", code.body):
            return "a directory tree"
        return "some output" + target
    name = LANG_NAMES.get(lang, lang)
    return _with_article(f"{name} snippet") + target


def single_line_value(code: CodeBlock) -> Optional[str]:
    """Short one-line text blocks (a URL, a value to paste) are worth reading out directly."""
    if code.lang not in OUTPUT_LANGS:
        return None
    lines = [l.strip() for l in code.body.splitlines() if l.strip()]
    if len(lines) == 1 and len(lines[0]) <= 100:
        return clean_inline(lines[0])
    return None


# ---------------------------------------------------------------------------
# Full (direct mode) rendering
# ---------------------------------------------------------------------------

def _table_row_text(header: List[str], row: List[str]) -> str:
    cells = [clean_inline(c) for c in row]
    if len(header) == 2 and len(cells) >= 2:
        return f"{cells[0]}: {cells[1]}"
    return ", ".join(c for c in cells if c)


def render_full(blocks: List[Block], include_code_notice: bool = True, speak_code: bool = False) -> str:
    """Reads every block in order. Code becomes a short notice, or with speak_code,
    spoken commands and a description of any other snippet."""
    out: List[str] = []

    def code_notice(code: CodeBlock) -> None:
        if speak_code:
            after_colon = bool(out) and out[-1].endswith(":")
            cmds: List[str] = []
            for raw in extract_commands(code) if is_shell_block(code) else []:
                spoken = speak_command(raw)
                if spoken and spoken not in cmds:
                    cmds.append(spoken)
            if cmds:
                joined = "; then ".join(cmds)
                out.append(end_sentence(joined if after_colon else f"Run: {joined}"))
                return
            value = single_line_value(code)
            if value and after_colon:
                out.append(end_sentence(value))
            else:
                desc = describe_code(code)
                out.append(f"there's {desc} on screen." if after_colon else f"There's {desc} on screen.")
            return
        if include_code_notice:
            label = LANG_NAMES.get(code.lang) or ("Shell" if code.lang in SHELL_LANGS else "A")
            out.append(f"{label} code block omitted.")

    for b in blocks:
        if b.kind in ("heading", "paragraph"):
            text = clean_inline(b.text)
            if text:
                out.append(end_sentence(text) if b.kind == "heading" or not text.endswith(":") else text)
        elif b.kind == "quote":
            text = clean_inline(b.text)
            if text:
                out.append(end_sentence((b.alert.capitalize() + ": " if b.alert else "") + text))
        elif b.kind == "list":
            for item in b.items:
                text = clean_inline(item.text)
                if text:
                    out.append(end_sentence(text) if not item.code or not text.endswith(":") else text)
                for code in item.code:
                    code_notice(code)
                for child in item.children:
                    child_text = clean_inline(child)
                    if child_text:
                        out.append(end_sentence(child_text))
        elif b.kind == "table" and b.rows:
            header = b.rows[0]
            for row in b.rows:
                text = _table_row_text(header, row)
                if text:
                    out.append(end_sentence(text))
        elif b.kind == "code":
            code_notice(b.code)
    return " ".join(out).strip()

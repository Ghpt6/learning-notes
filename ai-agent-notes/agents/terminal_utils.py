"""Terminal color printing utilities."""

import json
import os
import re
import unicodedata

_ANSI_RE = re.compile(r"\033\[[0-9;]*m")

COLORS = {
    "black":   "\033[30m",
    "red":     "\033[31m",
    "green":   "\033[32m",
    "yellow":  "\033[33m",
    "blue":    "\033[34m",
    "magenta": "\033[35m",
    "cyan":    "\033[36m",
    "white":   "\033[37m",
    "gray":         "\033[90m",
    "light_green":  "\033[38;2;180;255;180m",
}
RESET = "\033[0m"


def cprint(text, color=None, end="\n", flush=False):
    """Print text with optional ANSI color.

    Supported colors: black, red, green, yellow, blue, magenta, cyan, white, gray.
    """
    code = COLORS.get(color, "")
    print(f"{code}{text}{RESET}" if code else text, end=end, flush=flush)


def clear_screen():
    """Clear the terminal screen including the scrollback buffer.

    Uses the platform's native clear command (cls on Windows) because it
    clears the entire console buffer. ANSI escape sequences like \\033[2J
    only clear the visible area and may be ignored by Windows consoles
    without VT processing enabled.
    """
    os.system("cls" if os.name == "nt" else "clear")


def _char_width(char):
    """Return the number of terminal columns occupied by one Unicode character."""
    if unicodedata.combining(char) or unicodedata.category(char) in {"Cc", "Cf"}:
        return 0
    return 2 if unicodedata.east_asian_width(char) in {"W", "F"} else 1


def _display_width(text):
    """Return the terminal display width of *text*, ignoring ANSI codes."""
    return sum(_char_width(char) for char in _ANSI_RE.sub("", text))


def _wrap_display_line(text, width, continuation_indent=""):
    """Split one logical line and optionally indent its continuation lines.

    ANSI escape sequences are preserved in output but excluded from width
    calculations so they do not affect wrapping or alignment.
    """
    if not text:
        return [""]

    lines = []
    current = []
    current_width = 0
    i = 0

    while i < len(text):
        # Consume any ANSI escape sequence (preserve in output, zero width)
        m = _ANSI_RE.match(text, i)
        if m:
            current.append(m.group())
            i = m.end()
            continue

        char = text[i]
        i += 1

        if char == "\t":
            spaces = 4 - (current_width % 4)
            chars = " " * spaces
        else:
            chars = char

        for expanded_char in chars:
            char_width = _char_width(expanded_char)
            if current and current_width + char_width > width:
                lines.append("".join(current))
                current = list(continuation_indent)
                current_width = _display_width(continuation_indent)
            current.append(expanded_char)
            current_width += char_width

    lines.append("".join(current))
    return lines


def _print_boxed_line(text, width, color=None):
    """Print text wrapped, padded, and enclosed by both vertical borders."""
    logical_lines = text.splitlines() or [""]
    for logical_line in logical_lines:
        leading_spaces = len(logical_line) - len(logical_line.lstrip(" \t"))
        indent_width = max(2, len(logical_line[:leading_spaces].expandtabs(4)))
        continuation_indent = " " * min(indent_width, max(0, width - 1))
        for line in _wrap_display_line(logical_line, width, continuation_indent):
            padding = " " * max(0, width - _display_width(line))
            cprint(f"║{line}{padding}║", color=color)


def print_messages(messages, title="Debug Messages"):
    """Print agent message history with formatted box and colors.

    Args:
        messages: List of message dicts with role/content fields.
        title: Title shown in the top border.
    """
    try:
        width = max(1, os.get_terminal_size().columns - 2)
    except OSError:
        width = 80

    role_colors = {
        "system": "yellow",
        "user": "cyan",
        "assistant": "green",
        "tool": "magenta",
    }
    role_labels = {
        "system": "SYSTEM",
        "user": "USER",
        "assistant": "ASSISTANT",
        "tool": "TOOL",
    }

    # Top border
    title = _wrap_display_line(title, width)[0]
    pad = max(0, width - _display_width(title))
    left = pad // 2
    right = pad - left
    cprint(f"╔{'═' * left}{title}{'═' * right}╗", color="gray")

    for i, message in enumerate(messages):
        role = message.get("role", "unknown")
        color = role_colors.get(role, "white")
        label = role_labels.get(role, role.upper())

        # Role header
        tag = f" [{i + 1}] {label} "
        tag = _wrap_display_line(tag, width)[0]
        tag_width = _display_width(tag)
        cprint(f"║{tag}{'─' * max(0, width - tag_width)}║", color=color)

        # Content formatting
        content_parts = []
        reasoning_parts = []

        if role == "tool":
            content_parts.append(f"  call_id: {message.get('tool_call_id', '')}")

        content = message.get("content", "")
        if content:
            try:
                parsed = json.loads(content)
                content_parts.append(json.dumps(parsed, ensure_ascii=False, indent=2))
            except (json.JSONDecodeError, TypeError):
                for line in content.split("\n"):
                    content_parts.append(f"  {line}" if line else "")
        else:
            # content_parts.append("  (无内容)")
            pass

        reasoning = message.get("reasoning_content", "")
        if reasoning:
            for line in reasoning.split("\n"):
                reasoning_parts.append(f"  {line}" if line else "")

        tool_calls = message.get("tool_calls")
        if tool_calls:
            for tc in tool_calls:
                fn = tc.get("function", {})
                name = fn.get('name', '?')
                args = fn.get('arguments', '')
                call_id = tc.get('id', '')
                # Bright white for function name
                name_colored = f"\033[97m{name}\033[0m"
                content_parts.append(f"  {name_colored}({args}) - {call_id}")

        for line in reasoning_parts:
            _print_boxed_line(line, width, color="gray")

        for line in content_parts:
            _print_boxed_line(line, width)

    # Bottom border
    cprint(f"╚{'═' * width}╝", color="gray")


def print_tool_list(tool_list, title="工具列表"):
    """Print tool definitions inside the same formatted box as print_messages.

    Each tool gets a header row with its bright-white name (light-green
    border, matching the tool accent used elsewhere), followed by its
    description wrapped and indented like message content.
    """
    try:
        width = max(1, os.get_terminal_size().columns - 2)
    except OSError:
        width = 80

    # Top border with centered title
    header = f"{title}（{len(tool_list)}）"
    header = _wrap_display_line(header, width)[0]
    pad = max(0, width - _display_width(header))
    left = pad // 2
    right = pad - left
    cprint(f"╔{'═' * left}{header}{'═' * right}╗", color="gray")

    for i, tool in enumerate(tool_list):
        function = tool.get("function", {})
        name = function.get("name", "?")
        description = function.get("description") or "无描述"

        # Tool name row, bright white name like terminal_utils tool_calls
        name_colored = f"\033[97m{name}\033[0m"
        tag = f" [{i + 1}] {name_colored} "
        tag = _wrap_display_line(tag, width)[0]
        tag_width = _display_width(tag)
        cprint(f"║{tag}{'─' * max(0, width - tag_width)}║", color="light_green")

        # Description wrapped like message content (2-space indent)
        for line in description.split("\n") or [""]:
            _print_boxed_line(f"  {line}" if line else "", width, color="gray")

    if not tool_list:
        _print_boxed_line("  (none)", width, color="gray")

    # Bottom border
    cprint(f"╚{'═' * width}╝", color="gray")

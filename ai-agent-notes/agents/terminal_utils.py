"""Terminal color printing utilities."""

import json
import os

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


def print_messages(messages, title="Debug Messages"):
    """Print agent message history with formatted box and colors.

    Args:
        messages: List of message dicts with role/content fields.
        title: Title shown in the top border.
    """
    try:
        width = os.get_terminal_size().columns - 2
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
    pad = max(0, width - len(title))
    left = pad // 2
    right = pad - left
    cprint(f"╔{'═' * left}{title}{'═' * right}╗", color="gray")

    for i, message in enumerate(messages):
        role = message.get("role", "unknown")
        color = role_colors.get(role, "white")
        label = role_labels.get(role, role.upper())

        # Role header
        tag = f" [{i + 1}] {label} "
        cprint(f"║{tag}{'─' * max(0, width - len(tag))}║", color=color)

        # Content formatting
        content_parts = []
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
            content_parts.append("  (无内容)")

        reasoning = message.get("reasoning_content", "")
        if reasoning:
            content_parts.append("  ── reasoning ──")
            for line in reasoning.split("\n"):
                content_parts.append(f"  {line}" if line else "")

        tool_calls = message.get("tool_calls")
        if tool_calls:
            content_parts.append("  ── tool_calls ──")
            for tc in tool_calls:
                fn = tc.get("function", {})
                content_parts.append(f"  {fn.get('name', '?')}({fn.get('arguments', '')})")
                content_parts.append(f"  id: {tc.get('id', '')}")

        for line in content_parts:
            display = line if len(line) <= width else line[:width - 1] + "…"
            print(f"║{display}")

        # if i < len(messages) - 1:
        #     cprint(f"║{'┄' * width}║", color="gray")

    # Bottom border
    cprint(f"╚{'═' * width}╝", color="gray")

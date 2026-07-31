"""Terminal color printing utilities."""

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

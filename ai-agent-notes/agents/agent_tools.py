import importlib.util
import json
import os
import shutil
import subprocess
import time
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, urlopen

from context_compression import (
    ContextCompressor,
    latest_user_query,
    recent_conversation_context,
)
from terminal_utils import cprint

tools = [
    {
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": "Get the current date and time in the user's location",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": (
                "Read a local UTF-8 text file, or list every item in a local "
                "directory, including hidden files and directories"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Absolute or relative path to a local file or directory",
                    },
                },
                "required": ["path"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "Search the web for information. Returns titles, URLs, and snippets.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query"
                    },
                    "num_results": {
                        "type": "integer",
                        "description": "Number of results to return (default: 5)",
                        "default": 5
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_webpage",
            "description": "Fetch and extract text content from a specific webpage URL",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The URL of the webpage to fetch"
                    }
                },
                "required": ["url"]
            }
        }
    }
]


def execute_tool(name, arguments):
    if name == "get_current_time":
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if name == "read_file":
        return read_file(arguments)
    if name == "search_web":
        return search_web(arguments)
    if name == "fetch_webpage":
        return fetch_webpage(arguments)

    return json.dumps(
        {"ok": False, "error": "unknown_tool", "message": f"Unknown tool: {name}"},
        ensure_ascii=False,
    )


def search_web(arguments):
    """Search the web with Firecrawl CLI."""
    try:
        parsed = json.loads(arguments)
        query = parsed["query"]
        num_results = int(parsed.get("num_results", 5))
        if not isinstance(query, str) or not query.strip() or not 1 <= num_results <= 100:
            raise ValueError("query must be non-empty and num_results must be between 1 and 100")

        firecrawl = shutil.which("firecrawl")
        if not firecrawl:
            return error_result("search_failed", "firecrawl CLI was not found")
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        return error_result("invalid_arguments", str(error))

    command = [
        firecrawl,
        "search",
        query,
        "--limit",
        str(num_results),
        "--sources",
        "web",
        "--json",
    ]
    for attempt in range(2):
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=70,
                check=True,
            )
            break
        except (OSError, subprocess.SubprocessError) as error:
            if attempt == 0:
                time.sleep(1)
                continue
            stderr = getattr(error, "stderr", "") or ""
            return error_result("search_failed", stderr.strip() or str(error))

    try:
        data = json.loads(completed.stdout)
        web_results = data.get("data", {}).get("web", [])
        results = []
        for item in web_results:
            results.append(
                {
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "snippet": item.get("description", ""),
                }
            )

        return json.dumps(
            {
                "query": query,
                "num_results": len(results),
                "results": results,
                "timestamp": time.time(),
            },
            ensure_ascii=False,
        )
    except json.JSONDecodeError as error:
        return error_result("search_failed", str(error))

MAX_WEBPAGE_LENGTH = 50_000
_PAGE_CACHE = {}
class _TextExtractor(HTMLParser):
    """Extract readable text and the title from a small HTML document."""

    ignored_tags = {"script", "style", "nav", "footer", "header"}
    block_tags = {
        "article", "aside", "blockquote", "br", "div", "h1", "h2", "h3",
        "h4", "h5", "h6", "li", "main", "p", "section", "table", "tr",
    }

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.title_parts = []
        self.in_title = False
        self.ignored_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.ignored_tags:
            self.ignored_depth += 1
        elif tag == "title":
            self.in_title = True
        elif not self.ignored_depth and tag in self.block_tags:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self.ignored_tags:
            self.ignored_depth = max(0, self.ignored_depth - 1)
        elif tag == "title":
            self.in_title = False
        elif not self.ignored_depth and tag in self.block_tags:
            self.parts.append("\n")

    def handle_data(self, data):
        if self.in_title:
            self.title_parts.append(data)
        if not self.ignored_depth and not self.in_title:
            self.parts.append(data)

    @property
    def title(self):
        return " ".join("".join(self.title_parts).split()) or "No title"

    @property
    def text(self):
        return "\n".join(
            line for line in (" ".join(line.split()) for line in "".join(self.parts).splitlines())
            if line
        )

def fetch_webpage(arguments):
    """Fetch a webpage, remove page chrome, and return readable text."""
    try:
        parsed = json.loads(arguments)
        url = parsed["url"]
        if not isinstance(url, str) or not url.strip():
            raise ValueError("url must be a non-empty string")
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        return error_result("invalid_arguments", str(error))

    if url in _PAGE_CACHE:
        return json.dumps(_PAGE_CACHE[url], ensure_ascii=False)

    try:
        request = Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
        )
        with urlopen(request, timeout=10) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            html = response.read().decode(charset, errors="replace")

        parser = _TextExtractor()
        parser.feed(html)
        content = parser.text
        if len(content) > MAX_WEBPAGE_LENGTH:
            content = content[:MAX_WEBPAGE_LENGTH] + "\n\n[Content truncated...]"

        result = {
            "url": url,
            "title": parser.title,
            "content": content,
            "content_length": len(content),
            "success": True,
            "timestamp": time.time(),
        }
    except Exception as error:
        result = {
            "url": url,
            "title": "Error",
            "content": f"Failed to fetch webpage: {error}",
            "content_length": 0,
            "success": False,
            "error": str(error),
            "timestamp": time.time(),
        }

    _PAGE_CACHE[url] = result
    return json.dumps(result, ensure_ascii=False)

def read_file(arguments):
    try:
        parsed_arguments = json.loads(arguments)
    except (json.JSONDecodeError, TypeError) as error:
        return json.dumps(
            {"ok": False, "error": "invalid_arguments", "message": str(error)},
            ensure_ascii=False,
        )

    path = parsed_arguments.get("path") if isinstance(parsed_arguments, dict) else None
    if not isinstance(path, str) or not path.strip():
        return json.dumps(
            {
                "ok": False,
                "error": "invalid_path",
                "message": "path must be a non-empty string",
            },
            ensure_ascii=False,
        )

    resolved_path = os.path.abspath(os.path.expanduser(path))
    try:
        if os.path.isdir(resolved_path):
            entries = []
            with os.scandir(resolved_path) as directory:
                for entry in directory:
                    if entry.is_symlink():
                        entry_type = "symlink"
                    elif entry.is_dir(follow_symlinks=False):
                        entry_type = "directory"
                    elif entry.is_file(follow_symlinks=False):
                        entry_type = "file"
                    else:
                        entry_type = "other"

                    entries.append(
                        {
                            "name": entry.name,
                            "path": entry.path,
                            "type": entry_type,
                        }
                    )

            entries.sort(key=lambda entry: (entry["type"], entry["name"].casefold()))
            return json.dumps(
                {
                    "ok": True,
                    "path": resolved_path,
                    "type": "directory",
                    "entries": entries,
                },
                ensure_ascii=False,
            )

        with open(resolved_path, "r", encoding="utf-8") as file:
            content = file.read()
        return json.dumps(
            {
                "ok": True,
                "path": resolved_path,
                "type": "file",
                "content": content,
            },
            ensure_ascii=False,
        )
    except FileNotFoundError:
        error = "file_not_found"
        message = f"File does not exist: {resolved_path}"
    except PermissionError:
        error = "permission_denied"
        message = f"Permission denied: {resolved_path}"
    except UnicodeDecodeError:
        error = "decode_error"
        message = f"File is not valid UTF-8 text: {resolved_path}"
    except OSError as os_error:
        error = "io_error"
        message = str(os_error)

    return json.dumps(
        {"ok": False, "error": error, "message": message},
        ensure_ascii=False,
    )

SKILL_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_skill",
            "description": "Load a Skill's complete SKILL.md instructions before using it.",
            "parameters": {
                "type": "object",
                "properties": {"name": {"type": "string", "description": "Skill name"}},
                "required": ["name"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_skill_file",
            "description": "Read a text file inside a Skill for additional instructions or implementation details.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Skill name"},
                    "path": {"type": "string", "description": "Path relative to the skill directory"},
                },
                "required": ["name", "path"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_skill_script",
            "description": "Run the selected Skill's bundled Python script with a JSON payload.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Skill name"},
                    "script": {"type": "string", "description": "Filename inside the Skill's scripts directory"},
                    "payload": {"type": "string", "description": "JSON string passed to the bundled script"},
                },
                "required": ["name", "script", "payload"],
                "additionalProperties": False,
            },
        },
    },
]

# ── Agent Skills: progressive disclosure ──
ROOT = Path(__file__).resolve().parent
SKILLS_DIR = ROOT / "skills"
OUTPUT_DIR = ROOT / "output"


def is_within(path, directory):
    """Return whether a resolved path is inside directory (including on Windows)."""
    try:
        path.relative_to(directory)
        return True
    except ValueError:
        return False


def error_result(code, message):
    return json.dumps(
        {"ok": False, "error": code, "message": message},
        ensure_ascii=False,
    )


def read_skill(catalog, name):
    info = catalog.get(name)
    if not info:
        return error_result("skill_not_found", f"Skill does not exist: {name}")
    try:
        content = (info["dir"] / "SKILL.md").read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        return error_result("skill_read_failed", str(error))
    return json.dumps(
        {"ok": True, "name": name, "content": content},
        ensure_ascii=False,
    )


def read_skill_file(catalog, name, relative_path):
    info = catalog.get(name)
    if not info:
        return error_result("skill_not_found", f"Skill does not exist: {name}")

    target = (info["dir"] / relative_path).resolve()
    if not is_within(target, info["dir"]):
        return error_result("invalid_path", f"Path escapes the skill directory: {relative_path}")
    if not target.is_file():
        return error_result("file_not_found", f"Skill file does not exist: {relative_path}")
    try:
        content = target.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        return error_result("skill_file_read_failed", str(error))
    return json.dumps(
        {"ok": True, "name": name, "path": relative_path, "content": content},
        ensure_ascii=False,
    )


def run_skill_script(catalog, name, script, payload):
    info = catalog.get(name)
    if not info:
        return error_result("skill_not_found", f"Skill does not exist: {name}")

    scripts_dir = (info["dir"] / "scripts").resolve()
    script_path = (scripts_dir / script).resolve()
    if not is_within(script_path, scripts_dir):
        return error_result("invalid_script_path", f"Path escapes scripts directory: {script}")
    if not script_path.is_file() or script_path.suffix.lower() != ".py":
        return error_result("script_not_found", f"Python skill script does not exist: {script}")

    try:
        data = json.loads(payload) if isinstance(payload, str) else payload
    except json.JSONDecodeError as error:
        return error_result("invalid_payload", f"payload is not valid JSON: {error}")

    try:
        module_name = f"skill_{name}_{script_path.stem}"
        spec = importlib.util.spec_from_file_location(module_name, script_path)
        if spec is None or spec.loader is None:
            return error_result("script_load_failed", f"Cannot load skill script: {script}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        build_presentation = getattr(module, "build_presentation", None)
        if not callable(build_presentation):
            return error_result(
                "invalid_skill_script",
                "Skill script must expose build_presentation(payload, output_path)",
            )

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        output_path = OUTPUT_DIR / "presentation.pptx"
        result = build_presentation(data, str(output_path))
    except Exception as error:
        return error_result("skill_script_failed", f"{type(error).__name__}: {error}")

    return json.dumps(
        {"ok": True, "name": name, "script": script, "result": result},
        ensure_ascii=False,
        default=str,
    )


def execute_skill_tool(catalog, name, arguments):
    """Execute a skill-related tool call."""
    if name not in {"read_skill", "read_skill_file", "run_skill_script"}:
        return execute_tool(name, arguments)

    try:
        parsed = json.loads(arguments or "{}")
    except (json.JSONDecodeError, TypeError) as error:
        return error_result("invalid_arguments", str(error))
    if not isinstance(parsed, dict):
        return error_result("invalid_arguments", "Tool arguments must be a JSON object")

    required = {
        "read_skill": ("name",),
        "read_skill_file": ("name", "path"),
        "run_skill_script": ("name", "script", "payload"),
    }
    missing = [field for field in required[name] if field not in parsed]
    if missing:
        return error_result("missing_arguments", f"Missing: {', '.join(missing)}")

    string_fields = required[name]
    invalid = [
        field
        for field in string_fields
        if not isinstance(parsed[field], str) or not parsed[field].strip()
    ]
    if invalid:
        return error_result(
            "invalid_arguments",
            f"Must be non-empty strings: {', '.join(invalid)}",
        )

    if name == "read_skill":
        return read_skill(catalog, parsed["name"])
    if name == "read_skill_file":
        return read_skill_file(catalog, parsed["name"], parsed["path"])
    return run_skill_script(catalog, parsed["name"], parsed["script"], parsed["payload"])


def execute_agent_tool(
    catalog,
    name,
    arguments,
    *,
    messages,
    compression_client,
    compression_model,
    debug=True,
    compress_fetch=False,
):
    """Execute a tool and context-compress successful webpage results."""
    result = execute_skill_tool(catalog, name, arguments)
    if name != "fetch_webpage" or not compress_fetch:
        return result

    compressor = ContextCompressor(
        client=compression_client,
        model=compression_model,
    )
    compressed = compressor.compress_fetch_webpage_result(
        result,
        query=latest_user_query(messages),
        current_context=recent_conversation_context(messages),
    )

    if debug:
        cprint(
            f"\n===== fetch_webpage 原文（{compressed.original_length:,} 字符）=====",
            color="cyan",
        )
        print(result)
        ratio = (
            compressed.compressed_length / compressed.original_length * 100
            if compressed.original_length
            else 0
        )
        cprint(
            "===== CONTEXT_AWARE 压缩后 "
            f"（{compressed.original_length:,} → "
            f"{compressed.compressed_length:,} 字符, "
            f"压缩率 {ratio:.1f}%）=====",
            color="magenta",
        )
        print(compressed.content)
        if compressed.used_fallback:
            reason = compressed.error or "网页抓取未成功或正文为空"
            cprint(f"[压缩回退] {reason}", color="yellow")
        print()

    return compressed.content

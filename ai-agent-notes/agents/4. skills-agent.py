import argparse
import importlib.util
import json
import os
from types import SimpleNamespace
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI
from agent_tools import execute_tool as execute_base_tool
from agent_tools import tools as base_tools
from terminal_utils import cprint

# Parse command line arguments
parser = argparse.ArgumentParser()
parser.add_argument("--no-debug", action="store_true", help="Disable debug message output")
args = parser.parse_args()

# Load environment variables from .env in the project root
load_dotenv()

client = OpenAI(
    base_url=os.getenv("base_url") or "https://api.deepseek.com",
    api_key=os.getenv("api_key"),
)

ROOT = Path(__file__).resolve().parent
SKILLS_DIR = ROOT / "skills"
OUTPUT_DIR = ROOT / "output"


# ── Agent Skills: progressive disclosure ──
def parse_frontmatter(skill_md):
    """Parse the simple name/description YAML frontmatter used by SKILL.md."""
    lines = skill_md.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}

    metadata = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if ":" in line:
            key, value = line.split(":", 1)
            metadata[key.strip()] = value.strip().strip("\"'")
    return metadata


def scan_skill_catalog():
    """Read only skill metadata at startup; full instructions are loaded on demand."""
    catalog = {}
    if not SKILLS_DIR.is_dir():
        return catalog

    for skill_md in sorted(SKILLS_DIR.glob("*/SKILL.md")):
        try:
            metadata = parse_frontmatter(skill_md.read_text(encoding="utf-8"))
        except (OSError, UnicodeError) as error:
            cprint(f"[Skill] Failed to read {skill_md}: {error}", color="red")
            continue

        name = metadata.get("name") or skill_md.parent.name
        catalog[name] = {
            "description": metadata.get("description", ""),
            "dir": skill_md.parent.resolve(),
        }
    return catalog


def build_system_prompt(catalog):
    lines = [
        "You are a helpful assistant. Use tools to get real-time information when needed. "
        "Always reply in Chinese.",
        "",
        "You can use Agent Skills through progressive disclosure. The catalog below contains "
        "only each skill's name and routing description.",
        "When a task matches a skill, you must first call read_skill to load its complete "
        "SKILL.md. If more detail is needed, call read_skill_file. Follow the loaded instructions "
        "and use run_skill_script when the skill requires its bundled script. Do not guess a "
        "skill's workflow without reading SKILL.md.",
        "",
        "Installed skills:",
    ]
    if not catalog:
        lines.append("- (none)")
    else:
        for name, info in catalog.items():
            lines.append(f"- {name}: {info['description']}")
    return "\n".join(lines)


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


def execute_agent_tool(catalog, name, arguments):
    if name not in {"read_skill", "read_skill_file", "run_skill_script"}:
        return execute_base_tool(name, arguments)

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

# ── Message formatting ──
def normalize_assistant_message(message):
    normalized = {
        "role": message.role,
        "content": message.content,
        "reasoning_content": message.reasoning_content
    }

    if message.tool_calls:
        normalized["tool_calls"] = [
            {
                "id": tool_call.id,
                "type": tool_call.type,
                "function": {
                    "name": tool_call.function.name,
                    "arguments": tool_call.function.arguments,
                },
            }
            for tool_call in message.tool_calls
        ]

    return normalized


def collect_streaming_message(response):
    reasoning_content = ""
    content = ""
    tool_calls = {}
    content_started = False

    for chunk in response:
        if not chunk.choices:
            continue

        delta = chunk.choices[0].delta
        reasoning_delta = getattr(delta, "reasoning_content", None)
        content_delta = getattr(delta, "content", None)

        if reasoning_delta:
            reasoning_content += reasoning_delta
            cprint(reasoning_delta, color="gray", end="", flush=True)

        if content_delta:
            content += content_delta
            if reasoning_content and not content_started:
                print()
            print(content_delta, end="", flush=True)
            content_started = True

        for tool_call_delta in getattr(delta, "tool_calls", None) or []:
            tool_call = tool_calls.setdefault(
                tool_call_delta.index,
                {"id": "", "type": "function", "name": "", "arguments": ""},
            )
            if tool_call_delta.id:
                tool_call["id"] = tool_call_delta.id
            if tool_call_delta.type:
                tool_call["type"] = tool_call_delta.type
            if tool_call_delta.function:
                tool_call["name"] += tool_call_delta.function.name or ""
                tool_call["arguments"] += tool_call_delta.function.arguments or ""

    if reasoning_content or content:
        print()

    return SimpleNamespace(
        role="assistant",
        reasoning_content=reasoning_content,
        content=content,
        tool_calls=[
            SimpleNamespace(
                id=tool_call["id"],
                type=tool_call["type"],
                function=SimpleNamespace(
                    name=tool_call["name"],
                    arguments=tool_call["arguments"],
                ),
            )
            for _, tool_call in sorted(tool_calls.items())
        ] or None,
    )


def print_messages(messages):
    for message in messages:
        print(json.dumps(message, ensure_ascii=False))


# ── Initial message list ──
skill_catalog = scan_skill_catalog()
tools = base_tools + SKILL_TOOLS
user_input = input("> ")
messages = [
    {"role": "system", "content": build_system_prompt(skill_catalog)},
    {"role": "user", "content": user_input},
]

# ── Agent core loop ──
try:
    while True:
        response = client.chat.completions.create(
            model=os.getenv("model"), messages=messages, tools=tools,
            stream=True, reasoning_effort="max", extra_body={"thinking": {"type": "enabled"}}
        )
        assistant_message = collect_streaming_message(response)

        # Append model's response to message list (whether text or tool calls)
        messages.append(normalize_assistant_message(assistant_message))
        if not args.no_debug:
            print_messages(messages)
            print()

        # If no tool calls requested, the model has produced its final response
        if not assistant_message.tool_calls:
            user_input = input("> ")
            messages.append({"role": "user", "content": user_input})
        else:
            # Execute each tool requested by the model, append results to message list
            for tool_call in assistant_message.tool_calls:
                cprint(
                    f"[Tool] {tool_call.function.name}({tool_call.function.arguments})",
                    color="light_green",
                )
                result = execute_agent_tool(
                    skill_catalog,
                    tool_call.function.name,
                    tool_call.function.arguments,
                )
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result,
                })

except KeyboardInterrupt:
    print("\nbye！")

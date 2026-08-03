import argparse
import json
import os
from types import SimpleNamespace
from dotenv import load_dotenv
from openai import OpenAI
from agent_tools import execute_skill_tool, SKILL_TOOLS
from agent_tools import tools as base_tools
from terminal_utils import cprint, print_messages
from skill_catalog import scan_skill_catalog

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


# ── Initial message list ──
skill_catalog = scan_skill_catalog()
tools = base_tools + SKILL_TOOLS
messages = [
    {"role": "system", "content": build_system_prompt(skill_catalog)},
]

# ── Agent core loop ──
try:
    while True:
        user_input = input("> ")
        if user_input.strip() == "/debug":
            print_messages(messages)
            print()
            continue
        if user_input.strip() == "/clear":
            messages = [messages[0]]
            print("会话已清理\n")
            continue
        if user_input.strip().startswith("/"):
            print(f"未知命令: {user_input.strip()}\n")
            continue
        messages.append({"role": "user", "content": user_input})

        while True:
            response = client.chat.completions.create(
                model=os.getenv("model"), messages=messages, tools=tools,
                stream=True, reasoning_effort="max", extra_body={"thinking": {"type": "enabled"}}
            )
            assistant_message = collect_streaming_message(response)
            messages.append(normalize_assistant_message(assistant_message))
            
            if not args.no_debug:
                print_messages(messages)
                print()

            if not assistant_message.tool_calls:
                break

            # Execute each tool requested by the model, append results to message list
            for tool_call in assistant_message.tool_calls:
                cprint(
                    f"[Tool] {tool_call.function.name}({tool_call.function.arguments})",
                    color="light_green",
                )
                result = execute_skill_tool(
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

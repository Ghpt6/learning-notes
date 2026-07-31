import argparse
import json
import os
from types import SimpleNamespace

from dotenv import load_dotenv
from openai import OpenAI
from datetime import datetime

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

# ── Tool definitions ──
tools = [
    {
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": "Get the current date and time in a specific timezone",
            "parameters": {
                "type": "object",
                "properties": {
                    "timezone": {"type": "string", "description": "Timezone name, e.g. America/Vancouver"}
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get the current weather for a specific city",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "City name"},
                    "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]},
                },
            },
        },
    },
]

# ── Tool execution function
def execute_tool(name, arguments):
    if name == "get_current_time":
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    elif name == "get_weather":
        return '{"temperature": 13.2, "unit": "celsius", "conditions": "clear", "humidity": 93}'

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
            print(reasoning_delta, end="", flush=True)

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
user_input = input("> ")
messages = [
    {"role": "system", "content": "You are a helpful assistant. Use tools to get real-time information when needed. Always reply in Chinese."},
    {"role": "user", "content": user_input},
]

# ── Agent core loop ──
try:
    while True:
        response = client.chat.completions.create(
            model="deepseek-v4-pro", messages=messages, tools=tools,
            stream=True, reasoning_effort="high", extra_body={"thinking": {"type": "enabled"}}
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
                result = execute_tool(tool_call.function.name, tool_call.function.arguments)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result,
                })
            
except KeyboardInterrupt:
    print("\nbye！")

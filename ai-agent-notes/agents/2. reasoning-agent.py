import argparse
import json
import os

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
        "reasoning_content ": message.reasoning_content
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
            model=os.getenv("model"), messages=messages, tools=tools,
            reasoning_effort="max", extra_body={"thinking": {"type": "enabled"}}
        )
        assistant_message = response.choices[0].message

        # Append model's response to message list (whether text or tool calls)
        messages.append(normalize_assistant_message(assistant_message))
        if not args.no_debug:
            print_messages(messages)
            print()

        # If no tool calls requested, the model has produced its final response
        if not assistant_message.tool_calls:
            print(assistant_message.reasoning_content)
            print(assistant_message.content)
            user_input = input("> ")
            messages.append({"role": "user", "content": user_input})
        else:
            # Execute each tool requested by the model, append results to message list
            print(assistant_message.reasoning_content)
            print(assistant_message.content)
            for tool_call in assistant_message.tool_calls:
                result = execute_tool(tool_call.function.name, tool_call.function.arguments)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result,
                })
            
except KeyboardInterrupt:
    print("\nbye！")

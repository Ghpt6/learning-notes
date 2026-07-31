import json
import os
from datetime import datetime


tools = [
    {
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": "Get the current date and time in a specific timezone",
            "parameters": {
                "type": "object",
                "properties": {
                    "timezone": {
                        "type": "string",
                        "description": "Timezone name, e.g. America/Vancouver",
                    },
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
]


def execute_tool(name, arguments):
    if name == "get_current_time":
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if name == "get_weather":
        return '{"temperature": 13.2, "unit": "celsius", "conditions": "clear", "humidity": 93}'
    if name == "read_file":
        return read_file(arguments)

    return json.dumps(
        {"ok": False, "error": "unknown_tool", "message": f"Unknown tool: {name}"},
        ensure_ascii=False,
    )


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

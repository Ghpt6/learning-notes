"""Agent 应用配置：命令行参数、项目配置加载与环境变量应用。"""
import argparse
import json
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config.json"


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--compress-fetch", action="store_true", help="Enable fetch_webpage tool compression")
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help="JSON config path (default: <project root>/config.json)",
    )
    return parser.parse_args()


def load_project_config(path):
    """Load the agent environment and MCP servers from a JSON file."""
    try:
        with path.open("r", encoding="utf-8-sig") as config_file:
            config = json.load(config_file)
    except FileNotFoundError as error:
        raise ValueError(f"找不到配置文件: {path}") from error
    except OSError as error:
        raise ValueError(f"无法读取配置文件 {path}: {error}") from error
    except json.JSONDecodeError as error:
        raise ValueError(f"配置文件不是有效的 JSON ({path}): {error}") from error

    if not isinstance(config, dict):
        raise ValueError("配置文件根节点必须是 JSON 对象")

    env = config.get("env", {})
    if not isinstance(env, dict):
        raise ValueError("配置项 'env' 必须是 JSON 对象")
    mcp_servers = config.get("mcpServers", {})
    if not isinstance(mcp_servers, dict):
        raise ValueError("配置项 'mcpServers' 必须是 JSON 对象")

    normalized_env = {}
    for name, value in env.items():
        if not isinstance(name, str) or not name.strip():
            raise ValueError("'env' 中的变量名必须是非空字符串")
        if value is None or isinstance(value, (dict, list)):
            raise ValueError(f"环境变量 {name!r} 的值必须是字符串、数字或布尔值")
        normalized_env[name] = str(value)

    normalized_config = dict(config)
    normalized_config["env"] = normalized_env
    normalized_config["mcpServers"] = mcp_servers
    return normalized_config


def get_setting(env, name, default=None):
    """Read a setting after the JSON env has been applied to this process."""
    return os.getenv(name, env.get(name, default))


def apply_env(config_env):
    """Apply the configured env to this process, scoped to the current run."""
    os.environ.update(config_env)

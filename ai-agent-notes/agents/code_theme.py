"""Markdown 代码块配色主题管理(/code-theme 命令相关逻辑)。"""

import json

from rich.markdown import Markdown
from pygments.styles import get_all_styles

from terminal_utils import cprint

DEFAULT_THEME = "monokai"
CODE_THEMES = sorted(get_all_styles())
THEME_DEMO = """
```python
import os
from pathlib import Path

# 常量与装饰器
MAX_RETRIES = 3
BASE_URL = "https://api.example.com/v1"

@staticmethod
def greet(name: str) -> str:
    \"\"\"返回问候语\"\"\"
    return f"你好，{name}！"

class Agent:
    def __init__(self, model: str, temperature: float = 0.7):
        self.model = model
        self.temperature = temperature
        self._history: list[str] = []

    async def run(self, prompt: str) -> dict | None:
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = await self._call_api(prompt)
                self._history.append(response)
                return {"status": "ok", "data": response}
            except TimeoutError as error:
                print(f"[{attempt}/{MAX_RETRIES}] 请求超时: {error}")
        return None
```

```javascript
// 工具注册示例
const tools = [
  { name: "read_file",   description: "读取文件内容" },
  { name: "write_file",  description: "写入文件内容" },
  { name: "search_code", description: "搜索代码片段" },
];

async function executeTool(name, args) {
  const tool = tools.find(t => t.name === name);
  if (!tool) throw new Error(`Unknown tool: ${name}`);
  const result = await tool.handler(args);
  return { tool, result, timestamp: Date.now() };
}
```

```bash
# 启动 Agent 并加载配置
export AGENT_MODEL="gpt-4o"
python -m agent.main --config ./config.json --verbose
```
"""

# 当前 Markdown 代码块配色主题
_current_theme = DEFAULT_THEME


def render_markdown(text):
    """Render markdown text with the current code theme."""
    return Markdown(text, code_theme=_current_theme)


def load_theme(config):
    """Restore the saved theme from the config, falling back to DEFAULT_THEME."""
    global _current_theme
    theme = config.get("theme") or DEFAULT_THEME
    if theme not in CODE_THEMES:
        cprint(
            f"配置中的主题无效: {theme},已回退到 {DEFAULT_THEME}",
            color="yellow",
        )
        theme = DEFAULT_THEME
    _current_theme = theme


def set_theme(theme):
    """Validate and switch the theme; return an error message if invalid."""
    if theme not in CODE_THEMES:
        return f"未知主题: {theme}"
    global _current_theme
    _current_theme = theme
    return None


def save_theme_setting(config_path):
    """Persist the current theme into the config file; return None or an error."""
    try:
        with config_path.open("r", encoding="utf-8-sig") as config_file:
            config = json.load(config_file)
    except (OSError, json.JSONDecodeError) as error:
        return f"无法读取配置文件: {error}"
    config["theme"] = _current_theme
    try:
        with config_path.open("w", encoding="utf-8") as config_file:
            json.dump(config, config_file, ensure_ascii=False, indent=4)
            config_file.write("\n")
    except OSError as error:
        return f"无法写入配置文件: {error}"
    return None


def print_theme_options():
    """Print the current code theme and all available options."""
    cprint(f"当前代码块主题: {_current_theme}", color="cyan")
    print("可用主题:")
    for name in CODE_THEMES:
        marker = "  (当前)" if name == _current_theme else ""
        print(f"  {name:<18}{marker}")
    print("\n切换: /code-theme <主题名>")

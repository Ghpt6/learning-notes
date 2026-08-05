"""Markdown 代码块配色主题管理(/code-theme 命令相关逻辑)。"""

import json

from rich.markdown import Markdown
from pygments.styles import get_all_styles

from terminal_utils import cprint

DEFAULT_THEME = "monokai"
CODE_THEMES = sorted(get_all_styles())
THEME_DEMO = """# 一级标题 Heading 1

## 二级标题 Heading 2

### 三级标题 Heading 3

#### 四级标题 Heading 4

---

**加粗文本** 与 **bold**, *斜体文本* 与 *italic*, ***粗斜体***, ~~删除线~~, `行内代码`。

[普通链接](https://example.com) 和 **加粗链接**: [文档首页](https://example.com/docs)

> 引用块:这是一段引用的内容,
> 可以**换行**继续写,也可以 `代码`。

- 无序列表项一
- 无序列表项二
  - 嵌套子项
  - 嵌套子项
- 无序列表项三

1. 有序列表项一
2. 有序列表项二
3. 有序列表项三

| 列 A | 列 B | 列 C |
| :--- | :---: | ---: |
| 左对齐 | 居中 | 右对齐 |
| `code` | **bold** | [link](https://example.com) |

---

一段包含 `行内代码`、**粗体**、*斜体* 与 [链接](https://example.com) 的正文,末尾跟一个代码块:

```python
print("hello, world!")
print("你好，世界！")
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

"""Markdown 整体样式主题管理（/theme 命令相关逻辑）。

控制标题、链接、表格、引用、列表等所有 Markdown 元素的渲染样式，
通过 Rich Console 的 Theme 机制覆盖默认的 markdown.* 样式。
"""

import json

from rich.console import Console
from rich.style import Style
from rich.theme import Theme

from terminal_utils import cprint

DEFAULT_THEME_NAME = "default"

# ── 预设主题 ─────────────────────────────────────────────────────────
# 每个主题是一个 dict，键为 Rich 的 markdown.* 样式名，值为 Style 对象。
# 未覆盖的键会回退到 Rich 默认值。

MARKDOWN_THEMES = {
    "default": {},  # 不做任何覆盖，使用 Rich 内置样式

    "ocean": {
        "markdown.h1":             Style(bold=True, color="bright_cyan", underline=True),
        "markdown.h2":             Style(bold=True, color="cyan", underline=True),
        "markdown.h3":             Style(bold=True, color="bright_blue"),
        "markdown.h4":             Style(color="bright_blue", italic=True),
        "markdown.h5":             Style(color="cyan", italic=True),
        "markdown.h6":             Style(color="bright_cyan", dim=True),
        "markdown.link":           Style(color="bright_cyan", underline=True),
        "markdown.link_url":       Style(color="cyan", underline=True),
        "markdown.table.border":   Style(color="bright_blue"),
        "markdown.table.header":   Style(color="bright_cyan", bold=True),
        "markdown.block_quote":    Style(color="cyan", italic=True),
        "markdown.list":           Style(color="bright_blue"),
        "markdown.item.bullet":    Style(color="bright_cyan", bold=True),
        "markdown.item.number":    Style(color="bright_cyan"),
        "markdown.code":           Style(color="bright_cyan", bgcolor="grey23"),
        "markdown.hr":             Style(color="bright_blue", dim=True),
        "markdown.strong":         Style(bold=True, color="bright_white"),
        "markdown.em":             Style(italic=True, color="bright_cyan"),
    },

    "forest": {
        "markdown.h1":             Style(bold=True, color="bright_green", underline=True),
        "markdown.h2":             Style(bold=True, color="green", underline=True),
        "markdown.h3":             Style(bold=True, color="bright_green"),
        "markdown.h4":             Style(color="green", italic=True),
        "markdown.h5":             Style(color="bright_green", italic=True),
        "markdown.h6":             Style(color="green", dim=True),
        "markdown.link":           Style(color="bright_green", underline=True),
        "markdown.link_url":       Style(color="green", underline=True),
        "markdown.table.border":   Style(color="green"),
        "markdown.table.header":   Style(color="bright_green", bold=True),
        "markdown.block_quote":    Style(color="green", italic=True),
        "markdown.list":           Style(color="bright_green"),
        "markdown.item.bullet":    Style(color="bright_green", bold=True),
        "markdown.item.number":    Style(color="bright_green"),
        "markdown.code":           Style(color="bright_green", bgcolor="grey23"),
        "markdown.hr":             Style(color="green", dim=True),
        "markdown.strong":         Style(bold=True, color="bright_white"),
        "markdown.em":             Style(italic=True, color="bright_green"),
    },

    "sunset": {
        "markdown.h1":             Style(bold=True, color="bright_red", underline=True),
        "markdown.h2":             Style(bold=True, color="bright_yellow", underline=True),
        "markdown.h3":             Style(bold=True, color="bright_red"),
        "markdown.h4":             Style(color="bright_yellow", italic=True),
        "markdown.h5":             Style(color="red", italic=True),
        "markdown.h6":             Style(color="yellow", dim=True),
        "markdown.link":           Style(color="bright_yellow", underline=True),
        "markdown.link_url":       Style(color="yellow", underline=True),
        "markdown.table.border":   Style(color="bright_red"),
        "markdown.table.header":   Style(color="bright_yellow", bold=True),
        "markdown.block_quote":    Style(color="yellow", italic=True),
        "markdown.list":           Style(color="bright_red"),
        "markdown.item.bullet":    Style(color="bright_yellow", bold=True),
        "markdown.item.number":    Style(color="bright_yellow"),
        "markdown.code":           Style(color="bright_yellow", bgcolor="grey23"),
        "markdown.hr":             Style(color="bright_red", dim=True),
        "markdown.strong":         Style(bold=True, color="bright_white"),
        "markdown.em":             Style(italic=True, color="bright_yellow"),
    },

    "minimal": {
        "markdown.h1":             Style(bold=True, underline=True),
        "markdown.h2":             Style(bold=True, underline=True),
        "markdown.h3":             Style(bold=True),
        "markdown.h4":             Style(italic=True),
        "markdown.h5":             Style(italic=True),
        "markdown.h6":             Style(dim=True),
        "markdown.link":           Style(underline=True),
        "markdown.link_url":       Style(underline=True, dim=True),
        "markdown.table.border":   Style(),
        "markdown.table.header":   Style(bold=True),
        "markdown.block_quote":    Style(italic=True),
        "markdown.list":           Style(),
        "markdown.item.bullet":    Style(bold=True),
        "markdown.item.number":    Style(),
        "markdown.code":           Style(bgcolor="grey23"),
        "markdown.hr":             Style(dim=True),
        "markdown.strong":         Style(bold=True),
        "markdown.em":             Style(italic=True),
    },
}

THEME_NAMES = sorted(MARKDOWN_THEMES.keys())

# ── 主题 Demo（展示 Markdown 各元素） ─────────────────────────────────

MARKDOWN_THEME_DEMO = """\
# 一级标题：快速总览

## 二级标题：功能介绍

### 三级标题：实现细节

这是一段正文，包含 **粗体** 和 *斜体* 效果。行内代码示例：`pip install rich`。

> 这是一段引用文本，用于展示 blockquote 的样式效果。

- 列表项一：无序列表
- 列表项二
  - 嵌套子项

1. 有序列表第一项
2. 有序列表第二项

| 功能 | 状态 | 说明 |
|------|------|------|
| 标题 | ✅ | h1 ~ h6 |
| 链接 | ✅ | 超链接 |
| 表格 | ✅ | Markdown 表格 |

---

[示例链接](https://example.com) · [Rich 文档](https://rich.readthedocs.io)
"""

# ── 状态管理 ─────────────────────────────────────────────────────────

_current_theme_name = DEFAULT_THEME_NAME


def _build_console():
    """根据当前主题创建 Console 实例。"""
    styles = MARKDOWN_THEMES.get(_current_theme_name, {})
    theme = Theme(styles) if styles else None
    return Console(theme=theme)


def get_themed_console():
    """返回使用当前 Markdown 主题的 Console。"""
    return _build_console()


def load_markdown_theme(config):
    """从配置恢复上次保存的主题。"""
    global _current_theme_name
    name = config.get("markdownTheme") or DEFAULT_THEME_NAME
    if name not in MARKDOWN_THEMES:
        cprint(
            f"配置中的 Markdown 主题无效: {name},已回退到 {DEFAULT_THEME_NAME}",
            color="yellow",
        )
        name = DEFAULT_THEME_NAME
    _current_theme_name = name


def set_markdown_theme(name):
    """验证并切换主题；返回 None 或错误信息。"""
    if name not in MARKDOWN_THEMES:
        return f"未知主题: {name}"
    global _current_theme_name
    _current_theme_name = name
    return None


def save_markdown_theme_setting(config_path):
    """将当前主题名持久化到配置文件。"""
    try:
        with config_path.open("r", encoding="utf-8-sig") as f:
            config = json.load(f)
    except (OSError, json.JSONDecodeError) as error:
        return f"无法读取配置文件: {error}"
    config["markdownTheme"] = _current_theme_name
    try:
        with config_path.open("w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=4)
            f.write("\n")
    except OSError as error:
        return f"无法写入配置文件: {error}"
    return None


def print_markdown_theme_options():
    """打印当前主题和所有可用选项。"""
    cprint(f"当前 Markdown 主题: {_current_theme_name}", color="cyan")
    print("可用主题:")
    for name in THEME_NAMES:
        marker = "  (当前)" if name == _current_theme_name else ""
        print(f"  {name:<18}{marker}")
    print("\n切换: /theme <主题名>")

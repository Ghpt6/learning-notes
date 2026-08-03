from agent_tools import SKILLS_DIR
from terminal_utils import cprint


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

"""Build the system prompt the model sees at the start of every run."""
from pathlib import Path

# The project root, worked out from this file so it works from any folder.
ROOT = Path(__file__).resolve().parent.parent
AGENTS_FILE = ROOT / "AGENTS.md"
SKILLS_DIR = ROOT / "skills"


def parse_skill(path):
    """Return a dict with the name and description from the top of a SKILL.md file."""
    text = path.read_text(encoding="utf-8")
    _, header, _ = text.split("---", 2)
    skill = {}
    for line in header.strip().splitlines():
        key, value = line.split(":", 1)
        skill[key.strip()] = value.strip()
    return skill


def build_skill_index():
    """Return one line per skill, listing only its name and description."""
    lines = []
    for path in sorted(SKILLS_DIR.glob("*/SKILL.md")):
        skill = parse_skill(path)
        lines.append(f"- {skill['name']}: {skill['description']}")
    return "\n".join(lines)


def build_system_prompt():
    """Return the text to put in the system message."""
    text = AGENTS_FILE.read_text(encoding="utf-8")
    return f"{text}\n\n## Available skills\n{build_skill_index()}\n"


if __name__ == "__main__":
    print(build_system_prompt())

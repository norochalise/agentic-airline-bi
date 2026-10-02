from pathlib import Path

from agentic_bi.skills.registry import SKILL_REGISTRY


# Root-level directory containing reusable SKILL.md definitions.
SKILLS_ROOT = Path(__file__).resolve().parents[3] / "skills"


def load_skill(skill_name: str) -> str:
    """
    Load the Markdown definition for a registered skill.

    Raises:
        ValueError: If the requested skill is not registered.
        FileNotFoundError: If the registered skill definition is missing.
    """

    if skill_name not in SKILL_REGISTRY:
        raise ValueError(f"Unknown skill: {skill_name}")

    skill_path = SKILLS_ROOT / skill_name / "SKILL.md"

    if not skill_path.exists():
        raise FileNotFoundError(
            f"Skill definition not found: {skill_path}"
        )

    return skill_path.read_text(encoding="utf-8")
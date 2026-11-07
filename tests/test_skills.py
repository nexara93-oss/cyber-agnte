from __future__ import annotations

from pathlib import Path

from agent_cyber.skills import SkillLoader


def _write_skill(root: Path, skill_id: str, *, description: str = "Custom skill") -> Path:
    directory = root / skill_id
    directory.mkdir(parents=True)
    path = directory / "SKILL.md"
    path.write_text(
        "---\n"
        f"id: {skill_id}\n"
        f"name: {skill_id.title()}\n"
        f"description: {description}\n"
        "version: 1.0.0\n"
        "triggers: test, custom\n"
        "---\n\n"
        "# Body\n\nDo the thing.\n",
        encoding="utf-8",
    )
    return path


def test_builtin_skills_load():
    loader = SkillLoader()
    skills = loader.load_all()
    assert not loader.errors
    assert {"security-report", "vuln-triage", "recon-plan", "log-analysis"} <= set(skills)
    assert skills["security-report"].body
    assert skills["security-report"].source == "builtin"


def test_custom_skill_can_override_builtin(tmp_path: Path):
    _write_skill(tmp_path, "security-report", description="Custom override")
    loader = SkillLoader(extra_dirs=[tmp_path])
    skills = loader.load_all()
    assert skills["security-report"].description == "Custom override"
    assert skills["security-report"].source == "custom"


def test_invalid_skill_is_reported(tmp_path: Path):
    directory = tmp_path / "broken"
    directory.mkdir()
    (directory / "SKILL.md").write_text(
        "---\nid: broken\nname: Broken\n---\n\nbody\n",
        encoding="utf-8",
    )
    loader = SkillLoader(extra_dirs=[tmp_path])
    skills = loader.load_all()
    assert "broken" not in skills
    assert loader.errors


def test_find_by_id_and_name():
    loader = SkillLoader()
    skills = loader.load_all()
    assert SkillLoader.find(skills, "security-report") is not None
    assert SkillLoader.find(skills, "Security Report Writer") is not None
    assert SkillLoader.find(skills, "does-not-exist") is None

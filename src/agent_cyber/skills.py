"""Skill discovery and loading.

A skill is a directory containing ``SKILL.md`` with YAML front matter and a
Markdown body. Built-in skills ship with the package; users can add or override
skills in ``<config>/skills`` or ``./skills``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .config import user_skills_dir

SKILL_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


class SkillError(RuntimeError):
    """Raised for an invalid skill manifest."""


@dataclass(slots=True)
class Skill:
    id: str
    name: str
    description: str
    body: str
    path: Path
    source: str
    version: str = "1.0.0"
    triggers: list[str] = field(default_factory=list)

    @property
    def label(self) -> str:
        return f"{self.name} ({self.id})"


class SkillLoader:
    def __init__(self, extra_dirs: list[Path] | None = None):
        package_dir = Path(__file__).resolve().parent / "skills" / "builtin"
        self.search_dirs: list[tuple[Path, str]] = [(package_dir, "builtin")]
        self.search_dirs.append((Path.cwd() / "skills", "project"))
        self.search_dirs.append((user_skills_dir(), "user"))
        for directory in extra_dirs or []:
            self.search_dirs.append((Path(directory), "custom"))
        self.errors: list[str] = []

    def load_all(self) -> dict[str, Skill]:
        self.errors = []
        skills: dict[str, Skill] = {}
        for directory, source in self.search_dirs:
            if not directory.is_dir():
                continue
            for manifest in sorted(directory.glob("*/SKILL.md")):
                try:
                    skill = self._load_one(manifest, source)
                except SkillError as exc:
                    self.errors.append(f"{manifest}: {exc}")
                    continue
                # Later directories intentionally override earlier ones.
                skills[skill.id] = skill
        return dict(sorted(skills.items(), key=lambda item: item[0]))

    def _load_one(self, path: Path, source: str) -> Skill:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise SkillError(f"could not read file: {exc}") from exc

        meta, body = _parse_frontmatter(text)
        skill_id = str(meta.get("id") or path.parent.name).strip().lower()
        if not SKILL_ID_RE.match(skill_id):
            raise SkillError(f"invalid skill id: {skill_id!r}")
        name = str(meta.get("name") or skill_id).strip()
        description = str(meta.get("description") or "").strip()
        if not description:
            raise SkillError("missing description")
        if not body.strip():
            raise SkillError("missing skill body")

        triggers_raw = meta.get("triggers", [])
        if isinstance(triggers_raw, str):
            triggers = [item.strip() for item in triggers_raw.split(",") if item.strip()]
        elif isinstance(triggers_raw, list):
            triggers = [str(item).strip() for item in triggers_raw if str(item).strip()]
        else:
            triggers = []

        return Skill(
            id=skill_id,
            name=name,
            description=description,
            body=body.strip(),
            path=path,
            source=source,
            version=str(meta.get("version", "1.0.0")),
            triggers=triggers,
        )

    @staticmethod
    def find(skills: dict[str, Skill], query: str) -> Skill | None:
        query = query.strip().lower()
        if not query:
            return None
        if query in skills:
            return skills[query]
        for skill in skills.values():
            if skill.name.lower() == query:
                return skill
        return None

    @staticmethod
    def catalog_text(skills: dict[str, Skill]) -> str:
        if not skills:
            return "No skills are installed."
        lines = []
        for skill in skills.values():
            lines.append(f"- `{skill.id}` — **{skill.name}**: {skill.description}")
        return "\n".join(lines)


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        raise SkillError("unterminated YAML front matter")
    try:
        meta = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError as exc:
        raise SkillError(f"invalid YAML front matter: {exc}") from exc
    if not isinstance(meta, dict):
        raise SkillError("front matter must be a mapping")
    return meta, parts[2].lstrip("\n")

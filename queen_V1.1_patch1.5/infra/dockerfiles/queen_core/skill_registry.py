"""
skill_registry.py — Registre de skills (base de connaissances).
Chaque skill est un dossier dans skills/ contenant un SKILL.md.
Le LLM peut lister et lire les skills à la demande.

Pattern inspiré de CyberStrikeAI : les skills ne sont PAS injectés
automatiquement dans le prompt. Le LLM les charge via read_skill
quand il en a besoin (économie de tokens).

Usage:
    from queen_core.skill_registry import get_skill_registry
    reg = get_skill_registry()
    names = reg.list_skills()
    content = reg.read_skill("python-optimization")
"""

import os
import logging
import threading
from typing import Dict, List, Optional

logger = logging.getLogger("queen.skill_registry")


class SkillEntry:
    __slots__ = ("name", "path", "summary", "content")

    def __init__(self, name: str, path: str, content: str):
        self.name = name
        self.path = path
        self.content = content
        # Extrait les premières lignes comme résumé
        lines = content.strip().split("\n")
        self.summary = ""
        for line in lines[:10]:
            stripped = line.strip().lstrip("#").strip()
            if stripped and not stripped.startswith("---"):
                self.summary = stripped
                break


class SkillRegistry:

    def __init__(self, skills_dir: str = "/app/skills"):
        self._skills_dir = skills_dir
        self._skills: Dict[str, SkillEntry] = {}
        self._lock = threading.Lock()
        self._load_all()

    def _load_all(self):
        if not os.path.isdir(self._skills_dir):
            logger.info(f"Skills directory {self._skills_dir} not found, skipping")
            return

        loaded = 0
        for entry_name in sorted(os.listdir(self._skills_dir)):
            entry_path = os.path.join(self._skills_dir, entry_name)

            # Soit un dossier avec SKILL.md dedans
            skill_md = os.path.join(entry_path, "SKILL.md")
            if os.path.isdir(entry_path) and os.path.isfile(skill_md):
                try:
                    with open(skill_md, "r", encoding="utf-8") as f:
                        content = f.read()
                    skill = SkillEntry(entry_name, skill_md, content)
                    with self._lock:
                        self._skills[entry_name] = skill
                    loaded += 1
                except Exception as e:
                    logger.warning(f"Failed to load skill {entry_name}: {e}")
                continue

            # Soit un fichier .md directement
            if entry_name.endswith(".md") and os.path.isfile(entry_path):
                try:
                    with open(entry_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    name = entry_name.replace(".md", "")
                    skill = SkillEntry(name, entry_path, content)
                    with self._lock:
                        self._skills[name] = skill
                    loaded += 1
                except Exception as e:
                    logger.warning(f"Failed to load skill {entry_name}: {e}")

        logger.info(f"Skill registry: loaded {loaded} skills from {self._skills_dir}")

    def reload(self) -> Dict[str, int]:
        with self._lock:
            self._skills.clear()
        self._load_all()
        return {"loaded": len(self._skills)}

    def list_skills(self) -> List[Dict[str, str]]:
        """Liste les skills avec nom et résumé (pas le contenu complet)."""
        with self._lock:
            return [
                {"name": s.name, "summary": s.summary}
                for s in self._skills.values()
            ]

    def read_skill(self, name: str) -> Optional[str]:
        """Retourne le contenu complet d'un skill. None si introuvable."""
        with self._lock:
            skill = self._skills.get(name)
            return skill.content if skill else None

    def list_names(self) -> List[str]:
        with self._lock:
            return list(self._skills.keys())

    def count(self) -> int:
        with self._lock:
            return len(self._skills)


# ─── Singleton ────────────────────────────────────────────────────────────────

_skill_registry: Optional[SkillRegistry] = None
_skill_lock = threading.Lock()


def get_skill_registry(skills_dir: str = "/app/skills") -> SkillRegistry:
    global _skill_registry
    if _skill_registry is None:
        with _skill_lock:
            if _skill_registry is None:
                _skill_registry = SkillRegistry(skills_dir)
    return _skill_registry

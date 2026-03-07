"""
role_registry.py — Registre de rôles définis en YAML.
Chaque rôle pré-configure : le system_prompt LLM, les outils autorisés,
les contraintes par défaut, et les skills attachés.

Usage:
    from queen_core.role_registry import get_role_registry
    reg = get_role_registry()
    role = reg.get("optimizer")
    prompt = role.build_system_prompt()
"""

import os
import logging
import threading
from typing import Dict, List, Optional, Any

logger = logging.getLogger("queen.role_registry")

try:
    import yaml
except ImportError:
    yaml = None


class RoleDef:
    """Définition d'un rôle chargé depuis un fichier YAML."""

    __slots__ = (
        "name", "description", "icon", "user_prompt",
        "tools", "skills", "default_constraints", "enabled",
        "source_file",
    )

    def __init__(self, data: Dict[str, Any], source_file: str = ""):
        self.name: str = data.get("name", "")
        self.description: str = data.get("description", "")
        self.icon: str = data.get("icon", "🐝")
        self.user_prompt: str = data.get("user_prompt", "")
        self.tools: List[str] = data.get("tools", [])
        self.skills: List[str] = data.get("skills", [])
        self.default_constraints: Dict[str, Any] = data.get("default_constraints", {})
        self.enabled: bool = bool(data.get("enabled", True))
        self.source_file: str = source_file

    def build_system_prompt(self, extra_context: str = "") -> str:
        """
        Construit le system prompt complet pour le LLM.
        Injecte le user_prompt du rôle + les noms de skills comme hints.
        """
        parts = []
        parts.append(f"Tu es un agent spécialisé : {self.description}")
        if self.user_prompt:
            parts.append(self.user_prompt)
        if self.tools:
            parts.append(f"Outils disponibles : {', '.join(self.tools)}")
        if self.skills:
            parts.append(
                f"Skills recommandés (utilise read_skill pour les charger si besoin) : "
                f"{', '.join(self.skills)}"
            )
        if extra_context:
            parts.append(extra_context)
        return "\n\n".join(parts)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "icon": self.icon,
            "user_prompt": self.user_prompt,
            "tools": self.tools,
            "skills": self.skills,
            "default_constraints": self.default_constraints,
            "enabled": self.enabled,
        }


def _parse_yaml_file(filepath: str) -> Optional[Dict[str, Any]]:
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        if yaml:
            return yaml.safe_load(content)
        # Fallback basique
        result: Dict[str, Any] = {}
        for line in content.split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if ":" in line:
                k, _, v = line.partition(":")
                k, v = k.strip(), v.strip()
                if v.lower() == "true":
                    result[k] = True
                elif v.lower() == "false":
                    result[k] = False
                else:
                    result[k] = v
        return result
    except Exception as e:
        logger.warning(f"Failed to parse role {filepath}: {e}")
        return None


class RoleRegistry:

    def __init__(self, roles_dir: str = "/app/roles"):
        self._roles_dir = roles_dir
        self._roles: Dict[str, RoleDef] = {}
        self._lock = threading.Lock()
        self._load_all()

    def _load_all(self):
        if not os.path.isdir(self._roles_dir):
            logger.info(f"Roles directory {self._roles_dir} not found, skipping")
            return

        loaded = 0
        for filename in sorted(os.listdir(self._roles_dir)):
            if not filename.endswith((".yaml", ".yml")):
                continue
            filepath = os.path.join(self._roles_dir, filename)
            data = _parse_yaml_file(filepath)
            if not data or not data.get("name"):
                continue
            role = RoleDef(data, source_file=filepath)
            if role.enabled:
                with self._lock:
                    self._roles[role.name] = role
                loaded += 1

        logger.info(f"Role registry: loaded {loaded} roles from {self._roles_dir}")

    def reload(self) -> Dict[str, int]:
        with self._lock:
            self._roles.clear()
        self._load_all()
        return {"loaded": len(self._roles)}

    def get(self, name: str) -> Optional[RoleDef]:
        with self._lock:
            return self._roles.get(name)

    def list_roles(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [r.to_dict() for r in self._roles.values() if r.enabled]

    def list_names(self) -> List[str]:
        with self._lock:
            return [n for n, r in self._roles.items() if r.enabled]


# ─── Singleton ────────────────────────────────────────────────────────────────

_role_registry: Optional[RoleRegistry] = None
_role_lock = threading.Lock()


def get_role_registry(roles_dir: str = "/app/roles") -> RoleRegistry:
    global _role_registry
    if _role_registry is None:
        with _role_lock:
            if _role_registry is None:
                _role_registry = RoleRegistry(roles_dir)
    return _role_registry

"""
tool_registry.py — Registre dynamique d'outils définis en YAML.
Inspiré du pattern tools/ de CyberStrikeAI, adapté à Queen V1.

Chaque fichier YAML dans le dossier tools/ définit un outil que les workers
peuvent exécuter. Le registre supporte le hot-reload (détection de changements).

Usage:
    from queen_core.tool_registry import registry
    tool = registry.get("python_exec")
    all_tools = registry.list_tools()
    registry.reload()  # force refresh
"""

import os
import logging
import threading
import time
from datetime import datetime
from typing import Dict, List, Optional, Any

logger = logging.getLogger("queen.tool_registry")

try:
    import yaml
except ImportError:
    # Fallback: on parse du YAML basique à la main
    yaml = None


# ─── Tool dataclass ──────────────────────────────────────────────────────────

class ToolDef:
    """Définition d'un outil chargé depuis un fichier YAML."""

    __slots__ = (
        "name", "description", "category", "command_template",
        "timeout_seconds", "max_output_bytes", "sandbox",
        "allowed_extensions", "blocked_patterns", "enabled",
        "risk_level", "requires_approval", "env", "tags",
        "source_file", "loaded_at",
    )

    def __init__(self, data: Dict[str, Any], source_file: str = ""):
        self.name: str = data.get("name", "")
        self.description: str = data.get("description", "")
        self.category: str = data.get("category", "general")
        self.command_template: str = data.get("command_template", "")
        self.timeout_seconds: int = int(data.get("timeout_seconds", 300))
        self.max_output_bytes: int = int(data.get("max_output_bytes", 5_000_000))
        self.sandbox: bool = bool(data.get("sandbox", True))
        self.allowed_extensions: List[str] = data.get("allowed_extensions", [])
        self.blocked_patterns: List[str] = data.get("blocked_patterns", [])
        self.enabled: bool = bool(data.get("enabled", True))
        self.risk_level: str = data.get("risk_level", "medium")
        self.requires_approval: bool = bool(data.get("requires_approval", False))
        self.env: Dict[str, str] = data.get("env", {})
        self.tags: List[str] = data.get("tags", [])
        self.source_file: str = source_file
        self.loaded_at: str = datetime.utcnow().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "command_template": self.command_template,
            "timeout_seconds": self.timeout_seconds,
            "max_output_bytes": self.max_output_bytes,
            "sandbox": self.sandbox,
            "allowed_extensions": self.allowed_extensions,
            "blocked_patterns": self.blocked_patterns,
            "enabled": self.enabled,
            "risk_level": self.risk_level,
            "requires_approval": self.requires_approval,
            "tags": self.tags,
            "source_file": self.source_file,
        }

    def validate(self) -> List[str]:
        """Retourne une liste d'erreurs de validation (vide = OK)."""
        errors = []
        if not self.name:
            errors.append("name is required")
        if not self.name.replace("_", "").replace("-", "").isalnum():
            errors.append(f"name '{self.name}' must be alphanumeric (with - or _)")
        if self.timeout_seconds < 5 or self.timeout_seconds > 3600:
            errors.append(f"timeout_seconds {self.timeout_seconds} out of range [5, 3600]")
        if self.risk_level not in ("low", "medium", "high", "critical"):
            errors.append(f"risk_level '{self.risk_level}' invalid")
        return errors


# ─── YAML parsing ────────────────────────────────────────────────────────────

def _parse_yaml(filepath: str) -> Optional[Dict[str, Any]]:
    """Parse un fichier YAML. Supporte PyYAML ou fallback basique."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        if yaml:
            return yaml.safe_load(content)
        # Fallback très basique pour les cas sans PyYAML
        return _basic_yaml_parse(content)
    except Exception as e:
        logger.warning(f"Failed to parse {filepath}: {e}")
        return None


def _basic_yaml_parse(content: str) -> Dict[str, Any]:
    """Parser YAML minimaliste (clé: valeur, pas de nesting complexe)."""
    result: Dict[str, Any] = {}
    for line in content.split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" in line:
            key, _, val = line.partition(":")
            key = key.strip()
            val = val.strip()
            if val.lower() == "true":
                result[key] = True
            elif val.lower() == "false":
                result[key] = False
            elif val.isdigit():
                result[key] = int(val)
            else:
                result[key] = val
    return result


# ─── Registry ────────────────────────────────────────────────────────────────

class ToolRegistry:
    """
    Registre d'outils. Charge les YAML depuis un dossier,
    supporte hot-reload et filtrage par catégorie/tag.
    """

    def __init__(self, tools_dir: str = "/app/tools"):
        self._tools_dir = tools_dir
        self._tools: Dict[str, ToolDef] = {}
        self._lock = threading.Lock()
        self._file_mtimes: Dict[str, float] = {}
        self._load_all()

    def _load_all(self):
        """Charge ou recharge tous les fichiers YAML du dossier."""
        if not os.path.isdir(self._tools_dir):
            logger.info(f"Tools directory {self._tools_dir} not found, skipping")
            return

        loaded = 0
        errors = 0

        for filename in sorted(os.listdir(self._tools_dir)):
            if not filename.endswith((".yaml", ".yml")):
                continue
            filepath = os.path.join(self._tools_dir, filename)
            if not os.path.isfile(filepath):
                continue

            mtime = os.path.getmtime(filepath)
            self._file_mtimes[filepath] = mtime

            data = _parse_yaml(filepath)
            if not data:
                errors += 1
                continue

            tool = ToolDef(data, source_file=filepath)
            validation = tool.validate()
            if validation:
                logger.warning(f"Tool {filepath} validation errors: {validation}")
                errors += 1
                continue

            with self._lock:
                self._tools[tool.name] = tool
            loaded += 1

        logger.info(f"Tool registry: loaded {loaded} tools, {errors} errors from {self._tools_dir}")

    def reload(self) -> Dict[str, int]:
        """Force le rechargement complet. Retourne les stats."""
        with self._lock:
            self._tools.clear()
            self._file_mtimes.clear()
        self._load_all()
        return {"loaded": len(self._tools), "dir": self._tools_dir}

    def check_updates(self) -> int:
        """
        Vérifie les modifications (mtime) et recharge les fichiers changés.
        Retourne le nombre de fichiers rechargés.
        """
        if not os.path.isdir(self._tools_dir):
            return 0

        updated = 0
        for filename in os.listdir(self._tools_dir):
            if not filename.endswith((".yaml", ".yml")):
                continue
            filepath = os.path.join(self._tools_dir, filename)
            if not os.path.isfile(filepath):
                continue

            mtime = os.path.getmtime(filepath)
            old_mtime = self._file_mtimes.get(filepath, 0)

            if mtime > old_mtime:
                data = _parse_yaml(filepath)
                if data:
                    tool = ToolDef(data, source_file=filepath)
                    if not tool.validate():
                        with self._lock:
                            self._tools[tool.name] = tool
                        self._file_mtimes[filepath] = mtime
                        updated += 1
                        logger.info(f"Hot-reloaded tool: {tool.name}")

        return updated

    # ─── Accessors ────────────────────────────────────────────────────────

    def get(self, name: str) -> Optional[ToolDef]:
        """Récupère un outil par nom."""
        with self._lock:
            return self._tools.get(name)

    def list_tools(self, category: str = "", tag: str = "", enabled_only: bool = True) -> List[Dict[str, Any]]:
        """Liste les outils, filtrable par catégorie et/ou tag."""
        with self._lock:
            tools = list(self._tools.values())

        result = []
        for t in tools:
            if enabled_only and not t.enabled:
                continue
            if category and t.category != category:
                continue
            if tag and tag not in t.tags:
                continue
            result.append(t.to_dict())
        return result

    def list_names(self, enabled_only: bool = True) -> List[str]:
        """Liste juste les noms des outils."""
        with self._lock:
            if enabled_only:
                return [n for n, t in self._tools.items() if t.enabled]
            return list(self._tools.keys())

    def list_categories(self) -> List[str]:
        """Liste les catégories distinctes."""
        with self._lock:
            return sorted(set(t.category for t in self._tools.values()))

    def get_for_job_type(self, job_type: str) -> List[ToolDef]:
        """Retourne les outils dont la catégorie correspond au job_type."""
        with self._lock:
            return [t for t in self._tools.values() if t.enabled and (t.category == job_type or job_type in t.tags)]

    def count(self) -> int:
        with self._lock:
            return len(self._tools)


# ─── Singleton global ────────────────────────────────────────────────────────

_registry: Optional[ToolRegistry] = None
_registry_lock = threading.Lock()


def get_registry(tools_dir: str = "/app/tools") -> ToolRegistry:
    """Singleton thread-safe du registre."""
    global _registry
    if _registry is None:
        with _registry_lock:
            if _registry is None:
                _registry = ToolRegistry(tools_dir)
    return _registry


# Alias pour import direct
registry = None  # Initialisé au premier appel

def _ensure_registry():
    global registry
    if registry is None:
        registry = get_registry()
    return registry

"""
tool_routes.py — Endpoints API pour le registre d'outils.
À inclure dans api.py via: app.include_router(tool_router)
"""

from fastapi import APIRouter, HTTPException
from queen_core.tool_registry import get_registry

tool_router = APIRouter(prefix="/api/tools", tags=["Tools"])


@tool_router.get("")
def list_tools(category: str = "", tag: str = ""):
    """Liste tous les outils du registre, filtrable par catégorie ou tag."""
    reg = get_registry()
    return reg.list_tools(category=category, tag=tag)


@tool_router.get("/categories")
def list_categories():
    """Liste les catégories d'outils disponibles."""
    reg = get_registry()
    return {"categories": reg.list_categories()}


@tool_router.get("/stats")
def tool_stats():
    """Stats du registre : nombre d'outils, catégories, etc."""
    reg = get_registry()
    tools = reg.list_tools(enabled_only=False)
    enabled = [t for t in tools if t["enabled"]]
    return {
        "total": len(tools),
        "enabled": len(enabled),
        "categories": reg.list_categories(),
    }


@tool_router.get("/{tool_name}")
def get_tool(tool_name: str):
    """Détail d'un outil par nom."""
    reg = get_registry()
    tool = reg.get(tool_name)
    if not tool:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")
    return tool.to_dict()


@tool_router.post("/reload")
def reload_tools():
    """Force le rechargement de tous les fichiers YAML."""
    reg = get_registry()
    result = reg.reload()
    return result

"""skill_routes.py — Endpoints API pour le registre de skills (skills/)."""

from fastapi import APIRouter, HTTPException

from queen_core.skill_registry import get_skill_registry

skill_router = APIRouter(prefix="/api/skills", tags=["Skills"])


@skill_router.get("")
def list_skills():
    reg = get_skill_registry()
    return reg.list_skills()


@skill_router.get("/{skill_name}")
def read_skill(skill_name: str):
    reg = get_skill_registry()
    content = reg.read_skill(skill_name)
    if content is None:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_name}' not found")
    return {"name": skill_name, "content": content}


@skill_router.post("/reload")
def reload_skills():
    reg = get_skill_registry()
    return reg.reload()

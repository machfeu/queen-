"""role_routes.py — Endpoints API pour le registre de rôles (roles/)."""

from fastapi import APIRouter, HTTPException

from queen_core.role_registry import get_role_registry

role_router = APIRouter(prefix="/api/roles", tags=["Roles"])


@role_router.get("")
def list_roles():
    reg = get_role_registry()
    return reg.list_roles()


@role_router.get("/{role_name}")
def get_role(role_name: str):
    reg = get_role_registry()
    role = reg.get(role_name)
    if not role:
        raise HTTPException(status_code=404, detail=f"Role '{role_name}' not found")
    return role.to_dict()


@role_router.post("/reload")
def reload_roles():
    reg = get_role_registry()
    return reg.reload()

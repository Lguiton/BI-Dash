"""Practice / Real workspace switching and per-workspace settings."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services import workspaces

router = APIRouter(prefix="/api/workspaces", tags=["workspaces"])


class ActiveBody(BaseModel):
    name: str


class SettingsBody(BaseModel):
    ai_mode: str | None = None
    blocked_columns: list[str] | None = None
    backup_keep: int | None = None
    auto_backup: bool | None = None


@router.get("")
def get_workspaces():
    return {"active": workspaces.active(), "workspaces": workspaces.overview()}


@router.post("/active")
def set_active(body: ActiveBody):
    try:
        workspaces.activate(body.name)
    except workspaces.WorkspaceError as e:
        raise HTTPException(400, str(e)) from e
    return {"active": workspaces.active(), "workspaces": workspaces.overview()}


@router.get("/{name}/settings")
def get_settings(name: str):
    try:
        workspaces.path_of(name)
    except workspaces.WorkspaceError as e:
        raise HTTPException(404, str(e)) from e
    return workspaces.settings(name)


@router.put("/{name}/settings")
def put_settings(name: str, body: SettingsBody):
    try:
        return workspaces.update_settings(name, body.model_dump(exclude_none=True))
    except workspaces.WorkspaceError as e:
        raise HTTPException(400, str(e)) from e

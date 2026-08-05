"""Pydantic request/response models."""
from typing import Optional, List
from pydantic import BaseModel

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserCreate(BaseModel):
    username: str
    email: str
    password: str
    full_name: Optional[str] = None


class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None
    color: Optional[str] = "#3b82f6"


class MemberAdd(BaseModel):
    user_id: int
    role: str = "editor"


class TaskCreate(BaseModel):
    project_id: int
    title: str
    description: Optional[str] = None
    type: str = "Others"
    status: str = "Todo"
    priority: str = "Medium"
    start_date: Optional[str] = None
    due_date: Optional[str] = None
    progress: int = 0
    effort: Optional[int] = None
    figma_url: Optional[str] = None
    pr_url: Optional[str] = None
    labels: Optional[List[str]] = []
    assignee_id: Optional[int] = None


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    type: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    start_date: Optional[str] = None
    due_date: Optional[str] = None
    progress: Optional[int] = None
    effort: Optional[int] = None
    figma_url: Optional[str] = None
    pr_url: Optional[str] = None
    labels: Optional[List[str]] = None
    assignee_id: Optional[int] = None
    project_id: Optional[int] = None


class DependencyCreate(BaseModel):
    predecessor_id: int  # must finish (FS) before successor
    successor_id: int
    type: str = "FS"
    lag_days: int = 0


class PrefUpdate(BaseModel):
    theme: Optional[str] = None
    accent_color: Optional[str] = None
    default_view: Optional[str] = None
    density: Optional[str] = None
    sidebar_collapsed: Optional[bool] = None
    items_per_page: Optional[int] = None


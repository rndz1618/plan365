"""SQLAlchemy models matching the current SQLite schema for Alembic autogenerate."""
from sqlalchemy import (
    Column, Integer, String, Text, Boolean, DateTime, ForeignKey, 
    UniqueConstraint, CheckConstraint, Index, JSON, func
)
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(255), unique=True, nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=True)
    role = Column(String(50), nullable=False, default="user")
    is_active = Column(Integer, default=1)
    weekly_capacity = Column(Integer, default=40)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class Project(Base):
    __tablename__ = "projects"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    color = Column(String(20), default="#3b82f6")
    status = Column(String(50), default="Active")
    start_date = Column(String(20), nullable=True)
    due_date = Column(String(20), nullable=True)
    reference = Column(Text, nullable=True)
    supporting_data = Column(Text, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class ProjectMember(Base):
    __tablename__ = "project_members"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(50), nullable=False, default="editor")
    joined_at = Column(DateTime, server_default=func.now())
    
    __table_args__ = (
        UniqueConstraint("project_id", "user_id", name="uq_project_user"),
    )


class Task(Base):
    __tablename__ = "tasks"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    type = Column(String(50), nullable=False, default="Others")
    status = Column(String(50), nullable=False, default="Todo")
    priority = Column(String(20), nullable=False, default="Medium")
    start_date = Column(String(20), nullable=True)
    due_date = Column(String(20), nullable=True)
    progress = Column(Integer, default=0)
    effort = Column(Integer, nullable=True)
    figma_url = Column(String(500), nullable=True)
    pr_url = Column(String(500), nullable=True)
    labels = Column(JSON, default=list)
    is_milestone = Column(Integer, default=0)
    attachment_url = Column(String(500), nullable=True)
    baseline_start = Column(String(20), nullable=True)
    baseline_due = Column(String(20), nullable=True)
    assignee_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class Setting(Base):
    __tablename__ = "settings"
    
    key = Column(String(100), primary_key=True)
    value = Column(Text, nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    updated_by = Column(Integer, ForeignKey("users.id"), nullable=True)


class UserPreference(Base):
    __tablename__ = "user_preferences"
    
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    theme = Column(String(20), default="system")
    accent_color = Column(String(20), default="blue")
    default_view = Column(String(20), default="list")
    density = Column(String(20), default="comfortable")
    sidebar_collapsed = Column(Integer, default=0)
    items_per_page = Column(Integer, default=50)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class TaskDependency(Base):
    __tablename__ = "task_dependencies"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    predecessor_id = Column(Integer, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    successor_id = Column(Integer, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    type = Column(String(2), nullable=False, default="FS")
    lag_days = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, server_default=func.now())
    
    __table_args__ = (
        UniqueConstraint("predecessor_id", "successor_id", name="uq_pred_succ"),
        CheckConstraint("predecessor_id != successor_id", name="ck_no_self_dep"),
        CheckConstraint("type IN ('FS','SS','FF','SF')", name="ck_dep_type"),
    )


# Indexes (matching current schema)
Index("idx_tasks_project", Task.project_id)
Index("idx_tasks_type", Task.type)
Index("idx_tasks_status", Task.status)
Index("idx_project_members_user", ProjectMember.user_id)
Index("idx_dep_pred", TaskDependency.predecessor_id)
Index("idx_dep_succ", TaskDependency.successor_id)
Index("idx_tasks_assignee", Task.assignee_id)
Index("idx_tasks_milestone", Task.is_milestone)
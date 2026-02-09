"""Role model for RBAC."""

import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.postgres import Base


class Role(Base):
    """User roles with permissions."""
    __tablename__ = "roles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(50), unique=True)
    display_name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Permissions as JSON object
    # e.g., {"manage_users": true, "manage_tests": true, "run_tests": true}
    permissions: Mapped[dict] = mapped_column(JSONB, default=dict)

    # System roles cannot be deleted
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    users = relationship("User", back_populates="role")


# Default permissions for each role
DEFAULT_ROLES = {
    "admin": {
        "display_name": "Administrator",
        "description": "Full system access",
        "permissions": {
            "manage_users": True,
            "manage_org": True,
            "manage_roles": True,
            "manage_tests": True,
            "run_tests": True,
            "view_tests": True,
            "manage_schedules": True,
            "view_schedules": True,
            "manage_settings": True,
            "view_dashboard": True,
            "view_admin_dashboard": True,
        },
        "is_system": True,
    },
    "member": {
        "display_name": "Member",
        "description": "Standard team member access",
        "permissions": {
            "manage_users": False,
            "manage_org": False,
            "manage_roles": False,
            "manage_tests": True,
            "run_tests": True,
            "view_tests": True,
            "manage_schedules": True,
            "view_schedules": True,
            "manage_settings": False,
            "view_dashboard": True,
            "view_admin_dashboard": False,
        },
        "is_system": True,
    },
    "viewer": {
        "display_name": "Viewer",
        "description": "Read-only access",
        "permissions": {
            "manage_users": False,
            "manage_org": False,
            "manage_roles": False,
            "manage_tests": False,
            "run_tests": False,
            "view_tests": True,
            "manage_schedules": False,
            "view_schedules": True,
            "manage_settings": False,
            "view_dashboard": True,
            "view_admin_dashboard": False,
        },
        "is_system": True,
    },
}

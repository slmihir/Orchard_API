"""Admin API endpoints for user, role, and invitation management."""

import secrets
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete
from sqlalchemy.orm import selectinload
from uuid import UUID
from datetime import datetime, timedelta
from pydantic import BaseModel, EmailStr

from app.db.postgres import get_db
from app.models.user import User
from app.models.role import Role, DEFAULT_ROLES
from app.models.test import Test, Collection
from app.models.schedule import Schedule
from app.models.run import Run
from app.models.invitation import Invitation
from app.security import get_current_user, require_permission, get_password_hash

router = APIRouter()


# ============== Schemas ==============

class RoleResponse(BaseModel):
    id: UUID
    name: str
    display_name: str
    description: str | None
    permissions: dict
    is_system: bool
    created_at: datetime

    class Config:
        from_attributes = True


class RoleCreate(BaseModel):
    name: str
    display_name: str
    description: str | None = None
    permissions: dict


class RoleUpdate(BaseModel):
    display_name: str | None = None
    description: str | None = None
    permissions: dict | None = None


class UserAdminResponse(BaseModel):
    id: UUID
    email: str
    name: str
    is_active: bool
    created_at: datetime
    org_id: UUID | None
    role_id: UUID | None
    role_name: str | None

    class Config:
        from_attributes = True


class UserRoleUpdate(BaseModel):
    role_id: UUID


class UserStatusUpdate(BaseModel):
    is_active: bool


class InvitationCreate(BaseModel):
    email: EmailStr
    role_id: UUID
    message: str | None = None


class InvitationResponse(BaseModel):
    id: UUID
    email: str
    role_id: UUID
    role_name: str | None
    status: str
    message: str | None
    invited_by_name: str
    expires_at: datetime
    created_at: datetime
    magic_link: str | None = None

    class Config:
        from_attributes = True


class AdminStats(BaseModel):
    total_users: int
    active_users: int
    total_tests: int
    total_runs: int
    total_schedules: int
    pending_invitations: int
    users_by_role: dict


# ============== Role Endpoints ==============

@router.get("/roles", response_model=list[RoleResponse])
async def list_roles(
    current_user: User = Depends(require_permission("manage_roles")),
    db: AsyncSession = Depends(get_db)
):
    """List all roles."""
    result = await db.execute(select(Role).order_by(Role.name))
    return result.scalars().all()


@router.get("/roles/{role_id}", response_model=RoleResponse)
async def get_role(
    role_id: UUID,
    current_user: User = Depends(require_permission("manage_roles")),
    db: AsyncSession = Depends(get_db)
):
    """Get a specific role."""
    result = await db.execute(select(Role).where(Role.id == role_id))
    role = result.scalar_one_or_none()

    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    return role


@router.post("/roles", response_model=RoleResponse)
async def create_role(
    data: RoleCreate,
    current_user: User = Depends(require_permission("manage_roles")),
    db: AsyncSession = Depends(get_db)
):
    """Create a new custom role."""
    existing = await db.execute(select(Role).where(Role.name == data.name))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Role name already exists")

    role = Role(
        name=data.name,
        display_name=data.display_name,
        description=data.description,
        permissions=data.permissions,
        is_system=False,
    )
    db.add(role)
    await db.commit()
    await db.refresh(role)
    return role


@router.patch("/roles/{role_id}", response_model=RoleResponse)
async def update_role(
    role_id: UUID,
    data: RoleUpdate,
    current_user: User = Depends(require_permission("manage_roles")),
    db: AsyncSession = Depends(get_db)
):
    """Update a role. System roles can only have permissions updated."""
    result = await db.execute(select(Role).where(Role.id == role_id))
    role = result.scalar_one_or_none()

    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    if role.is_system:
        # Only allow permission updates for system roles
        if data.display_name is not None or data.description is not None:
            raise HTTPException(
                status_code=400,
                detail="Cannot modify name or description of system roles"
            )

    if data.display_name is not None:
        role.display_name = data.display_name
    if data.description is not None:
        role.description = data.description
    if data.permissions is not None:
        role.permissions = data.permissions

    role.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(role)
    return role


@router.delete("/roles/{role_id}")
async def delete_role(
    role_id: UUID,
    current_user: User = Depends(require_permission("manage_roles")),
    db: AsyncSession = Depends(get_db)
):
    """Delete a custom role. System roles cannot be deleted."""
    result = await db.execute(select(Role).where(Role.id == role_id))
    role = result.scalar_one_or_none()

    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    if role.is_system:
        raise HTTPException(status_code=400, detail="Cannot delete system roles")

    users_with_role = await db.execute(
        select(func.count(User.id)).where(User.role_id == role_id)
    )
    if users_with_role.scalar() > 0:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete role that is assigned to users"
        )

    await db.delete(role)
    await db.commit()
    return {"status": "deleted", "role_id": str(role_id)}


# ============== User Management Endpoints ==============

@router.get("/users", response_model=list[UserAdminResponse])
async def list_users(
    current_user: User = Depends(require_permission("manage_users")),
    db: AsyncSession = Depends(get_db)
):
    """List all users (admin only)."""
    result = await db.execute(
        select(User)
        .options(selectinload(User.role))
        .order_by(User.created_at.desc())
    )
    users = result.scalars().all()

    return [
        UserAdminResponse(
            id=user.id,
            email=user.email,
            name=user.name,
            is_active=user.is_active,
            created_at=user.created_at,
            org_id=user.org_id,
            role_id=user.role_id,
            role_name=user.role.display_name if user.role else None,
        )
        for user in users
    ]


@router.get("/users/{user_id}", response_model=UserAdminResponse)
async def get_user(
    user_id: UUID,
    current_user: User = Depends(require_permission("manage_users")),
    db: AsyncSession = Depends(get_db)
):
    """Get a specific user (admin only)."""
    result = await db.execute(
        select(User)
        .options(selectinload(User.role))
        .where(User.id == user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return UserAdminResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        is_active=user.is_active,
        created_at=user.created_at,
        org_id=user.org_id,
        role_id=user.role_id,
        role_name=user.role.display_name if user.role else None,
    )


@router.patch("/users/{user_id}/role", response_model=UserAdminResponse)
async def update_user_role(
    user_id: UUID,
    data: UserRoleUpdate,
    current_user: User = Depends(require_permission("manage_users")),
    db: AsyncSession = Depends(get_db)
):
    """Update a user's role (admin only)."""
    role_result = await db.execute(select(Role).where(Role.id == data.role_id))
    role = role_result.scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    result = await db.execute(
        select(User)
        .options(selectinload(User.role))
        .where(User.id == user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Prevent demoting yourself from admin
    if user.id == current_user.id and role.name != "admin":
        raise HTTPException(status_code=400, detail="Cannot demote yourself from admin")

    user.role_id = data.role_id
    await db.commit()

    # Reload with role
    result = await db.execute(
        select(User)
        .options(selectinload(User.role))
        .where(User.id == user_id)
    )
    user = result.scalar_one()

    return UserAdminResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        is_active=user.is_active,
        created_at=user.created_at,
        org_id=user.org_id,
        role_id=user.role_id,
        role_name=user.role.display_name if user.role else None,
    )


@router.patch("/users/{user_id}/status", response_model=UserAdminResponse)
async def update_user_status(
    user_id: UUID,
    data: UserStatusUpdate,
    current_user: User = Depends(require_permission("manage_users")),
    db: AsyncSession = Depends(get_db)
):
    """Activate or deactivate a user (admin only)."""
    result = await db.execute(
        select(User)
        .options(selectinload(User.role))
        .where(User.id == user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Prevent deactivating yourself
    if user.id == current_user.id and not data.is_active:
        raise HTTPException(status_code=400, detail="Cannot deactivate yourself")

    user.is_active = data.is_active
    await db.commit()
    await db.refresh(user)

    return UserAdminResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        is_active=user.is_active,
        created_at=user.created_at,
        org_id=user.org_id,
        role_id=user.role_id,
        role_name=user.role.display_name if user.role else None,
    )


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: UUID,
    current_user: User = Depends(require_permission("manage_users")),
    db: AsyncSession = Depends(get_db)
):
    """Delete a user (admin only)."""
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    await db.delete(user)
    await db.commit()
    return {"status": "deleted", "user_id": str(user_id)}


# ============== Invitation Endpoints ==============

def generate_magic_token() -> str:
    """Generate a secure random token for magic links."""
    return secrets.token_urlsafe(32)


async def send_invitation_email(email: str, token: str, invited_by: str, message: str | None):
    """Send invitation email with magic link. Placeholder for actual email service."""
    # TODO: Integrate with actual email service (SendGrid, AWS SES, etc.)
    # For now, just log the invitation
    magic_link = f"http://localhost:3000/invite/{token}"
    print(f"[INVITATION] To: {email}")
    print(f"[INVITATION] From: {invited_by}")
    print(f"[INVITATION] Link: {magic_link}")
    if message:
        print(f"[INVITATION] Message: {message}")


@router.get("/invitations", response_model=list[InvitationResponse])
async def list_invitations(
    current_user: User = Depends(require_permission("manage_users")),
    db: AsyncSession = Depends(get_db)
):
    """List all invitations."""
    result = await db.execute(
        select(Invitation)
        .options(selectinload(Invitation.role), selectinload(Invitation.invited_by))
        .order_by(Invitation.created_at.desc())
    )
    invitations = result.scalars().all()

    return [
        InvitationResponse(
            id=inv.id,
            email=inv.email,
            role_id=inv.role_id,
            role_name=inv.role.display_name if inv.role else None,
            status=inv.status,
            message=inv.message,
            invited_by_name=inv.invited_by.name if inv.invited_by else "Unknown",
            expires_at=inv.expires_at,
            created_at=inv.created_at,
        )
        for inv in invitations
    ]


@router.post("/invitations", response_model=InvitationResponse)
async def create_invitation(
    data: InvitationCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_permission("manage_users")),
    db: AsyncSession = Depends(get_db)
):
    """Create and send an invitation to a new user."""
    existing_user = await db.execute(select(User).where(User.email == data.email))
    if existing_user.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="User with this email already exists")

    existing_invite = await db.execute(
        select(Invitation).where(
            Invitation.email == data.email,
            Invitation.status == "pending"
        )
    )
    if existing_invite.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Pending invitation already exists for this email")

    role_result = await db.execute(select(Role).where(Role.id == data.role_id))
    role = role_result.scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    token = generate_magic_token()
    invitation = Invitation(
        email=data.email,
        token=token,
        role_id=data.role_id,
        invited_by_id=current_user.id,
        message=data.message,
        org_id=current_user.org_id,
    )
    db.add(invitation)
    await db.commit()
    await db.refresh(invitation)

    background_tasks.add_task(
        send_invitation_email,
        data.email,
        token,
        current_user.name,
        data.message
    )

    # Generate magic link for display
    magic_link = f"http://localhost:3000/invite/{token}"

    return InvitationResponse(
        id=invitation.id,
        email=invitation.email,
        role_id=invitation.role_id,
        role_name=role.display_name,
        status=invitation.status,
        message=invitation.message,
        invited_by_name=current_user.name,
        expires_at=invitation.expires_at,
        created_at=invitation.created_at,
        magic_link=magic_link,
    )


@router.post("/invitations/{invitation_id}/resend")
async def resend_invitation(
    invitation_id: UUID,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_permission("manage_users")),
    db: AsyncSession = Depends(get_db)
):
    """Resend an invitation email and extend expiry."""
    result = await db.execute(
        select(Invitation)
        .options(selectinload(Invitation.invited_by))
        .where(Invitation.id == invitation_id)
    )
    invitation = result.scalar_one_or_none()

    if not invitation:
        raise HTTPException(status_code=404, detail="Invitation not found")

    if invitation.status != "pending":
        raise HTTPException(status_code=400, detail="Can only resend pending invitations")

    # Generate new token and extend expiry
    invitation.token = generate_magic_token()
    invitation.expires_at = datetime.utcnow() + timedelta(days=7)
    await db.commit()

    background_tasks.add_task(
        send_invitation_email,
        invitation.email,
        invitation.token,
        current_user.name,
        invitation.message
    )

    return {"status": "resent", "expires_at": invitation.expires_at.isoformat()}


@router.delete("/invitations/{invitation_id}")
async def revoke_invitation(
    invitation_id: UUID,
    current_user: User = Depends(require_permission("manage_users")),
    db: AsyncSession = Depends(get_db)
):
    """Revoke/delete an invitation."""
    result = await db.execute(select(Invitation).where(Invitation.id == invitation_id))
    invitation = result.scalar_one_or_none()

    if not invitation:
        raise HTTPException(status_code=404, detail="Invitation not found")

    await db.delete(invitation)
    await db.commit()
    return {"status": "revoked", "invitation_id": str(invitation_id)}


# ============== Stats Endpoint ==============

@router.get("/stats", response_model=AdminStats)
async def get_admin_stats(
    current_user: User = Depends(require_permission("view_admin_dashboard")),
    db: AsyncSession = Depends(get_db)
):
    """Get admin dashboard statistics."""
    # Total users
    total_users_result = await db.execute(select(func.count(User.id)))
    total_users = total_users_result.scalar() or 0

    # Active users
    active_users_result = await db.execute(
        select(func.count(User.id)).where(User.is_active == True)
    )
    active_users = active_users_result.scalar() or 0

    # Total tests
    total_tests_result = await db.execute(select(func.count(Test.id)))
    total_tests = total_tests_result.scalar() or 0

    # Total runs
    total_runs_result = await db.execute(select(func.count(Run.id)))
    total_runs = total_runs_result.scalar() or 0

    # Total schedules
    total_schedules_result = await db.execute(select(func.count(Schedule.id)))
    total_schedules = total_schedules_result.scalar() or 0

    # Pending invitations
    pending_invites_result = await db.execute(
        select(func.count(Invitation.id)).where(Invitation.status == "pending")
    )
    pending_invitations = pending_invites_result.scalar() or 0

    # Users by role
    users_by_role_result = await db.execute(
        select(Role.display_name, func.count(User.id))
        .outerjoin(User, User.role_id == Role.id)
        .group_by(Role.id, Role.display_name)
    )
    users_by_role = {row[0]: row[1] for row in users_by_role_result.all()}

    return AdminStats(
        total_users=total_users,
        active_users=active_users,
        total_tests=total_tests,
        total_runs=total_runs,
        total_schedules=total_schedules,
        pending_invitations=pending_invitations,
        users_by_role=users_by_role,
    )

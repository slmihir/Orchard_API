from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.postgres import get_db
from app.models.user import User
from app.models.role import Role
from app.schemas.user import UserCreate, UserResponse, Token, TokenWithUser, RoleInfo
from app.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    get_current_user,
)

router = APIRouter()


def build_user_response(user: User) -> UserResponse:
    """Build UserResponse with role info."""
    role_info = None
    if user.role:
        role_info = RoleInfo(
            id=user.role.id,
            name=user.role.name,
            display_name=user.role.display_name,
            permissions=user.role.permissions,
        )
    return UserResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        is_active=user.is_active,
        created_at=user.created_at,
        org_id=user.org_id,
        role_id=user.role_id,
        role=role_info,
    )


@router.post("/register", response_model=TokenWithUser)
async def register(data: UserCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == data.email))
    existing_user = result.scalar_one_or_none()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    role_result = await db.execute(select(Role).where(Role.name == "member"))
    default_role = role_result.scalar_one_or_none()

    user = User(
        email=data.email,
        hashed_password=get_password_hash(data.password),
        name=data.name,
        role_id=default_role.id if default_role else None,
    )
    db.add(user)
    await db.commit()

    # Reload with role relationship
    result = await db.execute(
        select(User)
        .options(selectinload(User.role))
        .where(User.id == user.id)
    )
    user = result.scalar_one()

    access_token = create_access_token(data={"sub": str(user.id)})

    return TokenWithUser(
        access_token=access_token,
        token_type="bearer",
        user=build_user_response(user)
    )


@router.post("/login", response_model=TokenWithUser)
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(User)
        .options(selectinload(User.role))
        .where(User.email == form_data.username)
    )
    user = result.scalar_one_or_none()

    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )

    access_token = create_access_token(data={"sub": str(user.id)})

    return TokenWithUser(
        access_token=access_token,
        token_type="bearer",
        user=build_user_response(user)
    )


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: Annotated[User, Depends(get_current_user)]):
    return build_user_response(current_user)

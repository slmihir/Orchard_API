"""Multi-tenancy utilities for filtering queries by user/org."""

from sqlalchemy import and_, or_
from sqlalchemy.orm import Query
from app.models.user import User


def tenant_filter(model, user: User):
    """
    Return a SQLAlchemy filter clause for multi-tenancy.

    If user belongs to an organization, filter by org_id.
    Otherwise, filter by user_id (personal workspace).

    Usage:
        query = select(Test).where(tenant_filter(Test, current_user))
    """
    if user.org_id:
        return model.org_id == user.org_id
    return model.user_id == user.id


def set_tenant(obj, user: User):
    """
    Set tenant fields on a model instance before creation.

    Usage:
        test = Test(name="My Test", ...)
        set_tenant(test, current_user)
    """
    obj.user_id = user.id
    obj.org_id = user.org_id

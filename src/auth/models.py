"""Authentication/identity models"""
from enum import Enum

from pydantic import BaseModel


class RoleEnum(str, Enum):
    """User role — determines audit-log visibility once real auth exists"""
    ANALYST = "analyst"
    MANAGER = "manager"
    ADMIN = "admin"
    SYSTEM = "system"


class CurrentUser(BaseModel):
    """The identity attached to a request.

    Currently sourced from .env (local development simulation).
    Will be sourced from JWT once real login exists — only
    get_current_user() in dependencies.py needs to change then.
    """
    user_id: str
    user_name: str
    role: RoleEnum

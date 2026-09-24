"""FastAPI dependencies for resolving the current user"""
from src.auth.models import CurrentUser, RoleEnum
from src.config import settings


def get_current_user() -> CurrentUser:
    """
    Resolve the current user for this request.

    For now this reads the developer's local .env identity
    (APP_USER_ID/APP_USER_NAME/APP_USER_ROLE). Once real
    authentication is added, this function is the only place
    that needs to change — everywhere else that depends on
    CurrentUser stays the same.
    """
    return CurrentUser(
        user_id=settings.APP_USER_ID,
        user_name=settings.APP_USER_NAME,
        role=RoleEnum(settings.APP_USER_ROLE),
    )

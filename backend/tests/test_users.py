import uuid
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from app.api.dependencies import require_admin
from app.core.errors import AppError
from app.models import User, UserRole
from app.schemas.user import UserCreateRequest, UserPublic
from app.services.users import list_business_users


def test_user_create_accepts_only_agent_or_customer() -> None:
    for role in ("agent", "customer"):
        payload = UserCreateRequest(
            name="Example User",
            email=f"{role}@example.com",
            password="password123",
            role=role,
        )
        assert payload.role == role

    with pytest.raises(ValidationError):
        UserCreateRequest.model_validate(
            {
                "name": "Injected Admin",
                "email": "admin@example.com",
                "password": "password123",
                "role": "admin",
            }
        )


def test_user_create_forbids_client_business_id() -> None:
    with pytest.raises(ValidationError):
        UserCreateRequest.model_validate(
            {
                "name": "Agent",
                "email": "agent@example.com",
                "password": "password123",
                "role": "agent",
                "business_id": str(uuid.uuid4()),
            }
        )


def test_admin_dependency_rejects_non_admin() -> None:
    admin = User(role=UserRole.ADMIN)
    assert require_admin(admin) is admin

    with pytest.raises(AppError) as error:
        require_admin(User(role=UserRole.AGENT))
    assert error.value.status_code == 403
    assert error.value.code == "FORBIDDEN"


def test_user_list_query_is_explicitly_tenant_scoped() -> None:
    business_id = uuid.uuid4()
    db = MagicMock()
    db.scalars.return_value.all.return_value = []

    assert list_business_users(db, business_id) == []
    statement = db.scalars.call_args.args[0]
    assert "users.business_id" in str(statement)
    assert statement.compile().params == {"business_id_1": business_id}


def test_public_user_schema_omits_password_hash() -> None:
    fields = UserPublic.model_fields
    assert "password" not in fields
    assert "password_hash" not in fields

# packages/api/tests/db/test_user_invite_model.py
import pytest
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from src.db.models.user_invite import UserInvite


@pytest.mark.asyncio
async def test_create_invite(db_session, test_tenant, test_user, test_role):
    """Invite can be created with expiration."""
    invite = UserInvite(
        tenant_id=test_tenant.id,
        email="newuser@example.com",
        role_id=test_role.id,
        invited_by=test_user.id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    db_session.add(invite)
    await db_session.commit()
    await db_session.refresh(invite)

    assert invite.id is not None
    assert invite.token is not None  # Auto-generated
    assert len(invite.token) == 64  # Secure token
    assert invite.accepted_at is None


@pytest.mark.asyncio
async def test_invite_is_valid(db_session, test_tenant, test_user, test_role):
    """Invite validity check works."""
    valid_invite = UserInvite(
        tenant_id=test_tenant.id,
        email="valid@example.com",
        role_id=test_role.id,
        invited_by=test_user.id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    expired_invite = UserInvite(
        tenant_id=test_tenant.id,
        email="expired@example.com",
        role_id=test_role.id,
        invited_by=test_user.id,
        expires_at=datetime.now(timezone.utc) - timedelta(days=1),
    )
    db_session.add_all([valid_invite, expired_invite])
    await db_session.commit()

    assert valid_invite.is_valid is True
    assert expired_invite.is_valid is False

    # Accept the valid invite
    valid_invite.accepted_at = datetime.now(timezone.utc)
    await db_session.commit()
    assert valid_invite.is_valid is False  # Already accepted

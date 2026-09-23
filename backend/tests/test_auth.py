"""
Unit and integration tests for authentication, authorization (RBAC),
password hashing (pwdlib Argon2 + legacy Bcrypt), JWT tokens, and Google ID token verification.
"""

import uuid
from datetime import timedelta
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from unittest.mock import patch

from app.main import app
from app.core.config import settings
from app.core.database import Base, get_db
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    verify_token,
)
from app.models.user import User, UserRole
from app.models.project import Project
from app.models.deployment import Deployment, DeploymentStatus, DatabaseType
from app.models.pending_action import PendingAction, ActionStatus


# ── Test Database Fixtures (In-Memory SQLite) ──────────────────────

@pytest_asyncio.fixture
async def test_db_session():
    """Create a fresh in-memory SQLite database for each test function."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)

    async with session_factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def client(test_db_session):
    """FastAPI AsyncClient wired to the test database session."""
    async def override_get_db():
        yield test_db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


# ── Password Hashing Tests ─────────────────────────────────────────

def test_argon2_password_hashing():
    plain = "SuperSecret123!"
    hashed = hash_password(plain)
    assert hashed != plain
    assert "$argon2" in hashed
    assert verify_password(plain, hashed) is True
    assert verify_password("WrongPassword!", hashed) is False


def test_legacy_bcrypt_compatibility():
    """Verify that legacy bcrypt hashes are still verified correctly."""
    import bcrypt
    raw_bcrypt = bcrypt.hashpw(b"legacy_pass", bcrypt.gensalt()).decode("utf-8")
    assert verify_password("legacy_pass", raw_bcrypt) is True
    assert verify_password("wrong_pass", raw_bcrypt) is False


def test_invalid_hash_handling():
    assert verify_password("anything", "not-a-valid-hash") is False


# ── JWT Helpers Tests ─────────────────────────────────────────────

def test_jwt_create_and_verify():
    payload = {"sub": str(uuid.uuid4()), "email": "test@univ.edu", "role": "student"}
    token = create_access_token(payload)
    decoded = verify_token(token)
    assert decoded["sub"] == payload["sub"]
    assert decoded["email"] == "test@univ.edu"
    assert decoded["role"] == "student"


def test_jwt_expired_token():
    payload = {"sub": str(uuid.uuid4()), "role": "student"}
    token = create_access_token(payload, expires_delta=timedelta(seconds=-10))
    with pytest.raises(Exception):
        verify_token(token)


# ── Registration & Login Tests ────────────────────────────────────

@pytest.mark.asyncio
async def test_register_student_success(client: AsyncClient, test_db_session):
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "student1@univ.edu",
            "password": "Password123!",
            "full_name": "Student One",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "access_token" in data
    assert data["user"]["email"] == "student1@univ.edu"
    assert data["user"]["role"] == "student"
    assert data["user"]["full_name"] == "Student One"

    # Verify password was hashed in database
    user = await test_db_session.get(User, uuid.UUID(data["user"]["id"]))
    assert user.hashed_password != "Password123!"
    assert verify_password("Password123!", user.hashed_password) is True


@pytest.mark.asyncio
async def test_register_duplicate_email_fails(client: AsyncClient):
    await client.post(
        "/api/v1/auth/register",
        json={"email": "dupe@univ.edu", "password": "Password123!"},
    )
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": "dupe@univ.edu", "password": "AnotherPassword123!"},
    )
    assert resp.status_code == 409
    assert "already exists" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_public_registration_blocks_admin_and_guide(client: AsyncClient):
    # Attempt to self-register as ADMIN
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": "bad_admin@univ.edu", "password": "Password123!", "role": "admin"},
    )
    assert resp.status_code == 400
    assert "only allows creating student accounts" in resp.json()["detail"].lower()

    # Attempt to self-register as GUIDE
    resp2 = await client.post(
        "/api/v1/auth/register",
        json={"email": "bad_guide@univ.edu", "password": "Password123!", "role": "guide"},
    )
    assert resp2.status_code == 400


@pytest.mark.asyncio
async def test_login_flow(client: AsyncClient):
    await client.post(
        "/api/v1/auth/register",
        json={"email": "login_test@univ.edu", "password": "SecretPassword123"},
    )

    # Success
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "login_test@univ.edu", "password": "SecretPassword123"},
    )
    assert resp.status_code == 200
    assert "access_token" in resp.json()

    # Wrong password
    resp_bad = await client.post(
        "/api/v1/auth/login",
        json={"email": "login_test@univ.edu", "password": "WrongPassword"},
    )
    assert resp_bad.status_code == 401
    assert "invalid email or password" in resp_bad.json()["detail"].lower()

    # Non-existent user
    resp_none = await client.post(
        "/api/v1/auth/login",
        json={"email": "nonexistent@univ.edu", "password": "SomePassword"},
    )
    assert resp_none.status_code == 401


# ── Current User /auth/me Tests ────────────────────────────────────

@pytest.mark.asyncio
async def test_get_me_endpoint(client: AsyncClient):
    reg = await client.post(
        "/api/v1/auth/register",
        json={"email": "me_test@univ.edu", "password": "Password123!", "full_name": "Me Tester"},
    )
    token = reg.json()["access_token"]

    resp = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == "me_test@univ.edu"
    assert data["full_name"] == "Me Tester"

    # Unauthenticated
    resp_unauth = await client.get("/api/v1/auth/me")
    assert resp_unauth.status_code in (401, 403)


# ── Admin User & Role Management Tests ─────────────────────────────

@pytest.mark.asyncio
async def test_admin_role_management(client: AsyncClient, test_db_session):
    # 1. Create student
    student_reg = await client.post(
        "/api/v1/auth/register",
        json={"email": "promoteme@univ.edu", "password": "Password123!"},
    )
    student_id = student_reg.json()["user"]["id"]
    student_token = student_reg.json()["access_token"]

    # 2. Create admin directly in DB
    admin = User(
        email="admin@univ.edu",
        role=UserRole.ADMIN,
        hashed_password=hash_password("AdminPass123!"),
    )
    test_db_session.add(admin)
    await test_db_session.flush()
    admin_token = create_access_token({"sub": str(admin.id), "email": admin.email, "role": "admin"})

    # Student cannot list users
    res_forbidden = await client.get(
        "/api/v1/auth/users",
        headers={"Authorization": f"Bearer {student_token}"},
    )
    assert res_forbidden.status_code == 403

    # Admin can list users
    res_admin = await client.get(
        "/api/v1/auth/users",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res_admin.status_code == 200
    assert len(res_admin.json()) >= 2

    # Student cannot promote users
    res_promo_bad = await client.patch(
        f"/api/v1/auth/users/{student_id}/role",
        json={"role": "guide"},
        headers={"Authorization": f"Bearer {student_token}"},
    )
    assert res_promo_bad.status_code == 403

    # Admin promotes student to GUIDE
    res_promo_ok = await client.patch(
        f"/api/v1/auth/users/{student_id}/role",
        json={"role": "guide"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res_promo_ok.status_code == 200
    assert res_promo_ok.json()["role"] == "guide"


# ── Approval Decisions & RBAC Tests ────────────────────────────────

@pytest.mark.asyncio
async def test_approvals_rbac_and_server_side_reviewer(client: AsyncClient, test_db_session):
    # Setup users
    student = User(email="s@univ.edu", role=UserRole.STUDENT, hashed_password="h")
    guide = User(email="g@univ.edu", role=UserRole.GUIDE, hashed_password="h")
    test_db_session.add_all([student, guide])
    await test_db_session.flush()

    student_token = create_access_token({"sub": str(student.id), "email": student.email, "role": "student"})
    guide_token = create_access_token({"sub": str(guide.id), "email": guide.email, "role": "guide"})

    # Create a pending action
    action = PendingAction(
        tool_name="terraform_apply",
        tool_params={"plan": "sample"},
        user_id=student.id,
        status=ActionStatus.PENDING,
    )
    test_db_session.add(action)
    await test_db_session.flush()

    # Student cannot approve
    resp_student = await client.post(
        f"/api/v1/approvals/{action.id}/approve",
        json={"reason": "Self-approval attempt"},
        headers={"Authorization": f"Bearer {student_token}"},
    )
    assert resp_student.status_code == 403

    # Mock tool execution in registry.dispatch
    from unittest.mock import MagicMock
    mock_tool_result = MagicMock()
    mock_tool_result.to_dict.return_value = {"output": "success"}

    with patch("app.services.approval_service.registry.dispatch", return_value=mock_tool_result):
        resp_guide = await client.post(
            f"/api/v1/approvals/{action.id}/approve",
            json={"reason": "Looks good to me"},
            headers={"Authorization": f"Bearer {guide_token}"},
        )
        assert resp_guide.status_code == 200
        data = resp_guide.json()
        assert data["status"] == "approved"
        # Verify reviewer_id is derived from GUIDE's JWT token, not client payload
        assert data["reviewed_by"] == str(guide.id)


# ── Google OAuth Tests ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_google_auth_disabled_when_unconfigured(client: AsyncClient):
    with patch.object(settings, "GOOGLE_CLIENT_ID", ""):
        resp = await client.post(
            "/api/v1/auth/google",
            json={"id_token": "fake-google-token"},
        )
        assert resp.status_code == 503
        assert "not configured" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_google_auth_server_side_verification(client: AsyncClient, test_db_session):
    mock_id_info = {
        "sub": "google-user-sub-12345",
        "email": "google_student@univ.edu",
        "name": "Google Student",
        "email_verified": True,
    }

    with patch.object(settings, "GOOGLE_CLIENT_ID", "mock-client-id.apps.googleusercontent.com"):
        with patch("google.oauth2.id_token.verify_oauth2_token", return_value=mock_id_info):
            resp = await client.post(
                "/api/v1/auth/google",
                json={"id_token": "valid-google-id-token"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["user"]["email"] == "google_student@univ.edu"
            assert data["user"]["role"] == "student"
            assert data["user"]["full_name"] == "Google Student"

            # Check database: user has google_sub
            user = await test_db_session.get(User, uuid.UUID(data["user"]["id"]))
            assert user.google_sub == "google-user-sub-12345"
            assert user.hashed_password is None


# ── Project Authorization Tests ────────────────────────────────────

@pytest.mark.asyncio
async def test_project_ownership_authorization(client: AsyncClient, test_db_session):
    student1 = User(email="s1@univ.edu", role=UserRole.STUDENT, hashed_password="h")
    student2 = User(email="s2@univ.edu", role=UserRole.STUDENT, hashed_password="h")
    test_db_session.add_all([student1, student2])
    await test_db_session.flush()

    s1_token = create_access_token({"sub": str(student1.id), "email": student1.email, "role": "student"})
    s2_token = create_access_token({"sub": str(student2.id), "email": student2.email, "role": "student"})

    # Student 1 creates project
    proj = Project(
        service_name="student1-app",
        owner_id=student1.id,
        language="python",
        framework="fastapi",
    )
    test_db_session.add(proj)
    await test_db_session.flush()

    dep = Deployment(
        project_id=proj.id,
        replicas=2,
        db_type=DatabaseType.POSTGRES,
        cost_estimate=15.0,
        status=DeploymentStatus.PENDING,
        namespace="idp-student1-app",
    )
    test_db_session.add(dep)
    await test_db_session.flush()

    # Student 1 can view own project
    resp_s1 = await client.get(
        f"/api/v1/projects/{proj.id}/status",
        headers={"Authorization": f"Bearer {s1_token}"},
    )
    assert resp_s1.status_code == 200

    # Student 2 cannot view Student 1's project
    resp_s2 = await client.get(
        f"/api/v1/projects/{proj.id}/status",
        headers={"Authorization": f"Bearer {s2_token}"},
    )
    assert resp_s2.status_code == 403
    assert "students may only view their own projects" in resp_s2.json()["detail"].lower()

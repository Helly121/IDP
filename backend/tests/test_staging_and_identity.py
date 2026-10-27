"""
Unit tests for Phase 4: Staging Workspace, Validation Fix, and Server-Side Identity Injection.

Verifies:
1. write -> validate sees staged content (not in real tree).
2. reject -> staging cleaned up.
3. approve -> executes real file and cleans staging.
4. model-supplied user_id is ignored in favor of server-side ctx.
5. policy_approve_escalation approver_id is set server-side by reviewer.
6. path traversal is rejected in staging.
7. staging tree clones iac while skipping .terraform and *.tfstate.
"""

import shutil
import time
import uuid
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import async_session_factory, init_db
from app.models.user import User, UserRole
from app.models.pending_action import PendingAction, ActionStatus
from app.mcp_servers.registry import registry
from app.mcp_servers.policy_server import PolicyMCPServer
from app.mcp_servers.terraform_server import TerraformMCPServer
from app.mcp_servers.workflow_server import WorkflowMCPServer
from app.services import staging_service, approval_service


@pytest_asyncio.fixture(autouse=True)
async def setup_test_db():
    await init_db()
    registry.initialize()


@pytest.fixture
def tmp_staging_root(tmp_path, monkeypatch):
    staging_dir = tmp_path / "test_staging"
    staging_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(settings, "STAGING_ROOT", str(staging_dir))
    yield staging_dir
    shutil.rmtree(staging_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_write_then_validate_sees_staged_content(tmp_path, tmp_staging_root):
    """
    Staged content should be visible to read/validate tools when session_id is provided,
    while leaving the real directory untouched.
    """
    real_iac = tmp_path / "real_iac"
    real_iac.mkdir()
    (real_iac / "existing.tf").write_text("# existing code", encoding="utf-8")

    server = TerraformMCPServer(iac_root=real_iac)
    session_id = uuid.uuid4()
    staged_content = 'resource "aws_s3_bucket" "staged" {}\n'

    # Stage the file in the session
    staging_service.stage_terraform_file(
        session_id=session_id,
        file_path="environments/dev/main.tf",
        content=staged_content,
        real_iac_root=real_iac,
    )

    # Real tree should NOT contain the staged file
    assert not (real_iac / "environments" / "dev" / "main.tf").exists()

    # Reading without ctx or with a different session should not see staged file
    unshared_res = await server.execute_tool(
        "terraform_get_file",
        {"file_path": "environments/dev/main.tf"},
        ctx={"session_id": str(uuid.uuid4())},
    )
    assert unshared_res.success is False

    # Reading with matching session_id should return the staged content
    staged_res = await server.execute_tool(
        "terraform_get_file",
        {"file_path": "environments/dev/main.tf"},
        ctx={"session_id": str(session_id)},
    )
    assert staged_res.success is True
    assert staged_res.data["content"] == staged_content

    # list_files with matching session_id sees the staged file
    list_res = await server.execute_tool(
        "terraform_list_files",
        {"subpath": "environments/dev"},
        ctx={"session_id": str(session_id)},
    )
    assert list_res.success is True
    paths = [f["path"] for f in list_res.data["files"]]
    assert any("main.tf" in p for p in paths)


@pytest.mark.asyncio
async def test_workflow_validate_sees_staged_content(tmp_path, tmp_staging_root):
    """
    workflow_get and workflow_validate should find and validate files from the staging tree.
    """
    real_wf = tmp_path / "real_workflows"
    real_wf.mkdir()

    server = WorkflowMCPServer(workflows_root=real_wf)
    session_id = uuid.uuid4()
    valid_yaml = (
        "name: Staged CI\n"
        "on: [push]\n"
        "jobs:\n"
        "  build:\n"
        "    runs-on: ubuntu-latest\n"
        "    steps:\n"
        "      - run: echo 'staged'\n"
    )

    staging_service.stage_workflow_file(
        session_id=session_id,
        workflow_name="ci.yml",
        content=valid_yaml,
        real_workflows_root=real_wf,
    )

    # Real directory is untouched
    assert not (real_wf / "ci.yml").exists()

    # workflow_get returns staged content
    get_res = await server.execute_tool(
        "workflow_get",
        {"workflow_name": "ci.yml"},
        ctx={"session_id": str(session_id)},
    )
    assert get_res.success is True
    assert get_res.data["content"] == valid_yaml

    # workflow_validate without explicit content loads from staged file
    val_res = await server.execute_tool(
        "workflow_validate",
        {"workflow_name": "ci.yml"},
        ctx={"session_id": str(session_id)},
    )
    assert val_res.success is True
    assert val_res.data["valid"] is True
    assert val_res.data["name"] == "Staged CI"


@pytest.mark.asyncio
async def test_reject_action_cleans_staging(tmp_path, tmp_staging_root):
    """Rejecting a pending action should clean up the staging workspace."""
    session_id = uuid.uuid4()
    student_id = uuid.uuid4()
    guide_id = uuid.uuid4()

    async with async_session_factory() as db:
        student = User(
            id=student_id,
            email=f"student_{student_id.hex[:6]}@test.local",
            full_name="Student",
            role=UserRole.STUDENT,
        )
        guide = User(
            id=guide_id,
            email=f"guide_{guide_id.hex[:6]}@test.local",
            full_name="Guide",
            role=UserRole.GUIDE,
        )
        db.add_all([student, guide])
        await db.commit()

        # Stage a file
        staging_service.stage_terraform_file(
            session_id=session_id,
            file_path="main.tf",
            content="# test content",
        )
        assert staging_service.has_staged_files(session_id) is True

        # Create action
        action = await approval_service.create_pending_action(
            db=db,
            session_id=session_id,
            user_id=student_id,
            tool_name="terraform_write_file",
            tool_params={"file_path": "main.tf", "content": "# test content"},
        )
        await db.commit()

        # Reject action
        rejected = await approval_service.reject_action(db, action.id, guide_id, reason="Policy limit")
        await db.commit()

        assert rejected.status == ActionStatus.REJECTED
        # Staging should be completely cleaned up
        assert staging_service.has_staged_files(session_id) is False


@pytest.mark.asyncio
async def test_approve_action_cleans_staging(tmp_path, tmp_staging_root):
    """Approving an action should clean up the session staging tree."""
    session_id = uuid.uuid4()
    student_id = uuid.uuid4()
    admin_id = uuid.uuid4()

    async with async_session_factory() as db:
        student = User(
            id=student_id,
            email=f"student2_{student_id.hex[:6]}@test.local",
            full_name="Student",
            role=UserRole.STUDENT,
        )
        admin = User(
            id=admin_id,
            email=f"admin_{admin_id.hex[:6]}@test.local",
            full_name="Admin",
            role=UserRole.ADMIN,
        )
        db.add_all([student, admin])
        await db.commit()

        staging_service.stage_workflow_file(
            session_id=session_id,
            workflow_name="deploy.yml",
            content="name: Deploy\non: push\njobs:\n  d:\n    runs-on: ubuntu-latest\n",
        )
        assert staging_service.has_staged_files(session_id) is True

        action = await approval_service.create_pending_action(
            db=db,
            session_id=session_id,
            user_id=student_id,
            tool_name="workflow_write",
            tool_params={
                "workflow_name": "deploy.yml",
                "content": "name: Deploy\non: push\njobs:\n  d:\n    runs-on: ubuntu-latest\n",
            },
        )
        await db.commit()

        try:
            approved = await approval_service.approve_action(db, action.id, admin_id)
            await db.commit()

            assert approved.status == ActionStatus.APPROVED
            assert staging_service.has_staged_files(session_id) is False
        finally:
            for p in [
                Path(".github/workflows/deploy.yml"),
                Path("../.github/workflows/deploy.yml"),
            ]:
                if p.resolve().exists():
                    try:
                        p.resolve().unlink()
                    except OSError:
                        pass


@pytest.mark.asyncio
async def test_model_supplied_user_id_is_ignored():
    """
    If a model supplies a spoofed user_id in params, policy server must ignore it
    and enforce the authenticated user_id from ctx.
    """
    server = PolicyMCPServer()
    legitimate_user_id = uuid.uuid4()
    attacker_spoofed_id = uuid.uuid4()

    async with async_session_factory() as db:
        user = User(
            id=legitimate_user_id,
            email=f"legit_{legitimate_user_id.hex[:6]}@test.local",
            full_name="Legit User",
            role=UserRole.STUDENT,
        )
        db.add(user)
        await db.commit()

    # Pass spoofed attacker id in params, but real id in ctx
    result = await server.execute_tool(
        "policy_get_user_role",
        {"user_id": str(attacker_spoofed_id)},
        ctx={"user_id": str(legitimate_user_id)},
    )

    assert result.success is True
    # The returned data must match legitimate user, NOT spoofed attacker
    assert result.data["user_id"] == str(legitimate_user_id)
    assert result.data["email"] == f"legit_{legitimate_user_id.hex[:6]}@test.local"


@pytest.mark.asyncio
async def test_policy_escalation_approver_id_server_side():
    """
    policy_approve_escalation must not expose approver_id to the model,
    and approval_service must inject approver_id from the authenticated reviewer.
    """
    server = PolicyMCPServer()
    tools = {t.name: t for t in server.list_tools()}
    escalation_tool = tools["policy_approve_escalation"]

    # approver_id and user_id must be removed from model declarations
    param_names = [p.name for p in escalation_tool.parameters]
    assert "approver_id" not in param_names
    assert "user_id" not in param_names
    assert "requested_replicas" in param_names

    student_id = uuid.uuid4()
    guide_id = uuid.uuid4()

    async with async_session_factory() as db:
        student = User(
            id=student_id,
            email=f"student_{student_id.hex[:6]}@test.local",
            full_name="Student",
            role=UserRole.STUDENT,
        )
        guide = User(
            id=guide_id,
            email=f"guide_{guide_id.hex[:6]}@test.local",
            full_name="Guide",
            role=UserRole.GUIDE,
        )
        db.add_all([student, guide])
        await db.commit()

        # Pending action created without approver_id
        action = await approval_service.create_pending_action(
            db=db,
            session_id=uuid.uuid4(),
            user_id=student_id,
            tool_name="policy_approve_escalation",
            tool_params={"requested_replicas": 5},
        )
        await db.commit()

        # Approve sets approver_id from reviewer
        approved = await approval_service.approve_action(db, action.id, guide_id)
        await db.commit()

        assert approved.status == ActionStatus.APPROVED
        assert approved.result["success"] is True
        assert approved.result["data"]["approved_by"] == str(guide_id)



def test_path_traversal_rejected_in_staging(tmp_path, tmp_staging_root):
    """Path traversal attempts in staging must raise PermissionError."""
    session_id = uuid.uuid4()

    with pytest.raises(PermissionError):
        staging_service.stage_terraform_file(
            session_id=session_id,
            file_path="../../etc/passwd",
            content="evil",
        )

    with pytest.raises(PermissionError):
        staging_service.stage_workflow_file(
            session_id=session_id,
            workflow_name="../evil.yml",
            content="evil",
        )


def test_staging_skips_terraform_and_tfstate(tmp_path, tmp_staging_root):
    """Cloning iac/ to staging must omit .terraform and *.tfstate files."""
    real_iac = tmp_path / "base_iac"
    real_iac.mkdir()
    (real_iac / "main.tf").write_text("# main", encoding="utf-8")
    (real_iac / ".terraform").mkdir()
    (real_iac / ".terraform" / "plugin.bin").write_text("bin", encoding="utf-8")
    (real_iac / "terraform.tfstate").write_text("state", encoding="utf-8")
    (real_iac / "prod.tfstate").write_text("state", encoding="utf-8")

    session_id = uuid.uuid4()
    staging_service.stage_terraform_file(
        session_id=session_id,
        file_path="variables.tf",
        content="# vars",
        real_iac_root=real_iac,
    )

    staged_root = staging_service.get_staged_iac_root(session_id)
    assert staged_root is not None
    assert (staged_root / "main.tf").exists()
    assert (staged_root / "variables.tf").exists()
    # Must NOT copy .terraform or *.tfstate
    assert not (staged_root / ".terraform").exists()
    assert not (staged_root / "terraform.tfstate").exists()
    assert not (staged_root / "prod.tfstate").exists()

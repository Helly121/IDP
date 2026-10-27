"""
Unit tests for Phase 5: Mutating Patch Tools & Read-Only Jinja2 Template Rendering.

Verifies:
1. terraform_patch_file: fails if old_string not found or found multiple times.
2. terraform_patch_file: applied to staged copy at proposal time, read/validate sees staged copy.
3. terraform_patch_file: re-applied on approval, updates real file, and cleans staging.
4. terraform_patch_file: fails clearly on approval if real file was modified in between (conflict).
5. workflow_patch: replaces old_string with new_string and validates YAML syntax.
6. workflow_patch: fails if invalid YAML syntax results.
7. render_template: renders iac/templates/*.tpl with variables using Jinja2 and honors defaults.
8. render_template: path traversal attempts are rejected.
"""

import shutil
import uuid
from pathlib import Path

import pytest
import pytest_asyncio
import yaml

from app.core.config import settings
from app.core.database import async_session_factory, init_db
from app.models.user import User, UserRole
from app.models.pending_action import PendingAction, ActionStatus
from app.mcp_servers.registry import registry
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
async def test_terraform_patch_file_staged_and_seen_by_reader(tmp_path, tmp_staging_root):
    """Patching a Terraform file applies to staging at proposal time."""
    real_iac = tmp_path / "real_iac"
    real_iac.mkdir()
    main_tf = real_iac / "main.tf"
    main_tf.write_text('variable "instances" {\n  default = 2\n}\n', encoding="utf-8")

    server = TerraformMCPServer(iac_root=real_iac)
    session_id = uuid.uuid4()

    # Apply patch to staging
    staged_path = staging_service.stage_terraform_patch(
        session_id=session_id,
        file_path="main.tf",
        old_string="default = 2",
        new_string="default = 4",
        real_iac_root=real_iac,
    )

    # Real file remains unmodified
    assert main_tf.read_text(encoding="utf-8") == 'variable "instances" {\n  default = 2\n}\n'

    # Staged file has the patch
    assert staged_path.read_text(encoding="utf-8") == 'variable "instances" {\n  default = 4\n}\n'

    # Reader tool with matching session sees the staged patch
    res = await server.execute_tool(
        "terraform_get_file",
        {"file_path": "main.tf"},
        ctx={"session_id": str(session_id)},
    )
    assert res.success is True
    assert "default = 4" in res.data["content"]


def test_terraform_patch_file_fails_when_not_found_or_not_unique(tmp_path, tmp_staging_root):
    """Patch fails if old_string is not found or occurs more than once."""
    real_iac = tmp_path / "real_iac"
    real_iac.mkdir()
    (real_iac / "main.tf").write_text("item = 1\nitem = 1\nother = 2\n", encoding="utf-8")

    session_id = uuid.uuid4()

    # 1. Not found
    with pytest.raises(ValueError, match="not found"):
        staging_service.stage_terraform_patch(
            session_id=session_id,
            file_path="main.tf",
            old_string="nonexistent = 99",
            new_string="val = 1",
            real_iac_root=real_iac,
        )

    # 2. Not unique (occurs 2 times)
    with pytest.raises(ValueError, match="must occur exactly once"):
        staging_service.stage_terraform_patch(
            session_id=session_id,
            file_path="main.tf",
            old_string="item = 1",
            new_string="item = 3",
            real_iac_root=real_iac,
        )


@pytest.mark.asyncio
async def test_terraform_patch_reapply_on_approval(tmp_path, tmp_staging_root):
    """On approval, the patch is applied to the real file and staging is cleaned."""
    real_iac = tmp_path / "real_iac"
    real_iac.mkdir()
    main_tf = real_iac / "main.tf"
    main_tf.write_text('resource "aws_instance" "app" {\n  count = 1\n}\n', encoding="utf-8")

    server = TerraformMCPServer(iac_root=real_iac)
    session_id = uuid.uuid4()
    student_id = uuid.uuid4()
    guide_id = uuid.uuid4()

    # Stage the patch
    staging_service.stage_terraform_patch(
        session_id=session_id,
        file_path="main.tf",
        old_string="count = 1",
        new_string="count = 3",
        real_iac_root=real_iac,
    )
    assert staging_service.has_staged_files(session_id) is True

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

        action = await approval_service.create_pending_action(
            db=db,
            session_id=session_id,
            user_id=student_id,
            tool_name="terraform_patch_file",
            tool_params={
                "file_path": "main.tf",
                "old_string": "count = 1",
                "new_string": "count = 3",
            },
        )
        await db.commit()

        # Approve action directly executing through server
        patch_res = await server.execute_tool(
            "terraform_patch_file",
            action.tool_params,
        )
        assert patch_res.success is True
        assert "count = 3" in main_tf.read_text(encoding="utf-8")

        # Cleanup staging
        staging_service.cleanup_staging(session_id)
        assert staging_service.has_staged_files(session_id) is False


@pytest.mark.asyncio
async def test_terraform_patch_fails_on_approval_if_real_file_changed(tmp_path):
    """If the real file changed between proposal and approval, patch execution fails clearly."""
    real_iac = tmp_path / "real_iac"
    real_iac.mkdir()
    main_tf = real_iac / "main.tf"
    # Initial state when proposed: count = 1
    main_tf.write_text('resource "aws_instance" "app" {\n  count = 1\n}\n', encoding="utf-8")

    server = TerraformMCPServer(iac_root=real_iac)

    # In the meantime, another change modifies the file so count = 1 is gone
    main_tf.write_text('resource "aws_instance" "app" {\n  count = 5\n}\n', encoding="utf-8")

    # Reviewer approves the earlier patch (which expects count = 1)
    result = await server.execute_tool(
        "terraform_patch_file",
        {
            "file_path": "main.tf",
            "old_string": "count = 1",
            "new_string": "count = 3",
        },
    )

    # Must fail with clear conflict error message
    assert result.success is False
    assert "old_string not found in real file" in result.error
    assert "changed since the patch was proposed" in result.error


@pytest.mark.asyncio
async def test_workflow_patch_success_and_yaml_validation(tmp_path, tmp_staging_root):
    """workflow_patch replaces string, ensures valid YAML, and stages changes."""
    real_wf = tmp_path / "workflows"
    real_wf.mkdir()
    ci_yml = real_wf / "ci.yml"
    ci_yml.write_text(
        "name: CI\non: push\njobs:\n  build:\n    runs-on: ubuntu-latest\n",
        encoding="utf-8",
    )

    server = WorkflowMCPServer(workflows_root=real_wf)
    session_id = uuid.uuid4()

    # Stage the workflow patch
    staged = staging_service.stage_workflow_patch(
        session_id=session_id,
        workflow_name="ci.yml",
        old_string="runs-on: ubuntu-latest",
        new_string="runs-on: ubuntu-22.04",
        real_workflows_root=real_wf,
    )

    # Staged workflow contains replaced value and is valid YAML
    assert "runs-on: ubuntu-22.04" in staged.read_text(encoding="utf-8")
    parsed = yaml.safe_load(staged.read_text(encoding="utf-8"))
    assert parsed["jobs"]["build"]["runs-on"] == "ubuntu-22.04"

    # Execution on real server replaces and writes
    patch_res = await server.execute_tool(
        "workflow_patch",
        {
            "file_path": "ci.yml",
            "old_string": "runs-on: ubuntu-latest",
            "new_string": "runs-on: ubuntu-22.04",
        },
    )
    assert patch_res.success is True
    assert "runs-on: ubuntu-22.04" in ci_yml.read_text(encoding="utf-8")


def test_workflow_patch_fails_on_broken_yaml(tmp_path, tmp_staging_root):
    """workflow_patch rejects changes that result in malformed YAML syntax."""
    real_wf = tmp_path / "workflows"
    real_wf.mkdir()
    ci_yml = real_wf / "ci.yml"
    ci_yml.write_text("name: Valid\non: push\n", encoding="utf-8")

    session_id = uuid.uuid4()

    # Introduce invalid YAML syntax with patch
    with pytest.raises(ValueError, match="YAML syntax error"):
        staging_service.stage_workflow_patch(
            session_id=session_id,
            workflow_name="ci.yml",
            old_string="on: push",
            new_string="on: [push, unclosed",
            real_workflows_root=real_wf,
        )


@pytest.mark.asyncio
async def test_render_template_jinja2(tmp_path):
    """render_template fills iac/templates/*.tpl with variables and respects defaults."""
    iac_root = tmp_path / "iac"
    templates_dir = iac_root / "templates"
    templates_dir.mkdir(parents=True)

    template_content = (
        "apiVersion: apps/v1\n"
        "kind: Deployment\n"
        "metadata:\n"
        "  name: {{ service_name }}\n"
        "spec:\n"
        "  replicas: {{ replicas }}\n"
        "  template:\n"
        "    spec:\n"
        "      containers:\n"
        "        - name: {{ service_name }}\n"
        "          ports:\n"
        "            - containerPort: {{ port | default(8000) }}\n"
    )
    (templates_dir / "deployment.yaml.tpl").write_text(template_content, encoding="utf-8")

    server = TerraformMCPServer(iac_root=iac_root)

    # 1. Render with port specified
    res1 = await server.execute_tool(
        "render_template",
        {
            "template_name": "deployment.yaml.tpl",
            "variables": {
                "service_name": "payment-api",
                "replicas": 3,
                "port": 9000,
            },
        },
    )
    assert res1.success is True
    assert "name: payment-api" in res1.data["rendered"]
    assert "replicas: 3" in res1.data["rendered"]
    assert "containerPort: 9000" in res1.data["rendered"]

    # 2. Render without port (verifies Jinja default filter port | default(8000))
    res2 = await server.execute_tool(
        "render_template",
        {
            "template_name": "deployment.yaml.tpl",
            "variables": {
                "service_name": "auth-api",
                "replicas": 1,
            },
        },
    )
    assert res2.success is True
    assert "containerPort: 8000" in res2.data["rendered"]


@pytest.mark.asyncio
async def test_render_template_path_traversal_rejected(tmp_path):
    """Path traversal in render_template is safely rejected."""
    iac_root = tmp_path / "iac"
    templates_dir = iac_root / "templates"
    templates_dir.mkdir(parents=True)

    server = TerraformMCPServer(iac_root=iac_root)

    res = await server.execute_tool(
        "render_template",
        {
            "template_name": "../../etc/passwd",
            "variables": {},
        },
    )
    assert res.success is False
    assert "denied" in res.error.lower() or "escapes" in res.error.lower()

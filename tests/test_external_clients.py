import httpx
import pytest
from cryptography.fernet import Fernet

from app.core.database import SessionLocal
from app.models.command_center import IntegrationCredentialRecord
from app.services.outlook import OutlookClient, OutlookSettings
from app.services.outlook_auth import (
    OutlookCredentialVault,
    OutlookOAuthSettings,
    OutlookTokenManager,
    outlook_oauth_configuration,
)
from app.services.supabase import SupabaseClient, SupabaseSettings
from app.services.supervity import SupervityClient, SupervitySettings


@pytest.mark.asyncio
async def test_outlook_client_checks_inbox_with_backend_token() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["select"] = request.url.params["$select"]
        captured["authorization"] = request.headers["authorization"]
        return httpx.Response(
            200,
            json={
                "displayName": "Inbox",
                "totalItemCount": 42,
                "unreadItemCount": 7,
            },
        )

    client = OutlookClient(
        OutlookSettings(
            graph_base_url="https://graph.microsoft.test/v1.0",
            access_token="outlook-secret",
            timeout_seconds=1,
        ),
        transport=httpx.MockTransport(handler),
    )

    status = await client.inbox_status()

    assert status["totalItemCount"] == 42
    assert status["unreadItemCount"] == 7
    assert captured["path"] == "/v1.0/me/mailFolders/inbox"
    assert captured["select"] == "displayName,totalItemCount,unreadItemCount"
    assert captured["authorization"] == "Bearer outlook-secret"


@pytest.mark.asyncio
async def test_outlook_client_follows_delta_pages_and_keeps_graph_host() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path.endswith("/messages/delta"):
            return httpx.Response(
                200,
                json={
                    "value": [{"id": "MSG-1"}],
                    "@odata.nextLink": (
                        "https://graph.microsoft.test/v1.0/delta-page-2"
                    ),
                },
            )
        return httpx.Response(
            200,
            json={
                "value": [{"id": "MSG-2"}],
                "@odata.deltaLink": ("https://graph.microsoft.test/v1.0/delta-next"),
            },
        )

    client = OutlookClient(
        OutlookSettings(
            graph_base_url="https://graph.microsoft.test/v1.0",
            access_token="outlook-secret",
            timeout_seconds=1,
        ),
        transport=httpx.MockTransport(handler),
    )

    result = await client.collect_inbox_delta(max_pages=2)

    assert [message["id"] for message in result.messages] == ["MSG-1", "MSG-2"]
    assert result.delta_link.endswith("/delta-next")
    assert result.pages_seen == 2
    assert requests[0].url.params["$select"].startswith("id,internetMessageId")
    assert "$select" not in requests[1].url.params
    assert all(request.url.host == "graph.microsoft.test" for request in requests)
    assert all(
        request.headers["authorization"] == "Bearer outlook-secret"
        for request in requests
    )


@pytest.mark.asyncio
async def test_outlook_client_uses_refreshed_token_provider() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["authorization"] = request.headers["authorization"]
        return httpx.Response(
            200,
            json={
                "displayName": "Inbox",
                "totalItemCount": 5,
                "unreadItemCount": 2,
            },
        )

    client = OutlookClient(
        OutlookSettings(
            graph_base_url="https://graph.microsoft.test/v1.0",
            access_token=None,
            timeout_seconds=1,
        ),
        transport=httpx.MockTransport(handler),
        access_token_provider=lambda: "silently-refreshed-token",
    )

    await client.inbox_status()

    assert captured["authorization"] == "Bearer silently-refreshed-token"


def test_outlook_oauth_configuration_reports_missing_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in (
        "OUTLOOK_CLIENT_ID",
        "OUTLOOK_CLIENT_SECRET",
        "OUTLOOK_REDIRECT_URI",
        "OUTLOOK_TOKEN_CACHE_KEY",
        "OUTLOOK_ACCESS_TOKEN",
    ):
        monkeypatch.delenv(name, raising=False)

    metadata = outlook_oauth_configuration()

    assert metadata["oauth_configured"] is False
    assert metadata["auth_mode"] == "unconfigured"
    assert "OUTLOOK_CLIENT_ID" in metadata["oauth_missing"]


def test_outlook_vault_encrypts_persistent_token_cache() -> None:
    key = Fernet.generate_key().decode("ascii")
    db = SessionLocal()
    try:
        db.query(IntegrationCredentialRecord).filter(
            IntegrationCredentialRecord.integration_id == "outlook"
        ).delete()
        vault = OutlookCredentialVault(db, key)
        vault.save({"token_cache": "refresh-token-material", "version": 1})
        db.commit()

        stored = (
            db.query(IntegrationCredentialRecord)
            .filter(IntegrationCredentialRecord.integration_id == "outlook")
            .one()
        )
        assert "refresh-token-material" not in stored.encrypted_payload
        assert vault.load()["token_cache"] == "refresh-token-material"
    finally:
        db.rollback()
        db.close()


def test_outlook_token_manager_acquires_silently(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeConfidentialClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def get_accounts(self) -> list[dict]:
            return [{"username": "procurement@example.test"}]

        def acquire_token_silent(self, *, scopes: list[str], account: dict) -> dict:
            assert scopes == ["Mail.Read", "User.Read"]
            assert account["username"] == "procurement@example.test"
            return {"access_token": "refreshed-access-token"}

    monkeypatch.setattr(
        "app.services.outlook_auth.msal.ConfidentialClientApplication",
        FakeConfidentialClient,
    )
    db = SessionLocal()
    try:
        db.query(IntegrationCredentialRecord).filter(
            IntegrationCredentialRecord.integration_id == "outlook"
        ).delete()
        settings = OutlookOAuthSettings(
            client_id="client-id",
            client_secret="client-secret",
            tenant="consumers",
            redirect_uri="http://localhost:8001/callback",
            scopes=("Mail.Read", "User.Read"),
            token_cache_key=Fernet.generate_key().decode("ascii"),
        )
        manager = OutlookTokenManager(db, settings)

        assert manager.access_token() == "refreshed-access-token"
        assert manager.account_metadata() == {
            "oauth_connected": True,
            "oauth_account": "procurement@example.test",
        }
    finally:
        db.rollback()
        db.close()


def test_supabase_settings_prefers_new_secret_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SUPABASE_URL", "https://project.supabase.test/")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "sb_secret_preferred")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "legacy-service-role")
    monkeypatch.setenv("SUPABASE_API_KEY", "compatibility-key")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "sb_publishable_public")

    settings = SupabaseSettings.from_environment()

    assert settings.url == "https://project.supabase.test"
    assert settings.api_key == "sb_secret_preferred"


def test_supabase_settings_skips_publishable_key_in_service_role_slot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SUPABASE_URL", "https://project.supabase.test")
    monkeypatch.delenv("SUPABASE_SECRET_KEY", raising=False)
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "sb_publishable_misplaced")
    monkeypatch.setenv("SUPABASE_API_KEY", "sb_secret_compatibility")

    settings = SupabaseSettings.from_environment()

    assert settings.api_key == "sb_secret_compatibility"


def test_supabase_settings_uses_default_for_blank_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SUPABASE_URL", "https://project.supabase.test")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "sb_secret_backend")
    monkeypatch.setenv("SUPABASE_TIMEOUT_SECONDS", "")

    settings = SupabaseSettings.from_environment()

    assert settings.timeout_seconds == 30


@pytest.mark.parametrize("api_key", ["sb_secret_backend", "sb_publishable_public"])
def test_supabase_opaque_api_keys_are_not_sent_as_bearer_tokens(api_key: str) -> None:
    client = SupabaseClient(
        SupabaseSettings(
            url="https://project.supabase.test",
            api_key=api_key,
            timeout_seconds=1,
        )
    )

    assert client.headers["apikey"] == api_key
    assert "Authorization" not in client.headers


def test_supabase_legacy_jwt_is_sent_as_bearer_token() -> None:
    client = SupabaseClient(
        SupabaseSettings(
            url="https://project.supabase.test",
            api_key="eyJlegacy-service-role",
            timeout_seconds=1,
        )
    )

    assert client.headers["Authorization"] == "Bearer eyJlegacy-service-role"


@pytest.mark.asyncio
async def test_supervity_trigger_uses_backend_auth_and_callback_contract() -> None:
    captured: dict = {}
    announced_run_ids: list[str] = []

    async def announce_run_id(run_id: str) -> None:
        announced_run_ids.append(run_id)

    def handler(request: httpx.Request) -> httpx.Response:
        captured["authorization"] = request.headers["authorization"]
        captured["source"] = request.headers["x-source"]
        captured["timezone"] = request.headers["x-user-timezone"]
        captured["content_type"] = request.headers["content-type"]
        captured["body"] = request.content.decode()
        return httpx.Response(
            202,
            text=(
                'data: {"content":"working"}\n\n'
                'data: {"success":true,"message":"Workflow executed '
                'successfully","workflowRun":{"id":"AUTO-RUN-42",'
                '"status":"completed"}}\n\n'
            ),
            headers={
                "Content-Type": "text/event-stream",
                "x-workflow-run-id": "AUTO-RUN-42",
            },
        )

    client = SupervityClient(
        SupervitySettings(
            trigger_url="https://auto.example.test/workflows/run",
            api_key="server-secret",
            orchestrator_id="orchestrator-7",
            status_url_template=None,
            resume_url_template=None,
            source_header="external",
            user_timezone="Asia/Kuala_Lumpur",
            timeout_seconds=1,
            include_callback_inputs=True,
        ),
        transport=httpx.MockTransport(handler),
    )
    result = await client.trigger(
        command_center_run_id="CC-RUN-1",
        incident_id="DN-5046",
        inputs={
            "source": "outlook",
            "source_ref": "DN-5046",
            "received_at_raw": "2026-08-02T10:00:00+08:00",
            "sender_email": "supplier@example.test",
            "body": "Supplier shutdown reported",
        },
        callback_url="https://commander.example.test/api/command-center/supervity/callback",
        callback_token="per-run-token",
        on_run_id=announce_run_id,
    )

    assert result.run_id == "AUTO-RUN-42"
    assert result.success is True
    assert result.status == "completed"
    assert result.message == "Workflow executed successfully"
    assert announced_run_ids == ["AUTO-RUN-42"]
    assert captured["authorization"] == "Bearer server-secret"
    assert captured["source"] == "external"
    assert captured["timezone"] == "Asia/Kuala_Lumpur"
    assert captured["content_type"].startswith("multipart/form-data; boundary=")
    for expected in (
        'name="workflowId"',
        "orchestrator-7",
        'name="inputs[source]"',
        "outlook",
        'name="inputs[source_ref]"',
        "DN-5046",
        'name="inputs[received_at_raw]"',
        "2026-08-02T10:00:00+08:00",
        'name="inputs[sender_email]"',
        "supplier@example.test",
        'name="inputs[body]"',
        "Supplier shutdown reported",
        'name="inputs[command_center_run_id]"',
        "CC-RUN-1",
        'name="inputs[incident_id]"',
        "DN-5046",
        'name="inputs[callback_token]"',
        "per-run-token",
        'name="inputs[status_callback_url]"',
        "/api/command-center/supervity/callback",
        'name="inputs[notification_callback_url]"',
        "/api/command-center/supervity/notification",
        'name="inputs[decision_callback_url]"',
        "/api/command-center/supervity/decision",
        'name="inputs[policy_evaluate_url]"',
        "/api/command-center/policies/evaluate",
        'name="inputs[action_authorize_url]"',
        "/api/command-center/supervity/action-authorization",
        'name="inputs[action_complete_url]"',
        "/api/command-center/supervity/action-completion",
    ):
        assert expected in captured["body"]


@pytest.mark.asyncio
async def test_supervity_generic_workflow_trigger_maps_named_inputs() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.content.decode()
        return httpx.Response(
            202,
            text=(
                'data: {"success":true,"workflowRun":'
                '{"id":"AUTO-INSIGHT-7","status":"completed"}}\n\n'
            ),
            headers={"Content-Type": "text/event-stream"},
        )

    client = SupervityClient(
        SupervitySettings(
            trigger_url="https://auto.example.test/api/v1/workflow-runs/execute/stream",
            api_key="server-secret",
            orchestrator_id="primary-orchestrator",
            status_url_template=None,
            resume_url_template=None,
            source_header="external",
            user_timezone="Asia/Kuala_Lumpur",
            timeout_seconds=1,
        ),
        transport=httpx.MockTransport(handler),
    )
    result = await client.trigger_workflow(
        workflow_id="insight-workflow",
        inputs={
            "channel_id": "C-INSIGHT",
            "thread_ts": "1720000000.001",
            "text": "show inventory risk",
        },
        envs={"SLACK_BOT_TOKEN": "xoxb-test"},
    )

    assert result.run_id == "AUTO-INSIGHT-7"
    for expected in (
        'name="workflowId"',
        "insight-workflow",
        'name="inputs[channel_id]"',
        "C-INSIGHT",
        'name="inputs[thread_ts]"',
        "1720000000.001",
        'name="inputs[text]"',
        "show inventory risk",
        'name="envs[SLACK_BOT_TOKEN]"',
        "SLACK_BOT_TOKEN",
        "xoxb-test",
    ):
        assert expected in captured["body"]


@pytest.mark.asyncio
async def test_supervity_management_apis_use_active_org_and_documented_paths() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if (
            request.url.host == "workflow.example.test"
            and request.url.path == "/api/v1/workflow-runs/AUTO-42"
        ):
            return httpx.Response(200, json={"id": "AUTO-42", "status": "running"})
        if (
            request.url.host == "workflow.example.test"
            and request.url.path == "/api/v1/user-forms"
        ):
            return httpx.Response(200, json={"forms": [{"id": "FORM-1"}]})
        if (
            request.url.host == "workflow.example.test"
            and request.url.path == "/api/v1/user-forms/FORM-1"
        ):
            return httpx.Response(200, json={"html": "<h2>Review</h2>"})
        if (
            request.url.host == "integration.example.test"
            and request.url.path == "/api/v1/integrations/me"
        ):
            return httpx.Response(200, json={"integrations": [], "userActions": []})
        if (
            request.url.host == "workflow.example.test"
            and request.url.path == "/api/v1/schedules"
        ):
            return httpx.Response(200, json={"schedules": [{"id": "SCH-1"}]})
        return httpx.Response(404)

    client = SupervityClient(
        SupervitySettings(
            trigger_url="https://auto.example.test/api/v1/workflow-runs/execute/stream",
            api_key="server-secret",
            orchestrator_id="orchestrator-7",
            status_url_template=None,
            resume_url_template=None,
            source_header="external",
            user_timezone="Asia/Kuala_Lumpur",
            timeout_seconds=1,
            api_base_url="https://workflow.example.test/api/v1",
            integration_api_base_url="https://integration.example.test/api/v1",
            active_org="ORG-9",
        ),
        transport=httpx.MockTransport(handler),
    )

    assert (await client.status("AUTO-42"))["status"] == "running"
    assert await client.list_user_forms(status="pending") == [{"id": "FORM-1"}]
    assert await client.get_user_form("FORM-1") == {"html": "<h2>Review</h2>"}
    assert await client.integration_inventory() == {
        "integrations": [],
        "userActions": [],
    }
    assert await client.list_schedules() == [{"id": "SCH-1"}]
    assert all(
        request.headers["authorization"] == "Bearer server-secret"
        for request in requests
    )
    assert all(request.headers["x-active-org"] == "ORG-9" for request in requests)
    assert requests[1].url.params["status"] == "pending"
    assert (
        next(
            request
            for request in requests
            if request.url.path == "/api/v1/integrations/me"
        ).url.host
        == "integration.example.test"
    )


@pytest.mark.asyncio
async def test_supervity_user_form_submission_is_multipart_and_public() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["authorization"] = request.headers.get("authorization")
        captured["content_type"] = request.headers["content-type"]
        captured["body"] = request.content.decode()
        return httpx.Response(200, text="Form Submitted Successfully")

    client = SupervityClient(
        SupervitySettings(
            trigger_url="https://auto.example.test/api/v1/workflow-runs/execute/stream",
            api_key="server-secret",
            orchestrator_id="orchestrator-7",
            status_url_template=None,
            resume_url_template=None,
            source_header="external",
            user_timezone="Asia/Kuala_Lumpur",
            timeout_seconds=1,
            api_base_url="https://auto.example.test/api/v1",
        ),
        transport=httpx.MockTransport(handler),
    )

    result = await client.submit_user_form(
        activity_run_id="ACT-7",
        status="approve",
        fields={"decision": "approve", "payload": {"quantity": 4}},
    )

    assert result == "Form Submitted Successfully"
    assert captured["path"] == "/api/v1/user-forms/ACT-7/approve"
    assert captured["authorization"] is None
    assert captured["content_type"].startswith("multipart/form-data; boundary=")
    assert 'name="decision"' in captured["body"]
    assert 'name="payload"' in captured["body"]
    assert '"quantity": 4' in captured["body"]


@pytest.mark.asyncio
async def test_supabase_client_reads_rows_and_exact_counts() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.headers.get("range") == "0-0":
            total = 118 if request.url.path.endswith("disruption_notices") else 39
            return httpx.Response(
                206,
                json=[{"notice_id": "DN-5046"}],
                headers={"Content-Range": f"0-0/{total}"},
            )
        return httpx.Response(200, json=[{"notice_id": "DN-5046"}])

    client = SupabaseClient(
        SupabaseSettings(
            url="https://project.supabase.test",
            api_key="service-key",
            timeout_seconds=1,
        ),
        transport=httpx.MockTransport(handler),
    )

    rows = await client.fetch_rows(
        "disruption_notices",
        filters={"notice_id": "eq.DN-5046"},
    )
    count = await client.count("disruption_notices")
    table_counts = await client.count_tables(
        ("disruption_notices", "inventory_positions")
    )

    assert rows == [{"notice_id": "DN-5046"}]
    assert count == 118
    assert table_counts == {
        "disruption_notices": 118,
        "inventory_positions": 39,
    }
    assert all(request.headers["apikey"] == "service-key" for request in requests)

import asyncio
import hashlib
import hmac
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.routers import command_center as command_center_router
from app.security import get_current_user, verify_access
from app.services.outlook import OutlookDelta
from scripts.seed_db import seed_data

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def allow_test_access(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("SUPERVITY_WORKFLOW_API_KEY", raising=False)
    app.dependency_overrides[verify_access] = lambda: None
    app.dependency_overrides[get_current_user] = lambda: {
        "sub": "test-user",
        "email": "commander@example.com",
    }
    yield
    app.dependency_overrides.pop(verify_access, None)
    app.dependency_overrides.pop(get_current_user, None)


async def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _create_run(client: AsyncClient, incident_id: str) -> dict:
    response = await client.post(
        "/api/command-center/runs",
        json={
            "incident_id": incident_id,
            "source": "test",
            "input_payload": {"notice_id": incident_id},
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_outlook_poll_baselines_then_creates_and_starts_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed_data()
    monkeypatch.setenv("OUTLOOK_POLL_SECRET", "scheduler-secret")
    started: list[str] = []

    class FakeOutlookClient:
        async def collect_inbox_delta(
            self,
            *,
            delta_link: str | None = None,
            max_pages: int = 25,
        ) -> OutlookDelta:
            assert max_pages == 25
            if delta_link is None:
                return OutlookDelta(
                    messages=(
                        {
                            "id": "MSG-OLD-1",
                            "internetMessageId": "<old-1@example.test>",
                        },
                        {
                            "id": "MSG-OLD-2",
                            "internetMessageId": "<old-2@example.test>",
                        },
                    ),
                    delta_link="https://graph.microsoft.test/delta-1",
                    pages_seen=1,
                )
            return OutlookDelta(
                messages=(
                    {
                        "id": "MSG-NEW-1",
                        "internetMessageId": "<new-1@example.test>",
                    },
                ),
                delta_link=(
                    "https://graph.microsoft.test/delta-2"
                    if delta_link.endswith("delta-1")
                    else "https://graph.microsoft.test/delta-3"
                ),
                pages_seen=1,
            )

        async def inbox_status(self) -> dict:
            return {"displayName": "Inbox", "totalItemCount": 29}

        def auth_metadata(self) -> dict:
            return {"auth_mode": "static_access_token"}

        async def message_details(self, message_id: str) -> dict:
            assert message_id == "MSG-NEW-1"
            return {
                "id": message_id,
                "internetMessageId": "<new-1@example.test>",
                "subject": "DN-9001 supplier shutdown",
                "from": {"emailAddress": {"address": "supplier@example.test"}},
                "receivedDateTime": "2026-08-08T07:00:00Z",
                "body": {
                    "contentType": "text",
                    "content": "Plant shutdown affects SKU-CEM-101.",
                },
                "hasAttachments": False,
                "webLink": "https://outlook.office.test/message/MSG-NEW-1",
            }

    fake = FakeOutlookClient()
    monkeypatch.setattr(
        command_center_router.OutlookClient,
        "from_environment",
        classmethod(lambda cls, **kwargs: fake),
    )

    async def fake_consume(run_id: str) -> None:
        started.append(run_id)

    monkeypatch.setattr(
        command_center_router,
        "_consume_supervity_stream",
        fake_consume,
    )
    async with await _client() as client:
        reset = await client.put(
            "/api/command-center/integrations/outlook",
            json={
                "name": "Outlook",
                "category": "channel",
                "status": "unknown",
                "checked_at": "2026-08-08T06:50:00Z",
                "metadata": {"purpose": "Inbound disruption notices"},
            },
        )
        assert reset.status_code == 200, reset.text

        unauthorized = await client.post(
            "/api/command-center/outlook/poll",
            headers={"X-Outlook-Poll-Secret": "wrong"},
        )
        assert unauthorized.status_code == 401

        headers = {"X-Outlook-Poll-Secret": "scheduler-secret"}
        baseline = await client.post(
            "/api/command-center/outlook/poll",
            headers=headers,
        )
        assert baseline.status_code == 200, baseline.text
        assert baseline.json()["baseline_established"] is True
        assert baseline.json()["baseline_messages"] == 2
        assert baseline.json()["runs_created"] == 0

        created = await client.post(
            "/api/command-center/outlook/poll",
            headers=headers,
        )
        assert created.status_code == 200, created.text
        assert created.json()["baseline_established"] is False
        assert created.json()["runs_created"] == 1
        assert created.json()["runs_started"] == 1
        assert started == created.json()["run_ids"]

        run = await client.get(
            f"/api/command-center/runs/{created.json()['run_ids'][0]}"
        )
        assert run.status_code == 200, run.text
        assert run.json()["incident_id"] == "DN-9001"
        assert run.json()["source"] == "outlook"
        assert run.json()["source_ref"] == "<new-1@example.test>"
        assert run.json()["input_payload"]["sender_email"] == ("supplier@example.test")

        duplicate = await client.post(
            "/api/command-center/outlook/poll",
            headers=headers,
        )
        assert duplicate.status_code == 200, duplicate.text
        assert duplicate.json()["runs_created"] == 0
        assert duplicate.json()["duplicates_skipped"] == 1
        assert len(started) == 1

        integrations = await client.get("/api/command-center/integrations")
        outlook = next(
            item for item in integrations.json() if item["integration_id"] == "outlook"
        )
        assert outlook["status"] == "healthy"
        assert "_outlook_delta_link" not in outlook["metadata"]
        assert outlook["metadata"]["polling"]["last_runs_created"] == 0


async def test_outlook_connection_uses_supervity_inventory_not_graph(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed_data()
    connected_payload = {
        "integrations": [
            {
                "integrationSlug": "microsoft-outlook",
                "accountIdentifier": "buyer@example.test",
            }
        ],
        "userActions": [
            {
                "group": {"name": "microsoft-outlook"},
                "action": {"name": "send-email"},
            }
        ],
    }
    payloads = [
        connected_payload,
        connected_payload,
        {"integrations": [], "userActions": []},
    ]

    class FakeSupervityClient:
        async def integration_inventory(self) -> dict:
            return payloads.pop(0)

    monkeypatch.setattr(
        command_center_router.SupervityClient,
        "from_environment",
        classmethod(lambda cls: FakeSupervityClient()),
    )
    monkeypatch.setattr(
        command_center_router.OutlookClient,
        "from_environment",
        classmethod(
            lambda cls, **kwargs: pytest.fail(
                "The Data Manager Outlook test must not query Microsoft Graph"
            )
        ),
    )
    async with await _client() as client:
        inventory = await client.get("/api/command-center/supervity/integrations")
        assert inventory.status_code == 200, inventory.text
        assert inventory.json()["connected_accounts"][0]["name"] == (
            "buyer@example.test"
        )

        connected = await client.post("/api/command-center/integrations/outlook/test")
        assert connected.status_code == 200, connected.text
        assert connected.json()["status"] == "healthy"
        assert (
            connected.json()["metadata"]["status_source"]
            == "supervity_integrations_api"
        )
        assert connected.json()["metadata"]["actions_count"] == 1

        disconnected = await client.post(
            "/api/command-center/integrations/outlook/test"
        )
        assert disconnected.status_code == 200, disconnected.text
        assert disconnected.json()["status"] == "disconnected"
        assert disconnected.json()["last_error"] == (
            "Outlook is not connected in Supervity"
        )


async def test_integration_views_reconcile_supervity_as_single_source_of_truth(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed_data()
    payload = {
        "integrations": [
            {
                "integrationSlug": "microsoft-outlook",
                "accountIdentifier": "buyer@example.test",
            },
            {
                "integrationSlug": "slack",
                "accountIdentifier": "procurement-ops",
            },
            {
                "integrationSlug": "supabase",
                "accountIdentifier": "autopilot-data",
            },
        ],
        "userActions": [
            {
                "group": {"name": "microsoft-outlook"},
                "action": {"name": "send-email"},
            },
            {
                "group": {"name": "slack"},
                "action": {"name": "send-message"},
            },
            {
                "group": {"name": "supabase"},
                "action": {"name": "select-rows"},
            },
        ],
    }

    class FakeSupervityClient:
        async def integration_inventory(self) -> dict:
            return payload

    monkeypatch.setattr(
        command_center_router.SupervityClient,
        "from_environment",
        classmethod(lambda cls: FakeSupervityClient()),
    )

    async with await _client() as client:
        supabase = await client.put(
            "/api/command-center/integrations/supabase",
            json={
                "name": "Supabase",
                "category": "system_of_record",
                "status": "healthy",
                "checked_at": "2026-08-09T00:00:00Z",
                "last_success_at": "2026-08-09T00:00:00Z",
                "records_seen": 1854,
                "metadata": {"purpose": "Procurement operational data"},
            },
        )
        assert supabase.status_code == 200, supabase.text

        dashboard = await client.get("/api/command-center/dashboard")
        assert dashboard.status_code == 200, dashboard.text
        assert dashboard.json()["healthy_integrations"] == 4
        assert dashboard.json()["total_integrations"] == 4

        integrations = await client.get("/api/command-center/integrations")
        assert integrations.status_code == 200, integrations.text
        by_id = {item["integration_id"]: item for item in integrations.json()}
        assert by_id["supervity-auto"]["status"] == "healthy"
        assert by_id["outlook"]["status"] == "healthy"
        assert by_id["outlook"]["metadata"]["auto_account"] == (
            "buyer@example.test"
        )
        assert by_id["slack-via-supervity"]["name"] == "Slack"
        assert by_id["slack-via-supervity"]["category"] == "channel"
        assert by_id["slack-via-supervity"]["status"] == "healthy"
        assert by_id["slack-via-supervity"]["metadata"]["auto_account"] == (
            "procurement-ops"
        )

        manager = await client.post(
            "/api/ai/chat",
            json={"message": "Show integration health"},
        )
        assert manager.status_code == 200, manager.text
        assert "unknown" not in manager.json()["response"].lower()
        assert "**Slack** (channel): healthy" in manager.json()["response"]


async def test_policy_review_creates_workbench_and_persists_decision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed_data()
    monkeypatch.setenv("COMMAND_CENTER_CALLBACK_SECRET", "test-secret")
    async with await _client() as client:
        run = await _create_run(client, "DN-5046")
        response = await client.patch(
            f"/api/command-center/runs/{run['run_id']}",
            json={
                "status": "running",
                "current_operator": "Portfolio Prioritizer Operator",
            },
        )
        assert response.status_code == 200, response.text
        token = hmac.new(
            b"test-secret",
            run["run_id"].encode(),
            hashlib.sha256,
        ).hexdigest()
        response = await client.post(
            "/api/command-center/policies/evaluate",
            headers={"X-Command-Center-Secret": token},
            json={
                "run_id": run["run_id"],
                "incident_id": "DN-5046",
                "facts": {
                    "severity": "high",
                    "portfolio": {"resource_contested": True},
                    "proposed_action": {
                        "type": "alternate_supplier",
                        "supplier_id": "3055",
                    },
                },
            },
        )
        assert response.status_code == 200, response.text
        evaluation = response.json()
        assert evaluation["effective_decision"] == "review"
        assert evaluation["workbench_item_id"]

        response = await client.get("/api/command-center/workbench?status=open")
        assert response.status_code == 200, response.text
        item = next(
            row
            for row in response.json()
            if row["item_id"] == evaluation["workbench_item_id"]
        )
        response = await client.post(
            f"/api/command-center/workbench/{item['item_id']}/decision",
            json={
                "decision": "modify",
                "reason": "Split supplier capacity across the concurrent incidents",
                "payload": {"allocation": {"DN-5046": 0.7, "DN-5047": 0.3}},
                "expected_version": item["version"],
            },
        )
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "modified"

        response = await client.get(f"/api/command-center/runs/{run['run_id']}")
        assert response.status_code == 200
        assert response.json()["status"] == "needs_review"
        assert "Auto run ID" in response.json()["error"]


async def test_resource_reservations_prevent_over_allocation() -> None:
    async with await _client() as client:
        run = await _create_run(client, "DN-5047")
        resource_id = f"TEST-{run['run_id']}"
        first = await client.post(
            f"/api/command-center/runs/{run['run_id']}/reservations",
            json={
                "incident_id": "DN-5047",
                "resource_type": "supplier_capacity",
                "resource_id": resource_id,
                "quantity": "70",
                "available_quantity": "100",
                "unit": "percent",
                "idempotency_key": f"{run['run_id']}:3055:first",
            },
        )
        assert first.status_code == 201, first.text
        second = await client.post(
            f"/api/command-center/runs/{run['run_id']}/reservations",
            json={
                "incident_id": "DN-5047",
                "resource_type": "supplier_capacity",
                "resource_id": resource_id,
                "quantity": "40",
                "available_quantity": "100",
                "unit": "percent",
                "idempotency_key": f"{run['run_id']}:3055:second",
            },
        )
        assert second.status_code == 409
        assert second.json()["detail"]["message"] == "Insufficient unreserved capacity"


async def test_operator_result_round_trips_the_public_run_id() -> None:
    async with await _client() as client:
        run = await _create_run(client, "DN-OPERATOR-CONTRACT")
        response = await client.post(
            f"/api/command-center/runs/{run['run_id']}/operator-results",
            json={
                "incident_id": "DN-OPERATOR-CONTRACT",
                "run_id": "operator-run-001",
                "operator_name": "Intake & Triage Operator",
                "status": "succeeded",
                "confidence": 0.93,
                "started_at": "2026-08-01T00:00:00Z",
                "completed_at": "2026-08-01T00:00:01Z",
                "facts": {"classification": "supplier disruption"},
                "evidence": [],
            },
        )
        assert response.status_code == 201, response.text
        assert response.json()["run_id"] == "operator-run-001"

        response = await client.get(
            f"/api/command-center/runs/{run['run_id']}/operator-results"
        )
        assert response.status_code == 200, response.text
        assert response.json()[0]["run_id"] == "operator-run-001"


async def test_duplicate_source_trigger_is_an_auditable_no_op() -> None:
    async with await _client() as client:
        payload = {
            "incident_id": "DN-DUPLICATE-CONTRACT",
            "source": "outlook",
            "source_ref": "message-duplicate-contract",
            "input_payload": {"body": "same supplier notice"},
        }
        first = await client.post("/api/command-center/runs", json=payload)
        second = await client.post(
            "/api/command-center/runs",
            json={**payload, "incident_id": "DN-SHOULD-NOT-BE-CREATED"},
        )

        assert first.status_code == 201, first.text
        assert second.status_code == 201, second.text
        assert second.json()["run_id"] == first.json()["run_id"]
        assert second.json()["incident_id"] == "DN-DUPLICATE-CONTRACT"
        assert second.json()["duplicate_trigger_count"] == 1


async def test_operator_envelope_v2_preserves_attempt_and_evidence_values() -> None:
    async with await _client() as client:
        run = await _create_run(client, "DN-ENVELOPE-V2")
        payload = {
            "incident_id": "DN-ENVELOPE-V2",
            "run_id": "legacy-public-run-id",
            "operator_run_id": "OPR-ENVELOPE-V2",
            "operator_name": "Impact Assessor Operator",
            "operator_version": "auto-v7",
            "schema_version": "2.0",
            "subject_type": "cluster",
            "subject_id": "CLU-ENVELOPE-V2",
            "attempt": 2,
            "status": "no_match",
            "confidence": 0.81,
            "started_at": "2026-08-03T00:00:00Z",
            "completed_at": "2026-08-03T00:00:01Z",
            "facts": {"affected_shipments": []},
            "evidence": [
                {
                    "system": "supabase",
                    "entity_type": "shipments",
                    "entity_id": "SH-MISSING",
                    "observed_at": "2026-08-03T00:00:00Z",
                    "fields": ["shipment_id"],
                    "observed_values": {"shipment_id": "SH-MISSING"},
                }
            ],
            "proposed_actions": [],
        }
        response = await client.post(
            f"/api/command-center/runs/{run['run_id']}/operator-results",
            json=payload,
        )

        assert response.status_code == 201, response.text
        result = response.json()
        assert result["run_id"] == "OPR-ENVELOPE-V2"
        assert result["operator_run_id"] == "OPR-ENVELOPE-V2"
        assert result["subject_id"] == "CLU-ENVELOPE-V2"
        assert result["attempt"] == 2
        assert result["status"] == "no_match"
        assert result["evidence"][0]["observed_values"]["shipment_id"] == "SH-MISSING"


async def test_policy_snapshot_gates_an_idempotent_action_ledger(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed_data()
    monkeypatch.setenv("COMMAND_CENTER_CALLBACK_SECRET", "test-secret")
    async with await _client() as client:
        run = await _create_run(client, "DN-ACTION-LEDGER")
        token = hmac.new(
            b"test-secret", run["run_id"].encode(), hashlib.sha256
        ).hexdigest()
        evaluated = await client.post(
            "/api/command-center/policies/evaluate",
            headers={"X-Command-Center-Secret": token},
            json={
                "run_id": run["run_id"],
                "incident_id": "DN-ACTION-LEDGER",
                "facts": {
                    "severity": "low",
                    "proposed_action": {
                        "id": "OPTION-SAFE",
                        "type": "wait",
                    },
                },
            },
        )
        assert evaluated.status_code == 200, evaluated.text
        body = evaluated.json()
        assert body["effective_decision"] == "allow"
        assert len({item["input_hash"] for item in body["evaluations"]}) == 1
        evaluation_ids = [item["evaluation_id"] for item in body["evaluations"]]

        action_payload = {
            "incident_id": "DN-ACTION-LEDGER",
            "candidate_action_id": "OPTION-SAFE",
            "action_type": "supplier_notification",
            "external_system": "outlook",
            "target": "supplier-3020",
            "request_payload": {"template": "recovery-plan", "option": "OPTION-SAFE"},
            "policy_evaluation_ids": evaluation_ids,
        }
        mismatched = await client.post(
            f"/api/command-center/runs/{run['run_id']}/actions",
            json={**action_payload, "candidate_action_id": "OPTION-UNREVIEWED"},
        )
        assert mismatched.status_code == 409, mismatched.text

        first = await client.post(
            f"/api/command-center/runs/{run['run_id']}/actions",
            json=action_payload,
        )
        replay = await client.post(
            f"/api/command-center/runs/{run['run_id']}/actions",
            json=action_payload,
        )
        assert first.status_code == 201, first.text
        assert replay.status_code == 201, replay.text
        assert replay.json()["action_id"] == first.json()["action_id"]
        assert replay.json()["idempotency_key"] == first.json()["idempotency_key"]

        completed = await client.post(
            f"/api/command-center/actions/{first.json()['action_id']}/complete",
            json={
                "status": "completed",
                "external_ref": "MSG-123",
                "verification": {"delivered": True},
            },
        )
        assert completed.status_code == 200, completed.text
        assert completed.json()["status"] == "completed"
        assert completed.json()["external_ref"] == "MSG-123"


async def test_workbench_escalation_does_not_require_auto_resume(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed_data()
    monkeypatch.setenv("COMMAND_CENTER_CALLBACK_SECRET", "test-secret")
    async with await _client() as client:
        run = await _create_run(client, "DN-ESCALATE")
        running = await client.patch(
            f"/api/command-center/runs/{run['run_id']}",
            json={"status": "running"},
        )
        assert running.status_code == 200, running.text
        token = hmac.new(
            b"test-secret", run["run_id"].encode(), hashlib.sha256
        ).hexdigest()
        evaluated = await client.post(
            "/api/command-center/policies/evaluate",
            headers={"X-Command-Center-Secret": token},
            json={
                "run_id": run["run_id"],
                "incident_id": "DN-ESCALATE",
                "facts": {
                    "severity": "high",
                    "portfolio": {"resource_contested": True},
                    "proposed_action": {"type": "alternate_supplier"},
                },
            },
        )
        item_id = evaluated.json()["workbench_item_id"]
        items = await client.get("/api/command-center/workbench?status=open")
        item = next(row for row in items.json() if row["item_id"] == item_id)
        escalated = await client.post(
            f"/api/command-center/workbench/{item_id}/decision",
            json={
                "decision": "escalate",
                "reason": "Executive authorization is required for shared capacity",
                "expected_version": item["version"],
            },
        )

        assert escalated.status_code == 200, escalated.text
        assert escalated.json()["status"] == "escalated"
        updated_run = await client.get(f"/api/command-center/runs/{run['run_id']}")
        assert updated_run.json()["status"] == "needs_review"
        assert updated_run.json()["error"] is None


async def test_negative_cost_avoided_is_preserved_as_an_outcome() -> None:
    async with await _client() as client:
        run = await _create_run(client, "DN-NEGATIVE-OUTCOME")
        response = await client.patch(
            f"/api/command-center/runs/{run['run_id']}",
            json={"status": "running", "cost_avoided_myr": "-1250.50"},
        )

        assert response.status_code == 200, response.text
        assert response.json()["cost_avoided_myr"] == "-1250.50"


async def test_run_sync_imports_auto_activities_idempotently(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    auto_run_id = f"AUTO-SYNC-{uuid4().hex}"

    class FakeSupervityClient:
        async def status(self, run_id: str) -> dict:
            assert run_id == auto_run_id
            return {
                "workflowRun": {
                    "id": run_id,
                    "status": "waiting",
                },
                # The live status API returns activityRuns beside workflowRun.
                "activityRuns": [
                    {
                        "id": "ACT-IMPACT-1",
                        "stepName": "Impact Assessor",
                        "status": "completed",
                        "attempt": 1,
                        "createdAt": "2026-08-07T01:00:00Z",
                        "updatedAt": "2026-08-07T01:01:00Z",
                        "outputs": {
                            "facts": {
                                "cost_at_risk_myr": 125000,
                                "api_token": "must-not-persist",
                            },
                            "confidence": 0.92,
                            "proposedActions": [{"type": "assess"}],
                        },
                    }
                ],
            }

    fake = FakeSupervityClient()
    monkeypatch.setattr(
        command_center_router.SupervityClient,
        "from_environment",
        classmethod(lambda cls: fake),
    )
    async with await _client() as client:
        run = await _create_run(client, f"DN-AUTO-SYNC-{uuid4().hex}")
        running = await client.patch(
            f"/api/command-center/runs/{run['run_id']}",
            json={"status": "running", "auto_run_id": auto_run_id},
        )
        assert running.status_code == 200, running.text

        first = await client.post(
            f"/api/command-center/runs/{run['run_id']}/sync-supervity"
        )
        second = await client.post(
            f"/api/command-center/runs/{run['run_id']}/sync-supervity"
        )

        assert first.status_code == 200, first.text
        assert first.json()["operator_results_added"] == 1
        assert first.json()["local_status"] == "awaiting_approval"
        assert second.status_code == 200, second.text
        assert second.json()["operator_results_added"] == 0
        results = await client.get(
            f"/api/command-center/runs/{run['run_id']}/operator-results"
        )
        assert len(results.json()) == 1
        assert results.json()[0]["operator_name"] == "Impact Assessor Operator"
        assert results.json()[0]["facts"]["api_token"] == "[redacted]"


async def test_user_form_sync_and_decision_resume_same_auto_activity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("COMMAND_CENTER_CALLBACK_SECRET", "test-secret")
    submissions: list[dict] = []
    suffix = uuid4().hex
    form_id = f"FORM-{suffix}"
    auto_run_id = f"AUTO-FORM-{suffix}"
    activity_run_id = f"ACT-FORM-{suffix}"
    incident_id = f"DN-AUTO-FORM-{suffix}"

    class FakeSupervityClient:
        def __init__(self) -> None:
            self.form_status = "pending"

        async def list_user_forms(self, **kwargs) -> list[dict]:
            assert kwargs == {"page": 1, "limit": 100}
            return [
                {
                    "id": form_id,
                    "workflowRunId": auto_run_id,
                    "activityRunId": activity_run_id,
                    "workflowName": "Exception Commander",
                    "workflowStepName": "Commander approval",
                    "workflowStepDescription": "Approve the recovery plan",
                    "status": self.form_status,
                    "createdAt": "2026-08-07T02:00:00Z",
                    "updatedAt": "2026-08-07T02:05:00Z",
                }
            ]

        async def get_user_form(self, requested_form_id: str) -> dict:
            assert requested_form_id == form_id
            return {"html": f"""
                <div class="ag-card">
                  <h2 class="ag-h2">Recovery Plan Review</h2>
                  <p class="ag-body">Approve the recovery plan</p>
                  <div class="ag-card">
                    <span class="ag-muted">Incident ID</span>
                    <p class="ag-body">{incident_id}</p>
                  </div>
                  <label for="reviewer-action">Reviewer Action</label>
                  <select id="reviewer-action" name="Reviewer Action" required>
                    <option value="Approve">Approve</option>
                    <option value="Reject">Reject</option>
                  </select>
                </div>
                """}

        async def submit_user_form(self, **kwargs) -> str:
            submissions.append(kwargs)
            self.form_status = (
                "rejected" if kwargs["status"] == "reject" else "approved"
            )
            return "Form Submitted Successfully"

        async def status(self, requested_run_id: str) -> dict:
            assert requested_run_id == auto_run_id
            submitted = bool(submissions)
            return {
                "workflowRun": {
                    "id": auto_run_id,
                    "status": "running",
                    "updatedAt": "2026-08-07T02:05:00Z",
                },
                "activityRuns": [
                    {
                        "id": activity_run_id,
                        "status": "completed" if submitted else "waiting",
                        "userForm": {
                            "approved": (
                                self.form_status == "approved" if submitted else None
                            ),
                            "values": submissions[-1]["fields"] if submitted else {},
                            "reviewedAt": (
                                "2026-08-07T02:05:00Z" if submitted else None
                            ),
                        },
                    }
                ],
            }

    fake = FakeSupervityClient()
    monkeypatch.setattr(
        command_center_router.SupervityClient,
        "from_environment",
        classmethod(lambda cls: fake),
    )
    async with await _client() as client:
        run = await _create_run(client, incident_id)
        running = await client.patch(
            f"/api/command-center/runs/{run['run_id']}",
            json={"status": "running", "auto_run_id": auto_run_id},
        )
        assert running.status_code == 200, running.text

        synced = await client.post("/api/command-center/workbench/sync-supervity")
        assert synced.status_code == 200, synced.text
        assert synced.json()["items_created"] == 1
        items = await client.get("/api/command-center/workbench?status=open")
        item = next(row for row in items.json() if row["supervity_form_id"] == form_id)
        token = hmac.new(
            b"test-secret", run["run_id"].encode(), hashlib.sha256
        ).hexdigest()
        receipt = await client.post(
            "/api/command-center/supervity/notification",
            headers={"X-Command-Center-Secret": token},
            json={
                "command_center_run_id": run["run_id"],
                "event_id": "EVT-FORM-1-REVIEW",
                "notification_type": "review_required",
                "status": "delivered",
                "channel_id": "C-APPROVALS",
                "message_ts": "1723090000.000100",
                "workbench_item_id": item["item_id"],
            },
        )
        assert receipt.status_code == 201, receipt.text
        decided = await client.post(
            f"/api/command-center/workbench/{item['item_id']}/decision",
            json={
                "decision": "approve",
                "reason": "Evidence supports the proposed recovery plan",
                "expected_version": item["version"],
            },
        )

        assert decided.status_code == 200, decided.text
        assert decided.json()["supervity_form_status"] == "approved"
        assert submissions[0]["activity_run_id"] == activity_run_id
        assert submissions[0]["status"] == "approve"
        assert submissions[0]["fields"]["decision"] == "approve"
        assert submissions[0]["fields"]["decision_source"] == "command_center"
        assert submissions[0]["fields"]["command_center_run_id"] == run["run_id"]
        assert submissions[0]["fields"]["slack_channel_id"] == "C-APPROVALS"
        assert submissions[0]["fields"]["slack_message_ts"] == "1723090000.000100"
        updated_run = await client.get(f"/api/command-center/runs/{run['run_id']}")
        assert updated_run.json()["status"] == "running"


async def test_user_form_sync_imports_unmatched_run_and_parses_form_without_submitting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    submissions: list[dict] = []
    suffix = uuid4().hex
    form_id = f"FORM-UNMATCHED-{suffix}"
    auto_run_id = f"AUTO-UNMATCHED-{suffix}"
    activity_run_id = f"ACT-UNMATCHED-{suffix}"
    incident_id = f"INC-LIVE-{suffix}"

    class FakeSupervityClient:
        async def list_user_forms(self, **kwargs) -> list[dict]:
            assert kwargs == {"page": 1, "limit": 100}
            return [
                {
                    "id": form_id,
                    "workflowId": "WORKFLOW-1",
                    "workflowRunId": auto_run_id,
                    "activityRunId": activity_run_id,
                    "workflowName": "Exception Commander",
                    "workflowStepName": "Human Review",
                    "status": "pending",
                    "createdAt": "2026-08-08T15:04:41Z",
                }
            ]

        async def get_user_form(self, requested_form_id: str) -> dict:
            assert requested_form_id == form_id
            return {"html": f"""
                <div class="ag-card">
                  <h2 class="ag-h2">Recovery Plan Review</h2>
                  <p class="ag-body">Review the grounded recommendation.</p>
                  <div class="ag-card">
                    <span class="ag-muted">Incident ID</span>
                    <p class="ag-body">{incident_id}</p>
                  </div>
                  <div class="ag-card">
                    <span class="ag-muted">Severity</span>
                    <p class="ag-body">MEDIUM</p>
                  </div>
                  <div class="ag-card">
                    <span class="ag-muted">Guard status</span>
                    <pre class="ag-body">NEEDS_REVIEW</pre>
                  </div>
                  <label for="reviewer-action">Reviewer Action</label>
                  <select id="reviewer-action" name="Reviewer Action" required>
                    <option value="">Select an action</option>
                    <option value="Approve">Approve</option>
                    <option value="Request replan">Request replan</option>
                  </select>
                  <label for="approved-by">Approved By</label>
                  <input id="approved-by" name="Approved By" required />
                </div>
                """}

        async def status(self, requested_run_id: str) -> dict:
            assert requested_run_id == auto_run_id
            return {
                "workflowRun": {"id": auto_run_id, "status": "running"},
                "activityRuns": [
                    {
                        "id": activity_run_id,
                        "status": "waiting",
                        "userForm": {
                            "approved": None,
                            "values": {},
                            "reviewedAt": None,
                        },
                    }
                ],
            }

        async def submit_user_form(self, **kwargs) -> str:
            submissions.append(kwargs)
            raise AssertionError("Sync must never submit a pending form")

    monkeypatch.setattr(
        command_center_router.SupervityClient,
        "from_environment",
        classmethod(lambda cls: FakeSupervityClient()),
    )

    async with await _client() as client:
        synced = await client.post("/api/command-center/workbench/sync-supervity")
        assert synced.status_code == 200, synced.text
        assert synced.json() == {
            "forms_seen": 1,
            "pending_forms": 1,
            "approved_forms": 0,
            "modified_forms": 0,
            "rejected_forms": 0,
            "expired_forms": 0,
            "other_forms": 0,
            "matched_runs": 1,
            "items_created": 1,
            "items_updated": 0,
            "forms_skipped": 0,
        }

        items = await client.get("/api/command-center/workbench?status=open")
        item = next(row for row in items.json() if row["supervity_form_id"] == form_id)
        assert item["incident_id"] == incident_id
        assert item["title"] == "Recovery Plan Review"
        assert item["severity"] == "medium"
        assert item["proposed_action"]["user_form"]["context"] == [
            {"label": "Incident ID", "value": incident_id},
            {"label": "Severity", "value": "MEDIUM"},
            {"label": "Guard status", "value": "NEEDS_REVIEW"},
        ]
        review_summary = item["proposed_action"]["user_form"]["review_summary"]
        assert review_summary["incident_id"] == incident_id
        assert review_summary["severity"] == "medium"
        assert review_summary["requires_human_review"] is True
        assert review_summary["recommendation"] is None
        fields = item["proposed_action"]["user_form"]["fields"]
        assert fields[0]["name"] == "Reviewer Action"
        assert fields[0]["options"][2]["value"] == "Request replan"
        assert fields[1]["required"] is True
        assert submissions == []


async def test_user_form_severity_defaults_to_low() -> None:
    assert command_center_router._parsed_form_severity({"context": []}).value == "low"
    assert (
        command_center_router._parsed_form_severity(
            {"context": [{"label": "Severity", "value": "not-a-severity"}]}
        ).value
        == "low"
    )


@pytest.mark.parametrize(
    (
        "remote_status",
        "approved",
        "reviewer_action",
        "expected_status",
        "expected_decision",
    ),
    [
        ("rejected", False, "", "rejected", "reject"),
        ("approved", True, "Reject", "rejected", "reject"),
        ("approved", True, "Request replan", "modified", "modify"),
    ],
)
async def test_user_form_sync_reconciles_terminal_api_state(
    monkeypatch: pytest.MonkeyPatch,
    remote_status: str,
    approved: bool,
    reviewer_action: str,
    expected_status: str,
    expected_decision: str,
) -> None:
    suffix = uuid4().hex
    form_id = f"FORM-RECONCILE-{suffix}"
    auto_run_id = f"AUTO-RECONCILE-{suffix}"
    activity_run_id = f"ACT-RECONCILE-{suffix}"
    incident_id = f"INC-RECONCILE-{suffix}"
    state = {"form_status": "pending"}

    class FakeSupervityClient:
        async def list_user_forms(self, **kwargs) -> list[dict]:
            assert kwargs == {"page": 1, "limit": 100}
            return [
                {
                    "id": form_id,
                    "workflowRunId": auto_run_id,
                    "activityRunId": activity_run_id,
                    "workflowName": "Exception Commander",
                    "workflowStepName": "Human Review",
                    "status": state["form_status"],
                    "createdAt": "2026-08-08T15:00:00Z",
                    "updatedAt": "2026-08-08T15:10:00Z",
                }
            ]

        async def get_user_form(self, requested_form_id: str) -> dict:
            assert requested_form_id == form_id
            return {"html": f"""
                <h2>Recovery Plan Review</h2>
                <div class="ag-card">
                  <span class="ag-muted">Incident ID</span>
                  <p class="ag-body">{incident_id}</p>
                </div>
                <label for="reviewer-action">Reviewer Action</label>
                <select id="reviewer-action" name="Reviewer Action" required>
                  <option value="Approve">Approve</option>
                  <option value="Request replan">Request replan</option>
                  <option value="Reject">Reject</option>
                </select>
                """}

        async def status(self, requested_run_id: str) -> dict:
            assert requested_run_id == auto_run_id
            is_terminal = state["form_status"] != "pending"
            return {
                "workflowRun": {
                    "id": auto_run_id,
                    "status": "completed" if is_terminal else "running",
                    "updatedAt": "2026-08-08T15:10:01Z",
                },
                "activityRuns": [
                    {
                        "id": activity_run_id,
                        "status": "completed" if is_terminal else "waiting",
                        "userForm": {
                            "approved": approved if is_terminal else None,
                            "values": (
                                {
                                    "Reviewer Action": reviewer_action,
                                    "Approved By": "API Reviewer",
                                    "Decision Rationale": "Resolved in Supervity",
                                }
                                if is_terminal
                                else {}
                            ),
                            "reviewedAt": (
                                "2026-08-08T15:10:00Z" if is_terminal else None
                            ),
                        },
                    }
                ],
            }

        async def submit_user_form(self, **kwargs) -> str:
            raise AssertionError("Reconciliation must not submit a form")

    monkeypatch.setattr(
        command_center_router.SupervityClient,
        "from_environment",
        classmethod(lambda cls: FakeSupervityClient()),
    )

    async with await _client() as client:
        first_sync = await client.post("/api/command-center/workbench/sync-supervity")
        assert first_sync.status_code == 200, first_sync.text
        assert first_sync.json()["items_created"] == 1

        state["form_status"] = remote_status
        terminal_sync = await client.post(
            "/api/command-center/workbench/sync-supervity"
        )
        assert terminal_sync.status_code == 200, terminal_sync.text
        assert terminal_sync.json()["items_updated"] == 1
        semantic_count = (
            "modified_forms" if expected_status == "modified" else "rejected_forms"
        )
        assert terminal_sync.json()[semantic_count] == 1
        if expected_status == "rejected":
            assert terminal_sync.json()["approved_forms"] == 0

        items = await client.get("/api/command-center/workbench")
        item = next(row for row in items.json() if row["supervity_form_id"] == form_id)
        assert item["status"] == expected_status
        assert item["decision"] == expected_decision
        assert item["decision_by"] == "API Reviewer"
        assert item["decision_reason"] == "Resolved in Supervity"
        assert item["decision_source"] == "supervity_api"
        assert item["supervity_form_status"] == remote_status
        run = await client.get(f"/api/command-center/runs/{item['run_id']}")
        assert run.json()["status"] == "completed"


async def test_user_form_sync_expires_open_item_missing_from_api_inventory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    suffix = uuid4().hex
    form_id = f"FORM-MISSING-{suffix}"
    auto_run_id = f"AUTO-MISSING-{suffix}"
    activity_run_id = f"ACT-MISSING-{suffix}"
    state = {"visible": True}

    class FakeSupervityClient:
        async def list_user_forms(self, **kwargs) -> list[dict]:
            assert kwargs == {"page": 1, "limit": 100}
            if not state["visible"]:
                return []
            return [
                {
                    "id": form_id,
                    "workflowRunId": auto_run_id,
                    "activityRunId": activity_run_id,
                    "workflowName": "Exception Commander",
                    "workflowStepName": "Human Review",
                    "status": "pending",
                    "createdAt": "2026-08-08T15:00:00Z",
                }
            ]

        async def get_user_form(self, requested_form_id: str) -> dict:
            assert requested_form_id == form_id
            return {"html": "<h2>Recovery Plan Review</h2>"}

        async def status(self, requested_run_id: str) -> dict:
            assert requested_run_id == auto_run_id
            return {
                "workflowRun": {"id": auto_run_id, "status": "running"},
                "activityRuns": [
                    {
                        "id": activity_run_id,
                        "status": "waiting",
                        "userForm": {
                            "approved": None,
                            "values": {},
                            "reviewedAt": None,
                        },
                    }
                ],
            }

    monkeypatch.setattr(
        command_center_router.SupervityClient,
        "from_environment",
        classmethod(lambda cls: FakeSupervityClient()),
    )

    async with await _client() as client:
        first = await client.post("/api/command-center/workbench/sync-supervity")
        assert first.status_code == 200, first.text
        assert first.json()["items_created"] == 1

        state["visible"] = False
        second = await client.post("/api/command-center/workbench/sync-supervity")
        assert second.status_code == 200, second.text
        assert second.json()["items_updated"] == 1

        items = await client.get("/api/command-center/workbench")
        item = next(row for row in items.json() if row["supervity_form_id"] == form_id)
        assert item["status"] == "expired"
        assert item["supervity_form_status"] == "expired"
        assert "no longer returns this form" in item["decision_reason"]


async def test_user_form_sync_expires_pending_form_on_cancelled_workflow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    suffix = uuid4().hex
    form_id = f"FORM-CANCELLED-{suffix}"
    auto_run_id = f"AUTO-CANCELLED-{suffix}"
    activity_run_id = f"ACT-CANCELLED-{suffix}"
    state = {"cancelled": False}

    class FakeSupervityClient:
        async def list_user_forms(self, **kwargs) -> list[dict]:
            assert kwargs == {"page": 1, "limit": 100}
            return [
                {
                    "id": form_id,
                    "workflowRunId": auto_run_id,
                    "activityRunId": activity_run_id,
                    "workflowName": "Exception Commander",
                    "workflowStepName": "Human Review",
                    "status": "pending",
                    "createdAt": "2026-08-08T15:00:00Z",
                }
            ]

        async def get_user_form(self, requested_form_id: str) -> dict:
            assert requested_form_id == form_id
            return {"html": "<h2>Recovery Plan Review</h2>"}

        async def status(self, requested_run_id: str) -> dict:
            assert requested_run_id == auto_run_id
            return {
                "workflowRun": {
                    "id": auto_run_id,
                    "status": "cancelled" if state["cancelled"] else "running",
                    "updatedAt": "2026-08-08T15:10:00Z",
                },
                "activityRuns": [
                    {
                        "id": activity_run_id,
                        "status": "waiting",
                        "userForm": {
                            "approved": None,
                            "values": {},
                            "reviewedAt": None,
                        },
                    }
                ],
            }

    monkeypatch.setattr(
        command_center_router.SupervityClient,
        "from_environment",
        classmethod(lambda cls: FakeSupervityClient()),
    )

    async with await _client() as client:
        first = await client.post("/api/command-center/workbench/sync-supervity")
        assert first.status_code == 200, first.text
        assert first.json()["pending_forms"] == 1

        state["cancelled"] = True
        second = await client.post("/api/command-center/workbench/sync-supervity")
        assert second.status_code == 200, second.text
        assert second.json()["pending_forms"] == 0
        assert second.json()["expired_forms"] == 1

        items = await client.get("/api/command-center/workbench")
        item = next(row for row in items.json() if row["supervity_form_id"] == form_id)
        assert item["status"] == "expired"
        run = await client.get(f"/api/command-center/runs/{item['run_id']}")
        assert run.json()["status"] == "cancelled"


async def test_slack_delivery_receipt_is_idempotent_and_updates_health(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("COMMAND_CENTER_CALLBACK_SECRET", "test-secret")
    async with await _client() as client:
        run = await _create_run(client, "DN-SLACK-DELIVERY")
        token = hmac.new(
            b"test-secret", run["run_id"].encode(), hashlib.sha256
        ).hexdigest()
        headers = {"X-Command-Center-Secret": token}
        payload = {
            "command_center_run_id": run["run_id"],
            "event_id": "EVT-SLACK-DELIVERY-1",
            "notification_type": "review_required",
            "status": "delivered",
            "channel_id": "C-APPROVALS",
            "message_ts": "1723091000.000100",
            "occurred_at": "2026-08-08T08:00:00Z",
            "payload": {"presentation": "approval_card_v1"},
        }

        first = await client.post(
            "/api/command-center/supervity/notification",
            headers=headers,
            json=payload,
        )
        replay = await client.post(
            "/api/command-center/supervity/notification",
            headers=headers,
            json=payload,
        )
        regressed = await client.post(
            "/api/command-center/supervity/notification",
            headers=headers,
            json={**payload, "status": "failed", "error": "late retry failed"},
        )

        assert first.status_code == 201, first.text
        assert replay.status_code == 201, replay.text
        assert regressed.status_code == 201, regressed.text
        assert replay.json()["notification_id"] == first.json()["notification_id"]
        assert regressed.json()["status"] == "delivered"

        notifications = await client.get(
            f"/api/command-center/notifications?run_id={run['run_id']}"
        )
        assert notifications.status_code == 200, notifications.text
        assert len(notifications.json()) == 1

        integrations = await client.get("/api/command-center/integrations")
        slack = next(
            item
            for item in integrations.json()
            if item["integration_id"] == "slack-via-supervity"
        )
        assert slack["status"] == "healthy"
        assert slack["records_seen"] >= 1
        assert slack["metadata"]["managed_by"] == "supervity"
        assert slack["metadata"]["last_channel_id"] == "C-APPROVALS"


async def test_supervity_chat_receipt_supports_management_insight(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("COMMAND_CENTER_CALLBACK_SECRET", "test-secret")
    async with await _client() as client:
        run = await _create_run(client, "DN-CHAT-INSIGHT")
        token = hmac.new(
            b"test-secret", run["run_id"].encode(), hashlib.sha256
        ).hexdigest()
        receipt = await client.post(
            "/api/command-center/supervity/notification",
            headers={"X-Command-Center-Secret": token},
            json={
                "command_center_run_id": run["run_id"],
                "event_id": "EVT-CHAT-INSIGHT-1",
                "notification_type": "management_insight",
                "status": "delivered",
                "provider": "supervity_chat",
                "route_key": "originating_chat",
                "destination_id": "CHAT-JOB-1",
                "conversation_id": "CHAT-JOB-1",
                "message_id": "CHAT-MESSAGE-1",
                "thread_id": "CHAT-THREAD-1",
                "payload": {"presentation": "management_insight_v1"},
            },
        )

        assert receipt.status_code == 201, receipt.text
        body = receipt.json()
        assert body["provider"] == "supervity_chat"
        assert body["notification_type"] == "management_insight"
        assert body["destination"] == "CHAT-JOB-1"
        assert body["external_ref"] == "CHAT-MESSAGE-1"
        assert body["thread_ref"] == "CHAT-THREAD-1"
        assert body["payload"]["route_key"] == "originating_chat"
        assert body["payload"]["conversation_id"] == "CHAT-JOB-1"

        integrations = await client.get("/api/command-center/integrations")
        chat = next(
            item
            for item in integrations.json()
            if item["integration_id"] == "supervity-chat"
        )
        assert chat["status"] == "healthy"
        assert chat["metadata"]["transport"] == "supervity_chat"
        assert chat["metadata"]["last_route_key"] == "originating_chat"
        assert chat["metadata"]["last_destination_id"] == "CHAT-JOB-1"


async def test_slack_decision_is_idempotent_and_first_channel_wins(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("COMMAND_CENTER_CALLBACK_SECRET", "test-secret")
    async with await _client() as client:
        run = await _create_run(client, "DN-SLACK-DECISION")
        running = await client.patch(
            f"/api/command-center/runs/{run['run_id']}",
            json={"status": "running", "auto_run_id": "AUTO-SLACK-DECISION"},
        )
        assert running.status_code == 200, running.text
        waiting = await client.patch(
            f"/api/command-center/runs/{run['run_id']}",
            json={"status": "awaiting_approval"},
        )
        assert waiting.status_code == 200, waiting.text
        created = await client.post(
            "/api/command-center/workbench",
            json={
                "run_id": run["run_id"],
                "incident_id": run["incident_id"],
                "title": "Approve recovery route",
                "summary": "A human decision is required",
                "severity": "high",
                "proposed_action": {"type": "reroute"},
            },
        )
        assert created.status_code == 201, created.text
        item = created.json()

        token = hmac.new(
            b"test-secret", run["run_id"].encode(), hashlib.sha256
        ).hexdigest()
        headers = {"X-Command-Center-Secret": token}
        decision = {
            "command_center_run_id": run["run_id"],
            "workbench_item_id": item["item_id"],
            "decision": "approve",
            "reason": "Approved from the familiar Slack workflow",
            "decision_by": "manager@example.com",
            "decision_source": "slack",
            "external_interaction_id": "SLACK-ACTION-DECISION-1",
        }
        first = await client.post(
            "/api/command-center/supervity/decision",
            headers=headers,
            json=decision,
        )
        replay = await client.post(
            "/api/command-center/supervity/decision",
            headers=headers,
            json=decision,
        )
        competing_external = await client.post(
            "/api/command-center/supervity/decision",
            headers=headers,
            json={
                **decision,
                "decision": "reject",
                "external_interaction_id": "SUPERVITY-ACTION-DECISION-2",
            },
        )
        competing_platform = await client.post(
            f"/api/command-center/workbench/{item['item_id']}/decision",
            json={
                "decision": "reject",
                "reason": "Competing platform decision",
                "expected_version": item["version"],
            },
        )

        assert first.status_code == 200, first.text
        assert first.json()["decision_source"] == "slack"
        assert first.json()["decision_external_ref"] == "SLACK-ACTION-DECISION-1"
        assert replay.status_code == 200, replay.text
        assert replay.json()["version"] == first.json()["version"]
        assert competing_external.status_code == 409, competing_external.text
        assert competing_platform.status_code == 409, competing_platform.text
        updated_run = await client.get(f"/api/command-center/runs/{run['run_id']}")
        assert updated_run.json()["status"] == "executing"


async def test_completed_and_failed_runs_have_correlated_slack_receipts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("COMMAND_CENTER_CALLBACK_SECRET", "test-secret")
    async with await _client() as client:
        completed_run = await _create_run(client, "DN-SLACK-COMPLETED")
        completed_token = hmac.new(
            b"test-secret", completed_run["run_id"].encode(), hashlib.sha256
        ).hexdigest()
        completed_headers = {"X-Command-Center-Secret": completed_token}
        completed = await client.post(
            "/api/command-center/supervity/callback",
            headers=completed_headers,
            json={
                "command_center_run_id": completed_run["run_id"],
                "status": "completed",
                "output_payload": {"outcome": "supplier confirmed"},
            },
        )
        assert completed.status_code == 200, completed.text
        completion_receipt = await client.post(
            "/api/command-center/supervity/notification",
            headers=completed_headers,
            json={
                "command_center_run_id": completed_run["run_id"],
                "event_id": "EVT-SLACK-COMPLETED-1",
                "notification_type": "workflow_completed",
                "status": "updated",
                "channel_id": "C-APPROVALS",
                "message_ts": "1723092000.000100",
            },
        )
        assert completion_receipt.status_code == 201, completion_receipt.text
        assert completion_receipt.json()["status"] == "updated"

        failed_run = await _create_run(client, "DN-SLACK-FAILED")
        failed_token = hmac.new(
            b"test-secret", failed_run["run_id"].encode(), hashlib.sha256
        ).hexdigest()
        failed_headers = {"X-Command-Center-Secret": failed_token}
        failed = await client.post(
            "/api/command-center/supervity/callback",
            headers=failed_headers,
            json={
                "command_center_run_id": failed_run["run_id"],
                "status": "failed",
                "error": "Executor could not verify the external update",
            },
        )
        assert failed.status_code == 200, failed.text
        failed_receipt = await client.post(
            "/api/command-center/supervity/notification",
            headers=failed_headers,
            json={
                "command_center_run_id": failed_run["run_id"],
                "event_id": "EVT-SLACK-FAILED-1",
                "notification_type": "workflow_failed",
                "status": "failed",
                "channel_id": "C-APPROVALS",
                "message_ts": "1723093000.000100",
                "error": "Slack update failed",
            },
        )
        assert failed_receipt.status_code == 201, failed_receipt.text
        assert failed_receipt.json()["status"] == "failed"

        integrations = await client.get("/api/command-center/integrations")
        slack = next(
            item
            for item in integrations.json()
            if item["integration_id"] == "slack-via-supervity"
        )
        assert slack["status"] == "degraded"
        assert slack["last_error"] == "Slack update failed"


async def test_concurrent_external_decisions_resolve_exactly_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("COMMAND_CENTER_CALLBACK_SECRET", "test-secret")
    async with await _client() as client:
        run = await _create_run(client, "DN-CONCURRENT-DECISION")
        running = await client.patch(
            f"/api/command-center/runs/{run['run_id']}",
            json={"status": "running", "auto_run_id": "AUTO-CONCURRENT-DECISION"},
        )
        assert running.status_code == 200, running.text
        waiting = await client.patch(
            f"/api/command-center/runs/{run['run_id']}",
            json={"status": "awaiting_approval"},
        )
        assert waiting.status_code == 200, waiting.text
        created = await client.post(
            "/api/command-center/workbench",
            json={
                "run_id": run["run_id"],
                "incident_id": run["incident_id"],
                "title": "Concurrent decision guard",
                "summary": "Only the first signed decision may resolve this item",
                "severity": "high",
                "proposed_action": {"type": "alternate_supplier"},
            },
        )
        assert created.status_code == 201, created.text
        item = created.json()

        token = hmac.new(
            b"test-secret", run["run_id"].encode(), hashlib.sha256
        ).hexdigest()
        headers = {"X-Command-Center-Secret": token}
        base = {
            "command_center_run_id": run["run_id"],
            "workbench_item_id": item["item_id"],
            "reason": "Concurrent manager response",
            "decision_by": "manager@example.com",
            "decision_source": "slack",
        }
        approve, reject = await asyncio.gather(
            client.post(
                "/api/command-center/supervity/decision",
                headers=headers,
                json={
                    **base,
                    "decision": "approve",
                    "external_interaction_id": "CONCURRENT-APPROVE-1",
                },
            ),
            client.post(
                "/api/command-center/supervity/decision",
                headers=headers,
                json={
                    **base,
                    "decision": "reject",
                    "external_interaction_id": "CONCURRENT-REJECT-1",
                },
            ),
        )

        assert sorted((approve.status_code, reject.status_code)) == [200, 409]
        winner = approve if approve.status_code == 200 else reject
        winner_decision = winner.json()["decision"]
        items = await client.get("/api/command-center/workbench")
        resolved = next(
            row for row in items.json() if row["item_id"] == item["item_id"]
        )
        assert resolved["version"] == item["version"] + 1
        assert resolved["decision"] == winner_decision
        assert resolved["decision_external_ref"] in {
            "CONCURRENT-APPROVE-1",
            "CONCURRENT-REJECT-1",
        }
        updated_run = await client.get(f"/api/command-center/runs/{run['run_id']}")
        expected_status = "executing" if winner_decision == "approve" else "cancelled"
        assert updated_run.json()["status"] == expected_status

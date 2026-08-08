"""Backend-only adapter for the Supervity Auto Workflow API.

The public Workflow API contract can be supplied entirely through environment
variables. No API key or endpoint is exposed to the Next.js client.
"""

from __future__ import annotations

import json
import os
import re
from collections import deque
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Mapping
from urllib.parse import quote, urlsplit, urlunsplit

import httpx


class SupervityConfigurationError(RuntimeError):
    pass


class SupervityAPIError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class SupervityRunHandle:
    run_id: str
    raw_response: Mapping[str, Any]
    status: str | None = None
    success: bool | None = None
    message: str | None = None


@dataclass(frozen=True, slots=True)
class SupervitySettings:
    trigger_url: str
    api_key: str
    orchestrator_id: str | None
    status_url_template: str | None
    resume_url_template: str | None
    source_header: str
    user_timezone: str
    timeout_seconds: float
    api_base_url: str = "https://auto-workflow-api.supervity.ai/api/v1"
    integration_api_base_url: str = "https://auto-integration-api.supervity.ai/api/v1"
    active_org: str | None = None
    include_callback_inputs: bool = False

    @classmethod
    def from_environment(cls) -> SupervitySettings:
        trigger_url = os.getenv("SUPERVITY_WORKFLOW_TRIGGER_URL", "").strip()
        api_key = os.getenv("SUPERVITY_WORKFLOW_API_KEY", "").strip()
        orchestrator_id = os.getenv("SUPERVITY_ORCHESTRATOR_ID", "").strip()
        if not trigger_url or not api_key or not orchestrator_id:
            missing = []
            if not trigger_url:
                missing.append("SUPERVITY_WORKFLOW_TRIGGER_URL")
            if not api_key:
                missing.append("SUPERVITY_WORKFLOW_API_KEY")
            if not orchestrator_id:
                missing.append("SUPERVITY_ORCHESTRATOR_ID")
            raise SupervityConfigurationError(
                f"Missing backend configuration: {', '.join(missing)}"
            )
        return cls(
            trigger_url=trigger_url,
            api_key=api_key,
            orchestrator_id=orchestrator_id,
            status_url_template=os.getenv("SUPERVITY_WORKFLOW_STATUS_URL_TEMPLATE")
            or None,
            resume_url_template=os.getenv("SUPERVITY_WORKFLOW_RESUME_URL_TEMPLATE")
            or None,
            source_header=os.getenv("SUPERVITY_WORKFLOW_SOURCE", "external"),
            user_timezone=os.getenv("SUPERVITY_USER_TIMEZONE", "Asia/Kuala_Lumpur"),
            timeout_seconds=float(
                os.getenv("SUPERVITY_WORKFLOW_TIMEOUT_SECONDS", "30")
            ),
            api_base_url=(
                os.getenv("SUPERVITY_API_BASE_URL", "").strip().rstrip("/")
                or _api_base_from_trigger(trigger_url)
            ),
            integration_api_base_url=(
                os.getenv("SUPERVITY_INTEGRATION_API_BASE_URL", "").strip().rstrip("/")
                or "https://auto-integration-api.supervity.ai/api/v1"
            ),
            active_org=os.getenv("SUPERVITY_ACTIVE_ORG", "").strip() or None,
            include_callback_inputs=(
                os.getenv("SUPERVITY_INCLUDE_CALLBACK_INPUTS", "").strip().lower()
                in {"1", "true", "yes", "on"}
            ),
        )


class SupervityClient:
    def __init__(
        self,
        settings: SupervitySettings,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.settings = settings
        self._transport = transport

    @classmethod
    def from_environment(cls) -> SupervityClient:
        return cls(SupervitySettings.from_environment())

    @property
    def headers(self) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.settings.api_key}",
            "x-source": self.settings.source_header,
            "x-user-timezone": self.settings.user_timezone,
        }
        if self.settings.active_org:
            headers["x-active-org"] = self.settings.active_org
        return headers

    async def trigger(
        self,
        *,
        command_center_run_id: str,
        incident_id: str,
        inputs: Mapping[str, Any],
        callback_url: str | None,
        callback_token: str | None = None,
        on_run_id: Callable[[str], Awaitable[None]] | None = None,
    ) -> SupervityRunHandle:
        if not self.settings.orchestrator_id:
            raise SupervityConfigurationError(
                "SUPERVITY_ORCHESTRATOR_ID is required by the multipart trigger"
            )
        form = {
            "workflowId": self.settings.orchestrator_id,
            "inputs[source]": self._input_text(inputs, "source", "command_center"),
            "inputs[source_ref]": self._input_text(inputs, "source_ref", incident_id),
            "inputs[received_at_raw]": self._input_text(inputs, "received_at_raw"),
            "inputs[sender_email]": self._input_text(inputs, "sender_email"),
            "inputs[body]": self._input_text(inputs, "body"),
        }
        if self.settings.include_callback_inputs:
            if not callback_url or not callback_token:
                raise SupervityConfigurationError(
                    "Callback inputs require COMMAND_CENTER_API_URL and "
                    "COMMAND_CENTER_CALLBACK_SECRET"
                )
            callback_base = callback_url.rsplit("/", 1)[0]
            command_center_base = callback_url.rsplit("/supervity/callback", 1)[0]
            form.update(
                {
                    "inputs[command_center_run_id]": command_center_run_id,
                    "inputs[incident_id]": incident_id,
                    "inputs[callback_token]": callback_token,
                    "inputs[status_callback_url]": callback_url,
                    "inputs[notification_callback_url]": (
                        f"{callback_base}/notification"
                    ),
                    "inputs[decision_callback_url]": f"{callback_base}/decision",
                    "inputs[policy_evaluate_url]": (
                        f"{command_center_base}/policies/evaluate"
                    ),
                    "inputs[action_authorize_url]": (
                        f"{callback_base}/action-authorization"
                    ),
                    "inputs[action_complete_url]": (
                        f"{callback_base}/action-completion"
                    ),
                }
            )
        return await self._trigger_stream(form, on_run_id=on_run_id)

    async def trigger_workflow(
        self,
        *,
        workflow_id: str,
        inputs: Mapping[str, Any],
        envs: Mapping[str, Any] | None = None,
    ) -> SupervityRunHandle:
        """Trigger any saved workflow through the supported multipart API."""
        normalized_workflow_id = workflow_id.strip()
        if not normalized_workflow_id:
            raise SupervityConfigurationError("workflow_id is required")
        normalized_inputs = self._workflow_mapping("input", inputs)
        normalized_envs = self._workflow_mapping("environment", envs or {})
        form = {"workflowId": normalized_workflow_id}
        form.update(
            {f"inputs[{key}]": value for key, value in normalized_inputs.items()}
        )
        form.update({f"envs[{key}]": value for key, value in normalized_envs.items()})
        return await self._trigger_stream(form)

    def _workflow_mapping(
        self,
        label: str,
        values: Mapping[str, Any],
    ) -> dict[str, str]:
        normalized: dict[str, str] = {}
        for key, value in values.items():
            normalized_key = str(key).strip()
            if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", normalized_key):
                raise SupervityConfigurationError(
                    f"Invalid Supervity workflow {label} name: {normalized_key!r}"
                )
            if value is not None:
                normalized[normalized_key] = self._form_value(value)
        return normalized

    async def status(self, run_id: str) -> Mapping[str, Any]:
        url = (
            self.settings.status_url_template.format(run_id=run_id)
            if self.settings.status_url_template
            else self._api_url(f"workflow-runs/{run_id}")
        )
        return await self._request("GET", url)

    async def list_user_forms(
        self,
        *,
        status: str | None = None,
        page: int = 1,
        limit: int = 100,
    ) -> list[Mapping[str, Any]]:
        params: dict[str, str | int] = {"page": page, "limit": limit}
        if status:
            params["status"] = status
        payload = await self._request_payload(
            "GET",
            self._api_url("user-forms"),
            params=params,
        )
        return self._collection(payload, "forms", "userForms", "items", "data")

    async def get_user_form(self, form_id: str) -> Mapping[str, Any]:
        normalized_id = form_id.strip()
        if not normalized_id:
            raise SupervityConfigurationError("User form ID is required")
        return await self._request(
            "GET",
            self._api_url(f"user-forms/{quote(normalized_id, safe='')}"),
        )

    async def submit_user_form(
        self,
        *,
        activity_run_id: str,
        status: str,
        fields: Mapping[str, Any],
    ) -> str:
        normalized_status = status.strip().lower()
        if normalized_status not in {"approve", "reject"}:
            raise SupervityConfigurationError(
                "User form status must be 'approve' or 'reject'"
            )
        form = {key: (None, self._form_value(value)) for key, value in fields.items()}
        url = self._api_url(f"user-forms/{activity_run_id}/{normalized_status}")
        try:
            async with httpx.AsyncClient(
                timeout=self.settings.timeout_seconds,
                transport=self._transport,
            ) as client:
                response = await client.post(
                    url,
                    headers={"Accept": "text/html"},
                    files=form,
                )
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise SupervityAPIError(
                "Supervity user form returned "
                f"{exc.response.status_code}: {exc.response.text[:500]}"
            ) from exc
        except httpx.HTTPError as exc:
            raise SupervityAPIError(
                f"Supervity user form request failed: {exc}"
            ) from exc
        return response.text

    async def integration_inventory(self) -> Mapping[str, Any]:
        return await self._request("GET", self._integration_api_url("integrations/me"))

    async def list_schedules(
        self, *, page: int = 1, limit: int = 100
    ) -> list[Mapping[str, Any]]:
        payload = await self._request_payload(
            "GET",
            self._api_url("schedules"),
            params={"page": page, "limit": limit},
        )
        return self._collection(payload, "schedules", "items", "data")

    async def resume(
        self,
        *,
        run_id: str,
        decision: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        if not self.settings.resume_url_template:
            raise SupervityConfigurationError(
                "SUPERVITY_WORKFLOW_RESUME_URL_TEMPLATE is not configured"
            )
        url = self.settings.resume_url_template.format(run_id=run_id)
        return await self._request("POST", url, json={"decision": dict(decision)})

    async def _request(
        self,
        method: str,
        url: str,
        *,
        json: Mapping[str, Any] | None = None,
        params: Mapping[str, str | int] | None = None,
    ) -> Mapping[str, Any]:
        payload = await self._request_payload(
            method,
            url,
            json=json,
            params=params,
        )
        if not isinstance(payload, Mapping):
            raise SupervityAPIError("Supervity API response must be a JSON object")
        return payload

    async def _request_payload(
        self,
        method: str,
        url: str,
        *,
        json: Mapping[str, Any] | None = None,
        params: Mapping[str, str | int] | None = None,
    ) -> Any:
        try:
            async with httpx.AsyncClient(
                timeout=self.settings.timeout_seconds,
                transport=self._transport,
            ) as client:
                response = await client.request(
                    method,
                    url,
                    headers={**self.headers, "Accept": "application/json"},
                    json=json,
                    params=params,
                )
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            body = exc.response.text[:1000]
            raise SupervityAPIError(
                f"Supervity API returned {exc.response.status_code}: {body}"
            ) from exc
        except httpx.HTTPError as exc:
            raise SupervityAPIError(f"Supervity API request failed: {exc}") from exc
        try:
            return response.json()
        except ValueError as exc:
            raise SupervityAPIError("Supervity API returned non-JSON data") from exc

    def _api_url(self, path: str) -> str:
        return f"{self.settings.api_base_url.rstrip('/')}/{path.lstrip('/')}"

    def _integration_api_url(self, path: str) -> str:
        base_url = self.settings.integration_api_base_url.rstrip("/")
        return f"{base_url}/{path.lstrip('/')}"

    @staticmethod
    def _collection(payload: Any, *keys: str) -> list[Mapping[str, Any]]:
        values = payload
        if isinstance(payload, Mapping):
            values = next(
                (payload[key] for key in keys if isinstance(payload.get(key), list)),
                None,
            )
            if values is None and isinstance(payload.get("data"), Mapping):
                return SupervityClient._collection(payload["data"], *keys)
            if values is None:
                values = []
        if not isinstance(values, list):
            raise SupervityAPIError("Supervity API response did not contain a list")
        return [item for item in values if isinstance(item, Mapping)]

    @staticmethod
    def _form_value(value: Any) -> str:
        if isinstance(value, str):
            return value
        if value is None:
            return ""
        if isinstance(value, (dict, list, tuple, bool, int, float)):
            return json.dumps(value, default=str)
        return str(value)

    async def _trigger_stream(
        self,
        form: Mapping[str, str],
        *,
        on_run_id: Callable[[str], Awaitable[None]] | None = None,
    ) -> SupervityRunHandle:
        recent_events: deque[Mapping[str, Any]] = deque(maxlen=50)
        event_count = 0
        run_id: str | None = None
        announced_run_id: str | None = None
        files = {name: (None, value) for name, value in form.items()}
        try:
            async with httpx.AsyncClient(
                timeout=self.settings.timeout_seconds,
                transport=self._transport,
            ) as client:
                async with client.stream(
                    "POST",
                    self.settings.trigger_url,
                    headers={
                        **self.headers,
                        "Accept": "text/event-stream, application/json",
                    },
                    files=files,
                ) as response:
                    if response.is_error:
                        body = (await response.aread()).decode(errors="replace")[:1000]
                        raise SupervityAPIError(
                            f"Supervity API returned {response.status_code}: {body}"
                        )
                    run_id = self._run_id_from_headers(response.headers)
                    if run_id and on_run_id:
                        await on_run_id(run_id)
                        announced_run_id = run_id
                    async for line in response.aiter_lines():
                        event = self._parse_stream_line(line)
                        if event is None:
                            continue
                        event_count += 1
                        recent_events.append(event)
                        run_id = run_id or self._extract_run_id(event, required=False)
                        if run_id and on_run_id and run_id != announced_run_id:
                            await on_run_id(run_id)
                            announced_run_id = run_id
        except httpx.HTTPError as exc:
            raise SupervityAPIError(f"Supervity API request failed: {exc}") from exc

        if not run_id:
            raise SupervityAPIError(
                "Supervity stream completed without a workflow run identifier"
            )
        final_event = recent_events[-1] if recent_events else {}
        workflow_run = final_event.get("workflowRun")
        status = (
            workflow_run.get("status") if isinstance(workflow_run, Mapping) else None
        )
        success = final_event.get("success")
        message = final_event.get("message")
        return SupervityRunHandle(
            run_id=run_id,
            raw_response={
                "event_count": event_count,
                "events": list(recent_events),
            },
            status=str(status) if status is not None else None,
            success=success if isinstance(success, bool) else None,
            message=str(message) if message is not None else None,
        )

    @staticmethod
    def _input_text(
        inputs: Mapping[str, Any], key: str, default: str | None = None
    ) -> str:
        value = inputs.get(key, default)
        if value is None or not str(value).strip():
            raise SupervityConfigurationError(
                f"Supervity workflow input {key!r} is required"
            )
        return str(value).strip()

    @staticmethod
    def _parse_stream_line(line: str) -> Mapping[str, Any] | None:
        value = line.strip()
        if not value or value.startswith(":") or value.startswith("event:"):
            return None
        if value.startswith("data:"):
            value = value[5:].strip()
        if not value or value == "[DONE]":
            return None
        try:
            payload = json.loads(value)
        except ValueError:
            return {"message": value}
        return payload if isinstance(payload, Mapping) else {"data": payload}

    @staticmethod
    def _run_id_from_headers(headers: Mapping[str, str]) -> str | None:
        for key in (
            "x-workflow-run-id",
            "x-run-id",
            "workflow-run-id",
        ):
            value = headers.get(key)
            if value and value.strip():
                return value.strip()
        return None

    @staticmethod
    def _extract_run_id(
        payload: Mapping[str, Any], *, required: bool = True
    ) -> str | None:
        workflow_run = payload.get("workflowRun")
        if isinstance(workflow_run, Mapping):
            value = workflow_run.get("id")
            if isinstance(value, str) and value.strip():
                return value.strip()
        queue: list[Mapping[str, Any]] = [payload]
        while queue:
            container = queue.pop(0)
            for key in (
                "run_id",
                "runId",
                "workflow_run_id",
                "workflowRunId",
                "workflow_execution_id",
                "workflowExecutionId",
                "execution_id",
                "executionId",
            ):
                value = container.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
            for value in container.values():
                if isinstance(value, Mapping):
                    queue.append(value)
        if required:
            raise SupervityAPIError(
                "Supervity response did not include a workflow run identifier"
            )
        return None


def _api_base_from_trigger(trigger_url: str) -> str:
    parts = urlsplit(trigger_url)
    marker = "/api/v1/"
    path = parts.path
    if marker in path:
        path = f"{path.split(marker, 1)[0]}/api/v1"
    else:
        path = "/api/v1"
    return urlunsplit((parts.scheme, parts.netloc, path, "", "")).rstrip("/")

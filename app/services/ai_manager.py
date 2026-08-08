"""Grounded, read-only AI Manager answers from persisted Command Center state."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models.command_center import (
    IntegrationHealthRecord,
    PolicyDefinitionRecord,
    PolicyEvaluationRecord,
    WorkbenchItemRecord,
    WorkflowRunRecord,
)
from .governance_policies import SupabaseGovernancePolicyStore
from .integration_health import reconcile_supervity_integration_health
from .supabase import SupabaseAPIError, SupabaseConfigurationError


@dataclass(frozen=True, slots=True)
class ManagerToolCall:
    id: str
    name: str
    args: dict[str, Any]
    result: Any


@dataclass(frozen=True, slots=True)
class ManagerAnswer:
    response: str
    tool_calls: tuple[ManagerToolCall, ...]


class GroundedAIManager:
    """A deterministic query layer that never invents operational facts."""

    async def answer(self, *, message: str, db: Session) -> ManagerAnswer:
        normalized = message.strip()
        incident_match = re.search(r"\b(?:DN|INC)-[A-Z0-9-]+\b", normalized, re.I)
        run_match = re.search(r"\bRUN-[A-F0-9-]+\b", normalized, re.I)
        if run_match or incident_match:
            return self._answer_run(
                db,
                run_id=run_match.group(0).upper() if run_match else None,
                incident_id=(
                    incident_match.group(0).upper() if incident_match else None
                ),
            )
        lowered = normalized.lower()
        if any(
            word in lowered for word in ("integration", "outlook", "supabase", "slack")
        ):
            return await self._answer_integrations(db)
        if any(
            word in lowered for word in ("policy", "threshold", "blocked", "approval")
        ):
            return await self._answer_policies(db)
        if any(
            word in lowered for word in ("workbench", "decision", "waiting", "pending")
        ):
            return self._answer_workbench(db)
        return self._answer_portfolio(db)

    def _tool(self, name: str, args: dict[str, Any], result: Any) -> ManagerToolCall:
        return ManagerToolCall(
            id=f"tool-{uuid4().hex}",
            name=name,
            args=args,
            result=result,
        )

    def _answer_run(
        self,
        db: Session,
        *,
        run_id: str | None,
        incident_id: str | None,
    ) -> ManagerAnswer:
        query = db.query(WorkflowRunRecord)
        if run_id:
            query = query.filter(WorkflowRunRecord.run_id == run_id)
        else:
            query = query.filter(WorkflowRunRecord.incident_id == incident_id)
        run = query.order_by(WorkflowRunRecord.created_at.desc()).first()
        tool = self._tool(
            "query_workflow_run",
            {"run_id": run_id, "incident_id": incident_id},
            (
                {
                    "run_id": run.run_id,
                    "incident_id": run.incident_id,
                    "status": run.status,
                    "current_operator": run.current_operator,
                }
                if run
                else None
            ),
        )
        if run is None:
            identifier = run_id or incident_id
            return ManagerAnswer(
                response=f"I could not find persisted workflow evidence for {identifier}.",
                tool_calls=(tool,),
            )
        evaluations = (
            db.query(PolicyEvaluationRecord)
            .filter(PolicyEvaluationRecord.run_id == run.run_id)
            .order_by(PolicyEvaluationRecord.evaluated_at.desc())
            .all()
        )
        workbench = (
            db.query(WorkbenchItemRecord)
            .filter(WorkbenchItemRecord.run_id == run.run_id)
            .order_by(WorkbenchItemRecord.created_at.desc())
            .first()
        )
        matched = [evaluation for evaluation in evaluations if evaluation.matched]
        lines = [
            f"{run.incident_id} is **{run.status.replace('_', ' ')}** in run `{run.run_id}`.",
            f"Current step: {run.current_operator or 'Orchestrator'}.",
            f"Recorded exposure is MYR {run.cost_at_risk_myr or 0:,.2f}; recorded cost avoided is MYR {run.cost_avoided_myr or 0:,.2f}.",
        ]
        if matched:
            reasons = "; ".join(
                f"{evaluation.decision}: {evaluation.reason}" for evaluation in matched
            )
            lines.append(f"Matched policy evidence: {reasons}")
        else:
            lines.append("No matched policy evaluation is persisted for this run.")
        if workbench:
            lines.append(
                f"Workbench item `{workbench.item_id}` is {workbench.status}"
                + (
                    f"; decision by {workbench.decision_by}: {workbench.decision_reason}."
                    if workbench.decision_by
                    else "."
                )
            )
        if run.error:
            lines.append(f"Latest recorded error: {run.error}")
        return ManagerAnswer(
            response="\n\n".join(lines),
            tool_calls=(
                tool,
                self._tool(
                    "query_policy_evaluations",
                    {"run_id": run.run_id},
                    [
                        {
                            "policy_id": evaluation.policy_id,
                            "version": evaluation.policy_version,
                            "matched": evaluation.matched,
                            "decision": evaluation.decision,
                            "reason": evaluation.reason,
                        }
                        for evaluation in evaluations
                    ],
                ),
            ),
        )

    async def _answer_integrations(self, db: Session) -> ManagerAnswer:
        await reconcile_supervity_integration_health(db)
        records = (
            db.query(IntegrationHealthRecord)
            .order_by(IntegrationHealthRecord.name)
            .all()
        )
        result = [
            {
                "name": item.name,
                "category": item.category,
                "status": item.status,
                "last_success_at": (
                    item.last_success_at.isoformat() if item.last_success_at else None
                ),
                "last_error": item.last_error,
            }
            for item in records
        ]
        if not records:
            response = "No integration-health records are configured."
        else:
            response = "\n".join(
                f"- **{item.name}** ({item.category}): {item.status}"
                + (f" — {item.last_error}" if item.last_error else "")
                for item in records
            )
        return ManagerAnswer(
            response=response,
            tool_calls=(self._tool("query_integration_health", {}, result),),
        )

    async def _answer_policies(self, db: Session) -> ManagerAnswer:
        if os.getenv("COMMAND_CENTER_POLICY_STORE", "supabase").lower() == "supabase":
            try:
                records = await SupabaseGovernancePolicyStore.from_environment().list()
            except (SupabaseConfigurationError, SupabaseAPIError) as exc:
                return ManagerAnswer(
                    response=(
                        "The governance policy store is unavailable. Command Center "
                        f"will not authorize governed actions: {exc}"
                    ),
                    tool_calls=(
                        self._tool(
                            "query_current_policies",
                            {},
                            {"status": "unavailable", "decision": "review"},
                        ),
                    ),
                )
        else:
            records = (
                db.query(PolicyDefinitionRecord)
                .filter(PolicyDefinitionRecord.is_current.is_(True))
                .order_by(PolicyDefinitionRecord.priority.desc())
                .all()
            )
        result = [
            {
                "policy_id": item.policy_id,
                "version": item.version,
                "enabled": item.enabled,
                "decision": (
                    item.decision.value
                    if hasattr(item.decision, "value")
                    else item.decision
                ),
                "parameters": item.parameters,
            }
            for item in records
        ]
        response = (
            "\n".join(
                f"- **{item.name}** v{item.version}: "
                f"{item.decision.value if hasattr(item.decision, 'value') else item.decision}, "
                f"{'enabled' if item.enabled else 'disabled'}; parameters `{item.parameters}`"
                for item in records
            )
            if records
            else "No current policy versions are configured."
        )
        return ManagerAnswer(
            response=response,
            tool_calls=(self._tool("query_current_policies", {}, result),),
        )

    def _answer_workbench(self, db: Session) -> ManagerAnswer:
        records = (
            db.query(WorkbenchItemRecord)
            .filter(WorkbenchItemRecord.status == "open")
            .order_by(WorkbenchItemRecord.created_at)
            .all()
        )
        result = [
            {
                "item_id": item.item_id,
                "incident_id": item.incident_id,
                "severity": item.severity,
                "title": item.title,
            }
            for item in records
        ]
        response = (
            "\n".join(
                f"- **{item.incident_id}** ({item.severity}): {item.title} — `{item.item_id}`"
                for item in records
            )
            if records
            else "No Workbench decisions are currently waiting."
        )
        return ManagerAnswer(
            response=response,
            tool_calls=(self._tool("query_open_workbench", {}, result),),
        )

    def _answer_portfolio(self, db: Session) -> ManagerAnswer:
        open_statuses = [
            "queued",
            "running",
            "awaiting_approval",
            "executing",
            "needs_review",
        ]
        open_count = (
            db.query(func.count(WorkflowRunRecord.run_id))
            .filter(WorkflowRunRecord.status.in_(open_statuses))
            .scalar()
            or 0
        )
        critical_count = (
            db.query(func.count(WorkflowRunRecord.run_id))
            .filter(
                WorkflowRunRecord.status.in_(open_statuses),
                WorkflowRunRecord.severity == "critical",
            )
            .scalar()
            or 0
        )
        awaiting = (
            db.query(func.count(WorkbenchItemRecord.item_id))
            .filter(WorkbenchItemRecord.status == "open")
            .scalar()
            or 0
        )
        result = {
            "open_disruptions": open_count,
            "critical_disruptions": critical_count,
            "awaiting_decisions": awaiting,
        }
        return ManagerAnswer(
            response=(
                f"The persisted portfolio has **{open_count} open disruptions**, "
                f"including **{critical_count} critical**, with **{awaiting} human decisions** waiting. "
                "Name an incident such as DN-5046 for its policy and Workbench evidence."
            ),
            tool_calls=(self._tool("query_portfolio_summary", {}, result),),
        )

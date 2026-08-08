"""Canonical policy facts assembled from exact Operator result lineage."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from .supabase import SupabaseClient


class PolicyFactsError(RuntimeError):
    pass


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().lower()
    if text in {"true", "1", "yes", "allowed"}:
        return True
    if text in {"false", "0", "no", "prohibited"}:
        return False
    return None


def _number(value: Any) -> float | None:
    try:
        if value is None or str(value).strip() == "":
            return None
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None


def build_policy_facts(
    *,
    incident_id: str,
    guard: Mapping[str, Any],
    portfolio: Mapping[str, Any],
    planner: Mapping[str, Any],
    proposed_action: Mapping[str, Any] | None = None,
    base_facts: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build one fail-closed facts object from three exact result envelopes."""

    for name, row in (("guard", guard), ("portfolio", portfolio), ("planner", planner)):
        if row.get("incident_id") != incident_id:
            raise PolicyFactsError(f"{name} result belongs to another incident")

    guard_run_id = str(guard.get("run_id") or "").strip()
    portfolio_run_id = str(portfolio.get("run_id") or "").strip()
    planner_run_id = str(planner.get("run_id") or "").strip()
    if not all((guard_run_id, portfolio_run_id, planner_run_id)):
        raise PolicyFactsError("Guard, Portfolio, and Planner run IDs are required")

    planner_evidence = _mapping(planner.get("evidence_refs"))
    portfolio_evidence = _mapping(portfolio.get("evidence_refs"))
    if planner_evidence.get("guard_run_id") != guard_run_id:
        raise PolicyFactsError("Planner does not reference the supplied Guard run")
    if planner_evidence.get("portfolio_run_id") != portfolio_run_id:
        raise PolicyFactsError("Planner does not reference the supplied Portfolio run")
    if portfolio_evidence.get("guard_run_id") != guard_run_id:
        raise PolicyFactsError("Portfolio does not reference the supplied Guard run")

    planner_facts = _mapping(planner.get("facts"))
    guard_facts = _mapping(guard.get("facts"))
    portfolio_facts = _mapping(portfolio.get("facts"))
    action = dict(proposed_action or _mapping(planner_facts.get("recommended_option")))
    action_type = (
        action.get("type") or action.get("option_type") or action.get("action_type")
    )
    if action_type is not None:
        action["type"] = str(action_type)

    candidate_id = action.get("option_id") or action.get("id")
    verdicts = guard_facts.get("candidate_verdicts") or []
    verdict = next(
        (
            _mapping(item)
            for item in verdicts
            if isinstance(item, Mapping) and item.get("candidate_id") == candidate_id
        ),
        {},
    )
    supplier_id = action.get("supplier_id") or verdict.get("supplier_id")

    contract_rows = guard_facts.get("contract_results") or {}
    supplier_contracts = (
        contract_rows.get(str(supplier_id), [])
        if isinstance(contract_rows, Mapping) and supplier_id is not None
        else []
    )
    valid_contracts = [
        _mapping(item)
        for item in supplier_contracts
        if isinstance(item, Mapping) and item.get("valid") is True
    ]
    expedite_values = {
        _bool(item.get("expedite_allowed"))
        for item in valid_contracts
        if _bool(item.get("expedite_allowed")) is not None
    }
    expedite_allowed = (
        next(iter(expedite_values)) if len(expedite_values) == 1 else None
    )

    incremental = _number(action.get("incremental_cost_myr"))
    penalty = _number(action.get("penalty_cost_myr"))
    governed_cost = incremental + (penalty or 0.0) if incremental is not None else None
    priority = (
        _mapping(base_facts or {}).get("customer", {}).get("priority")
        if isinstance(_mapping(base_facts or {}).get("customer"), Mapping)
        else None
    )

    return {
        **dict(base_facts or {}),
        "severity": _mapping(planner_facts.get("baseline")).get("severity"),
        "proposed_action": action,
        "contract": {
            "expedite_allowed": expedite_allowed,
            "valid_contract_ids": [item.get("contract_id") for item in valid_contracts],
        },
        "candidate_supplier": {
            "active": verdict.get("supplier_active"),
            "quote_valid": verdict.get("quote_valid"),
            "moq_satisfied": verdict.get("moq_satisfied"),
        },
        "customer": {"priority": priority},
        "portfolio": {
            "resource_contested": bool(
                portfolio_facts.get("competing_incident_ids")
                or portfolio_facts.get("shared_resource_ids")
            ),
            "recommended_winner": portfolio_facts.get("recommended_winner"),
        },
        "recovery": {
            "governed_cost_myr": governed_cost,
            "required_quantity": _mapping(planner_facts.get("baseline")).get(
                "required_quantity"
            ),
            "required_unit": _mapping(planner_facts.get("baseline")).get(
                "required_unit"
            ),
        },
        "lineage": {
            "guard_run_id": guard_run_id,
            "portfolio_run_id": portfolio_run_id,
            "planner_run_id": planner_run_id,
            "assembled_at": datetime.now(timezone.utc).isoformat(),
        },
    }


class SupabasePolicyFactsLoader:
    EXPECTED_OPERATORS = {
        "guard": "Contract & Policy Guard",
        "portfolio": "Portfolio Prioritizer",
        "planner": "Recovery Planner",
    }

    def __init__(self, client: SupabaseClient) -> None:
        self.client = client

    @classmethod
    def from_environment(cls) -> "SupabasePolicyFactsLoader":
        return cls(SupabaseClient.from_environment())

    async def _exact_result(
        self,
        *,
        incident_id: str,
        operator: str,
        run_id: str,
    ) -> dict[str, Any]:
        rows = await self.client.fetch_rows(
            "operator_results",
            filters={
                "incident_id": f"eq.{incident_id}",
                "operator": f"eq.{operator}",
                "run_id": f"eq.{run_id}",
            },
            limit=2,
        )
        if len(rows) != 1:
            raise PolicyFactsError(
                f"Expected one {operator} result for run_id={run_id}; found {len(rows)}"
            )
        return rows[0]

    async def load(
        self,
        *,
        incident_id: str,
        operator_run_ids: Mapping[str, str],
        proposed_action: Mapping[str, Any] | None,
        base_facts: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        rows: dict[str, dict[str, Any]] = {}
        for key, operator in self.EXPECTED_OPERATORS.items():
            run_id = str(operator_run_ids.get(key) or "").strip()
            if not run_id:
                raise PolicyFactsError(f"operator_run_ids.{key} is required")
            rows[key] = await self._exact_result(
                incident_id=incident_id,
                operator=operator,
                run_id=run_id,
            )
        return build_policy_facts(
            incident_id=incident_id,
            guard=rows["guard"],
            portfolio=rows["portfolio"],
            planner=rows["planner"],
            proposed_action=proposed_action,
            base_facts=base_facts,
        )

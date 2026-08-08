"""Deterministic, version-aware evaluation for editable no-code policies."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable, Mapping
from uuid import uuid4

from ..domain import (
    PolicyCondition,
    PolicyDecision,
    PolicyDefinition,
    PolicyEvaluation,
    PolicyMatchMode,
    PolicyOperator,
    utc_now,
)


class MissingFact:
    pass


MISSING = MissingFact()


def facts_hash(facts: Mapping[str, Any]) -> str:
    """Return a stable fingerprint for the exact policy input snapshot."""

    canonical = json.dumps(
        facts,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(canonical).hexdigest()}"


def resolve_field(facts: Mapping[str, Any], field_path: str) -> Any:
    """Resolve a dot-separated field path without guessing missing values."""

    current: Any = facts
    for part in field_path.split("."):
        if not isinstance(current, Mapping) or part not in current:
            return MISSING
        current = current[part]
    return current


def _parameter_value(value: Any, parameters: Mapping[str, Any]) -> Any:
    if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
        key = value[2:-1]
        if key not in parameters:
            raise ValueError(f"policy parameter {key!r} is not defined")
        return parameters[key]
    return value


def _numeric_pair(left: Any, right: Any) -> tuple[Decimal, Decimal] | None:
    if isinstance(left, bool) or isinstance(right, bool):
        return None
    try:
        return Decimal(str(left)), Decimal(str(right))
    except (InvalidOperation, TypeError, ValueError):
        return None


def condition_matches(
    condition: PolicyCondition,
    facts: Mapping[str, Any],
    parameters: Mapping[str, Any],
) -> bool:
    left = resolve_field(facts, condition.field_path)
    right = _parameter_value(condition.value, parameters)

    if condition.operator is PolicyOperator.EXISTS:
        expected = True if right is None else bool(right)
        return (left is not MISSING and left is not None) is expected
    if left is MISSING:
        return False
    if condition.operator is PolicyOperator.EQUALS:
        return left == right
    if condition.operator is PolicyOperator.NOT_EQUALS:
        return left != right
    if condition.operator in {
        PolicyOperator.GREATER_THAN,
        PolicyOperator.GREATER_THAN_OR_EQUAL,
        PolicyOperator.LESS_THAN,
        PolicyOperator.LESS_THAN_OR_EQUAL,
    }:
        pair = _numeric_pair(left, right)
        if pair is None:
            return False
        left_number, right_number = pair
        if condition.operator is PolicyOperator.GREATER_THAN:
            return left_number > right_number
        if condition.operator is PolicyOperator.GREATER_THAN_OR_EQUAL:
            return left_number >= right_number
        if condition.operator is PolicyOperator.LESS_THAN:
            return left_number < right_number
        return left_number <= right_number
    if condition.operator is PolicyOperator.IN:
        return left in right
    if condition.operator is PolicyOperator.NOT_IN:
        return left not in right
    if condition.operator is PolicyOperator.CONTAINS:
        try:
            return right in left
        except TypeError:
            return False
    raise ValueError(f"unsupported policy operator: {condition.operator}")


def evaluate_policy(
    policy: PolicyDefinition,
    *,
    run_id: str,
    incident_id: str,
    facts: Mapping[str, Any],
    evaluation_id: str | None = None,
    evaluated_at: datetime | None = None,
) -> PolicyEvaluation:
    """Evaluate one policy and return an auditable result, including non-matches."""

    now = evaluated_at or utc_now()
    action_type = resolve_field(facts, "proposed_action.type")
    applicable = not policy.action_classes or (
        action_type is not MISSING and str(action_type) in policy.action_classes
    )
    missing_facts = tuple(
        field_path
        for field_path in policy.required_facts
        if (
            resolve_field(facts, field_path) is MISSING
            or resolve_field(facts, field_path) is None
        )
    )
    condition_results = [
        condition_matches(condition, facts, policy.parameters)
        for condition in policy.conditions
    ]
    matched = (
        all(condition_results)
        if policy.match_mode is PolicyMatchMode.ALL
        else any(condition_results)
    )
    matched_conditions = tuple(
        condition.field_path
        for condition, did_match in zip(policy.conditions, condition_results)
        if did_match
    )
    is_effective = policy.effective_from <= now and (
        policy.expires_at is None or now < policy.expires_at
    )
    if not policy.enabled or not is_effective or not applicable:
        decision = PolicyDecision.ALLOW
    elif missing_facts:
        decision = PolicyDecision.REVIEW
        matched = False
    else:
        decision = policy.decision if matched else PolicyDecision.ALLOW
    if not policy.enabled:
        reason = "Policy is disabled"
        reason_code = "POLICY_DISABLED"
    elif not is_effective:
        reason = "Policy is outside its effective date range"
        reason_code = "POLICY_NOT_EFFECTIVE"
    elif not applicable:
        reason = "Policy does not govern this action class"
        reason_code = "POLICY_NOT_APPLICABLE"
    elif missing_facts:
        reason = "Required policy facts are missing: " + ", ".join(missing_facts)
        reason_code = "MISSING_REQUIRED_FACTS"
    elif not matched:
        reason = "Policy conditions did not match"
        reason_code = "CONDITIONS_NOT_MATCHED"
    else:
        reason = policy.reason_template
        reason_code = {
            PolicyDecision.ALLOW: "POLICY_ALLOWED",
            PolicyDecision.REVIEW: "POLICY_REQUIRES_REVIEW",
            PolicyDecision.BLOCK: "POLICY_BLOCKED",
        }[policy.decision]

    proposed_action = facts.get("proposed_action")
    candidate_action_id = None
    if isinstance(proposed_action, Mapping):
        raw_candidate_id = proposed_action.get("option_id") or proposed_action.get("id")
        if raw_candidate_id is not None:
            candidate_action_id = str(raw_candidate_id)

    return PolicyEvaluation(
        evaluation_id=evaluation_id or f"PE-{uuid4().hex}",
        policy_id=policy.policy_id,
        policy_version=policy.version,
        run_id=run_id,
        incident_id=incident_id,
        matched=policy.enabled and is_effective and applicable and matched,
        decision=decision,
        reason=reason,
        facts=dict(facts),
        input_hash=facts_hash(facts),
        matched_conditions=matched_conditions,
        approval_role=(
            (policy.approval_role or "procurement_commander")
            if decision is PolicyDecision.REVIEW
            else None
        ),
        reason_code=reason_code,
        candidate_action_id=candidate_action_id,
        missing_facts=missing_facts if applicable else (),
        evaluated_at=now,
    )


def evaluate_policies(
    policies: Iterable[PolicyDefinition],
    *,
    run_id: str,
    incident_id: str,
    facts: Mapping[str, Any],
) -> list[PolicyEvaluation]:
    ordered = sorted(policies, key=lambda policy: (-policy.priority, policy.policy_id))
    return [
        evaluate_policy(
            policy,
            run_id=run_id,
            incident_id=incident_id,
            facts=facts,
        )
        for policy in ordered
    ]


def effective_decision(evaluations: Iterable[PolicyEvaluation]) -> PolicyDecision:
    decisions = {evaluation.decision for evaluation in evaluations}
    if PolicyDecision.BLOCK in decisions:
        return PolicyDecision.BLOCK
    if PolicyDecision.REVIEW in decisions:
        return PolicyDecision.REVIEW
    return PolicyDecision.ALLOW

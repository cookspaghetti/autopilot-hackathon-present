import unittest

from app.domain import (
    PolicyCondition,
    PolicyDecision,
    PolicyDefinition,
    PolicyMatchMode,
    PolicyOperator,
    utc_now,
)
from app.services.policy_engine import (
    condition_matches,
    effective_decision,
    evaluate_policies,
    evaluate_policy,
)


def spend_policy(*, enabled: bool = True) -> PolicyDefinition:
    timestamp = utc_now()
    return PolicyDefinition(
        policy_id="POL-EXPEDITE-LIMIT",
        name="Expedite spend ceiling",
        description="Routes high governed spend to the procurement commander",
        version=3,
        priority=500,
        enabled=enabled,
        match_mode=PolicyMatchMode.ALL,
        conditions=(
            PolicyCondition(
                field_path="recovery.governed_cost_myr",
                operator=PolicyOperator.GREATER_THAN,
                value="${limit_myr}",
            ),
        ),
        decision=PolicyDecision.REVIEW,
        reason_template="Governed spend exceeds the editable limit",
        approval_role="procurement_commander",
        parameters={"limit_myr": "100000"},
        created_at=timestamp,
        updated_at=timestamp,
    )


class PolicyEngineTests(unittest.TestCase):
    def test_parameterized_numeric_condition_matches(self) -> None:
        condition = spend_policy().conditions[0]
        self.assertTrue(
            condition_matches(
                condition,
                {"recovery": {"governed_cost_myr": "120000"}},
                {"limit_myr": 100000},
            )
        )

    def test_missing_fact_never_matches(self) -> None:
        condition = spend_policy().conditions[0]
        self.assertFalse(condition_matches(condition, {}, {"limit_myr": 100000}))

    def test_missing_required_fact_routes_to_review_instead_of_allow(self) -> None:
        policy = spend_policy()
        object.__setattr__(
            policy,
            "required_facts",
            ("proposed_action.type", "recovery.governed_cost_myr"),
        )
        object.__setattr__(policy, "action_classes", ("expedite",))

        evaluation = evaluate_policy(
            policy,
            run_id="RUN-MISSING",
            incident_id="DN-MISSING",
            facts={"proposed_action": {"type": "expedite"}},
        )

        self.assertIs(evaluation.decision, PolicyDecision.REVIEW)
        self.assertEqual(evaluation.reason_code, "MISSING_REQUIRED_FACTS")
        self.assertEqual(
            evaluation.missing_facts,
            ("recovery.governed_cost_myr",),
        )

    def test_policy_does_not_require_unrelated_action_facts(self) -> None:
        policy = spend_policy()
        object.__setattr__(
            policy,
            "required_facts",
            ("proposed_action.type", "recovery.governed_cost_myr"),
        )
        object.__setattr__(policy, "action_classes", ("expedite",))

        evaluation = evaluate_policy(
            policy,
            run_id="RUN-WAIT",
            incident_id="DN-WAIT",
            facts={"proposed_action": {"type": "wait"}},
        )

        self.assertIs(evaluation.decision, PolicyDecision.ALLOW)
        self.assertEqual(evaluation.reason_code, "POLICY_NOT_APPLICABLE")
        self.assertEqual(evaluation.missing_facts, ())

    def test_matching_policy_requires_review_and_logs_version(self) -> None:
        evaluation = evaluate_policy(
            spend_policy(),
            run_id="RUN-1",
            incident_id="DN-5048",
            facts={"recovery": {"governed_cost_myr": 120000}},
        )

        self.assertTrue(evaluation.matched)
        self.assertIs(evaluation.decision, PolicyDecision.REVIEW)
        self.assertEqual(evaluation.policy_version, 3)
        self.assertEqual(evaluation.approval_role, "procurement_commander")

    def test_disabled_or_nonmatching_policy_allows_with_audit_result(self) -> None:
        evaluation = evaluate_policy(
            spend_policy(enabled=False),
            run_id="RUN-1",
            incident_id="DN-5048",
            facts={"recovery": {"governed_cost_myr": 999999}},
        )

        self.assertFalse(evaluation.matched)
        self.assertIs(evaluation.decision, PolicyDecision.ALLOW)
        self.assertEqual(evaluation.reason, "Policy is disabled")

    def test_block_has_precedence_over_review(self) -> None:
        review = spend_policy()
        timestamp = utc_now()
        block = PolicyDefinition(
            policy_id="POL-CONTRACT-BLOCK",
            name="Contract restriction",
            description="Blocks contractually prohibited actions",
            version=1,
            priority=900,
            enabled=True,
            match_mode=PolicyMatchMode.ALL,
            conditions=(
                PolicyCondition(
                    field_path="contract.expedite_allowed",
                    operator=PolicyOperator.EQUALS,
                    value=False,
                ),
            ),
            decision=PolicyDecision.BLOCK,
            reason_template="The active contract prohibits expedite",
            created_at=timestamp,
            updated_at=timestamp,
        )
        evaluations = evaluate_policies(
            [review, block],
            run_id="RUN-1",
            incident_id="DN-5048",
            facts={
                "recovery": {"governed_cost_myr": 120000},
                "contract": {"expedite_allowed": False},
            },
        )

        self.assertEqual(evaluations[0].policy_id, "POL-CONTRACT-BLOCK")
        self.assertIs(effective_decision(evaluations), PolicyDecision.BLOCK)


if __name__ == "__main__":
    unittest.main()

import unittest
from datetime import timedelta
from decimal import Decimal

from app.domain import (
    EvidenceReference,
    Insight,
    InsightKind,
    Money,
    OperatorResultEnvelope,
    OperatorRunStatus,
    PolicyCondition,
    PolicyDecision,
    PolicyDefinition,
    PolicyMatchMode,
    PolicyOperator,
    ResourceReservation,
    Severity,
    WorkbenchDecision,
    WorkbenchItem,
    WorkbenchStatus,
    WorkflowRun,
    WorkflowStatus,
    to_primitive,
    utc_now,
)


def evidence() -> EvidenceReference:
    return EvidenceReference(
        system="supabase",
        entity_type="disruption_notice",
        entity_id="DN-5046",
        observed_at=utc_now(),
        fields=("supplier_id", "item_number", "severity"),
    )


class DomainModelTests(unittest.TestCase):
    def test_operator_envelope_rejects_invalid_confidence(self) -> None:
        with self.assertRaisesRegex(ValueError, "confidence"):
            OperatorResultEnvelope(
                incident_id="INC-1",
                run_id="RUN-1",
                operator_name="Impact Assessor Operator",
                status=OperatorRunStatus.SUCCEEDED,
                confidence=1.01,
                started_at=utc_now(),
            )

    def test_recovery_money_uses_decimal_and_currency(self) -> None:
        value = Money(amount="120000.50", currency="myr")

        self.assertEqual(value.amount, Decimal("120000.50"))
        self.assertEqual(value.currency, "MYR")

    def test_review_policy_requires_approval_role(self) -> None:
        timestamp = utc_now()

        with self.assertRaisesRegex(ValueError, "approval_role"):
            PolicyDefinition(
                policy_id="expedite-limit",
                name="Expedite spend ceiling",
                description="Routes expensive recovery for review",
                version=1,
                priority=10,
                enabled=True,
                match_mode=PolicyMatchMode.ALL,
                conditions=(
                    PolicyCondition(
                        field_path="recovery.governed_cost_myr",
                        operator=PolicyOperator.GREATER_THAN,
                        value=100000,
                    ),
                ),
                decision=PolicyDecision.REVIEW,
                reason_template="Governed spend exceeds the configured ceiling",
                created_at=timestamp,
                updated_at=timestamp,
            )

    def test_workbench_resolution_is_one_way_and_versioned(self) -> None:
        created = utc_now()
        item = WorkbenchItem(
            item_id="WB-1",
            run_id="RUN-1",
            incident_id="DN-5046",
            title="Shared alternate requires allocation decision",
            summary="Two incidents request supplier 3055",
            severity=Severity.CRITICAL,
            proposed_action={"supplier_id": "3055", "reserve_for": "DN-5046"},
            status=WorkbenchStatus.OPEN,
            created_at=created,
            updated_at=created,
            evidence=(evidence(),),
        )

        resolved = item.resolve(
            decision=WorkbenchDecision.MODIFY,
            decided_by="commander@example.com",
            reason="Split capacity and protect the critical order",
            decided_at=created + timedelta(minutes=3),
            payload={"allocation": {"DN-5046": 0.7, "DN-5047": 0.3}},
        )

        self.assertIs(item.status, WorkbenchStatus.OPEN)
        self.assertIs(resolved.status, WorkbenchStatus.MODIFIED)
        self.assertEqual(resolved.version, 2)
        with self.assertRaisesRegex(ValueError, "only open"):
            resolved.resolve(
                decision=WorkbenchDecision.APPROVE,
                decided_by="commander@example.com",
                reason="Second decision",
                decided_at=created + timedelta(minutes=4),
            )

    def test_reservation_requires_positive_quantity_and_idempotency_key(self) -> None:
        with self.assertRaisesRegex(ValueError, "quantity"):
            ResourceReservation(
                reservation_id="RES-1",
                run_id="RUN-1",
                incident_id="DN-5046",
                resource_type="supplier_capacity",
                resource_id="3055",
                quantity=0,
                unit="units",
                created_at=utc_now(),
                idempotency_key="RUN-1:3055",
            )

    def test_insights_require_verifiable_evidence(self) -> None:
        with self.assertRaisesRegex(ValueError, "evidence"):
            Insight(
                insight_id="INS-1",
                kind=InsightKind.ANOMALY,
                severity=Severity.HIGH,
                title="Tier-two dependency concentration",
                summary="Five tier-one suppliers depend on one source",
                recommendation="Qualify another tier-two source",
                evidence=(),
                created_at=utc_now(),
            )

    def test_domain_values_serialize_to_json_primitives(self) -> None:
        item = {
            "severity": Severity.HIGH,
            "cost": Money(amount="42.10"),
            "evidence": (evidence(),),
        }

        result = to_primitive(item)

        self.assertEqual(result["severity"], "high")
        self.assertEqual(result["cost"], {"amount": "42.10", "currency": "MYR"})
        self.assertEqual(result["evidence"][0]["entity_id"], "DN-5046")

    def test_workflow_rejects_invalid_terminal_transition(self) -> None:
        timestamp = utc_now()
        run = WorkflowRun(
            run_id="RUN-1",
            incident_id="DN-5046",
            status=WorkflowStatus.COMPLETED,
            source="outlook",
            input_payload={},
            created_at=timestamp,
            updated_at=timestamp,
        )

        with self.assertRaisesRegex(ValueError, "invalid workflow transition"):
            run.transition(WorkflowStatus.RUNNING, updated_at=timestamp)


if __name__ == "__main__":
    unittest.main()

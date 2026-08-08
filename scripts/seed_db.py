#!/usr/bin/env python3
"""Idempotently seed required Command Center control-plane configuration."""

import logging
import os
import sys
from datetime import datetime, timezone

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import sessionmaker

from app.core.database import engine
from app.models.command_center import IntegrationHealthRecord, PolicyDefinitionRecord

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


POLICIES = [
    {
        "policy_id": "POL-EXPEDITE-SPEND",
        "name": "Expedite spend ceiling",
        "description": "Routes premium plus penalty exposure above the editable limit.",
        "priority": 700,
        "enabled": True,
        "match_mode": "all",
        "conditions": [
            {
                "field_path": "recovery.governed_cost_myr",
                "operator": "greater_than",
                "value": "${limit_myr}",
            }
        ],
        "decision": "review",
        "reason_template": "Governed recovery cost exceeds the configured expedite ceiling.",
        "approval_role": "procurement_commander",
        "parameters": {"limit_myr": 100000},
        "required_facts": ["proposed_action.type", "recovery.governed_cost_myr"],
        "action_classes": ["expedite"],
        "owner": "procurement_governance",
        "change_reason": "Command Center baseline",
    },
    {
        "policy_id": "POL-CONTRACT-EXPEDITE",
        "name": "Contract expedite restriction",
        "description": "Blocks expedite when the active contract disallows it.",
        "priority": 1000,
        "enabled": True,
        "match_mode": "all",
        "conditions": [
            {
                "field_path": "proposed_action.type",
                "operator": "equals",
                "value": "expedite",
            },
            {
                "field_path": "contract.expedite_allowed",
                "operator": "equals",
                "value": False,
            },
        ],
        "decision": "block",
        "reason_template": "The active contract prohibits expedite for this supplier.",
        "approval_role": None,
        "parameters": {},
        "required_facts": ["proposed_action.type", "contract.expedite_allowed"],
        "action_classes": ["expedite"],
        "owner": "procurement_governance",
        "change_reason": "Command Center baseline",
    },
    {
        "policy_id": "POL-CRITICAL-CUSTOMER",
        "name": "Critical customer protection",
        "description": "Requires review before reallocating stock committed to a critical customer.",
        "priority": 850,
        "enabled": True,
        "match_mode": "all",
        "conditions": [
            {
                "field_path": "customer.priority",
                "operator": "equals",
                "value": "critical",
            },
            {
                "field_path": "proposed_action.type",
                "operator": "in",
                "value": ["transfer_inventory", "inventory_reallocation"],
            },
        ],
        "decision": "review",
        "reason_template": "The proposal changes inventory committed to a critical customer.",
        "approval_role": "customer_service_lead",
        "parameters": {},
        "required_facts": ["proposed_action.type", "customer.priority"],
        "action_classes": ["transfer_inventory", "inventory_reallocation"],
        "owner": "procurement_governance",
        "change_reason": "Command Center baseline",
    },
    {
        "policy_id": "POL-SUPPLIER-ELIGIBILITY",
        "name": "Supplier eligibility guard",
        "description": "Blocks a substitution to an inactive or unverified supplier.",
        "priority": 950,
        "enabled": True,
        "match_mode": "any",
        "conditions": [
            {
                "field_path": "candidate_supplier.active",
                "operator": "equals",
                "value": False,
            },
            {
                "field_path": "candidate_supplier.quote_valid",
                "operator": "equals",
                "value": False,
            },
            {
                "field_path": "candidate_supplier.moq_satisfied",
                "operator": "equals",
                "value": False,
            },
        ],
        "decision": "block",
        "reason_template": "The proposed supplier does not satisfy substitution eligibility.",
        "approval_role": None,
        "parameters": {},
        "required_facts": [
            "proposed_action.type",
            "candidate_supplier.active",
            "candidate_supplier.quote_valid",
            "candidate_supplier.moq_satisfied",
        ],
        "action_classes": ["alternate_supplier", "supplier_switch"],
        "owner": "procurement_governance",
        "change_reason": "Command Center baseline",
    },
    {
        "policy_id": "POL-SHARED-RESOURCE",
        "name": "Shared recovery resource contention",
        "description": "Routes contested supplier capacity or inventory buffers for portfolio review.",
        "priority": 900,
        "enabled": True,
        "match_mode": "all",
        "conditions": [
            {
                "field_path": "portfolio.resource_contested",
                "operator": "equals",
                "value": True,
            }
        ],
        "decision": "review",
        "reason_template": "Multiple incidents are competing for the same recovery resource.",
        "approval_role": "procurement_commander",
        "parameters": {},
        "required_facts": ["proposed_action.type", "portfolio.resource_contested"],
        "action_classes": [
            "expedite",
            "alternate_supplier",
            "supplier_switch",
            "transfer_inventory",
            "inventory_reallocation",
        ],
        "owner": "procurement_governance",
        "change_reason": "Command Center baseline",
    },
    {
        "policy_id": "POL-GOVERNED-ACTION",
        "name": "Governed action review",
        "description": (
            "Requires explicit authorization for commitments, substitutions, "
            "reallocations, expedites, and external supplier messages."
        ),
        "priority": 800,
        "enabled": True,
        "match_mode": "all",
        "conditions": [
            {
                "field_path": "proposed_action.type",
                "operator": "in",
                "value": [
                    "expedite",
                    "alternate_supplier",
                    "supplier_switch",
                    "transfer_inventory",
                    "inventory_reallocation",
                    "financial_commitment",
                    "external_supplier_message",
                    "supplier_notification",
                ],
            }
        ],
        "decision": "review",
        "reason_template": (
            "The proposed action changes governed resources or creates an "
            "external commitment."
        ),
        "approval_role": "procurement_commander",
        "parameters": {},
        "required_facts": ["proposed_action.type"],
        "action_classes": [
            "expedite",
            "alternate_supplier",
            "supplier_switch",
            "transfer_inventory",
            "inventory_reallocation",
            "financial_commitment",
            "external_supplier_message",
            "supplier_notification",
        ],
        "owner": "procurement_governance",
        "change_reason": "General governed-action safety net",
    },
]


INTEGRATIONS = [
    {
        "integration_id": "outlook",
        "name": "Outlook",
        "category": "channel",
        "metadata_json": {"purpose": "Inbound disruption notices"},
    },
    {
        "integration_id": "supabase",
        "name": "Supabase",
        "category": "system_of_record",
        "metadata_json": {"purpose": "Procurement operational data"},
    },
    {
        "integration_id": "slack-via-supervity",
        "name": "Slack",
        "category": "channel",
        "metadata_json": {
            "purpose": "Decision and outcome notifications",
            "managed_by": "supervity",
        },
    },
    {
        "integration_id": "supervity-auto",
        "name": "Supervity Auto",
        "category": "agent_platform",
        "metadata_json": {"purpose": "Orchestrator and Operator execution"},
    },
]


def seed_data() -> None:
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        for policy in POLICIES:
            exists = (
                db.query(PolicyDefinitionRecord)
                .filter(
                    PolicyDefinitionRecord.policy_id == policy["policy_id"],
                    PolicyDefinitionRecord.is_current.is_(True),
                )
                .first()
            )
            if exists is None:
                db.add(
                    PolicyDefinitionRecord(
                        **policy,
                        version=1,
                        is_current=True,
                        created_at=now,
                        updated_at=now,
                    )
                )
        for integration in INTEGRATIONS:
            exists = (
                db.query(IntegrationHealthRecord)
                .filter(
                    IntegrationHealthRecord.integration_id
                    == integration["integration_id"]
                )
                .first()
            )
            if exists is None:
                db.add(
                    IntegrationHealthRecord(
                        **integration,
                        status="unknown",
                        checked_at=now,
                    )
                )
        db.commit()
        log.info("Command Center policy and integration baseline is ready.")
    except Exception:
        db.rollback()
        log.exception("Unable to seed Command Center baseline")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_data()

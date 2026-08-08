import pytest

from app.services.policy_facts import PolicyFactsError, build_policy_facts


def _rows() -> tuple[dict, dict, dict]:
    guard = {
        "incident_id": "INC-1",
        "run_id": "GUARD-1",
        "facts": {
            "candidate_verdicts": [
                {
                    "candidate_id": "OPTION-1",
                    "supplier_id": "3055",
                    "supplier_active": True,
                    "quote_valid": True,
                    "moq_satisfied": True,
                }
            ],
            "contract_results": {
                "3055": [
                    {
                        "contract_id": "CT-1",
                        "valid": True,
                        "expedite_allowed": False,
                    }
                ]
            },
        },
    }
    portfolio = {
        "incident_id": "INC-1",
        "run_id": "PORTFOLIO-1",
        "facts": {
            "competing_incident_ids": ["INC-2"],
            "shared_resource_ids": ["supplier_capacity:3055"],
            "recommended_winner": "INC-1",
        },
        "evidence_refs": {"guard_run_id": "GUARD-1"},
    }
    planner = {
        "incident_id": "INC-1",
        "run_id": "PLANNER-1",
        "facts": {
            "baseline": {
                "severity": "HIGH",
                "required_quantity": 420,
                "required_unit": "TON",
            },
            "recommended_option": {
                "option_id": "OPTION-1",
                "option_type": "expedite",
                "supplier_id": "3055",
                "incremental_cost_myr": 120000,
            },
        },
        "evidence_refs": {
            "guard_run_id": "GUARD-1",
            "portfolio_run_id": "PORTFOLIO-1",
        },
    }
    return guard, portfolio, planner


def test_build_policy_facts_uses_exact_lineage() -> None:
    guard, portfolio, planner = _rows()

    facts = build_policy_facts(
        incident_id="INC-1",
        guard=guard,
        portfolio=portfolio,
        planner=planner,
    )

    assert facts["lineage"]["guard_run_id"] == "GUARD-1"
    assert facts["portfolio"]["resource_contested"] is True
    assert facts["contract"]["expedite_allowed"] is False
    assert facts["candidate_supplier"]["active"] is True
    assert facts["recovery"]["governed_cost_myr"] == 120000
    assert facts["recovery"]["required_quantity"] == 420


def test_build_policy_facts_rejects_mismatched_lineage() -> None:
    guard, portfolio, planner = _rows()
    planner["evidence_refs"]["guard_run_id"] = "OTHER-GUARD"

    with pytest.raises(PolicyFactsError, match="does not reference"):
        build_policy_facts(
            incident_id="INC-1",
            guard=guard,
            portfolio=portfolio,
            planner=planner,
        )

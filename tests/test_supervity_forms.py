from app.services.supervity_forms import parse_supervity_user_form


def test_parse_supervity_user_form_extracts_context_and_controls_safely() -> None:
    parsed = parse_supervity_user_form({"html": """
            <div class="ag-card">
              <h2 class="ag-h2">Recovery Plan Review</h2>
              <p class="ag-body">Review the grounded recommendation.</p>
              <div class="ag-card">
                <span class="ag-muted">Incident ID</span>
                <p class="ag-body">INC-42</p>
              </div>
              <label for="reviewer-action">Reviewer Action</label>
              <select id="reviewer-action" name="Reviewer Action" required>
                <option value="">Select an action</option>
                <option value="Approve">Approve</option>
                <option value="Request replan">Request replan</option>
              </select>
              <label for="rationale">Decision Rationale</label>
              <textarea id="rationale" name="Decision Rationale"></textarea>
              <button formaction="https://example.test/submit">Submit</button>
              <script>window.evil = true</script>
            </div>
            """})

    assert parsed["title"] == "Recovery Plan Review"
    assert parsed["description"] == "Review the grounded recommendation."
    assert parsed["context"] == [{"label": "Incident ID", "value": "INC-42"}]
    assert parsed["fields"][0] == {
        "id": "reviewer-action",
        "name": "Reviewer Action",
        "label": "Reviewer Action",
        "type": "select",
        "required": True,
        "placeholder": None,
        "options": [
            {"value": "", "label": "Select an action"},
            {"value": "Approve", "label": "Approve"},
            {"value": "Request replan", "label": "Request replan"},
        ],
    }
    assert parsed["fields"][1]["type"] == "textarea"
    assert "html" not in parsed
    assert "formaction" not in str(parsed)
    assert "window.evil" not in str(parsed)


def test_parse_supervity_user_form_builds_human_review_summary() -> None:
    parsed = parse_supervity_user_form({"html": """
        <div class="ag-card">
          <h2 class="ag-h2">Recovery Plan Review</h2>
          <p class="ag-body">Review the grounded recommendation.</p>
          <div class="ag-card">
            <span class="ag-muted">Incident ID</span>
            <p class="ag-body">INC-5050</p>
          </div>
          <div class="ag-card">
            <span class="ag-muted">Severity</span>
            <p class="ag-body">MEDIUM</p>
          </div>
          <div class="ag-card">
            <span class="ag-muted">Decision lane</span>
            <p class="ag-body">human_review</p>
          </div>
          <div class="ag-card">
            <span class="ag-muted">Lane reasons</span>
            <pre class="ag-body">[
              "guard_requires_review",
              "action_not_auto_allowed",
              "cost_missing_or_above_auto_limit"
            ]</pre>
          </div>
          <div class="ag-card">
            <span class="ag-muted">Recommended option</span>
            <pre class="ag-body">{
              "option_id": "inventory:SKU-CEM-101:TH01",
              "option_type": "transfer_inventory",
              "source_location": "TH01",
              "destination_location": "MY02",
              "item_number": "SKU-CEM-101",
              "proposed_quantity": 318,
              "available_quantity": 400,
              "fulfills_required_quantity": true,
              "unit": "TON",
              "lead_time_days": 3,
              "incremental_cost_myr": null,
              "guard_verdict": "ALLOWED",
              "source_row_refs": ["inventory_positions:SKU-CEM-101@TH01"]
            }</pre>
          </div>
          <div class="ag-card">
            <span class="ag-muted">Options</span>
            <pre class="ag-body">[{
              "option_id": "inventory:SKU-CEM-101:TH01",
              "option_type": "transfer_inventory"
            }]</pre>
          </div>
          <div class="ag-card">
            <span class="ag-muted">Guard status</span>
            <pre class="ag-body">NEEDS_REVIEW</pre>
          </div>
          <div class="ag-card">
            <span class="ag-muted">Portfolio status</span>
            <pre class="ag-body">OK</pre>
          </div>
          <div class="ag-card">
            <span class="ag-muted">Governance decision</span>
            <pre class="ag-body">review</pre>
          </div>
          <div class="ag-card">
            <span class="ag-muted">Governance approval roles</span>
            <pre class="ag-body">["procurement_commander"]</pre>
          </div>
          <div class="ag-card">
            <span class="ag-muted">Governance policy references</span>
            <pre class="ag-body">[
              {"policy_id": "POL-GOVERNED-ACTION", "version": 1},
              {"policy_id": "POL-EXPEDITE-SPEND", "version": 2}
            ]</pre>
          </div>
          <div class="ag-card">
            <span class="ag-muted">Exact operator run IDs</span>
            <pre class="ag-body">{"guard": "RUN-GUARD", "planner": "RUN-PLAN"}</pre>
          </div>
        </div>
        """})

    summary = parsed["review_summary"]
    assert summary["incident_id"] == "INC-5050"
    assert summary["severity"] == "medium"
    assert summary["requires_human_review"] is True
    assert summary["recommendation"] == {
        "option_id": "inventory:SKU-CEM-101:TH01",
        "option_type": "transfer_inventory",
        "source_location": "TH01",
        "destination_location": "MY02",
        "item_number": "SKU-CEM-101",
        "proposed_quantity": 318,
        "available_quantity": 400,
        "fulfills_required_quantity": True,
        "unit": "TON",
        "lead_time_days": 3,
        "incremental_cost_myr": None,
        "guard_verdict": "ALLOWED",
        "source_row_refs": ["inventory_positions:SKU-CEM-101@TH01"],
    }
    assert summary["alternatives"] == []
    assert summary["review_reasons"][0]["explanation"] == (
        "The policy guard requires human approval."
    )
    assert summary["governance"]["approval_roles"] == [
        "Procurement Commander"
    ]
    assert summary["governance"]["policy_count"] == 2
    assert summary["technical_details"]["operator_run_ids"] == {
        "Guard": "RUN-GUARD",
        "Planner": "RUN-PLAN",
    }


def test_parse_supervity_user_form_handles_unfamiliar_or_malformed_context() -> None:
    parsed = parse_supervity_user_form({"html": """
        <div class="ag-card">
          <h2>Review</h2>
          <div class="ag-card">
            <span class="ag-muted">Lane reasons</span>
            <pre class="ag-body">not-json</pre>
          </div>
          <div class="ag-card">
            <span class="ag-muted">Recommended option</span>
            <pre class="ag-body">not-json</pre>
          </div>
        </div>
        """})

    assert parsed["review_summary"]["severity"] == "low"
    assert parsed["review_summary"]["recommendation"] is None
    assert parsed["review_summary"]["review_reasons"] == []

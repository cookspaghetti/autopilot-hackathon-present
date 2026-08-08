"""Safe, semantic parsing for Supervity Human Review forms."""

from __future__ import annotations

import json
from html.parser import HTMLParser
from typing import Any, Mapping


_REVIEW_REASON_EXPLANATIONS = {
    "portfolio_contention_or_review": (
        "This recovery may compete with other portfolio priorities or shared "
        "resources."
    ),
    "guard_requires_review": "The policy guard requires human approval.",
    "action_not_auto_allowed": (
        "This action type is not authorized for automatic execution."
    ),
    "cost_missing_or_above_auto_limit": (
        "The cost is missing or cannot be confirmed within the automatic "
        "approval limit."
    ),
}


def _humanize(value: str) -> str:
    return " ".join(value.replace("-", "_").split("_")).strip().title()


def _json_value(value: str, expected_type: type[Any]) -> Any:
    if not value.strip():
        return expected_type()
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError, json.JSONDecodeError):
        return expected_type()
    return parsed if isinstance(parsed, expected_type) else expected_type()


def _string(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _option(value: Mapping[str, Any]) -> dict[str, Any]:
    """Return only the decision-relevant portion of a recovery option."""
    string_fields = (
        "option_id",
        "option_type",
        "supplier_id",
        "source_location",
        "destination_location",
        "item_number",
        "unit",
        "guard_verdict",
    )
    number_fields = (
        "requested_quantity",
        "proposed_quantity",
        "available_quantity",
        "lead_time_days",
        "incremental_cost_myr",
    )
    normalized = {
        key: _string(value.get(key))
        for key in string_fields
        if key in value
    }
    normalized.update(
        {
            key: item
            for key in number_fields
            if key in value
            and (
                (item := value.get(key)) is None
                or (isinstance(item, (int, float)) and not isinstance(item, bool))
            )
        }
    )
    coverage = value.get("fulfills_required_quantity")
    if isinstance(coverage, bool):
        normalized["fulfills_required_quantity"] = coverage
    source_refs = value.get("source_row_refs")
    if isinstance(source_refs, list):
        normalized["source_row_refs"] = [
            item.strip()
            for item in source_refs
            if isinstance(item, str) and item.strip()
        ]
    return normalized


def _review_summary(context: list[dict[str, str]]) -> dict[str, Any] | None:
    values = {
        item["label"].strip().lower(): item["value"]
        for item in context
        if item.get("label")
    }
    recognized_labels = {
        "incident id",
        "severity",
        "current lane",
        "decision lane",
        "lane reasons",
        "recommended option",
        "options",
        "plan status",
        "guard status",
        "portfolio status",
        "governance decision",
        "governance approval roles",
        "governance policy references",
        "exact operator run ids",
    }
    if not recognized_labels.intersection(values):
        return None
    recommendation_raw = _json_value(values.get("recommended option", ""), dict)
    recommendation = _option(recommendation_raw) if recommendation_raw else None

    options = _json_value(values.get("options", ""), list)
    recommendation_id = (
        _string(recommendation.get("option_id")) if recommendation else None
    )
    alternatives = [
        _option(item)
        for item in options
        if isinstance(item, Mapping)
        and (
            recommendation_id is None
            or _string(item.get("option_id")) != recommendation_id
        )
    ]

    reason_codes = _json_value(values.get("lane reasons", ""), list)
    review_reasons = []
    for raw_code in reason_codes:
        code = _string(raw_code)
        if not code:
            continue
        review_reasons.append(
            {
                "code": code,
                "explanation": _REVIEW_REASON_EXPLANATIONS.get(
                    code,
                    f"{_humanize(code)} requires human consideration.",
                ),
            }
        )

    approval_roles = [
        _humanize(str(role))
        for role in _json_value(values.get("governance approval roles", ""), list)
        if _string(role)
    ]
    policy_references = [
        {
            "policy_id": _string(item.get("policy_id")),
            "version": (
                item.get("version")
                if isinstance(item.get("version"), (int, str))
                else None
            ),
        }
        for item in _json_value(
            values.get("governance policy references", ""), list
        )
        if isinstance(item, Mapping) and _string(item.get("policy_id"))
    ]
    operator_run_ids = {
        _humanize(str(key)): str(value)
        for key, value in _json_value(
            values.get("exact operator run ids", ""), dict
        ).items()
        if _string(value)
    }

    governance_decision = _string(values.get("governance decision"))
    plan_status = _string(values.get("plan status"))
    guard_status = _string(values.get("guard status"))
    decision_lane = _string(
        values.get("decision lane") or values.get("current lane")
    )
    requires_review = any(
        value and value.lower() in {"review", "needs_review", "human_review"}
        for value in (governance_decision, plan_status, guard_status, decision_lane)
    )

    return {
        "incident_id": _string(values.get("incident id")),
        "severity": (_string(values.get("severity")) or "low").lower(),
        "requires_human_review": requires_review,
        "recommendation": recommendation,
        "alternatives": alternatives,
        "review_reasons": review_reasons,
        "governance": {
            "decision": governance_decision,
            "guard_status": guard_status,
            "portfolio_status": _string(values.get("portfolio status")),
            "approval_roles": approval_roles,
            "policy_count": len(policy_references),
            "policy_references": policy_references,
        },
        "technical_details": {
            "operator_run_ids": operator_run_ids,
        },
    }


def _text(chunks: list[str], *, limit: int = 10_000) -> str:
    return " ".join("".join(chunks).split())[:limit]


class _UserFormHTMLParser(HTMLParser):
    """Extract display data and controls without retaining executable HTML."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[dict[str, Any]] = []
        self.title_chunks: list[str] = []
        self.body_paragraphs: list[str] = []
        self.context: list[dict[str, str]] = []
        self.fields: list[dict[str, Any]] = []
        self.labels: dict[str, str] = {}
        self._label_for: str | None = None
        self._label_chunks: list[str] = []
        self._title_depth: int | None = None
        self._paragraph_depth: int | None = None
        self._paragraph_chunks: list[str] = []
        self._select: dict[str, Any] | None = None
        self._option: dict[str, Any] | None = None

    @staticmethod
    def _attrs(attrs: list[tuple[str, str | None]]) -> dict[str, str]:
        return {key: value or "" for key, value in attrs}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = self._attrs(attrs)
        classes = set(attributes.get("class", "").split())
        node: dict[str, Any] = {"tag": tag, "classes": classes}
        if tag == "div" and "ag-card" in classes:
            node["card"] = {"label": [], "value": []}
        self.stack.append(node)

        if tag in {"h1", "h2"} and not self.title_chunks:
            self._title_depth = len(self.stack)
        if tag == "p" and "ag-body" in classes:
            self._paragraph_depth = len(self.stack)
            self._paragraph_chunks = []
        if tag == "label":
            self._label_for = attributes.get("for") or None
            self._label_chunks = []

        if tag in {"input", "select", "textarea"}:
            field_type = attributes.get("type", "text") if tag == "input" else tag
            if field_type not in {"hidden", "submit", "button"}:
                field = {
                    "id": attributes.get("id") or attributes.get("name") or "field",
                    "name": attributes.get("name") or attributes.get("id") or "field",
                    "label": "",
                    "type": field_type,
                    "required": "required" in attributes,
                    "placeholder": attributes.get("placeholder") or None,
                    "options": [],
                }
                self.fields.append(field)
                if tag == "select":
                    self._select = field

        if tag == "option" and self._select is not None:
            self._option = {
                "value": attributes.get("value", ""),
                "label_chunks": [],
            }

    def handle_data(self, data: str) -> None:
        if self._title_depth is not None:
            self.title_chunks.append(data)
        if self._paragraph_depth is not None:
            self._paragraph_chunks.append(data)
        if self._label_for is not None:
            self._label_chunks.append(data)
        if self._option is not None:
            self._option["label_chunks"].append(data)

        current = self.stack[-1] if self.stack else {}
        card = next(
            (node["card"] for node in reversed(self.stack) if "card" in node),
            None,
        )
        if card is None:
            return
        if current.get("tag") == "span" and "ag-muted" in current.get("classes", set()):
            card["label"].append(data)
        elif current.get("tag") in {"p", "pre"} and "ag-body" in current.get(
            "classes", set()
        ):
            card["value"].append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "label" and self._label_for is not None:
            self.labels[self._label_for] = _text(self._label_chunks, limit=500)
            self._label_for = None
            self._label_chunks = []
        if tag in {"h1", "h2"} and self._title_depth == len(self.stack):
            self._title_depth = None
        if tag == "p" and self._paragraph_depth == len(self.stack):
            paragraph = _text(self._paragraph_chunks)
            if paragraph:
                self.body_paragraphs.append(paragraph)
            self._paragraph_depth = None
            self._paragraph_chunks = []
        if tag == "option" and self._option is not None and self._select is not None:
            self._select["options"].append(
                {
                    "value": self._option["value"],
                    "label": _text(self._option["label_chunks"], limit=500),
                }
            )
            self._option = None
        if tag == "select":
            self._select = None

        if not self.stack:
            return
        node = self.stack.pop()
        card = node.get("card")
        if card is not None:
            label = _text(card["label"], limit=500)
            value = _text(card["value"])
            keep_empty = label.strip().lower() in {"recommended option"}
            if (
                label
                and label.upper() != "EXCEPTION COMMANDER"
                and (value or keep_empty)
            ):
                self.context.append({"label": label, "value": value})

    def result(self) -> dict[str, Any]:
        for field in self.fields:
            field["label"] = self.labels.get(field["id"]) or field["name"]
        description = next(
            (
                paragraph
                for paragraph in self.body_paragraphs
                if not paragraph.startswith("Statuses, options")
                and not paragraph.startswith("Required fields")
            ),
            "",
        )
        return {
            "title": _text(self.title_chunks, limit=500) or "Human Review",
            "description": description,
            "context": self.context[:50],
            "fields": self.fields[:50],
            "review_summary": _review_summary(self.context[:50]),
        }


def parse_supervity_user_form(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Return an allow-listed form model; raw HTML and action URLs are discarded."""

    html = payload.get("html")
    if not isinstance(html, str) or not html.strip():
        return {
            "title": "Human Review",
            "description": "",
            "context": [],
            "fields": [],
            "review_summary": _review_summary([]),
        }
    parser = _UserFormHTMLParser()
    parser.feed(html[:250_000])
    parser.close()
    return parser.result()

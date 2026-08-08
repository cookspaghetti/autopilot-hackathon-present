"""Deterministic procurement Insights generated from live Supabase rows."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from ..domain import EvidenceReference, Insight, InsightKind, Severity, utc_now
from .supabase import SupabaseClient


def _decimal(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value).replace(",", ""))
    except (InvalidOperation, ValueError):
        return None


def _date(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    raw = str(value).strip()
    candidates = [
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%b %d %Y",
        "%B %d %Y",
    ]
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        pass
    for pattern in candidates:
        try:
            return datetime.strptime(raw, pattern).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _evidence(
    entity_type: str, entity_id: str, fields: tuple[str, ...]
) -> EvidenceReference:
    return EvidenceReference(
        system="supabase",
        entity_type=entity_type,
        entity_id=entity_id,
        observed_at=utc_now(),
        fields=fields,
    )


class ProcurementInsightService:
    def __init__(self, client: SupabaseClient) -> None:
        self.client = client

    async def generate(self) -> list[Insight]:
        (
            tiers,
            alternatives,
            inventory,
            shipments,
            po_headers,
        ) = await asyncio.gather(
            self.client.fetch_rows("supplier_tiers"),
            self.client.fetch_rows("alternative_suppliers"),
            self.client.fetch_rows("inventory_positions"),
            self.client.fetch_rows("shipments"),
            self.client.fetch_rows("purchase_order_headers", select="id"),
        )
        insights = [
            self._tier_cascade(tiers),
            self._alternate_contention(alternatives),
            self._inventory_commitment(inventory),
            self._port_cutoff(shipments),
            self._orphan_shipments(shipments, po_headers),
        ]
        return [insight for insight in insights if insight is not None]

    def _tier_cascade(self, rows: list[dict[str, Any]]) -> Insight | None:
        dependencies: dict[str, set[str]] = defaultdict(set)
        evidence_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            depends_on = str(row.get("depends_on_supplier_id") or "").strip()
            parent = str(row.get("parent_supplier_id") or "").strip()
            if depends_on and parent:
                dependencies[depends_on].add(parent)
                evidence_rows[depends_on].append(row)
        if not dependencies:
            return None
        supplier_id, parents = max(dependencies.items(), key=lambda item: len(item[1]))
        source_rows = evidence_rows[supplier_id]
        return Insight(
            insight_id="INS-TIER-CASCADE",
            kind=InsightKind.PATTERN,
            severity=Severity.CRITICAL if len(parents) >= 5 else Severity.HIGH,
            title="Tier-two dependency concentration",
            summary=(
                f"Supplier {supplier_id} supports {len(parents)} parent suppliers, "
                "creating a concentrated cascade path."
            ),
            recommendation="Qualify a second tier-two source and pre-plan parent-supplier allocation.",
            evidence=tuple(
                _evidence(
                    "supplier_tier",
                    str(row.get("id")),
                    ("parent_supplier_id", "depends_on_supplier_id", "criticality"),
                )
                for row in source_rows
            ),
            affected_entity_ids=tuple(sorted(parents | {supplier_id})),
            action_type="open_workbench",
            action_payload={"supplier_id": supplier_id},
            created_at=utc_now(),
        )

    def _alternate_contention(self, rows: list[dict[str, Any]]) -> Insight | None:
        items_by_supplier: dict[str, set[str]] = defaultdict(set)
        rows_by_supplier: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            supplier = str(row.get("supplier_id") or "").strip()
            item = str(row.get("item_number") or "").strip()
            if supplier and item:
                items_by_supplier[supplier].add(item)
                rows_by_supplier[supplier].append(row)
        contested = [item for item in items_by_supplier.items() if len(item[1]) > 1]
        if not contested:
            return None
        supplier_id, items = max(contested, key=lambda item: len(item[1]))
        return Insight(
            insight_id="INS-ALTERNATE-CONTENTION",
            kind=InsightKind.ANOMALY,
            severity=Severity.HIGH,
            title="One alternate is shared across disrupted items",
            summary=(
                f"Alternate supplier {supplier_id} has active quotes across "
                f"{len(items)} items ({', '.join(sorted(items))}). Independent plans can double-book capacity."
            ),
            recommendation="Reserve capacity at portfolio level before selecting an alternate.",
            evidence=tuple(
                _evidence(
                    "alternative_supplier",
                    str(row.get("id")),
                    ("item_number", "supplier_id", "lead_time_days", "valid_until"),
                )
                for row in rows_by_supplier[supplier_id]
            ),
            affected_entity_ids=tuple(sorted(items | {supplier_id})),
            action_type="open_workbench",
            action_payload={"supplier_id": supplier_id, "items": sorted(items)},
            created_at=utc_now(),
        )

    def _inventory_commitment(self, rows: list[dict[str, Any]]) -> Insight | None:
        stressed: list[tuple[dict[str, Any], Decimal, Decimal]] = []
        for row in rows:
            on_hand = _decimal(row.get("on_hand_qty"))
            committed = _decimal(row.get("committed_qty")) or Decimal("0")
            safety = _decimal(row.get("safety_stock"))
            if on_hand is None or safety is None:
                continue
            net = on_hand - committed
            if net < safety:
                stressed.append((row, net, safety))
        if not stressed:
            return None
        stressed.sort(key=lambda item: item[1] - item[2])
        top = stressed[0]
        row, net, safety = top
        return Insight(
            insight_id="INS-NET-INVENTORY",
            kind=InsightKind.ANOMALY,
            severity=Severity.CRITICAL if net <= 0 else Severity.HIGH,
            title="Committed stock hides an inventory shortfall",
            summary=(
                f"{len(stressed)} item-location positions fall below safety stock after commitments. "
                f"{row.get('item_number')} at {row.get('location')} has {net} net units versus {safety} safety stock."
            ),
            recommendation="Use net available inventory for recovery planning and protect committed customer orders.",
            evidence=tuple(
                _evidence(
                    "inventory_position",
                    f"{item.get('item_number')}:{item.get('location')}",
                    ("on_hand_qty", "committed_qty", "safety_stock"),
                )
                for item, _, _ in stressed
            ),
            affected_entity_ids=tuple(
                f"{item.get('item_number')}:{item.get('location')}"
                for item, _, _ in stressed
            ),
            action_type="open_workbench",
            action_payload={
                "item_number": row.get("item_number"),
                "location": row.get("location"),
            },
            created_at=utc_now(),
        )

    def _port_cutoff(self, rows: list[dict[str, Any]]) -> Insight | None:
        late = []
        for row in rows:
            if str(row.get("status", "")).lower() == "delivered":
                continue
            cutoff = _date(row.get("port_cutoff"))
            eta = _date(row.get("eta"))
            if cutoff and eta and eta > cutoff:
                late.append(row)
        if not late:
            return None
        return Insight(
            insight_id="INS-PORT-CUTOFF",
            kind=InsightKind.PATTERN,
            severity=Severity.HIGH,
            title="Active shipments are projected beyond port cutoff",
            summary=f"{len(late)} active shipments have ETA later than their recorded cutoff.",
            recommendation="Group affected POs by port and reserve the next feasible sailing as a portfolio action.",
            evidence=tuple(
                _evidence(
                    "shipment",
                    str(row.get("id")),
                    ("po_header_id", "origin_port", "port_cutoff", "eta", "status"),
                )
                for row in late
            ),
            affected_entity_ids=tuple(str(row.get("id")) for row in late),
            action_type="open_workbench",
            action_payload={"shipment_ids": [row.get("id") for row in late]},
            created_at=utc_now(),
        )

    def _orphan_shipments(
        self,
        shipments: list[dict[str, Any]],
        po_headers: list[dict[str, Any]],
    ) -> Insight | None:
        valid = {str(row.get("id")) for row in po_headers}
        orphans = [
            row for row in shipments if str(row.get("po_header_id") or "") not in valid
        ]
        if not orphans:
            return None
        return Insight(
            insight_id="INS-ORPHAN-SHIPMENT",
            kind=InsightKind.ANOMALY,
            severity=Severity.MEDIUM,
            title="Shipment references an unknown purchase order",
            summary=f"{len(orphans)} shipment records cannot be joined to the PO header source.",
            recommendation="Quarantine the records and request source-system reconciliation before acting.",
            evidence=tuple(
                _evidence(
                    "shipment",
                    str(row.get("id")),
                    ("po_header_id", "carrier", "status"),
                )
                for row in orphans
            ),
            affected_entity_ids=tuple(str(row.get("id")) for row in orphans),
            action_type="open_workbench",
            action_payload={"shipment_ids": [row.get("id") for row in orphans]},
            created_at=utc_now(),
        )

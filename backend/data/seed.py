"""
Seed data for the Dig Once MVP demonstration.
Corridor: Whitefield–Mahadevapura corridor, Bengaluru.
DEMO DATA ONLY — not official government infrastructure data.
"""
from __future__ import annotations
from datetime import date, datetime
from copy import deepcopy
from backend.models import (
    WorkOrder, WorkOrderStatus, Department, Priority,
    Corridor, PolicyRule, PolicyStatus
)

# ── Corridor ─────────────────────────────────────────────────────────────────

CORRIDORS: list[Corridor] = [
    Corridor(
        id="COR-001",
        name="Whitefield–Mahadevapura Demo Corridor",
        description="DEMO: Arterial corridor from Mahadevapura to Whitefield, Bengaluru. ~8 km stretch. Not official data.",
        resurfacing_planned_date=date(2026, 12, 1),
        resurfacing_moratorium_days=365,
        lat=12.9784,
        lon=77.7480,
    )
]

# ── Work Orders ───────────────────────────────────────────────────────────────
# Six orders across four departments; two deliberate conflicts seeded.

_SEED_WORK_ORDERS: list[WorkOrder] = [
    # WO-101: Water main replacement — flexible window
    WorkOrder(
        id="WO-101",
        department=Department.WATER,
        corridor_id="COR-001",
        description="DEMO: Water main rehabilitation — 600mm trunk main replacement, 1.2 km section near Mahadevapura junction.",
        start_window=date(2026, 10, 1),
        end_window=date(2026, 12, 31),
        duration_days=14,
        deadline=date(2026, 12, 15),
        priority=Priority.HIGH,
        delay_cost_per_day=45000.0,
        flexibility_days=30,
        dependencies=[],
        status=WorkOrderStatus.PENDING,
        proposed_start=date(2026, 11, 20),  # CONFLICT: clashes with resurfacing
        proposed_end=date(2026, 12, 3),
        created_at=datetime(2026, 9, 1, 9, 0),
        is_emergency=False,
    ),
    # WO-102: Power cable duct — can share trench with fibre
    WorkOrder(
        id="WO-102",
        department=Department.POWER,
        corridor_id="COR-001",
        description="DEMO: BESCOM underground cabling — 33kV feeder duct installation, 0.8 km section.",
        start_window=date(2026, 10, 1),
        end_window=date(2026, 11, 30),
        duration_days=7,
        deadline=date(2026, 11, 30),
        priority=Priority.MEDIUM,
        delay_cost_per_day=30000.0,
        flexibility_days=14,
        dependencies=[],
        status=WorkOrderStatus.PENDING,
        proposed_start=date(2026, 11, 1),
        proposed_end=date(2026, 11, 7),
        created_at=datetime(2026, 9, 5, 10, 0),
        is_emergency=False,
    ),
    # WO-103: Fibre installation — overlaps with WO-102 (CONFLICT — same dates, same trench)
    WorkOrder(
        id="WO-103",
        department=Department.FIBRE,
        corridor_id="COR-001",
        description="DEMO: Jio/Airtel dark-fibre conduit installation along same 0.8 km section.",
        start_window=date(2026, 10, 1),
        end_window=date(2026, 11, 30),
        duration_days=5,
        deadline=date(2026, 11, 25),
        priority=Priority.MEDIUM,
        delay_cost_per_day=12000.0,
        flexibility_days=20,
        dependencies=[],
        status=WorkOrderStatus.PENDING,
        proposed_start=date(2026, 11, 1),  # CONFLICT: overlaps with WO-102 same corridor
        proposed_end=date(2026, 11, 5),
        created_at=datetime(2026, 9, 6, 11, 0),
        is_emergency=False,
    ),
    # WO-104: Road resurfacing — the anchor event
    WorkOrder(
        id="WO-104",
        department=Department.ROAD,
        corridor_id="COR-001",
        description="DEMO: Full-depth reclamation and hot-mix asphalt resurfacing of entire 8 km corridor.",
        start_window=date(2026, 12, 1),
        end_window=date(2026, 12, 15),
        duration_days=10,
        deadline=date(2026, 12, 15),
        priority=Priority.CRITICAL,
        delay_cost_per_day=80000.0,
        flexibility_days=5,
        dependencies=[],
        status=WorkOrderStatus.APPROVED,
        proposed_start=date(2026, 12, 1),
        proposed_end=date(2026, 12, 10),
        created_at=datetime(2026, 8, 1, 8, 0),
        is_emergency=False,
    ),
    # WO-105: Stormwater drain — must finish before resurfacing
    WorkOrder(
        id="WO-105",
        department=Department.WATER,
        corridor_id="COR-001",
        description="DEMO: BBMP stormwater drain rehabilitation — lateral connections and manhole covers, 0.5 km.",
        start_window=date(2026, 10, 15),
        end_window=date(2026, 11, 30),
        duration_days=6,
        deadline=date(2026, 11, 28),
        priority=Priority.HIGH,
        delay_cost_per_day=18000.0,
        flexibility_days=10,
        dependencies=[],
        status=WorkOrderStatus.PENDING,
        proposed_start=date(2026, 11, 10),
        proposed_end=date(2026, 11, 15),
        created_at=datetime(2026, 9, 10, 9, 30),
        is_emergency=False,
    ),
    # WO-106: Telecom duct — late booking, post-resurfacing risk
    WorkOrder(
        id="WO-106",
        department=Department.FIBRE,
        corridor_id="COR-001",
        description="DEMO: BSNL FTTH rollout — micro-trenching for last-mile fibre, 1.0 km section.",
        start_window=date(2026, 11, 1),
        end_window=date(2027, 1, 31),
        duration_days=8,
        deadline=date(2027, 1, 15),
        priority=Priority.LOW,
        delay_cost_per_day=5000.0,
        flexibility_days=60,
        dependencies=[],
        status=WorkOrderStatus.PENDING,
        proposed_start=date(2027, 1, 5),   # Would cut freshly resurfaced road! Well inside moratorium.
        proposed_end=date(2027, 1, 12),
        created_at=datetime(2026, 10, 1, 14, 0),
        is_emergency=False,
    ),
]

# Keep original for reset
_ORIGINAL_SEED = deepcopy(_SEED_WORK_ORDERS)

# ── Default Policies ──────────────────────────────────────────────────────────

DEFAULT_POLICIES: list[PolicyRule] = [
    PolicyRule(
        id="POL-001",
        name="Post-Resurfacing Excavation Moratorium",
        description="No excavation permitted within 365 days of road resurfacing on the same corridor.",
        rule_type="resurfacing",
        parameters={"moratorium_days": 365},
        status=PolicyStatus.APPROVED,
        proposed_by="system",
        proposed_at=datetime(2026, 1, 1),
        approved_at=datetime(2026, 1, 1),
    ),
    PolicyRule(
        id="POL-002",
        name="Concurrent Trench Sharing",
        description="Two or more utility orders on the same corridor within 7 days should share a single trench opening.",
        rule_type="overlap",
        parameters={"window_days": 7, "max_concurrent": 2},
        status=PolicyStatus.APPROVED,
        proposed_by="system",
        proposed_at=datetime(2026, 1, 1),
        approved_at=datetime(2026, 1, 1),
    ),
    PolicyRule(
        id="POL-003",
        name="Exam Period Excavation Restriction (Demo)",
        description="DEMO POLICY: No excavation within 200m of a designated school during the configured exam window.",
        rule_type="restricted_period",
        parameters={
            "label": "Exam Season",
            "start_date": "2026-10-15",
            "end_date": "2026-10-30",
            "radius_meters": 200,
            "affected_corridors": ["COR-001"],
        },
        status=PolicyStatus.PROPOSED,
        proposed_by="coordinator",
        proposed_at=datetime(2026, 9, 20),
    ),
]


# ── Public accessors (mutated in-place for demo state) ────────────────────────

_work_orders: list[WorkOrder] = deepcopy(_SEED_WORK_ORDERS)
_policies: list[PolicyRule] = deepcopy(DEFAULT_POLICIES)


def get_work_orders() -> list[WorkOrder]:
    return _work_orders


def get_corridors() -> list[Corridor]:
    return CORRIDORS


def get_policies() -> list[PolicyRule]:
    return _policies


def add_work_order(wo: WorkOrder) -> None:
    _work_orders.append(wo)


def update_work_order(wo: WorkOrder) -> None:
    for i, existing in enumerate(_work_orders):
        if existing.id == wo.id:
            _work_orders[i] = wo
            return


def get_work_order_by_id(wo_id: str) -> WorkOrder | None:
    for wo in _work_orders:
        if wo.id == wo_id:
            return wo
    return None


def add_policy(policy: PolicyRule) -> None:
    _policies.append(policy)


def update_policy(policy: PolicyRule) -> None:
    for i, existing in enumerate(_policies):
        if existing.id == policy.id:
            _policies[i] = policy
            return


def get_policy_by_id(policy_id: str) -> PolicyRule | None:
    for p in _policies:
        if p.id == policy_id:
            return p
    return None


def reset_demo_data() -> None:
    """Restore seed state so the demo can be repeated."""
    global _work_orders, _policies
    _work_orders = deepcopy(_ORIGINAL_SEED)
    _policies = deepcopy(DEFAULT_POLICIES)

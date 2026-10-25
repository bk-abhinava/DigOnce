"""
Conflict detection service.
Identifies overlaps, resurfacing conflicts, deadline violations, and dependency issues.
"""
from __future__ import annotations
from datetime import date, timedelta
from typing import List
import uuid

from backend.models import (
    WorkOrder, Corridor, Conflict, ConflictType, Department
)


def _date_ranges_overlap(
    s1: date, e1: date, s2: date, e2: date, grace_days: int = 0
) -> bool:
    """Return True if [s1,e1] overlaps [s2,e2] after shrinking by grace_days."""
    return s1 <= (e2 - timedelta(days=grace_days)) and s2 <= (e1 - timedelta(days=grace_days))


def detect_conflicts(
    work_orders: List[WorkOrder],
    corridors: List[Corridor],
) -> List[Conflict]:
    """
    Run all conflict detection rules and return a deduplicated list.
    """
    conflicts: list[Conflict] = []
    corridor_map = {c.id: c for c in corridors}

    active = [
        wo for wo in work_orders
        if wo.proposed_start and wo.proposed_end
        and wo.status not in ("cancelled", "completed")
    ]

    # ── Rule 1: Department work overlap (same corridor, overlapping dates) ────
    for i in range(len(active)):
        for j in range(i + 1, len(active)):
            a, b = active[i], active[j]
            if a.corridor_id != b.corridor_id:
                continue
            if a.department == b.department:
                continue  # Same dept can share trench (handled separately)
            if _date_ranges_overlap(a.proposed_start, a.proposed_end, b.proposed_start, b.proposed_end):
                conflicts.append(Conflict(
                    id=f"CON-{uuid.uuid4().hex[:6].upper()}",
                    conflict_type=ConflictType.OVERLAP,
                    work_order_ids=[a.id, b.id],
                    description=(
                        f"Work orders {a.id} ({a.department.value}) and {b.id} "
                        f"({b.department.value}) overlap on corridor {a.corridor_id}: "
                        f"{a.proposed_start} – {a.proposed_end} vs "
                        f"{b.proposed_start} – {b.proposed_end}. "
                        f"Coordinate to share trench or stagger work."
                    ),
                    severity="high" if (a.priority in ("critical", "high") or b.priority in ("critical", "high")) else "medium",
                ))

    # ── Rule 2: Post-resurfacing excavation ───────────────────────────────────
    for wo in active:
        if wo.department == Department.ROAD:
            continue
        corridor = corridor_map.get(wo.corridor_id)
        if not corridor or not corridor.resurfacing_planned_date:
            continue
        resurfacing_end = corridor.resurfacing_planned_date + timedelta(days=14)
        moratorium_end = resurfacing_end + timedelta(days=corridor.resurfacing_moratorium_days)
        if wo.proposed_start >= resurfacing_end and wo.proposed_start < moratorium_end:
            conflicts.append(Conflict(
                id=f"CON-{uuid.uuid4().hex[:6].upper()}",
                conflict_type=ConflictType.RESURFACING,
                work_order_ids=[wo.id],
                description=(
                    f"Work order {wo.id} ({wo.department.value}) proposes excavation "
                    f"starting {wo.proposed_start}, which is {(wo.proposed_start - resurfacing_end).days} days "
                    f"after resurfacing completes ({resurfacing_end}). "
                    f"Moratorium: {corridor.resurfacing_moratorium_days} days. "
                    f"Move excavation before {corridor.resurfacing_planned_date} or after {moratorium_end}."
                ),
                severity="high",
            ))

    # ── Rule 3: Deadline violations ───────────────────────────────────────────
    for wo in active:
        if wo.proposed_end and wo.proposed_end > wo.deadline:
            days_late = (wo.proposed_end - wo.deadline).days
            conflicts.append(Conflict(
                id=f"CON-{uuid.uuid4().hex[:6].upper()}",
                conflict_type=ConflictType.DEADLINE,
                work_order_ids=[wo.id],
                description=(
                    f"Work order {wo.id} ({wo.department.value}) proposed end date "
                    f"{wo.proposed_end} exceeds deadline {wo.deadline} by {days_late} day(s)."
                ),
                severity="high" if wo.priority in ("critical", "high") else "medium",
            ))

    # ── Rule 4: Dependency ordering ───────────────────────────────────────────
    wo_map = {wo.id: wo for wo in work_orders}
    for wo in active:
        for dep_id in wo.dependencies:
            dep = wo_map.get(dep_id)
            if not dep or not dep.proposed_end or not wo.proposed_start:
                continue
            if wo.proposed_start < dep.proposed_end:
                conflicts.append(Conflict(
                    id=f"CON-{uuid.uuid4().hex[:6].upper()}",
                    conflict_type=ConflictType.DEPENDENCY,
                    work_order_ids=[wo.id, dep_id],
                    description=(
                        f"Work order {wo.id} depends on {dep_id} completing first "
                        f"but starts {wo.proposed_start} before {dep_id} ends {dep.proposed_end}."
                    ),
                    severity="high",
                ))

    return conflicts

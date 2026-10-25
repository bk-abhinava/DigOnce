"""
Deterministic validation service.
Validates proposed schedules against hard and soft constraints.
Never trusts an agent's claim that a schedule is valid.
"""
from __future__ import annotations
from datetime import date, timedelta, datetime, UTC
from typing import List

from backend.models import (
    ScheduledItem, ValidationResult, ValidationViolation, Corridor,
    WorkOrder, PolicyRule, Department
)


def validate_plan(
    items: List[ScheduledItem],
    work_orders: List[WorkOrder],
    corridor: Corridor,
    policies: List[PolicyRule],
) -> ValidationResult:
    """
    Run all validation rules.  Returns structured ValidationResult.
    Hard violations → valid=False.
    Soft violations → warnings only.
    """
    violations: list[ValidationViolation] = []
    warnings: list[str] = []
    explanations: list[str] = []
    affected_wo: set[str] = set()

    wo_map = {wo.id: wo for wo in work_orders}
    item_map = {i.work_order_id: i for i in items}

    # ── V1: Date format / range sanity ────────────────────────────────────────
    for item in items:
        if item.proposed_end < item.proposed_start:
            violations.append(ValidationViolation(
                rule="DATE_RANGE",
                severity="hard",
                work_order_ids=[item.work_order_id],
                description=f"{item.work_order_id}: end date {item.proposed_end} is before start {item.proposed_start}.",
            ))
            affected_wo.add(item.work_order_id)

        expected_days = (item.proposed_end - item.proposed_start).days + 1
        if expected_days != item.duration_days:
            violations.append(ValidationViolation(
                rule="DURATION_MISMATCH",
                severity="hard",
                work_order_ids=[item.work_order_id],
                description=(
                    f"{item.work_order_id}: duration_days={item.duration_days} "
                    f"but date span is {expected_days} days."
                ),
            ))
            affected_wo.add(item.work_order_id)

    # ── V2: Work-order window compliance ──────────────────────────────────────
    for item in items:
        wo = wo_map.get(item.work_order_id)
        if not wo:
            continue
        if item.proposed_start < wo.start_window:
            violations.append(ValidationViolation(
                rule="WINDOW_VIOLATION",
                severity="hard",
                work_order_ids=[item.work_order_id],
                description=(
                    f"{item.work_order_id}: proposed start {item.proposed_start} "
                    f"is before allowed window start {wo.start_window}."
                ),
            ))
            affected_wo.add(item.work_order_id)
        if item.proposed_start > wo.end_window:
            violations.append(ValidationViolation(
                rule="WINDOW_VIOLATION",
                severity="hard",
                work_order_ids=[item.work_order_id],
                description=(
                    f"{item.work_order_id}: proposed start {item.proposed_start} "
                    f"is after allowed window end {wo.end_window}."
                ),
            ))
            affected_wo.add(item.work_order_id)

    # ── V3: Deadline compliance ───────────────────────────────────────────────
    for item in items:
        wo = wo_map.get(item.work_order_id)
        if not wo:
            continue
        if item.proposed_end > wo.deadline:
            severity = "hard" if wo.priority in ("critical", "high") else "soft"
            violations.append(ValidationViolation(
                rule="DEADLINE_VIOLATION",
                severity=severity,
                work_order_ids=[item.work_order_id],
                description=(
                    f"{item.work_order_id}: proposed end {item.proposed_end} "
                    f"exceeds deadline {wo.deadline} by "
                    f"{(item.proposed_end - wo.deadline).days} day(s)."
                ),
            ))
            affected_wo.add(item.work_order_id)

    # ── V4: Resurfacing moratorium ────────────────────────────────────────────
    if corridor.resurfacing_planned_date:
        resurfacing_end = corridor.resurfacing_planned_date + timedelta(days=14)
        moratorium_end = resurfacing_end + timedelta(days=corridor.resurfacing_moratorium_days)
        for item in items:
            if item.department == Department.ROAD:
                continue
            if resurfacing_end <= item.proposed_start < moratorium_end:
                violations.append(ValidationViolation(
                    rule="RESURFACING_MORATORIUM",
                    severity="hard",
                    work_order_ids=[item.work_order_id],
                    description=(
                        f"{item.work_order_id}: excavation starts {item.proposed_start}, "
                        f"which violates the {corridor.resurfacing_moratorium_days}-day moratorium "
                        f"after resurfacing (moratorium ends {moratorium_end})."
                    ),
                ))
                affected_wo.add(item.work_order_id)

    # ── V5: Dependency ordering ───────────────────────────────────────────────
    for item in items:
        wo = wo_map.get(item.work_order_id)
        if not wo:
            continue
        for dep_id in wo.dependencies:
            dep_item = item_map.get(dep_id)
            dep_wo = wo_map.get(dep_id)
            # Dependency must end before this item starts
            dep_end = dep_item.proposed_end if dep_item else (dep_wo.proposed_end if dep_wo else None)
            if dep_end and item.proposed_start <= dep_end:
                violations.append(ValidationViolation(
                    rule="DEPENDENCY_ORDER",
                    severity="hard",
                    work_order_ids=[item.work_order_id, dep_id],
                    description=(
                        f"{item.work_order_id} depends on {dep_id} "
                        f"but starts {item.proposed_start} before {dep_id} ends {dep_end}."
                    ),
                ))
                affected_wo.update([item.work_order_id, dep_id])

    # ── V6: Policy-based restricted periods ──────────────────────────────────
    for policy in policies:
        if policy.status != "approved":
            continue
        if policy.rule_type == "restricted_period":
            params = policy.parameters
            try:
                r_start = date.fromisoformat(params["start_date"])
                r_end = date.fromisoformat(params["end_date"])
                affected_corridors = params.get("affected_corridors", [])
            except (KeyError, ValueError):
                warnings.append(f"Policy {policy.id} has invalid parameters — skipped.")
                continue
            for item in items:
                if affected_corridors and item_map.get(item.work_order_id):
                    wo = wo_map.get(item.work_order_id)
                    if wo and wo.corridor_id not in affected_corridors:
                        continue
                if item.department == Department.ROAD:
                    continue
                if item.proposed_start <= r_end and item.proposed_end >= r_start:
                    violations.append(ValidationViolation(
                        rule=f"POLICY_{policy.id}",
                        severity="soft",
                        work_order_ids=[item.work_order_id],
                        description=(
                            f"Policy '{policy.name}': work order {item.work_order_id} "
                            f"is scheduled during restricted period {r_start} – {r_end}."
                        ),
                    ))
                    warnings.append(
                        f"{item.work_order_id} conflicts with policy '{policy.name}'."
                    )

    # ── Soft: Trench sharing opportunity ──────────────────────────────────────
    utility_items = [i for i in items if i.department != Department.ROAD]
    for i in range(len(utility_items)):
        for j in range(i + 1, len(utility_items)):
            a, b = utility_items[i], utility_items[j]
            delta = abs((a.proposed_start - b.proposed_start).days)
            if 0 < delta <= 14:
                warnings.append(
                    f"Trench-sharing opportunity: {a.work_order_id} ({a.proposed_start}) "
                    f"and {b.work_order_id} ({b.proposed_start}) are {delta} days apart — "
                    f"consider bundling."
                )

    # ── Score ─────────────────────────────────────────────────────────────────
    hard_count = sum(1 for v in violations if v.severity == "hard")
    score = max(0.0, round(100 - hard_count * 25 - len(warnings) * 2, 1))
    score_breakdown = {
        "base": 100,
        "hard_violations": -hard_count * 25,
        "warnings": -len(warnings) * 2,
    }

    valid = hard_count == 0

    if valid:
        explanations.append("All hard constraints satisfied.")
    else:
        explanations.append(f"{hard_count} hard constraint(s) violated — plan cannot be approved.")

    return ValidationResult(
        valid=valid,
        violations=violations,
        warnings=warnings,
        affected_work_orders=list(affected_wo),
        explanations=explanations,
        validated_at=datetime.now(UTC),
        score=score,
        score_breakdown=score_breakdown,
    )

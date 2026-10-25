"""
Deterministic scheduling engine.
Greedy scheduler that minimizes road openings, delay cost, and resurfacing conflicts.
OR-Tools is not required; this is a documented deterministic fallback.
"""
from __future__ import annotations
from datetime import date, timedelta
from typing import List

from backend.models import (
    WorkOrder, Corridor, ScheduledItem, PlanMetrics, Department
)


def _effective_end(start: date, duration_days: int) -> date:
    """Inclusive end: start + duration - 1 days."""
    return start + timedelta(days=duration_days - 1)


def _can_bundle(a: WorkOrder, b: WorkOrder, window_days: int = 7) -> bool:
    """Two orders can share a trench if they start within window_days of each other."""
    if not a.proposed_start or not b.proposed_start:
        return False
    return abs((a.proposed_start - b.proposed_start).days) <= window_days


def _respects_resurfacing(start: date, corridor: Corridor) -> bool:
    """True if start is before resurfacing or after moratorium."""
    if not corridor.resurfacing_planned_date:
        return True
    resurfacing_end = corridor.resurfacing_planned_date + timedelta(days=14)
    moratorium_end = resurfacing_end + timedelta(days=corridor.resurfacing_moratorium_days)
    return start < corridor.resurfacing_planned_date or start >= moratorium_end


def schedule(
    work_orders: List[WorkOrder],
    corridor: Corridor,
) -> tuple[List[ScheduledItem], str]:
    """
    Greedy scheduler.
    Strategy:
      1. Sort by priority, then deadline, then delay_cost.
      2. For each order: place as early as feasible inside its window.
      3. Bundle compatible utilities (same corridor within 7 days).
      4. Enforce resurfacing moratorium.
    Returns (items, explanation_text).
    """
    items: list[ScheduledItem] = []
    explanation_lines: list[str] = []

    # Sort: critical first, then earliest deadline, then highest delay cost
    priority_rank = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    sorted_orders = sorted(
        work_orders,
        key=lambda w: (priority_rank.get(w.priority, 3), w.deadline, -w.delay_cost_per_day),
    )

    placed: list[ScheduledItem] = []

    def find_earliest_start(wo: WorkOrder) -> date | None:
        """Find earliest valid start within the work order's window."""
        candidate = wo.start_window
        resurfacing_start = corridor.resurfacing_planned_date

        # Don't schedule road-dept before its window
        while candidate <= wo.end_window:
            cand_end = _effective_end(candidate, wo.duration_days)

            # Resurfacing check (skip for road dept)
            if wo.department != Department.ROAD:
                if not _respects_resurfacing(candidate, corridor):
                    # Jump to after moratorium
                    if resurfacing_start:
                        resurfacing_end = resurfacing_start + timedelta(days=14)
                        moratorium_end = resurfacing_end + timedelta(days=corridor.resurfacing_moratorium_days)
                        candidate = moratorium_end
                        continue

            # Deadline check
            if cand_end > wo.deadline:
                return None

            # Bundle opportunity: look for already-placed utility to share trench
            bundle_with = None
            for existing in placed:
                if (existing.department != wo.department
                        and wo.department != Department.ROAD
                        and existing.department != Department.ROAD
                        and _can_bundle_item(candidate, existing, 7)):
                    bundle_with = existing
                    break

            if bundle_with:
                # Align start with bundle partner
                explanation_lines.append(
                    f"{wo.id}: bundled with {bundle_with.work_order_id} "
                    f"(shared trench starting {bundle_with.proposed_start})"
                )
                candidate = bundle_with.proposed_start

            return candidate if candidate >= wo.start_window else None
        return None

    for wo in sorted_orders:
        if wo.department == Department.ROAD:
            # Road dept uses its own fixed window
            proposed_start = wo.start_window
        else:
            proposed_start = find_earliest_start(wo)

        if proposed_start is None:
            # Fallback: use original proposed dates or window start
            proposed_start = wo.proposed_start or wo.start_window
            explanation_lines.append(
                f"{wo.id}: could not find feasible slot — using original proposed date {proposed_start}."
            )

        proposed_end = _effective_end(proposed_start, wo.duration_days)

        item = ScheduledItem(
            work_order_id=wo.id,
            department=wo.department,
            description=wo.description,
            proposed_start=proposed_start,
            proposed_end=proposed_end,
            duration_days=wo.duration_days,
            reason=_generate_reason(wo, proposed_start, corridor),
            delay_cost=_compute_delay_cost(wo, proposed_start),
        )
        items.append(item)
        placed.append(item)

    explanation = (
        "Greedy scheduler placed work orders by priority and deadline. "
        + " ".join(explanation_lines)
        if explanation_lines
        else "All work orders placed within their allowed windows respecting resurfacing moratorium."
    )
    return items, explanation


def _can_bundle_item(candidate: date, existing: ScheduledItem, window_days: int) -> bool:
    return abs((candidate - existing.proposed_start).days) <= window_days


def _generate_reason(wo: WorkOrder, proposed_start: date, corridor: Corridor) -> str:
    if wo.proposed_start and proposed_start != wo.proposed_start:
        delta = (proposed_start - wo.proposed_start).days
        direction = "earlier" if delta < 0 else "later"
        return (
            f"Rescheduled {abs(delta)} days {direction} from original "
            f"{wo.proposed_start} to coordinate with corridor plan."
        )
    return "Placed at earliest feasible date within allowed window."


def _compute_delay_cost(wo: WorkOrder, proposed_start: date) -> float:
    if not wo.proposed_start:
        return 0.0
    delay = max(0, (proposed_start - wo.proposed_start).days)
    return round(delay * wo.delay_cost_per_day, 2)


def compute_baseline_metrics(work_orders: List[WorkOrder], corridor: Corridor) -> PlanMetrics:
    """Metrics for the un-coordinated (original) schedule."""
    active = [
        wo for wo in work_orders
        if wo.proposed_start and wo.proposed_end
        and wo.status not in ("cancelled", "completed")
    ]
    road_openings = _count_road_openings(active)
    resurfacing_conflicts = _count_resurfacing_conflicts(active, corridor)
    total_work_days = sum(wo.duration_days for wo in active)
    total_delay_cost = 0.0  # Baseline has no additional delay
    hard_violations = resurfacing_conflicts + sum(
        1 for wo in active if wo.proposed_end and wo.proposed_end > wo.deadline
    )
    score = _compute_score(road_openings, resurfacing_conflicts, total_delay_cost, hard_violations)
    return PlanMetrics(
        road_openings=road_openings,
        resurfacing_conflicts=resurfacing_conflicts,
        total_work_days=total_work_days,
        total_delay_cost=total_delay_cost,
        hard_violations=hard_violations,
        score=score,
    )


def compute_optimized_metrics(items: List[ScheduledItem], corridor: Corridor) -> PlanMetrics:
    """Metrics for the coordinated schedule."""
    road_openings = _count_road_openings_items(items)
    resurfacing_conflicts = _count_resurfacing_conflicts_items(items, corridor)
    total_work_days = sum(i.duration_days for i in items)
    total_delay_cost = sum(i.delay_cost for i in items)
    hard_violations = resurfacing_conflicts
    score = _compute_score(road_openings, resurfacing_conflicts, total_delay_cost, hard_violations)
    return PlanMetrics(
        road_openings=road_openings,
        resurfacing_conflicts=resurfacing_conflicts,
        total_work_days=total_work_days,
        total_delay_cost=total_delay_cost,
        hard_violations=hard_violations,
        score=score,
    )


def _count_road_openings(work_orders: list) -> int:
    """
    Count distinct road openings = groups of overlapping/adjacent digs.
    Each isolated time window is one opening.
    """
    if not work_orders:
        return 0
    events = sorted(
        [(wo.proposed_start, wo.proposed_end) for wo in work_orders
         if wo.proposed_start and wo.proposed_end],
        key=lambda x: x[0],
    )
    if not events:
        return 0
    openings = 1
    current_end = events[0][1]
    for start, end in events[1:]:
        if start > current_end + timedelta(days=1):
            openings += 1
        current_end = max(current_end, end)
    return openings


def _count_road_openings_items(items: list[ScheduledItem]) -> int:
    if not items:
        return 0
    utility_items = [i for i in items if i.department != Department.ROAD]
    if not utility_items:
        return 0
    events = sorted([(i.proposed_start, i.proposed_end) for i in utility_items], key=lambda x: x[0])
    openings = 1
    current_end = events[0][1]
    for start, end in events[1:]:
        if start > current_end + timedelta(days=1):
            openings += 1
        current_end = max(current_end, end)
    return openings


def _count_resurfacing_conflicts(work_orders: list, corridor: Corridor) -> int:
    if not corridor.resurfacing_planned_date:
        return 0
    resurfacing_end = corridor.resurfacing_planned_date + timedelta(days=14)
    moratorium_end = resurfacing_end + timedelta(days=corridor.resurfacing_moratorium_days)
    return sum(
        1 for wo in work_orders
        if wo.department != Department.ROAD
        and wo.proposed_start
        and resurfacing_end <= wo.proposed_start < moratorium_end
    )


def _count_resurfacing_conflicts_items(items: list[ScheduledItem], corridor: Corridor) -> int:
    if not corridor.resurfacing_planned_date:
        return 0
    resurfacing_end = corridor.resurfacing_planned_date + timedelta(days=14)
    moratorium_end = resurfacing_end + timedelta(days=corridor.resurfacing_moratorium_days)
    return sum(
        1 for i in items
        if i.department != Department.ROAD
        and resurfacing_end <= i.proposed_start < moratorium_end
    )


def _compute_score(
    road_openings: int,
    resurfacing_conflicts: int,
    total_delay_cost: float,
    hard_violations: int,
) -> float:
    """
    Scoring (higher is better, 0–100).
    -10 per road opening, -20 per resurfacing conflict, -1 per 100k delay cost, -30 per hard violation.
    """
    score = 100.0
    score -= road_openings * 10
    score -= resurfacing_conflicts * 20
    score -= (total_delay_cost / 100_000) * 1
    score -= hard_violations * 30
    return max(0.0, round(score, 1))

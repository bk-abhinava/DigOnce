"""
Plan orchestration service.
Ties together: negotiation → scheduling → validation → storage.
"""
from __future__ import annotations
from datetime import datetime, UTC
from typing import List
import uuid

from backend.models import (
    WorkOrder, Corridor, Plan, PlanStatus, ScheduledItem,
    AuditAction, PolicyRule
)
from backend.agents.negotiation import MediatorAgent
from backend.services import scheduler as sched
from backend.services.validator import validate_plan
from backend.services import store
from backend.data.seed import get_corridors


def generate_plan(
    work_orders: List[WorkOrder],
    corridor: Corridor,
    policies: List[PolicyRule],
) -> Plan:
    """
    Full plan generation pipeline:
    1. Baseline metrics from current proposed dates.
    2. Multi-agent negotiation.
    3. Greedy scheduling using agent proposals.
    4. Deterministic validation.
    5. Store and return plan.
    """
    plan_id = f"PLAN-{uuid.uuid4().hex[:8].upper()}"

    # ── Step 1: Baseline metrics ──────────────────────────────────────────────
    baseline_metrics = sched.compute_baseline_metrics(work_orders, corridor)

    # ── Step 2: Agent negotiation ─────────────────────────────────────────────
    mediator = MediatorAgent()
    agent_proposals, negotiation_rounds, explanation = mediator.negotiate(
        work_orders, corridor, max_rounds=3
    )

    # Build updated work orders from agent proposals
    wo_map = {wo.id: wo for wo in work_orders}
    import copy
    updated_orders: List[WorkOrder] = []
    proposal_map: dict[str, "AgentProposal"] = {}
    for p in agent_proposals:
        proposal_map[p.work_order_id] = p

    for wo in work_orders:
        updated = copy.deepcopy(wo)
        if wo.id in proposal_map:
            prop = proposal_map[wo.id]
            updated.proposed_start = prop.proposed_start
            updated.proposed_end = prop.proposed_end
        updated_orders.append(updated)

    # ── Step 3: Greedy scheduling ─────────────────────────────────────────────
    items, sched_explanation = sched.schedule(updated_orders, corridor)

    # ── Step 4: Validation ────────────────────────────────────────────────────
    validation_result = validate_plan(items, work_orders, corridor, policies)

    # ── Step 5: Optimized metrics ─────────────────────────────────────────────
    optimized_metrics = sched.compute_optimized_metrics(items, corridor)

    # ── Step 6: Build and store plan ──────────────────────────────────────────
    plan = Plan(
        id=plan_id,
        corridor_id=corridor.id,
        status=PlanStatus.VALIDATED if validation_result.valid else PlanStatus.PROPOSED,
        items=items,
        negotiation_rounds=negotiation_rounds,
        baseline_metrics=baseline_metrics,
        optimized_metrics=optimized_metrics,
        explanation=f"{explanation} {sched_explanation}",
        created_at=datetime.now(UTC),
        validation_result=validation_result,
        agent_mode="local_deterministic",
    )

    store.save_plan(plan)
    store.add_audit_entry(
        action=AuditAction.PLAN_PROPOSED,
        entity_id=plan_id,
        entity_type="plan",
        actor="system",
        details={
            "corridor_id": corridor.id,
            "work_order_count": len(work_orders),
            "valid": validation_result.valid,
        },
    )

    return plan


def approve_plan(plan_id: str, approved_by: str = "coordinator") -> Plan:
    plan = store.get_plan(plan_id)
    if not plan:
        raise ValueError(f"Plan {plan_id} not found.")
    if plan.status == PlanStatus.REJECTED:
        raise ValueError("Cannot approve a plan that has been rejected.")
    if plan.status == PlanStatus.APPROVED:
        raise ValueError("Plan is already approved.")
    if not plan.validation_result or not plan.validation_result.valid:
        raise ValueError("Cannot approve a plan that has not passed validation.")
    plan.status = PlanStatus.APPROVED
    plan.approved_at = datetime.now(UTC)
    plan.approved_by = approved_by
    store.save_plan(plan)
    store.add_audit_entry(
        action=AuditAction.PLAN_APPROVED,
        entity_id=plan_id,
        entity_type="plan",
        actor=approved_by,
        details={"approved_by": approved_by},
    )
    return plan


def reject_plan(plan_id: str, rejected_by: str, reason: str) -> Plan:
    plan = store.get_plan(plan_id)
    if not plan:
        raise ValueError(f"Plan {plan_id} not found.")
    plan.status = PlanStatus.REJECTED
    plan.rejection_reason = reason
    store.save_plan(plan)
    store.add_audit_entry(
        action=AuditAction.PLAN_REJECTED,
        entity_id=plan_id,
        entity_type="plan",
        actor=rejected_by,
        details={"reason": reason},
    )
    return plan


def edit_plan(
    plan_id: str,
    new_items: List[ScheduledItem],
    work_orders: List[WorkOrder],
    corridor: Corridor,
    policies: List[PolicyRule],
    edited_by: str,
) -> Plan:
    plan = store.get_plan(plan_id)
    if not plan:
        raise ValueError(f"Plan {plan_id} not found.")

    # Re-validate
    validation_result = validate_plan(new_items, work_orders, corridor, policies)
    new_metrics = sched.compute_optimized_metrics(new_items, corridor)

    plan.items = new_items
    plan.validation_result = validation_result
    plan.optimized_metrics = new_metrics
    plan.status = PlanStatus.VALIDATED if validation_result.valid else PlanStatus.PROPOSED
    store.save_plan(plan)
    store.add_audit_entry(
        action=AuditAction.PLAN_EDITED,
        entity_id=plan_id,
        entity_type="plan",
        actor=edited_by,
        details={"valid_after_edit": validation_result.valid},
    )
    return plan

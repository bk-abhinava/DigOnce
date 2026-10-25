"""
Dig Once — FastAPI backend.
All responses are clearly labeled as simulated/prototype data.
"""
from __future__ import annotations
import os
import uuid
from datetime import datetime, UTC
from typing import List, Optional

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.models import (
    WorkOrder, WorkOrderCreate, CorridorListResponse,
    ConflictsResponse, Plan, ValidationResult, Advisory,
    AuditEntry, PolicyRule, PolicyPropose, PolicyApprove,
    ApproveRequest, RejectRequest, EditRequest,
    Emergency, EmergencyCreate, AuditAction, PolicyStatus,
    HealthResponse, PlanStatus
)
from backend.data.seed import (
    get_work_orders, get_corridors, get_policies, add_work_order,
    get_work_order_by_id, reset_demo_data, add_policy, update_policy,
    get_policy_by_id
)
from backend.services.conflict_service import detect_conflicts
from backend.services.orchestrator import (
    generate_plan, approve_plan, reject_plan, edit_plan
)
from backend.services.validator import validate_plan
from backend.services.advisory_service import generate_advisory
from backend.services.emergency_service import create_emergency
from backend.services import store

# ── App setup ─────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Dig Once API",
    description="Agentic AI for Coordinated Bengaluru Roadworks — DEMO/PROTOTYPE",
    version="1.0.0",
)

ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:3000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

AGENT_MODE = os.getenv("AGENT_MODE", "local_deterministic")


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse)
def health():
    return HealthResponse(
        status="ok",
        version="1.0.0",
        agent_mode=AGENT_MODE,
        timestamp=datetime.now(UTC),
    )


# ── Work Orders ───────────────────────────────────────────────────────────────

@app.get("/api/work-orders", response_model=List[WorkOrder])
def list_work_orders(corridor_id: Optional[str] = None):
    orders = get_work_orders()
    if corridor_id:
        orders = [o for o in orders if o.corridor_id == corridor_id]
    return orders


@app.post("/api/work-orders", response_model=WorkOrder, status_code=status.HTTP_201_CREATED)
def create_work_order(body: WorkOrderCreate):
    wo = WorkOrder(
        id=f"WO-{uuid.uuid4().hex[:6].upper()}",
        **body.model_dump(),
    )
    add_work_order(wo)
    store.add_audit_entry(
        action=AuditAction.WORK_ORDER_CREATED,
        entity_id=wo.id,
        entity_type="work_order",
        actor="coordinator",
    )
    return wo


# ── Corridors ─────────────────────────────────────────────────────────────────

@app.get("/api/corridors", response_model=CorridorListResponse)
def list_corridors():
    return CorridorListResponse(corridors=get_corridors())


# ── Conflicts ─────────────────────────────────────────────────────────────────

@app.get("/api/conflicts", response_model=ConflictsResponse)
def get_conflicts(corridor_id: Optional[str] = None):
    work_orders = get_work_orders()
    corridors = get_corridors()
    if corridor_id:
        work_orders = [wo for wo in work_orders if wo.corridor_id == corridor_id]
        corridors = [c for c in corridors if c.id == corridor_id]
    conflicts = detect_conflicts(work_orders, corridors)
    return ConflictsResponse(conflicts=conflicts, total=len(conflicts))


# ── Plans ─────────────────────────────────────────────────────────────────────

class GeneratePlanRequest(BaseModel):
    corridor_id: str


@app.post("/api/plans/generate", response_model=Plan, status_code=status.HTTP_201_CREATED)
def generate(body: GeneratePlanRequest):
    corridors = get_corridors()
    corridor = next((c for c in corridors if c.id == body.corridor_id), None)
    if not corridor:
        raise HTTPException(status_code=404, detail=f"Corridor {body.corridor_id} not found.")
    work_orders = [wo for wo in get_work_orders() if wo.corridor_id == body.corridor_id]
    policies = get_policies()
    plan = generate_plan(work_orders, corridor, policies)
    return plan


@app.get("/api/plans", response_model=List[Plan])
def list_plans():
    return store.list_plans()


@app.get("/api/plans/{plan_id}", response_model=Plan)
def get_plan(plan_id: str):
    plan = store.get_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail=f"Plan {plan_id} not found.")
    return plan


@app.post("/api/plans/{plan_id}/validate", response_model=ValidationResult)
def validate_plan_endpoint(plan_id: str):
    plan = store.get_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail=f"Plan {plan_id} not found.")
    corridors = get_corridors()
    corridor = next((c for c in corridors if c.id == plan.corridor_id), None)
    if not corridor:
        raise HTTPException(status_code=404, detail="Corridor not found.")
    work_orders = get_work_orders()
    policies = get_policies()
    result = validate_plan(plan.items, work_orders, corridor, policies)
    plan.validation_result = result
    plan.status = PlanStatus.VALIDATED if result.valid else PlanStatus.PROPOSED
    store.save_plan(plan)
    store.add_audit_entry(
        action=AuditAction.PLAN_VALIDATED,
        entity_id=plan_id,
        entity_type="plan",
        details={"valid": result.valid},
    )
    return result


@app.post("/api/plans/{plan_id}/approve", response_model=Plan)
def approve(plan_id: str, body: ApproveRequest):
    try:
        return approve_plan(plan_id, body.approved_by)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/plans/{plan_id}/reject", response_model=Plan)
def reject(plan_id: str, body: RejectRequest):
    try:
        return reject_plan(plan_id, body.rejected_by, body.reason)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/plans/{plan_id}/edit", response_model=Plan)
def edit(plan_id: str, body: EditRequest):
    corridors = get_corridors()
    plan = store.get_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail=f"Plan {plan_id} not found.")
    corridor = next((c for c in corridors if c.id == plan.corridor_id), None)
    if not corridor:
        raise HTTPException(status_code=404, detail="Corridor not found.")
    work_orders = get_work_orders()
    policies = get_policies()
    try:
        return edit_plan(plan_id, body.items, work_orders, corridor, policies, body.edited_by)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Emergencies ───────────────────────────────────────────────────────────────

@app.post("/api/emergencies", response_model=Emergency, status_code=status.HTTP_201_CREATED)
def report_emergency(body: EmergencyCreate):
    # Duplicate protection
    if store.is_duplicate_emergency(body.corridor_id, body.description):
        raise HTTPException(
            status_code=409,
            detail="A similar emergency was already reported within the last 5 minutes.",
        )
    emergency = create_emergency(
        corridor_id=body.corridor_id,
        description=body.description,
        location=body.location,
        reported_by=body.reported_by,
    )
    return emergency


@app.get("/api/emergencies", response_model=List[Emergency])
def list_emergencies():
    return store.get_emergencies()


# ── Audit log ─────────────────────────────────────────────────────────────────

@app.get("/api/audit-log", response_model=List[AuditEntry])
def audit_log():
    return store.get_audit_log()


# ── Policies ──────────────────────────────────────────────────────────────────

@app.get("/api/policies", response_model=List[PolicyRule])
def list_policies():
    return get_policies()


@app.post("/api/policies/propose", response_model=PolicyRule, status_code=status.HTTP_201_CREATED)
def propose_policy(body: PolicyPropose):
    policy = PolicyRule(
        id=f"POL-{uuid.uuid4().hex[:6].upper()}",
        name=body.name,
        description=body.description,
        rule_type=body.rule_type,
        parameters=body.parameters,
        status=PolicyStatus.PROPOSED,
        proposed_by=body.proposed_by,
        proposed_at=datetime.now(UTC),
    )
    add_policy(policy)
    store.add_audit_entry(
        action=AuditAction.POLICY_PROPOSED,
        entity_id=policy.id,
        entity_type="policy",
        actor=body.proposed_by,
        details={"name": body.name, "rule_type": body.rule_type},
    )
    return policy


@app.post("/api/policies/{policy_id}/approve", response_model=PolicyRule)
def approve_policy(policy_id: str, body: PolicyApprove):
    policy = get_policy_by_id(policy_id)
    if not policy:
        raise HTTPException(status_code=404, detail=f"Policy {policy_id} not found.")
    policy.status = PolicyStatus.APPROVED
    policy.approved_at = datetime.now(UTC)
    update_policy(policy)
    store.add_audit_entry(
        action=AuditAction.POLICY_APPROVED,
        entity_id=policy_id,
        entity_type="policy",
        actor=body.approved_by,
    )
    return policy


# ── Advisories ────────────────────────────────────────────────────────────────

@app.get("/api/advisories/{plan_id}", response_model=Advisory)
def get_advisory(plan_id: str):
    plan = store.get_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail=f"Plan {plan_id} not found.")
    corridors = get_corridors()
    corridor = next((c for c in corridors if c.id == plan.corridor_id), None)
    corridor_name = corridor.name if corridor else plan.corridor_id
    try:
        return generate_advisory(plan, corridor_name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Demo reset ────────────────────────────────────────────────────────────────

@app.post("/api/demo/reset", status_code=status.HTTP_200_OK)
def reset_demo():
    reset_demo_data()
    store.reset_store()
    store.add_audit_entry(
        action=AuditAction.DEMO_RESET,
        entity_id="demo",
        entity_type="system",
        actor="coordinator",
        details={"message": "Demo data reset to initial seed state."},
    )
    return {"message": "Demo data reset successfully.", "timestamp": datetime.now(UTC).isoformat()}

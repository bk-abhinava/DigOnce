"""
Pydantic models / schemas for Dig Once backend.
"""
from __future__ import annotations
from datetime import date, datetime, UTC
from enum import Enum
from typing import Any, List, Optional
from pydantic import BaseModel, Field


def _now() -> datetime:
    return datetime.now(UTC)


# ── Enums ────────────────────────────────────────────────────────────────────

class Department(str, Enum):
    WATER = "water"
    POWER = "power"
    FIBRE = "fibre"
    ROAD = "road"

class Priority(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class WorkOrderStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    EMERGENCY = "emergency"

class PlanStatus(str, Enum):
    PROPOSED = "proposed"
    VALIDATED = "validated"
    APPROVED = "approved"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"

class ConflictType(str, Enum):
    OVERLAP = "overlap"
    RESURFACING = "resurfacing"
    DEADLINE = "deadline"
    DEPENDENCY = "dependency"
    RESTRICTED_PERIOD = "restricted_period"

class PolicyStatus(str, Enum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    REJECTED = "rejected"

class AuditAction(str, Enum):
    PLAN_PROPOSED = "plan_proposed"
    PLAN_VALIDATED = "plan_validated"
    PLAN_APPROVED = "plan_approved"
    PLAN_REJECTED = "plan_rejected"
    PLAN_EDITED = "plan_edited"
    EMERGENCY_CREATED = "emergency_created"
    EMERGENCY_REPLANNED = "emergency_replanned"
    POLICY_PROPOSED = "policy_proposed"
    POLICY_APPROVED = "policy_approved"
    POLICY_REJECTED = "policy_rejected"
    WORK_ORDER_CREATED = "work_order_created"
    DEMO_RESET = "demo_reset"


# ── Work Orders ───────────────────────────────────────────────────────────────

class WorkOrderBase(BaseModel):
    department: Department
    corridor_id: str
    description: str
    start_window: date
    end_window: date
    duration_days: int = Field(ge=1)
    deadline: date
    priority: Priority = Priority.MEDIUM
    delay_cost_per_day: float = Field(ge=0.0)
    flexibility_days: int = Field(ge=0, default=0)
    dependencies: List[str] = []
    is_emergency: bool = False

class WorkOrderCreate(WorkOrderBase):
    pass

class WorkOrder(WorkOrderBase):
    id: str
    status: WorkOrderStatus = WorkOrderStatus.PENDING
    proposed_start: Optional[date] = None
    proposed_end: Optional[date] = None
    created_at: datetime = Field(default_factory=_now)

    model_config = {"from_attributes": True}


# ── Corridors ─────────────────────────────────────────────────────────────────

class Corridor(BaseModel):
    id: str
    name: str
    description: str
    resurfacing_planned_date: Optional[date] = None
    resurfacing_moratorium_days: int = 365
    lat: float = 12.9716
    lon: float = 77.5946

class CorridorListResponse(BaseModel):
    corridors: List[Corridor]


# ── Conflicts ─────────────────────────────────────────────────────────────────

class Conflict(BaseModel):
    id: str
    conflict_type: ConflictType
    work_order_ids: List[str]
    description: str
    severity: str  # "high" | "medium" | "low"
    detected_at: datetime = Field(default_factory=_now)

class ConflictsResponse(BaseModel):
    conflicts: List[Conflict]
    total: int


# ── Agent proposals ───────────────────────────────────────────────────────────

class AgentProposal(BaseModel):
    agent: str
    work_order_id: str
    proposed_start: date
    proposed_end: date
    duration_days: int
    reason: str
    delay_cost: float
    round_number: int = 1

class NegotiationRound(BaseModel):
    round_number: int
    proposals: List[AgentProposal]
    conflicts_remaining: int
    notes: str


# ── Plans ─────────────────────────────────────────────────────────────────────

class ScheduledItem(BaseModel):
    work_order_id: str
    department: Department
    description: str
    proposed_start: date
    proposed_end: date
    duration_days: int
    reason: str
    delay_cost: float

class PlanMetrics(BaseModel):
    road_openings: int
    resurfacing_conflicts: int
    total_work_days: int
    total_delay_cost: float
    hard_violations: int
    score: float

class Plan(BaseModel):
    id: str
    corridor_id: str
    status: PlanStatus = PlanStatus.PROPOSED
    items: List[ScheduledItem]
    negotiation_rounds: List[NegotiationRound] = []
    baseline_metrics: Optional[PlanMetrics] = None
    optimized_metrics: Optional[PlanMetrics] = None
    explanation: str = ""
    created_at: datetime = Field(default_factory=_now)
    approved_at: Optional[datetime] = None
    approved_by: str = "coordinator"
    rejection_reason: Optional[str] = None
    validation_result: Optional["ValidationResult"] = None
    agent_mode: str = "local_deterministic"


# ── Validation ────────────────────────────────────────────────────────────────

class ValidationViolation(BaseModel):
    rule: str
    severity: str  # "hard" | "soft"
    work_order_ids: List[str]
    description: str

class ValidationResult(BaseModel):
    valid: bool
    violations: List[ValidationViolation] = []
    warnings: List[str] = []
    affected_work_orders: List[str] = []
    explanations: List[str] = []
    validated_at: datetime = Field(default_factory=_now)
    score: float = 0.0
    score_breakdown: dict = {}


# ── Approvals ─────────────────────────────────────────────────────────────────

class ApproveRequest(BaseModel):
    approved_by: str = "coordinator"

class RejectRequest(BaseModel):
    rejected_by: str = "coordinator"
    reason: str

class EditRequest(BaseModel):
    items: List[ScheduledItem]
    edited_by: str = "coordinator"


# ── Emergencies ───────────────────────────────────────────────────────────────

class EmergencyCreate(BaseModel):
    corridor_id: str
    description: str
    location: str
    reported_by: str = "field_crew"

class Emergency(BaseModel):
    id: str
    corridor_id: str
    description: str
    location: str
    reported_by: str
    created_at: datetime = Field(default_factory=_now)
    work_order_id: str
    revised_plan_id: Optional[str] = None


# ── Policies ──────────────────────────────────────────────────────────────────

class PolicyRule(BaseModel):
    id: str
    name: str
    description: str
    rule_type: str  # "restricted_period" | "proximity" | "overlap" | "resurfacing"
    parameters: dict[str, Any] = {}
    status: PolicyStatus = PolicyStatus.PROPOSED
    proposed_by: str = "coordinator"
    proposed_at: datetime = Field(default_factory=_now)
    approved_at: Optional[datetime] = None
    test_results: Optional[dict] = None

class PolicyPropose(BaseModel):
    name: str
    description: str
    rule_type: str
    parameters: dict[str, Any] = {}
    proposed_by: str = "coordinator"

class PolicyApprove(BaseModel):
    approved_by: str = "coordinator"


# ── Advisories ────────────────────────────────────────────────────────────────

class Advisory(BaseModel):
    plan_id: str
    corridor_name: str
    work_types: List[str]
    start_date: date
    end_date: date
    impact_en: str
    impact_kn: str
    precaution_en: str
    precaution_kn: str
    status: str = "active"
    updated_at: datetime = Field(default_factory=_now)
    is_prototype: bool = True


# ── Audit ─────────────────────────────────────────────────────────────────────

class AuditEntry(BaseModel):
    id: str
    action: AuditAction
    entity_id: str
    entity_type: str
    actor: str = "system"
    details: dict[str, Any] = {}
    timestamp: datetime = Field(default_factory=_now)


# ── Misc responses ────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    version: str
    agent_mode: str
    timestamp: datetime


Plan.model_rebuild()

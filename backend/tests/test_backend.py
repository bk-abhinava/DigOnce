"""
Backend tests for Dig Once MVP.
Tests: conflict detection, scheduling, validation, agents, API endpoints.
Run: cd backend && python -m pytest tests/ -v
"""
import pytest
from datetime import date, timedelta, datetime, UTC
from httpx import AsyncClient, ASGITransport

from backend.main import app
from backend.models import (
    WorkOrder, WorkOrderStatus, Department, Priority,
    Corridor, ScheduledItem
)
from backend.services.conflict_service import detect_conflicts
from backend.services.scheduler import schedule, compute_baseline_metrics, compute_optimized_metrics
from backend.services.validator import validate_plan
from backend.agents.negotiation import MediatorAgent
from backend.data.seed import (
    get_work_orders, get_corridors, get_policies, reset_demo_data
)
from backend.services import store


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def reset_between_tests():
    """Ensure seed data is fresh before each test."""
    reset_demo_data()
    store.reset_store()
    yield
    reset_demo_data()
    store.reset_store()


@pytest.fixture
def demo_corridor() -> Corridor:
    return get_corridors()[0]


@pytest.fixture
def demo_orders() -> list[WorkOrder]:
    return get_work_orders()


@pytest.fixture
def simple_corridor() -> Corridor:
    return Corridor(
        id="TEST-COR",
        name="Test Corridor",
        description="Test",
        resurfacing_planned_date=date(2026, 12, 1),
        resurfacing_moratorium_days=365,
        lat=12.97,
        lon=77.59,
    )


def _make_wo(
    wo_id: str,
    dept: Department,
    start: date,
    end: date,
    duration: int,
    deadline: date | None = None,
    priority: Priority = Priority.MEDIUM,
) -> WorkOrder:
    return WorkOrder(
        id=wo_id,
        department=dept,
        corridor_id="TEST-COR",
        description=f"Test {wo_id}",
        start_window=start,
        end_window=end,
        duration_days=duration,
        deadline=deadline or end,
        priority=priority,
        delay_cost_per_day=10000.0,
        flexibility_days=10,
        dependencies=[],
        status=WorkOrderStatus.PENDING,
        proposed_start=start,
        proposed_end=start + timedelta(days=duration - 1),
        created_at=datetime.now(UTC),
    )


# ── Test 1: Conflict detection — overlap ──────────────────────────────────────

def test_conflict_detection_overlap(simple_corridor):
    wo_a = _make_wo("A", Department.WATER, date(2026, 10, 1), date(2026, 10, 31), 5)
    wo_b = _make_wo("B", Department.POWER, date(2026, 10, 1), date(2026, 10, 31), 5)
    # Same start: clear overlap
    conflicts = detect_conflicts([wo_a, wo_b], [simple_corridor])
    overlap_conflicts = [c for c in conflicts if c.conflict_type == "overlap"]
    assert len(overlap_conflicts) >= 1, "Expected at least one overlap conflict"


# ── Test 2: Post-resurfacing excavation conflict ───────────────────────────────

def test_conflict_detection_resurfacing(simple_corridor):
    # Resurfacing Dec 1 2026; moratorium 365 days → ends Dec 15 2027
    # Schedule water work in Jan 2027 → should conflict
    wo = _make_wo(
        "WO-RESURF",
        Department.WATER,
        date(2027, 1, 5),
        date(2027, 1, 20),
        5,
        deadline=date(2027, 1, 20),
    )
    wo.proposed_start = date(2027, 1, 5)
    wo.proposed_end = date(2027, 1, 9)
    conflicts = detect_conflicts([wo], [simple_corridor])
    resurfacing_conflicts = [c for c in conflicts if c.conflict_type == "resurfacing"]
    assert len(resurfacing_conflicts) >= 1, "Expected post-resurfacing excavation conflict"


# ── Test 3: Deadline violation conflict ───────────────────────────────────────

def test_conflict_detection_deadline(simple_corridor):
    wo = _make_wo("WO-LATE", Department.FIBRE, date(2026, 10, 1), date(2026, 12, 31), 10)
    wo.proposed_start = date(2026, 10, 20)
    wo.proposed_end = date(2026, 12, 31)  # past deadline
    wo.deadline = date(2026, 10, 25)
    conflicts = detect_conflicts([wo], [simple_corridor])
    deadline_conflicts = [c for c in conflicts if c.conflict_type == "deadline"]
    assert len(deadline_conflicts) >= 1


# ── Test 4: Valid coordinated schedule ────────────────────────────────────────

def test_valid_schedule(simple_corridor):
    wo_water = _make_wo("W1", Department.WATER, date(2026, 10, 1), date(2026, 11, 30), 5)
    wo_power = _make_wo("P1", Department.POWER, date(2026, 10, 1), date(2026, 11, 30), 5)
    items, _ = schedule([wo_water, wo_power], simple_corridor)
    result = validate_plan(items, [wo_water, wo_power], simple_corridor, [])
    # Should have no resurfacing violations (work is well before Dec 1)
    resurfacing_viols = [v for v in result.violations if v.rule == "RESURFACING_MORATORIUM"]
    assert len(resurfacing_viols) == 0


# ── Test 5: Invalid schedule — post-resurfacing ────────────────────────────────

def test_invalid_schedule_resurfacing(simple_corridor):
    # Force a work item into the moratorium period
    item = ScheduledItem(
        work_order_id="WO-BAD",
        department=Department.FIBRE,
        description="Bad",
        proposed_start=date(2027, 1, 5),
        proposed_end=date(2027, 1, 9),
        duration_days=5,
        reason="Test",
        delay_cost=0.0,
    )
    wo = _make_wo("WO-BAD", Department.FIBRE, date(2026, 10, 1), date(2027, 6, 30), 5)
    result = validate_plan([item], [wo], simple_corridor, [])
    assert result.valid is False
    assert any(v.rule == "RESURFACING_MORATORIUM" for v in result.violations)


# ── Test 6: Agent negotiation and fallback ────────────────────────────────────

def test_agent_negotiation(simple_corridor, demo_orders):
    mediator = MediatorAgent()
    proposals, rounds, explanation = mediator.negotiate(demo_orders, simple_corridor)
    assert len(proposals) > 0, "Should have at least one proposal"
    assert len(rounds) >= 1, "Should have at least one round"
    assert "LOCAL SIMULATED AGENTS" in explanation


# ── Test 7: Plan approval ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_plan_approve():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Generate plan
        resp = await client.post("/api/plans/generate", json={"corridor_id": "COR-001"})
        assert resp.status_code == 201, f"Generate failed: {resp.text}"
        plan = resp.json()
        plan_id = plan["id"]

        # Validate
        await client.post(f"/api/plans/{plan_id}/validate")

        # Check if valid
        plan_resp = await client.get(f"/api/plans/{plan_id}")
        plan_data = plan_resp.json()

        if plan_data.get("validation_result", {}).get("valid", False):
            approve_resp = await client.post(
                f"/api/plans/{plan_id}/approve",
                json={"approved_by": "test_coordinator"},
            )
            assert approve_resp.status_code == 200
            assert approve_resp.json()["status"] == "approved"


# ── Test 8: Rejection requires reason ────────────────────────────────────────

@pytest.mark.asyncio
async def test_plan_reject_requires_reason():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/plans/generate", json={"corridor_id": "COR-001"})
        assert resp.status_code == 201
        plan_id = resp.json()["id"]
        # Reject without reason should fail
        bad_resp = await client.post(f"/api/plans/{plan_id}/reject", json={})
        assert bad_resp.status_code in (400, 422)


# ── Test 9: Edit schedule and revalidate ─────────────────────────────────────

@pytest.mark.asyncio
async def test_plan_edit_revalidates():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/plans/generate", json={"corridor_id": "COR-001"})
        plan = resp.json()
        plan_id = plan["id"]

        items = plan["items"]
        # Inject a bad date (end before start)
        if items:
            items[0]["proposed_end"] = items[0]["proposed_start"]
            items[0]["duration_days"] = 1

        edit_resp = await client.post(
            f"/api/plans/{plan_id}/edit",
            json={"items": items, "edited_by": "coordinator"},
        )
        assert edit_resp.status_code == 200
        updated = edit_resp.json()
        # Validation should have run
        assert "validation_result" in updated


# ── Test 10: Emergency creation and re-planning ───────────────────────────────

@pytest.mark.asyncio
async def test_emergency_creation():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/emergencies", json={
            "corridor_id": "COR-001",
            "description": "Burst water main at Mahadevapura junction",
            "location": "Mahadevapura junction",
            "reported_by": "field_crew_1",
        })
        assert resp.status_code == 201
        em = resp.json()
        assert em["corridor_id"] == "COR-001"
        assert em["work_order_id"].startswith("EM-WO-")

        # Verify emergency work order was added
        wo_resp = await client.get("/api/work-orders?corridor_id=COR-001")
        wo_ids = [w["id"] for w in wo_resp.json()]
        assert em["work_order_id"] in wo_ids


# ── Test 11: Audit log ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_audit_log_created():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post("/api/plans/generate", json={"corridor_id": "COR-001"})
        audit_resp = await client.get("/api/audit-log")
        assert audit_resp.status_code == 200
        entries = audit_resp.json()
        assert any(e["action"] == "plan_proposed" for e in entries)


# ── Test 12: Advisory — English and Kannada ───────────────────────────────────

@pytest.mark.asyncio
async def test_advisory_english_kannada():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/plans/generate", json={"corridor_id": "COR-001"})
        plan_id = resp.json()["id"]
        adv_resp = await client.get(f"/api/advisories/{plan_id}")
        assert adv_resp.status_code == 200
        adv = adv_resp.json()
        assert adv["impact_en"] != ""
        assert adv["impact_kn"] != ""
        # Kannada text should contain Kannada Unicode characters
        assert any(0x0C80 <= ord(c) <= 0x0CFF for c in adv["impact_kn"]), \
            "Expected Kannada characters in impact_kn"
        assert adv["is_prototype"] is True


# ── Test 13: Policy proposal and approval ────────────────────────────────────

@pytest.mark.asyncio
async def test_policy_approve():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/policies/propose", json={
            "name": "Test Policy",
            "description": "No digging on Sundays",
            "rule_type": "restricted_period",
            "parameters": {"start_date": "2026-10-25", "end_date": "2026-10-25"},
            "proposed_by": "coordinator",
        })
        assert resp.status_code == 201
        policy_id = resp.json()["id"]

        approve_resp = await client.post(
            f"/api/policies/{policy_id}/approve",
            json={"approved_by": "coordinator"},
        )
        assert approve_resp.status_code == 200
        assert approve_resp.json()["status"] == "approved"


# ── Test 14: Regression — exam policy ────────────────────────────────────────

def test_exam_policy_regression(simple_corridor):
    """
    Regression: when exam period policy is approved,
    work during that period should produce a soft warning.
    """
    from backend.models import PolicyRule, PolicyStatus
    exam_policy = PolicyRule(
        id="TEST-POL",
        name="Exam Period",
        description="No digging during exams",
        rule_type="restricted_period",
        parameters={
            "start_date": "2026-10-15",
            "end_date": "2026-10-30",
            "affected_corridors": ["TEST-COR"],
        },
        status=PolicyStatus.APPROVED,
        proposed_by="coordinator",
        proposed_at=datetime.now(UTC),
    )
    item = ScheduledItem(
        work_order_id="WO-EXAM",
        department=Department.WATER,
        description="Exam overlap test",
        proposed_start=date(2026, 10, 20),
        proposed_end=date(2026, 10, 24),
        duration_days=5,
        reason="Test",
        delay_cost=0.0,
    )
    wo = _make_wo("WO-EXAM", Department.WATER, date(2026, 10, 1), date(2026, 11, 30), 5)
    result = validate_plan([item], [wo], simple_corridor, [exam_policy])
    policy_violations = [v for v in result.violations if "TEST-POL" in v.rule]
    assert len(policy_violations) >= 1, "Expected exam period policy violation"


# ── Test 15: API error handling ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_api_404_plan():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/plans/NONEXISTENT")
        assert resp.status_code == 404


@pytest.mark.asyncio
async def test_api_404_advisory():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/advisories/NONEXISTENT")
        assert resp.status_code == 404


# ── Test 16: Demo reset repeatability ────────────────────────────────────────

@pytest.mark.asyncio
async def test_demo_reset():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Generate a plan and approve it
        resp = await client.post("/api/plans/generate", json={"corridor_id": "COR-001"})
        assert resp.status_code == 201

        # Reset
        reset_resp = await client.post("/api/demo/reset")
        assert reset_resp.status_code == 200

        # Plans should be cleared
        plans = await client.get("/api/plans")
        assert plans.json() == []

        # Work orders should match original seed
        wo_resp = await client.get("/api/work-orders")
        assert len(wo_resp.json()) == 6  # original seed count


# ── Test 17: Seed has >= 2 conflicts ─────────────────────────────────────────

def test_seed_has_conflicts():
    work_orders = get_work_orders()
    corridors = get_corridors()
    conflicts = detect_conflicts(work_orders, corridors)
    assert len(conflicts) >= 2, (
        f"Expected at least 2 conflicts in seed data, got {len(conflicts)}: "
        + str([c.conflict_type for c in conflicts])
    )


# ── Test 18: Duplicate emergency protection ───────────────────────────────────

@pytest.mark.asyncio
async def test_duplicate_emergency_rejected():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "corridor_id": "COR-001",
            "description": "Duplicate burst pipe test",
            "location": "Test location",
            "reported_by": "field_crew",
        }
        resp1 = await client.post("/api/emergencies", json=payload)
        assert resp1.status_code == 201
        resp2 = await client.post("/api/emergencies", json=payload)
        assert resp2.status_code == 409

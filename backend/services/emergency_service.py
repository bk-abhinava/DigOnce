"""
Emergency re-planning service.
Records burst-pipe or other emergency events,
creates high-priority work orders, and re-generates the schedule.
"""
from __future__ import annotations
from datetime import datetime, date, timedelta, UTC
import uuid

from backend.models import (
    WorkOrder, WorkOrderStatus, Department, Priority, Emergency,
    AuditAction
)
from backend.services import store
from backend.data.seed import add_work_order


def create_emergency(
    corridor_id: str,
    description: str,
    location: str,
    reported_by: str = "field_crew",
) -> Emergency:
    """
    Records the emergency, creates an urgent WATER work order,
    and stores the event.
    """
    emer_id = f"EM-{uuid.uuid4().hex[:6].upper()}"
    wo_id = f"EM-WO-{uuid.uuid4().hex[:6].upper()}"
    today = datetime.now(UTC).date()

    emergency_wo = WorkOrder(
        id=wo_id,
        department=Department.WATER,
        corridor_id=corridor_id,
        description=f"[EMERGENCY] {description} — reported at {location}",
        start_window=today,
        end_window=today + timedelta(days=7),
        duration_days=3,
        deadline=today + timedelta(days=3),
        priority=Priority.CRITICAL,
        delay_cost_per_day=200000.0,
        flexibility_days=0,
        dependencies=[],
        status=WorkOrderStatus.EMERGENCY,
        proposed_start=today,
        proposed_end=today + timedelta(days=2),
        created_at=datetime.now(UTC),
        is_emergency=True,
    )
    add_work_order(emergency_wo)

    emergency = Emergency(
        id=emer_id,
        corridor_id=corridor_id,
        description=description,
        location=location,
        reported_by=reported_by,
        created_at=datetime.now(UTC),
        work_order_id=wo_id,
    )
    store.save_emergency(emergency)
    store.add_audit_entry(
        action=AuditAction.EMERGENCY_CREATED,
        entity_id=emer_id,
        entity_type="emergency",
        actor=reported_by,
        details={
            "corridor_id": corridor_id,
            "work_order_id": wo_id,
            "location": location,
        },
    )
    return emergency

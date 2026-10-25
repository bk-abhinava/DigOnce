"""
In-memory store for Plans, Emergencies, and Audit Log.
Replaceable with SQLite or a production DB in a later phase.
"""
from __future__ import annotations
from datetime import datetime, UTC
from typing import Optional
import uuid

from backend.models import Plan, Emergency, AuditEntry, AuditAction

# ── In-memory stores ──────────────────────────────────────────────────────────

_plans: dict[str, Plan] = {}
_emergencies: list[Emergency] = []
_audit_log: list[AuditEntry] = []

# ── Plans ─────────────────────────────────────────────────────────────────────

def save_plan(plan: Plan) -> Plan:
    _plans[plan.id] = plan
    return plan


def get_plan(plan_id: str) -> Optional[Plan]:
    return _plans.get(plan_id)


def list_plans() -> list[Plan]:
    return list(_plans.values())


def clear_plans() -> None:
    _plans.clear()


# ── Emergencies ───────────────────────────────────────────────────────────────

_seen_emergency_descriptions: set[str] = set()

def save_emergency(emergency: Emergency) -> Emergency:
    _emergencies.append(emergency)
    return emergency


def get_emergencies() -> list[Emergency]:
    return list(_emergencies)


def is_duplicate_emergency(corridor_id: str, description: str, window_minutes: int = 5) -> bool:
    """Duplicate protection: same corridor + description within window_minutes."""
    key = f"{corridor_id}::{description.strip().lower()}"
    cutoff = datetime.now(UTC).timestamp() - window_minutes * 60
    for e in _emergencies:
        e_key = f"{e.corridor_id}::{e.description.strip().lower()}"
        if e_key == key and e.created_at.timestamp() > cutoff:
            return True
    return False


def clear_emergencies() -> None:
    _emergencies.clear()


# ── Audit log ─────────────────────────────────────────────────────────────────

def add_audit_entry(
    action: AuditAction,
    entity_id: str,
    entity_type: str,
    actor: str = "system",
    details: dict | None = None,
) -> AuditEntry:
    entry = AuditEntry(
        id=f"AUD-{uuid.uuid4().hex[:8].upper()}",
        action=action,
        entity_id=entity_id,
        entity_type=entity_type,
        actor=actor,
        details=details or {},
        timestamp=datetime.now(UTC),
    )
    _audit_log.append(entry)
    return entry


def get_audit_log() -> list[AuditEntry]:
    return list(reversed(_audit_log))  # Newest first


def clear_audit_log() -> None:
    _audit_log.clear()


# ── Full reset ────────────────────────────────────────────────────────────────

def reset_store() -> None:
    clear_plans()
    clear_emergencies()
    clear_audit_log()

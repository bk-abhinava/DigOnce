"""
Advisory generation service.
Generates citizen-facing notices in English and Kannada.
OUTPUT IS A PROTOTYPE NOTICE — not an official government advisory.
"""
from __future__ import annotations
from datetime import datetime, date, UTC
from typing import List

from backend.models import Advisory, Plan, ScheduledItem, Department


_WORK_TYPE_EN = {
    Department.WATER: "water main / drainage works",
    Department.POWER: "underground power cabling",
    Department.FIBRE: "fibre / telecom duct installation",
    Department.ROAD: "road resurfacing",
}

_WORK_TYPE_KN = {
    Department.WATER: "ನೀರಿನ ಮುಖ್ಯ / ಒಳಚರಂಡಿ ಕಾಮಗಾರಿ",
    Department.POWER: "ಭೂಗತ ವಿದ್ಯುತ್ ಕೇಬಲ್ ಕೆಲಸ",
    Department.FIBRE: "ಫೈಬರ್ / ದೂರಸಂಪರ್ಕ ಡಕ್ಟ್ ಅಳವಡಿಕೆ",
    Department.ROAD: "ರಸ್ತೆ ಮೇಲ್ಮೈ ನವೀಕರಣ",
}

_IMPACT_TEMPLATE_EN = (
    "Road work is scheduled on {corridor} from {start} to {end}. "
    "Expect lane reductions and temporary traffic diversions. "
    "Work involves: {work_types}."
)

_IMPACT_TEMPLATE_KN = (
    "{corridor} ರಸ್ತೆಯಲ್ಲಿ {start} ರಿಂದ {end} ರವರೆಗೆ ರಸ್ತೆ ಕಾಮಗಾರಿ ನಡೆಯಲಿದೆ. "
    "ಲೇನ್ ಕಡಿತ ಮತ್ತು ತಾತ್ಕಾಲಿಕ ದಟ್ಟಣೆ ತಿರುವು ನಿರೀಕ್ಷಿಸಿ. "
    "ಕಾಮಗಾರಿ: {work_types}."
)

_PRECAUTION_EN = (
    "Allow extra travel time. Use alternate routes where possible. "
    "Pedestrians: use designated footpaths. "
    "NOTE: This is a prototype-generated notice and NOT an official public announcement."
)

_PRECAUTION_KN = (
    "ಹೆಚ್ಚುವರಿ ಪ್ರಯಾಣ ಸಮಯ ಅನುಮತಿಸಿ. ಸಾಧ್ಯವಾದಲ್ಲಿ ಪರ್ಯಾಯ ಮಾರ್ಗ ಬಳಸಿ. "
    "ಪಾದಚಾರಿಗಳು: ನಿಗದಿತ ಪಾದಚಾರಿ ಮಾರ್ಗ ಬಳಸಿ. "
    "ಗಮನಿಸಿ: ಇದು ಮಾದರಿ-ಉತ್ಪಾದಿತ ಸೂಚನೆ ಮಾತ್ರ, ಅಧಿಕೃತ ಸಾರ್ವಜನಿಕ ಪ್ರಕಟಣೆ ಅಲ್ಲ."
)


def _format_date(d: date) -> str:
    return d.strftime("%d %B %Y")


def _format_date_kn(d: date) -> str:
    months_kn = [
        "ಜನವರಿ", "ಫೆಬ್ರವರಿ", "ಮಾರ್ಚ್", "ಏಪ್ರಿಲ್",
        "ಮೇ", "ಜೂನ್", "ಜುಲೈ", "ಆಗಸ್ಟ್",
        "ಸೆಪ್ಟೆಂಬರ್", "ಅಕ್ಟೋಬರ್", "ನವೆಂಬರ್", "ಡಿಸೆಂಬರ್"
    ]
    return f"{d.day} {months_kn[d.month - 1]} {d.year}"


def generate_advisory(plan: Plan, corridor_name: str) -> Advisory:
    items: List[ScheduledItem] = plan.items
    if not items:
        raise ValueError("Plan has no scheduled items.")

    all_starts = [i.proposed_start for i in items]
    all_ends = [i.proposed_end for i in items]
    start_date = min(all_starts)
    end_date = max(all_ends)

    depts = list({i.department for i in items})
    work_types_en = [_WORK_TYPE_EN.get(d, d.value) for d in depts]
    work_types_kn = [_WORK_TYPE_KN.get(d, d.value) for d in depts]

    impact_en = _IMPACT_TEMPLATE_EN.format(
        corridor=corridor_name,
        start=_format_date(start_date),
        end=_format_date(end_date),
        work_types=", ".join(work_types_en),
    )
    impact_kn = _IMPACT_TEMPLATE_KN.format(
        corridor=corridor_name,
        start=_format_date_kn(start_date),
        end=_format_date_kn(end_date),
        work_types=", ".join(work_types_kn),
    )

    return Advisory(
        plan_id=plan.id,
        corridor_name=corridor_name,
        work_types=work_types_en,
        start_date=start_date,
        end_date=end_date,
        impact_en=impact_en,
        impact_kn=impact_kn,
        precaution_en=_PRECAUTION_EN,
        precaution_kn=_PRECAUTION_KN,
        status="active",
        updated_at=datetime.now(UTC),
        is_prototype=True,
    )

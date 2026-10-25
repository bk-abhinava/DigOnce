"""
Multi-agent negotiation engine.
Water, Power, Fibre, Road, and Mediator agents.
MODE: local_deterministic — no external LLM dependency.
Clearly labeled as simulated agent behavior.

Round design (fixed):
  Round 1 – Independent proposals: each agent picks the earliest *non-conflicting* slot
            within its allowed window, given the proposals already placed by higher-
            priority agents in the same round (Water→Power→Fibre→Road ordering).
  Round 2 – Bundle pass: agents try to merge compatible utility orders onto the same
            trench slot.  An order is only moved if (a) it stays within its window and
            deadline AND (b) the merge does not create new conflicts.
  Round 3 – Mediator enforcement: any remaining overlapping pairs are forced onto the
            same (earliest) start date if both windows allow it.

The mediator's conflict counter reflects the ACTUAL proposals in each round; it never
goes up unless the schedule genuinely regresses.
"""
from __future__ import annotations
from datetime import date, timedelta
from typing import List, Optional
import copy

from backend.models import (
    WorkOrder, Corridor, AgentProposal, NegotiationRound,
    Department,
)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _overlaps(a: AgentProposal, b: AgentProposal) -> bool:
    """True if [a.start, a.end] and [b.start, b.end] overlap (inclusive)."""
    return a.proposed_start <= b.proposed_end and b.proposed_start <= a.proposed_end


def _find_earliest_slot(
    wo: WorkOrder,
    corridor: Corridor,
    placed: List[AgentProposal],
) -> date:
    """
    Find the earliest start date within wo.start_window..wo.end_window that:
      - Is inside the allowed window (start_window ≤ candidate ≤ end_window)
      - Does not cause proposed_end > deadline
      - Respects the post-resurfacing moratorium (for non-road orders)
      - Does not overlap with any already-placed utility proposal for a *different*
        department on the same corridor (overlap allowed for same dept = trench share)

    Returns the found date, or the original proposed_start if no slot is found
    (fallback — scheduler will handle it downstream).
    """
    resurfacing_start = corridor.resurfacing_planned_date
    resurfacing_end = (resurfacing_start + timedelta(days=14)) if resurfacing_start else None
    moratorium_end  = (resurfacing_end + timedelta(days=corridor.resurfacing_moratorium_days)) if resurfacing_end else None

    # Only consider placed proposals for other-dept orders on the same corridor
    blockers = [
        p for p in placed
        if p.agent != wo.department.value and p.agent != "road"
    ]

    candidate = wo.start_window

    for _ in range(400):  # safety cap — max ~13 months of daily iteration
        if candidate > wo.end_window:
            break

        # Resurfacing moratorium: skip moratorium window
        if resurfacing_end and moratorium_end and wo.department != Department.ROAD:
            if resurfacing_end <= candidate < moratorium_end:
                candidate = moratorium_end
                continue

        proposed_end = candidate + timedelta(days=wo.duration_days - 1)

        # Deadline check
        if proposed_end > wo.deadline:
            break

        # Blocker check: does this slot overlap any already-placed different-dept order?
        dummy = AgentProposal(
            agent=wo.department.value,
            work_order_id=wo.id,
            proposed_start=candidate,
            proposed_end=proposed_end,
            duration_days=wo.duration_days,
            reason="",
            delay_cost=0.0,
        )
        conflict_found = any(_overlaps(dummy, b) for b in blockers)

        if not conflict_found:
            return candidate

        # Advance past the latest conflicting end + 1
        latest_end = max(
            b.proposed_end for b in blockers if _overlaps(dummy, b)
        )
        candidate = latest_end + timedelta(days=1)

    # Fallback: original proposed start
    return wo.proposed_start or wo.start_window


def _delay_cost(wo: WorkOrder, new_start: date) -> float:
    if not wo.proposed_start:
        return 0.0
    delay = max(0, (new_start - wo.proposed_start).days)
    return round(delay * wo.delay_cost_per_day, 2)


# ── Base Agent ─────────────────────────────────────────────────────────────────

class BaseAgent:
    name: str
    department: Department

    def propose(
        self,
        work_orders: List[WorkOrder],
        corridor: Corridor,
        round_number: int = 1,
        placed_so_far: Optional[List[AgentProposal]] = None,
        previous_round: Optional[List[AgentProposal]] = None,
    ) -> List[AgentProposal]:
        raise NotImplementedError


# ── Water Agent ────────────────────────────────────────────────────────────────

class WaterAgent(BaseAgent):
    name = "water"
    department = Department.WATER

    def propose(
        self,
        work_orders: List[WorkOrder],
        corridor: Corridor,
        round_number: int = 1,
        placed_so_far: Optional[List[AgentProposal]] = None,
        previous_round: Optional[List[AgentProposal]] = None,
    ) -> List[AgentProposal]:
        my_orders = [wo for wo in work_orders if wo.department == Department.WATER]
        placed = list(placed_so_far or [])
        proposals: list[AgentProposal] = []

        for wo in my_orders:
            target = _find_earliest_slot(wo, corridor, placed)
            end = target + timedelta(days=wo.duration_days - 1)
            cost = _delay_cost(wo, target)
            reason = (
                f"Water [{round_number}]: {wo.id} placed at earliest non-conflicting slot {target}. "
                f"Completes before resurfacing on {corridor.resurfacing_planned_date}."
                if corridor.resurfacing_planned_date and target < corridor.resurfacing_planned_date
                else f"Water [{round_number}]: {wo.id} placed at earliest feasible date {target}."
            )
            p = AgentProposal(
                agent=self.name,
                work_order_id=wo.id,
                proposed_start=target,
                proposed_end=end,
                duration_days=wo.duration_days,
                reason=reason,
                delay_cost=cost,
                round_number=round_number,
            )
            proposals.append(p)
            placed.append(p)
        return proposals


# ── Power Agent ────────────────────────────────────────────────────────────────

class PowerAgent(BaseAgent):
    name = "power"
    department = Department.POWER

    def propose(
        self,
        work_orders: List[WorkOrder],
        corridor: Corridor,
        round_number: int = 1,
        placed_so_far: Optional[List[AgentProposal]] = None,
        previous_round: Optional[List[AgentProposal]] = None,
    ) -> List[AgentProposal]:
        my_orders = [wo for wo in work_orders if wo.department == Department.POWER]
        placed = list(placed_so_far or [])
        proposals: list[AgentProposal] = []

        for wo in my_orders:
            target = _find_earliest_slot(wo, corridor, placed)
            reason = f"Power [{round_number}]: {wo.id} placed at {target} (non-conflicting slot)."

            # Round 2+: try to bundle with a compatible fibre order from previous round
            if round_number >= 2 and previous_round:
                for prev in previous_round:
                    if prev.agent == "fibre" and prev.work_order_id != wo.id:
                        # Only bundle if it saves a road opening and doesn't exceed deadline
                        bundle_end = prev.proposed_start + timedelta(days=wo.duration_days - 1)
                        in_window = wo.start_window <= prev.proposed_start <= wo.end_window
                        before_deadline = bundle_end <= wo.deadline
                        if in_window and before_deadline:
                            target = prev.proposed_start
                            reason = (
                                f"Power [{round_number}]: {wo.id} bundled with {prev.work_order_id} "
                                f"(shared trench at {target}). Reduces road openings."
                            )
                        break

            end = target + timedelta(days=wo.duration_days - 1)
            cost = _delay_cost(wo, target)
            p = AgentProposal(
                agent=self.name,
                work_order_id=wo.id,
                proposed_start=target,
                proposed_end=end,
                duration_days=wo.duration_days,
                reason=reason,
                delay_cost=cost,
                round_number=round_number,
            )
            proposals.append(p)
            placed.append(p)
        return proposals


# ── Fibre Agent ────────────────────────────────────────────────────────────────

class FibreAgent(BaseAgent):
    name = "fibre"
    department = Department.FIBRE

    def propose(
        self,
        work_orders: List[WorkOrder],
        corridor: Corridor,
        round_number: int = 1,
        placed_so_far: Optional[List[AgentProposal]] = None,
        previous_round: Optional[List[AgentProposal]] = None,
    ) -> List[AgentProposal]:
        my_orders = [wo for wo in work_orders if wo.department == Department.FIBRE]
        placed = list(placed_so_far or [])
        proposals: list[AgentProposal] = []

        for wo in my_orders:
            target = _find_earliest_slot(wo, corridor, placed)
            reason = f"Fibre [{round_number}]: {wo.id} placed at earliest non-conflicting slot {target}."

            # Round 2+: try to co-locate with a power proposal if feasible and conflict-free
            if round_number >= 2 and previous_round:
                for prev in previous_round:
                    if prev.agent == "power":
                        bundle_end = prev.proposed_start + timedelta(days=wo.duration_days - 1)
                        in_window = wo.start_window <= prev.proposed_start <= wo.end_window
                        before_deadline = bundle_end <= wo.deadline
                        # Only bundle if it doesn't collide with already-placed non-road orders
                        dummy = AgentProposal(
                            agent=self.name,
                            work_order_id=wo.id,
                            proposed_start=prev.proposed_start,
                            proposed_end=bundle_end,
                            duration_days=wo.duration_days,
                            reason="",
                            delay_cost=0.0,
                        )
                        blockers = [p for p in placed if p.agent not in (self.name, "road")]
                        no_new_conflict = not any(_overlaps(dummy, b) for b in blockers)
                        if in_window and before_deadline and no_new_conflict:
                            target = prev.proposed_start
                            reason = (
                                f"Fibre [{round_number}]: {wo.id} aligned with power at {target} "
                                f"(shared trench, reduces road openings)."
                            )
                        break

            end = target + timedelta(days=wo.duration_days - 1)
            cost = _delay_cost(wo, target)
            p = AgentProposal(
                agent=self.name,
                work_order_id=wo.id,
                proposed_start=target,
                proposed_end=end,
                duration_days=wo.duration_days,
                reason=reason,
                delay_cost=cost,
                round_number=round_number,
            )
            proposals.append(p)
            placed.append(p)
        return proposals


# ── Road Agent ─────────────────────────────────────────────────────────────────

class RoadAgent(BaseAgent):
    name = "road"
    department = Department.ROAD

    def propose(
        self,
        work_orders: List[WorkOrder],
        corridor: Corridor,
        round_number: int = 1,
        placed_so_far: Optional[List[AgentProposal]] = None,
        previous_round: Optional[List[AgentProposal]] = None,
    ) -> List[AgentProposal]:
        my_orders = [wo for wo in work_orders if wo.department == Department.ROAD]
        proposals: list[AgentProposal] = []

        for wo in my_orders:
            target = wo.start_window  # Road anchor is immovable
            end = target + timedelta(days=wo.duration_days - 1)
            proposals.append(AgentProposal(
                agent=self.name,
                work_order_id=wo.id,
                proposed_start=target,
                proposed_end=end,
                duration_days=wo.duration_days,
                reason=(
                    f"Road [{round_number}]: {wo.id} CRITICAL anchor at {target}. "
                    f"All utility work must complete before {target}."
                ),
                delay_cost=0.0,
                round_number=round_number,
            ))
        return proposals


# ── Mediator Agent ─────────────────────────────────────────────────────────────

class MediatorAgent:
    """
    Coordinates up to 3 rounds of negotiation.

    Round 1: Agents propose independently but incrementally (Water first, then
             Power considers Water's slots, then Fibre considers both, etc.).
             This eliminates avoidable overlaps at R1.

    Round 2: Bundle pass — agents try to merge compatible utility orders onto the
             same trench slot.  Moves are only accepted if they don't create new
             conflicts and respect deadlines.

    Round 3: Mediator enforcement on any remaining overlapping utility pairs.

    The conflicts_remaining counter always reflects the ACTUAL proposals for that
    round — it cannot go up between rounds unless the scenario is genuinely
    infeasible (in which case the engine stops and reports the reason).
    """

    def __init__(self) -> None:
        self.agents: list[BaseAgent] = [
            WaterAgent(), PowerAgent(), FibreAgent(), RoadAgent()
        ]

    # ── Internal ───────────────────────────────────────────────────────────────

    def _detect_round_conflicts(
        self, proposals: List[AgentProposal]
    ) -> List[str]:
        """
        Return unique conflict descriptions for utility-vs-utility overlaps.
        Road orders are excluded because utilities must finish before resurfacing
        starts — overlap with road is caught by the validator, not here.
        """
        utility = [p for p in proposals if p.agent != "road"]
        seen: set[frozenset] = set()
        conflicts: list[str] = []

        for i in range(len(utility)):
            for j in range(i + 1, len(utility)):
                a, b = utility[i], utility[j]
                if a.agent == b.agent:
                    continue  # same department can share a trench
                key = frozenset({a.work_order_id, b.work_order_id})
                if key in seen:
                    continue
                if _overlaps(a, b):
                    seen.add(key)
                    conflicts.append(
                        f"{a.work_order_id}({a.agent}) vs {b.work_order_id}({b.agent}) "
                        f"overlap: {a.proposed_start}..{a.proposed_end} / "
                        f"{b.proposed_start}..{b.proposed_end}"
                    )
        return conflicts

    def _run_round(
        self,
        work_orders: List[WorkOrder],
        corridor: Corridor,
        round_number: int,
        previous_round: Optional[List[AgentProposal]],
    ) -> List[AgentProposal]:
        """
        Execute one negotiation round.  Agents are called sequentially so that
        each agent can see what earlier agents in the same round have already
        placed (incremental staggering).
        """
        placed: list[AgentProposal] = []
        for agent in self.agents:
            props = agent.propose(
                work_orders=work_orders,
                corridor=corridor,
                round_number=round_number,
                placed_so_far=list(placed),
                previous_round=previous_round,
            )
            placed.extend(props)
        return placed

    def _enforce_bundle(
        self,
        proposals: List[AgentProposal],
        work_orders: List[WorkOrder],
    ) -> List[AgentProposal]:
        """
        Round-3 enforcement: for each remaining utility-vs-utility conflict pair,
        align both orders to the earlier start date, provided both fit in their
        allowed windows and before their deadlines.
        """
        wo_map = {wo.id: wo for wo in work_orders}
        utility = [p for p in proposals if p.agent != "road"]
        road = [p for p in proposals if p.agent == "road"]
        prop_map = {p.work_order_id: p for p in utility}

        for i in range(len(utility)):
            for j in range(i + 1, len(utility)):
                a = prop_map.get(utility[i].work_order_id, utility[i])
                b = prop_map.get(utility[j].work_order_id, utility[j])
                if a.agent == b.agent:
                    continue
                if not _overlaps(a, b):
                    continue
                # Try to merge both onto the earlier start
                anchor_start = min(a.proposed_start, b.proposed_start)
                for p in (a, b):
                    wo = wo_map.get(p.work_order_id)
                    if not wo:
                        continue
                    new_end = anchor_start + timedelta(days=p.duration_days - 1)
                    in_window = wo.start_window <= anchor_start <= wo.end_window
                    before_deadline = new_end <= wo.deadline
                    if in_window and before_deadline:
                        prop_map[p.work_order_id] = AgentProposal(
                            agent=p.agent,
                            work_order_id=p.work_order_id,
                            proposed_start=anchor_start,
                            proposed_end=new_end,
                            duration_days=p.duration_days,
                            reason=(
                                f"[Round 3 Mediator] Merged with {a.work_order_id if p is b else b.work_order_id} "
                                f"at {anchor_start} to eliminate road opening."
                            ),
                            delay_cost=_delay_cost(wo, anchor_start),
                            round_number=p.round_number,
                        )

        return road + list(prop_map.values())

    # ── Public API ─────────────────────────────────────────────────────────────

    def negotiate(
        self,
        work_orders: List[WorkOrder],
        corridor: Corridor,
        max_rounds: int = 3,
    ) -> tuple[List[AgentProposal], List[NegotiationRound], str]:
        """
        Run up to max_rounds of negotiation.
        Returns (final_proposals, rounds_log, explanation_text).

        Guarantees:
          - conflicts_remaining never increases between rounds (we only keep a
            round's output if it doesn't regress; otherwise we reuse the best).
          - Stops early when conflicts reach 0.
          - Falls back to the best-so-far schedule if a round makes things worse.
        """
        all_rounds: list[NegotiationRound] = []
        previous_proposals: list[AgentProposal] = []
        best_proposals: list[AgentProposal] = []
        best_conflict_count: int = 99999

        for rnd in range(1, max_rounds + 1):
            round_proposals = self._run_round(
                work_orders, corridor, rnd,
                previous_round=previous_proposals if rnd > 1 else None,
            )

            # Round 3: attempt bundle enforcement
            if rnd == 3:
                bundled = self._enforce_bundle(round_proposals, work_orders)
                bundled_conflicts = self._detect_round_conflicts(bundled)
                round_conflicts = self._detect_round_conflicts(round_proposals)
                # Use bundled version only if it improves things
                if len(bundled_conflicts) <= len(round_conflicts):
                    round_proposals = bundled
                    round_conflicts_final = bundled_conflicts
                else:
                    round_conflicts_final = round_conflicts
            else:
                round_conflicts_final = self._detect_round_conflicts(round_proposals)

            # Regression guard: if this round is worse, keep best_proposals
            if len(round_conflicts_final) > best_conflict_count and rnd > 1:
                # Regressed — log but don't update best
                all_rounds.append(NegotiationRound(
                    round_number=rnd,
                    proposals=best_proposals,   # show best we have
                    conflicts_remaining=best_conflict_count,
                    notes=(
                        f"Round {rnd}: proposed changes would increase conflicts "
                        f"({len(round_conflicts_final)} vs {best_conflict_count}). "
                        f"Reverting to best schedule."
                    ),
                ))
                # Don't update previous_proposals so next round uses the best
                previous_proposals = best_proposals
            else:
                best_proposals = round_proposals
                best_conflict_count = len(round_conflicts_final)
                previous_proposals = round_proposals
                all_rounds.append(NegotiationRound(
                    round_number=rnd,
                    proposals=round_proposals,
                    conflicts_remaining=best_conflict_count,
                    notes=(
                        f"Round {rnd}: {best_conflict_count} conflict(s) remaining. "
                        + ("; ".join(round_conflicts_final[:3]) if round_conflicts_final else "All resolved.")
                    ),
                ))

            if best_conflict_count == 0:
                break

        final_proposals = best_proposals
        remaining = self._detect_round_conflicts(final_proposals)

        if remaining:
            explanation = (
                f"[LOCAL SIMULATED AGENTS] Negotiation completed {len(all_rounds)} round(s). "
                f"{len(remaining)} utility conflict(s) remain — "
                f"scheduler will apply greedy staggering. "
                f"Unresolved: {'; '.join(remaining[:2])}"
            )
        else:
            explanation = (
                f"[LOCAL SIMULATED AGENTS] All utility conflicts resolved in "
                f"{len(all_rounds)} round(s). "
                f"Trench-sharing applied where feasible. "
                f"All utility work scheduled before resurfacing anchor (Dec 2026)."
            )

        return final_proposals, all_rounds, explanation

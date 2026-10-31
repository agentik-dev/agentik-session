"""Spend policy for a sitting.

The problem this solves: a session that runs to 100% dies mid-thought. There is
no budget left to write down what it was doing, commit the work, or hand off --
so the most valuable turn of the sitting, the handoff, is the one that never
happens.

So: hold back a reserve. Everything above the reserve floor is working budget;
the reserve itself is for wrapping up. Zones escalate as the budget fills, and
the enforcement point is the hook that spawns subagents, because that is where
a session commits to spending a lot of budget at once.

All pure. The caller computes `used_pct`, a percentage of the sitting's own
ceilings; with no reading the zone is `unknown` and nothing is signalled.
"""

from __future__ import annotations

from dataclasses import dataclass

CLEAR, NOTICE, WINDDOWN, RESERVE, EXHAUSTED = (
    "clear", "notice", "wind-down", "reserve", "exhausted")
UNKNOWN = "unknown"

ZONE_ORDER = [CLEAR, NOTICE, WINDDOWN, RESERVE, EXHAUSTED]


@dataclass(frozen=True)
class Policy:
    """Where the tripwires sit, as percentages of the sitting's ceilings."""
    # The reserve floor must sit at or above wind-down, or the wind-down zone is
    # unreachable. 8% reserve puts the floor at 92, leaving the familiar 80/90
    # thresholds intact below it.
    reserve_pct: float = 8.0      # held back for the wrap-up
    notice_pct: float = 80.0      # first warning
    winddown_pct: float = 90.0    # stop starting things you cannot finish

    @property
    def reserve_floor(self) -> float:
        """Utilization at which the reserve begins."""
        return max(0.0, 100.0 - self.reserve_pct)

    def validate(self) -> None:
        if not 0 < self.reserve_pct < 100:
            raise ValueError("reserve_pct must be between 0 and 100")
        if not (self.notice_pct < self.winddown_pct <= self.reserve_floor):
            raise ValueError(
                f"thresholds must satisfy notice ({self.notice_pct:.0f}) < "
                f"wind-down ({self.winddown_pct:.0f}) <= reserve floor "
                f"({self.reserve_floor:.0f}). With reserve_pct={self.reserve_pct:.0f} "
                f"the floor is {self.reserve_floor:.0f}; lower --winddown and "
                "--notice to fit under it, e.g. "
                f"--winddown {max(1, self.reserve_floor - 5):.0f} "
                f"--notice {max(0, self.reserve_floor - 15):.0f}"
            )

    @classmethod
    def for_reserve(cls, reserve_pct: float, base: "Policy | None" = None) -> "Policy":
        """A coherent policy for a given reserve.

        Keeps the base thresholds when they fit under the new floor and
        slides them down when they do not, so asking for a BIGGER reserve
        can never fail validation and fall back to a smaller one.
        """
        base = base or cls()
        floor = max(1.0, 100.0 - reserve_pct)
        wind = min(base.winddown_pct, floor)
        notice = min(base.notice_pct, wind - 1.0)
        p = cls(reserve_pct=reserve_pct, notice_pct=max(0.0, notice), winddown_pct=wind)
        p.validate()
        return p



def effective_policy(reserve_pct: float, stored: "Policy | None" = None) -> Policy:
    """ONE policy from ONE reserve. The session config owns reserve_pct; the
    stored policy contributes notice/wind-down thresholds, slid down if the
    reserve floor requires it. Every reader must go through this."""
    return Policy.for_reserve(reserve_pct, stored)


def zone_for(used_pct: float | None, policy: Policy) -> str:
    if used_pct is None:
        return UNKNOWN
    if used_pct >= 100.0:
        return EXHAUSTED
    if used_pct >= policy.reserve_floor:
        return RESERVE
    if used_pct >= policy.winddown_pct:
        return WINDDOWN
    if used_pct >= policy.notice_pct:
        return NOTICE
    return CLEAR


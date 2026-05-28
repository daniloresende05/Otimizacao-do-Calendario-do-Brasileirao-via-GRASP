from __future__ import annotations
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple

@dataclass(frozen=True)
class Team:
    name: str
    stadium: str
    state: str

@dataclass(frozen=True)
class Match:
    home: str
    away: str

@dataclass(frozen=True)
class ScheduledMatch:
    round: int
    day: str          # data como string (ex: "2023-08-20") ou o formato que vier do CSV
    home: str
    away: str
    stadium: str
    home_state: str
    away_state: str

Schedule = List[ScheduledMatch]
TeamMap = Dict[str, Team]


@dataclass(frozen=True)
class PRVOccurrence:
    stadium: str
    match_a: ScheduledMatch
    match_b: ScheduledMatch
    days_between: int


@dataclass(frozen=True)
class PRVResult:
    total_prv: int
    occurrences: List[PRVOccurrence]
    prv_by_stadium: Dict[str, int]


@dataclass(frozen=True)
class ConstraintViolation:
    constraint_id: str
    description: str
    round: Optional[int] = None
    team: Optional[str] = None
    stadium: Optional[str] = None


@dataclass(frozen=True)
class EvaluationResult:
    total_cost: float
    total_prv: int
    prv_result: PRVResult
    hard_constraint_violations: List[ConstraintViolation]
    soft_constraint_violations: List[ConstraintViolation]
    violations_by_type: Dict[str, int]

    @property
    def is_feasible(self) -> bool:
        return not self.hard_constraint_violations

    def lexicographic_key(self) -> Tuple[int, int, int]:
        """Chave de comparacao lexicografica: (hard, soft_estruturais, prv).

        Quanto MENOR a tupla, melhor a solucao."""
        hard_count = len(self.hard_constraint_violations)
        soft_estruturais = sum(
            1 for v in self.soft_constraint_violations
            if v.constraint_id != "h"
        )
        return (hard_count, soft_estruturais, self.total_prv)

    def is_better_than(self, other: "EvaluationResult") -> bool:
        """True sse self eh estritamente melhor que other lexicograficamente."""
        return self.lexicographic_key() < other.lexicographic_key()

    def summary(self) -> str:
        lines = [
            "Schedule evaluation",
            f"  is_feasible: {self.is_feasible}",
            f"  lex_key:     {self.lexicographic_key()}",
            f"  total_cost:  {self.total_cost:.2f}",
            f"  total_prv:   {self.total_prv}",
            f"  hard:        {len(self.hard_constraint_violations)}",
            f"  soft:        {len(self.soft_constraint_violations)}",
            "  violations_by_type:",
        ]
        for cid, count in self.violations_by_type.items():
            lines.append(f"    {cid}: {count}")
        return "\n".join(lines)

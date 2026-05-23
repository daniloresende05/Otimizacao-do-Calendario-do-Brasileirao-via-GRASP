from __future__ import annotations

import logging
import warnings
from datetime import datetime
from typing import TYPE_CHECKING

from .constraints import CONSTRAINT_CHECKS
from .domain import (
    ConstraintViolation,
    EvaluationResult,
    PRVOccurrence,
    PRVResult,
    Schedule,
    ScheduledMatch,
)

if TYPE_CHECKING:
    import pandas as pd

logger = logging.getLogger(__name__)

HARD_CONSTRAINTS: set[str] = {"a", "b"}

# h tem peso 0 por design: o custo de PRV já é contabilizado pelo termo
# w["prv"] * total_prv. A entrada "h" em violations_by_type permanece como
# registro informativo (a checagem (h) continua no registry para uniformidade).
DEFAULT_WEIGHTS: dict[str, float] = {
    "prv": 1.0,
    "a": 100.0,
    "b": 100.0,
    "c": 100.0,
    "d": 100.0,
    "e": 100.0,
    "f": 100.0,
    "g": 100.0,
    "h": 0.0,
}

_DATE_FMT = "%d/%m/%Y"


def _parse_day(day: str) -> datetime:
    return datetime.strptime(day, _DATE_FMT)


def compute_prv(schedule: Schedule, prv_days: int = 5) -> PRVResult:
    """Conta PRVs: pares consecutivos no mesmo estádio com intervalo < prv_days dias."""
    by_stadium: dict[str, list[ScheduledMatch]] = {}
    for match in schedule:
        by_stadium.setdefault(match.stadium, []).append(match)

    occurrences: list[PRVOccurrence] = []
    prv_by_stadium: dict[str, int] = {}

    for stadium, matches in by_stadium.items():
        ordered = sorted(matches, key=lambda m: (_parse_day(m.day), m.round))
        for earlier, later in zip(ordered, ordered[1:]):
            delta = (_parse_day(later.day) - _parse_day(earlier.day)).days
            if delta < prv_days:
                occurrences.append(
                    PRVOccurrence(
                        stadium=stadium,
                        match_a=earlier,
                        match_b=later,
                        days_between=delta,
                    )
                )
                prv_by_stadium[stadium] = prv_by_stadium.get(stadium, 0) + 1

    total_prv = sum(prv_by_stadium.values())
    return PRVResult(
        total_prv=total_prv,
        occurrences=occurrences,
        prv_by_stadium=prv_by_stadium,
    )


def evaluate(
    schedule: Schedule,
    weights: dict[str, float] | None = None,
    prv_days: int = 5,
) -> EvaluationResult:
    """
    Avalia f(x) = w[prv] * total_prv + Σ_c w[c] * |violations_c|
    iterando o registry CONSTRAINT_CHECKS.

    HARD_CONSTRAINTS = {"a", "b"} populam hard_constraint_violations;
    demais populam soft_constraint_violations.

    weights faltantes herdam de DEFAULT_WEIGHTS. (h) tem peso default 0
    para evitar dupla contagem com w["prv"] * total_prv.
    """
    w = {**DEFAULT_WEIGHTS, **(weights or {})}

    prv_result = compute_prv(schedule, prv_days=prv_days)

    hard: list[ConstraintViolation] = []
    soft: list[ConstraintViolation] = []
    violations_by_type: dict[str, int] = {}

    for constraint_id, check_fn in CONSTRAINT_CHECKS:
        if constraint_id == "h":
            violations = check_fn(schedule, prv_days=prv_days)
        else:
            violations = check_fn(schedule)

        violations_by_type[constraint_id] = len(violations)
        target = hard if constraint_id in HARD_CONSTRAINTS else soft
        target.extend(violations)

    total_cost = w["prv"] * prv_result.total_prv + sum(
        w.get(cid, 0.0) * count for cid, count in violations_by_type.items()
    )

    logger.debug(
        "evaluate: total_prv=%d violations=%s total_cost=%.2f",
        prv_result.total_prv,
        violations_by_type,
        total_cost,
    )

    return EvaluationResult(
        total_cost=total_cost,
        total_prv=prv_result.total_prv,
        prv_result=prv_result,
        hard_constraint_violations=hard,
        soft_constraint_violations=soft,
        violations_by_type=violations_by_type,
    )


def add_prv_column(df: "pd.DataFrame", prv_days: int = 5) -> "pd.DataFrame":
    """DEPRECATED: use compute_prv(schedule)."""
    warnings.warn(
        "add_prv_column é deprecated; use compute_prv(schedule) sobre objetos do domínio.",
        DeprecationWarning,
        stacklevel=2,
    )
    import pandas as pd  # noqa: F401  (mantido isolado do escopo de módulo)

    schedule: Schedule = [
        ScheduledMatch(
            round=int(row["round"]),
            day=str(row["day"]),
            home=str(row["home"]),
            away=str(row["away"]),
            stadium=str(row["stadium"]),
            home_state=str(row["home_state"]) if "home_state" in row else "",
            away_state=str(row["away_state"]) if "away_state" in row else "",
        )
        for _, row in df.iterrows()
    ]
    result = compute_prv(schedule, prv_days=prv_days)

    prv_keys = {
        (occ.match_b.round, occ.match_b.home, occ.match_b.away, occ.match_b.day)
        for occ in result.occurrences
    }

    df_out = df.copy()
    df_out["PRV"] = [
        1
        if (int(row["round"]), str(row["home"]), str(row["away"]), str(row["day"]))
        in prv_keys
        else 0
        for _, row in df_out.iterrows()
    ]
    return df_out

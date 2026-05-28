from __future__ import annotations

import logging
import random
from dataclasses import dataclass, field
from datetime import date

from .construction import construct_schedule
from .domain import EvaluationResult, Schedule, TeamMap
from .objective import evaluate

logger = logging.getLogger(__name__)

DEFAULT_ALPHA_POOL: list[float] = [0.1, 0.2, 0.3, 0.4]


@dataclass(frozen=True)
class GRASPIteration:
    """Registro de uma unica iteracao do loop multi-start."""

    iter_number: int
    seed: int
    alpha: float
    total_prv: int
    total_cost: float
    is_feasible: bool
    is_new_best: bool
    lex_key: tuple[int, int, int]


@dataclass
class GRASPResult:
    """Resultado completo da execucao do GRASP."""

    best_schedule: Schedule
    best_evaluation: EvaluationResult
    best_iter: int
    best_seed: int
    best_alpha: float
    total_iterations: int
    stopped_by: str  # "max_iter" | "max_iter_no_improve"
    history: list[GRASPIteration] = field(default_factory=list)


def grasp(
    teams_map: TeamMap,
    dates: list[date],
    *,
    max_iter: int = 50,
    max_iter_no_improve: int = 20,
    alpha_pool: list[float] | None = None,
    seed: int = 42,
    round_gap: int = 7,
    round_span: int = 3,
    prv_days: int = 5,
    min_team_rest_days: int = 3,
    max_consecutive: int = 2,
    weights: dict[str, float] | None = None,
) -> GRASPResult:
    """Loop multi-start do GRASP (Algoritmo 1, sem busca local)."""
    rng_alpha = random.Random(seed)
    pool = alpha_pool if alpha_pool is not None else DEFAULT_ALPHA_POOL

    best_schedule: Schedule | None = None
    best_eval: EvaluationResult | None = None
    best_iter = -1
    best_seed = -1
    best_alpha = -1.0
    history: list[GRASPIteration] = []
    iter_no_improve = 0
    stopped_by = "max_iter"

    for i in range(max_iter):
        seed_iter = seed + i
        alpha_iter = rng_alpha.choice(pool)

        schedule = construct_schedule(
            teams_map,
            dates,
            alpha=alpha_iter,
            seed=seed_iter,
            round_gap=round_gap,
            round_span=round_span,
            prv_days=prv_days,
            min_team_rest_days=min_team_rest_days,
            max_consecutive=max_consecutive,
        )
        avaliacao = evaluate(schedule, weights=weights, prv_days=prv_days)

        is_new_best = best_eval is None or avaliacao.is_better_than(best_eval)

        if is_new_best:
            best_schedule = schedule
            best_eval = avaliacao
            best_iter = i
            best_seed = seed_iter
            best_alpha = alpha_iter
            iter_no_improve = 0
            logger.info(
                "Iter %d/%d: novo melhor lex=%s, PRV=%d",
                i + 1,
                max_iter,
                avaliacao.lexicographic_key(),
                avaliacao.total_prv,
            )
        else:
            iter_no_improve += 1

        history.append(
            GRASPIteration(
                iter_number=i + 1,
                seed=seed_iter,
                alpha=alpha_iter,
                total_prv=avaliacao.total_prv,
                total_cost=avaliacao.total_cost,
                is_feasible=avaliacao.is_feasible,
                is_new_best=is_new_best,
                lex_key=avaliacao.lexicographic_key(),
            )
        )

        if iter_no_improve >= max_iter_no_improve:
            stopped_by = "max_iter_no_improve"
            break

    assert best_schedule is not None and best_eval is not None
    return GRASPResult(
        best_schedule=best_schedule,
        best_evaluation=best_eval,
        best_iter=best_iter + 1,
        best_seed=best_seed,
        best_alpha=best_alpha,
        total_iterations=len(history),
        stopped_by=stopped_by,
        history=history,
    )

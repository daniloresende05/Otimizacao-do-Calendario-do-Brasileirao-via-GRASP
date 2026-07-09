"""Iterated Local Search (ILS) para o calendário do Brasileirão.

Arquitetura (Opção B): o ILS é uma **pós-otimização** — roda UMA vez sobre a
melhor solução do GRASP. Ele USA o VND (:mod:`brasileirao.local_search`) como
caixa-preta (chama ``local_search``) e NÃO reimplementa busca local.

Esqueleto do ILS::

    s0 -> VND -> s*        (ótimo local inicial)
    repete:
        s'  = perturba(s*, k)        # k movimentos aleatórios, aceitos mesmo piorando
        s'' = VND(s')                # re-otimiza
        se s''.is_better_than(s*): s* = s'' ; k = k_min   (aceitação better-only)
        senão:                       k += step (até k_max)  (força crescente kp)
    retorna melhor global

API pública:
  * ``perturb`` — aplica ``k`` movimentos aleatórios (vizinhanças do VND).
  * ``next_k`` — regra de força crescente ``kp``.
  * ``iterated_local_search`` — o motor do ILS.

Decisões fixas refletidas aqui:
  * A perturbação aplica ``k`` movimentos ALEATÓRIOS em sequência, escolhidos
    entre as vizinhanças do VND (``swap_homes``/``swap_days`` via
    ``NEIGHBORHOODS``), ACEITOS mesmo que piorem (é a piora que escapa do ótimo
    local). Não avalia custo aqui.
  * Cada movimento respeita âncoras ``{1,2,18,19,20,21,37,38}`` e validade
    (``min_team_rest_days``, janela) — isso já é garantido pelos geradores de
    vizinhança reutilizados; a regra NÃO é reimplementada.
  * Aceitação BETTER-ONLY via ``EvaluationResult.is_better_than``.
  * Determinístico dado o ``rng``/``seed``.
"""
from __future__ import annotations

import random

from .domain import EvaluationResult, Schedule, TeamMap
from .local_search import FROZEN_ROUNDS, NEIGHBORHOODS, local_search
from .objective import evaluate


# ---------------------------------------------------------------------------
# Perturbação
# ---------------------------------------------------------------------------

def _apply_random_move(
    schedule: Schedule,
    teams_map: TeamMap,
    rng: random.Random,
    neighborhood_names: list[str],
    min_team_rest_days: int,
) -> Schedule:
    """Aplica UM movimento aleatório e válido, ou devolve ``schedule`` intacto.

    Sorteia uma ordem das vizinhanças e usa a primeira que gerar ao menos um
    vizinho válido (os geradores já pulam âncoras e movimentos inválidos);
    dentre eles, escolhe um ao acaso. Se nenhuma vizinhança conseguir mover,
    retorna a agenda inalterada.
    """
    order = list(neighborhood_names)
    rng.shuffle(order)
    for name in order:
        generate = NEIGHBORHOODS[name]
        neighbors = generate(
            schedule,
            teams_map,
            frozen_rounds=FROZEN_ROUNDS,
            min_team_rest_days=min_team_rest_days,
        )
        if neighbors:
            return rng.choice(neighbors)
    return schedule


def perturb(
    schedule: Schedule,
    teams_map: TeamMap,
    k: int,
    rng: random.Random,
    *,
    neighborhoods: list[str] | None = None,
    min_team_rest_days: int = 3,
) -> Schedule:
    """Perturba ``schedule`` aplicando ``k`` movimentos aleatórios em sequência.

    Cada movimento é sorteado entre as vizinhanças do VND (default: todas as de
    ``NEIGHBORHOODS``) e ACEITO mesmo que piore a solução — a perturbação não
    avalia custo. Devolve uma NOVA ``Schedule`` (não muta a entrada) e é
    determinística dado ``rng``.
    """
    names = list(neighborhoods) if neighborhoods is not None else list(NEIGHBORHOODS)
    current = schedule
    for _ in range(k):
        current = _apply_random_move(current, teams_map, rng, names, min_team_rest_days)
    return current


# ---------------------------------------------------------------------------
# Força crescente kp
# ---------------------------------------------------------------------------

def next_k(
    k: int,
    *,
    improved: bool,
    perturbation_min: int,
    perturbation_step: int,
    perturbation_max: int,
) -> int:
    """Próximo valor de ``k`` na regra de força crescente (estilo ``kp``).

    Ao MELHORAR, a força volta ao mínimo; caso contrário, sobe um passo, sem
    nunca ultrapassar ``perturbation_max``.
    """
    if improved:
        return perturbation_min
    return min(k + perturbation_step, perturbation_max)


# ---------------------------------------------------------------------------
# Motor do ILS
# ---------------------------------------------------------------------------

def iterated_local_search(
    schedule: Schedule,
    teams_map: TeamMap,
    *,
    neighborhoods: list[str] | None = None,
    weights: dict[str, float] | None = None,
    prv_days: int = 5,
    min_team_rest_days: int = 3,
    perturbation_min: int = 1,
    perturbation_step: int = 1,
    perturbation_max: int = 5,
    max_iter_no_improve: int = 20,
    max_iter: int = 200,
    seed: int = 42,
) -> Schedule:
    """Iterated Local Search sobre ``schedule`` (pós-otimização do GRASP).

    Estrutura: ``s* = VND(s)``; repete ``[ perturba(s*, k) -> VND -> aceita ]``
    com aceitação BETTER-ONLY e força crescente ``kp``; retorna o melhor global
    ``s_best``. O VND (``local_search``) é usado como caixa-preta.

    Para quando atinge ``max_iter_no_improve`` iterações seguidas sem melhorar
    ``s_best`` ou ``max_iter`` iterações no total (``max_iter=0`` devolve apenas
    o VND inicial). Determinístico dado ``seed`` (a perturbação é aleatória).
    """
    def vnd(candidate: Schedule) -> Schedule:
        return local_search(
            candidate,
            teams_map,
            neighborhoods=neighborhoods,
            weights=weights,
            prv_days=prv_days,
            min_team_rest_days=min_team_rest_days,
        )

    def evaluated(candidate: Schedule) -> EvaluationResult:
        return evaluate(candidate, weights=weights, prv_days=prv_days)

    rng = random.Random(seed)

    star = vnd(schedule)
    star_eval = evaluated(star)
    best, best_eval = star, star_eval

    k = perturbation_min
    no_improve = 0
    iterations = 0
    while iterations < max_iter and no_improve < max_iter_no_improve:
        iterations += 1
        perturbed = perturb(
            star,
            teams_map,
            k,
            rng,
            neighborhoods=neighborhoods,
            min_team_rest_days=min_team_rest_days,
        )
        trial = vnd(perturbed)
        trial_eval = evaluated(trial)

        improved = trial_eval.is_better_than(star_eval)
        if improved:
            star, star_eval = trial, trial_eval
            if trial_eval.is_better_than(best_eval):
                best, best_eval = trial, trial_eval
            no_improve = 0
        else:
            no_improve += 1
        k = next_k(
            k,
            improved=improved,
            perturbation_min=perturbation_min,
            perturbation_step=perturbation_step,
            perturbation_max=perturbation_max,
        )
    return best

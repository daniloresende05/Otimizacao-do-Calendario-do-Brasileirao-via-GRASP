"""Busca local (VND) para o calendário do Brasileirão.

Este módulo implementa a fase de busca local do GRASP+ILS na forma de um
**VND (Variable Neighborhood Descent)** sobre uma ``Schedule``, minimizando
lexicograficamente ``(hard, soft_estruturais, total_prv)`` via
``EvaluationResult.is_better_than``.

Decisões fixas (não reabrir):
  * VND com lista ORDENADA de vizinhanças (default ``["swap_homes", "swap_days"]``):
    explora uma vizinhança enquanto melhora; parou de melhorar, passa à próxima;
    se QUALQUER vizinhança melhora, VOLTA à primeira; termina quando nenhuma
    melhora. A ordem é PARÂMETRO (lista), não fixa no meio do código.
  * Dentro de uma vizinhança: best-improvement (melhor vizinho do movimento).
  * Movimentos v1: apenas ``swap_homes`` e ``swap_days``.
  * Âncoras CONGELADAS: rodadas ``{1,2,18,19,20,21,37,38}`` nunca são tocadas.

API pública:
  * ``swap_homes`` / ``swap_days`` — geradores puros de vizinhos válidos.
  * ``NEIGHBORHOODS`` — registro nome -> gerador, consumido pelo motor.
  * ``descend`` — best-improvement em UMA vizinhança até seu ótimo local.
  * ``local_search`` — o motor do VND.
"""
from __future__ import annotations

from datetime import datetime
from typing import Callable

from .dates import parse_day as _parse_day
from .domain import EvaluationResult, Schedule, ScheduledMatch, TeamMap
from .objective import evaluate

# ---------------------------------------------------------------------------
# Constantes e tipos do módulo
# ---------------------------------------------------------------------------

#: Rodadas congeladas (âncoras estruturais): nunca são tocadas por nenhum movimento.
FROZEN_ROUNDS: frozenset[int] = frozenset({1, 2, 18, 19, 20, 21, 37, 38})

#: Ordem default das vizinhanças exploradas pelo VND.
DEFAULT_NEIGHBORHOODS: list[str] = ["swap_homes", "swap_days"]

#: Assinatura de um gerador de vizinhança: (schedule, teams_map, *) -> vizinhos.
NeighborhoodFn = Callable[..., list[Schedule]]


# ---------------------------------------------------------------------------
# Helpers puros sobre jogos/agenda (sem I/O, sem mutação; ScheduledMatch é frozen)
# ---------------------------------------------------------------------------

def _pair_key(m: ScheduledMatch) -> tuple[str, str]:
    """Confronto de ``m`` como par não-ordenado canônico (times em ordem)."""
    a, b = sorted((m.home, m.away))
    return (a, b)


def _touches_frozen(m: ScheduledMatch, frozen_rounds: frozenset[int]) -> bool:
    """``True`` sse o jogo pertence a uma rodada congelada (âncora)."""
    return m.round in frozen_rounds


def _with_home_inverted(m: ScheduledMatch, teams_map: TeamMap) -> ScheduledMatch:
    """Novo jogo com o mando invertido (mandante vira visitante e vice-versa).

    Preserva ``round`` e ``day``; ``stadium``/estados passam a refletir o novo
    mandante.
    """
    new_home, new_away = m.away, m.home
    return ScheduledMatch(
        round=m.round,
        day=m.day,
        home=new_home,
        away=new_away,
        stadium=teams_map[new_home].stadium,
        home_state=teams_map[new_home].state,
        away_state=teams_map[new_away].state,
    )


def _with_day(m: ScheduledMatch, day: str) -> ScheduledMatch:
    """Novo jogo idêntico a ``m``, porém com outra data (``day``)."""
    return ScheduledMatch(
        round=m.round,
        day=day,
        home=m.home,
        away=m.away,
        stadium=m.stadium,
        home_state=m.home_state,
        away_state=m.away_state,
    )


def _respects_min_rest(schedule: Schedule, min_team_rest_days: int) -> bool:
    """``True`` sse todo par de jogos consecutivos de um mesmo time respeita
    o descanso mínimo (``>= min_team_rest_days`` dias entre datas)."""
    days_by_team: dict[str, list[datetime]] = {}
    for m in schedule:
        day = _parse_day(m.day)
        days_by_team.setdefault(m.home, []).append(day)
        days_by_team.setdefault(m.away, []).append(day)
    for days in days_by_team.values():
        days.sort()
        for earlier, later in zip(days, days[1:]):
            if (later - earlier).days < min_team_rest_days:
                return False
    return True


def _group_by(schedule: Schedule, key: Callable[[ScheduledMatch], object]) -> dict:
    """Índices dos jogos de ``schedule`` agrupados por ``key(jogo)``."""
    groups: dict = {}
    for i, m in enumerate(schedule):
        groups.setdefault(key(m), []).append(i)
    return groups


# ---------------------------------------------------------------------------
# Vizinhança 1: swap_homes — inverte o mando de um confronto (duplo turno)
# ---------------------------------------------------------------------------

def _invert_confronto(schedule: Schedule, legs: list[int], teams_map: TeamMap) -> Schedule:
    """Nova agenda com o mando invertido em todas as pernas indicadas."""
    to_invert = set(legs)
    return [
        _with_home_inverted(m, teams_map) if i in to_invert else m
        for i, m in enumerate(schedule)
    ]


def swap_homes(
    schedule: Schedule,
    teams_map: TeamMap,
    *,
    frozen_rounds: frozenset[int] = FROZEN_ROUNDS,
    min_team_rest_days: int = 3,
) -> list[Schedule]:
    """Gera os vizinhos de ``swap_homes``.

    Para cada confronto (par não-ordenado de times), inverte o mando de TODAS
    as suas pernas simultaneamente — preservando o duplo turno (constraint b:
    continua havendo uma perna em cada direção). Não altera datas.

    Regras de validade:
      * PULA o confronto se QUALQUER perna estiver em rodada congelada.
      * PULA vizinhos que violem ``min_team_rest_days`` (swap_homes não muda as
        datas de nenhum time, então na prática isso só descarta ruídos).

    Cada vizinho é uma ``Schedule`` nova; a função é pura (não muta ``schedule``).
    """
    legs_by_confronto = _group_by(schedule, _pair_key)

    neighbors: list[Schedule] = []
    for confronto in sorted(legs_by_confronto):
        legs = legs_by_confronto[confronto]
        if any(_touches_frozen(schedule[i], frozen_rounds) for i in legs):
            continue
        neighbor = _invert_confronto(schedule, legs, teams_map)
        if _respects_min_rest(neighbor, min_team_rest_days):
            neighbors.append(neighbor)
    return neighbors


# ---------------------------------------------------------------------------
# Vizinhança 2: swap_days — troca a data entre dois jogos da mesma rodada
# ---------------------------------------------------------------------------

def _swap_days_between(schedule: Schedule, i: int, j: int) -> Schedule:
    """Nova agenda com as datas dos jogos ``i`` e ``j`` trocadas entre si."""
    neighbor = list(schedule)
    neighbor[i] = _with_day(schedule[i], schedule[j].day)
    neighbor[j] = _with_day(schedule[j], schedule[i].day)
    return neighbor


def swap_days(
    schedule: Schedule,
    teams_map: TeamMap,
    *,
    frozen_rounds: frozenset[int] = FROZEN_ROUNDS,
    min_team_rest_days: int = 3,
) -> list[Schedule]:
    """Gera os vizinhos de ``swap_days``.

    Para cada rodada não-congelada, troca a data (``day``) entre cada par de
    jogos daquela rodada. Mantém mandos e confrontos intactos (só mexe em
    datas), e como só permuta datas já presentes, nenhum jogo sai da janela.

    Regras de validade:
      * PULA rodadas congeladas (âncoras).
      * PULA pares cujos jogos já tenham a MESMA data (movimento nulo).
      * PULA vizinhos que violem ``min_team_rest_days``.

    Cada vizinho é uma ``Schedule`` nova; a função é pura.
    """
    legs_by_round = _group_by(schedule, lambda m: m.round)

    neighbors: list[Schedule] = []
    for rnd in sorted(legs_by_round):
        if rnd in frozen_rounds:
            continue
        legs = legs_by_round[rnd]
        for a in range(len(legs)):
            for b in range(a + 1, len(legs)):
                i, j = legs[a], legs[b]
                if schedule[i].day == schedule[j].day:
                    continue  # movimento nulo
                neighbor = _swap_days_between(schedule, i, j)
                if _respects_min_rest(neighbor, min_team_rest_days):
                    neighbors.append(neighbor)
    return neighbors


# ---------------------------------------------------------------------------
# Registro nome -> gerador de vizinhança (consumido pelo motor do VND)
# ---------------------------------------------------------------------------

#: Mapeia o nome de uma vizinhança à sua função geradora. O motor do VND
#: recebe uma lista ORDENADA de nomes e resolve as funções por aqui.
NEIGHBORHOODS: dict[str, NeighborhoodFn] = {
    "swap_homes": swap_homes,
    "swap_days": swap_days,
}


# ---------------------------------------------------------------------------
# Motor do VND
# ---------------------------------------------------------------------------

def _best_improving_neighbor(
    schedule: Schedule,
    base_eval: EvaluationResult,
    generate: NeighborhoodFn,
    teams_map: TeamMap,
    *,
    weights: dict[str, float] | None,
    prv_days: int,
    min_team_rest_days: int,
) -> tuple[Schedule, EvaluationResult] | None:
    """Melhor vizinho ESTRITAMENTE melhor que ``base_eval``, ou ``None``.

    ``is_better_than`` é estrito, então empates preservam o PRIMEIRO candidato
    na ordem (determinística) de geração — garantindo determinismo por seed.
    """
    best: tuple[Schedule, EvaluationResult] | None = None
    best_eval = base_eval
    for neighbor in generate(
        schedule,
        teams_map,
        frozen_rounds=FROZEN_ROUNDS,
        min_team_rest_days=min_team_rest_days,
    ):
        cand_eval = evaluate(neighbor, weights=weights, prv_days=prv_days)
        if cand_eval.is_better_than(best_eval):
            best = (neighbor, cand_eval)
            best_eval = cand_eval
    return best


def descend(
    schedule: Schedule,
    teams_map: TeamMap,
    neighborhood: str,
    *,
    weights: dict[str, float] | None = None,
    prv_days: int = 5,
    min_team_rest_days: int = 3,
) -> Schedule:
    """Best-improvement dentro de UMA vizinhança até seu ótimo local.

    Aplica repetidamente o melhor vizinho estritamente melhor gerado pela
    vizinhança ``neighborhood``; termina quando nenhum vizinho melhora.

    A vizinhança é resolvida por ``NEIGHBORHOODS[neighborhood]`` (e não por
    referência direta) para que instrumentações/substituições do registro
    sejam respeitadas.
    """
    generate = NEIGHBORHOODS[neighborhood]
    current = schedule
    current_eval = evaluate(current, weights=weights, prv_days=prv_days)
    while True:
        improvement = _best_improving_neighbor(
            current,
            current_eval,
            generate,
            teams_map,
            weights=weights,
            prv_days=prv_days,
            min_team_rest_days=min_team_rest_days,
        )
        if improvement is None:
            return current
        current, current_eval = improvement


def local_search(
    schedule: Schedule,
    teams_map: TeamMap,
    *,
    neighborhoods: list[str] | None = None,
    weights: dict[str, float] | None = None,
    prv_days: int = 5,
    max_consecutive: int = 2,
    min_team_rest_days: int = 3,
    max_iter_no_improve: int = 50,
    seed: int = 42,
) -> Schedule:
    """Busca local VND sobre ``schedule``.

    Percorre a lista ORDENADA de vizinhanças ``neighborhoods`` (default
    ``DEFAULT_NEIGHBORHOODS``): faz o *descend* (best-improvement) na vizinhança
    atual; se melhorou, VOLTA à primeira; senão, passa à próxima. Termina quando
    nenhuma vizinhança melhora (ótimo local conjunto).

    Como cada melhora reduz estritamente a chave lexicográfica (limitada por
    baixo em ``(0,0,0)``), o laço termina naturalmente; ``max_iter_no_improve``
    é apenas uma REDE DE SEGURANÇA contra laços patológicos. ``seed`` é aceito
    para compatibilidade de contrato — o VND v1 (best-improvement) é
    determinístico e não usa aleatoriedade. ``max_consecutive`` segue o default
    de ``evaluate``/``check_g`` (não é re-exposto por ``evaluate``).
    """
    order = list(neighborhoods) if neighborhoods is not None else list(DEFAULT_NEIGHBORHOODS)

    current = schedule
    current_eval = evaluate(current, weights=weights, prv_days=prv_days)

    k = 0
    improvements = 0
    while k < len(order) and improvements < max_iter_no_improve:
        candidate = descend(
            current,
            teams_map,
            order[k],
            weights=weights,
            prv_days=prv_days,
            min_team_rest_days=min_team_rest_days,
        )
        candidate_eval = evaluate(candidate, weights=weights, prv_days=prv_days)
        if candidate_eval.is_better_than(current_eval):
            current, current_eval = candidate, candidate_eval
            improvements += 1
            k = 0  # reinicia na primeira vizinhança
        else:
            k += 1  # nenhuma melhora aqui -> próxima vizinhança
    return current

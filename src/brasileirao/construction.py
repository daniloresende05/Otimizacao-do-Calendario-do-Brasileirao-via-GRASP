from __future__ import annotations

import random
from datetime import date
from math import ceil
from typing import Iterator

from .domain import Match, Schedule, ScheduledMatch, TeamMap
from .round_robin import circle_method

MatchesByRound = dict[int, list[Match]]

CONSTRUCTION_WEIGHTS = {
    "f": 100.0,
    "g": 300.0,
}


class ConstructionFailedError(Exception):
    """Levantada se a construção esgota matchings sem completar 19 rodadas."""


# ---------------------------------------------------------------------------
# Funções auxiliares públicas
# ---------------------------------------------------------------------------

def enumerate_all_orientations(
    pairs: list[tuple[str, str]],
) -> Iterator[list[tuple[str, str]]]:
    """Gera todas as 2^len(pairs) orientações possíveis (1024 para 10 pares).

    Convenção: bit `k` ligado em `mask` significa que o par `pairs[k]` mantém
    a ordem `(a, b)` (a manda); bit desligado inverte para `(b, a)`.
    """
    n = len(pairs)
    for mask in range(1 << n):
        yield [
            (a, b) if (mask >> k) & 1 else (b, a)
            for k, (a, b) in enumerate(pairs)
        ]


def no_classico_estadual(
    pairs: list[tuple[str, str]],
    teams_map: TeamMap,
) -> bool:
    """True se nenhum par tem times do mesmo estado."""
    return all(teams_map[a].state != teams_map[b].state for a, b in pairs)


def count_classicos(
    pairs: list[tuple[str, str]],
    teams_map: TeamMap,
) -> int:
    """Quantos pares são clássicos estaduais."""
    return sum(1 for a, b in pairs if teams_map[a].state == teams_map[b].state)


def orient_randomly(
    pairs: list[tuple[str, str]],
    rng: random.Random,
) -> list[tuple[str, str]]:
    """Sorteia orientação par a par."""
    return [(a, b) if rng.random() < 0.5 else (b, a) for a, b in pairs]


def orient_by_inversion(
    pairs: list[tuple[str, str]],
    reference_oriented: list[tuple[str, str]],
) -> list[tuple[str, str]]:
    """Orienta cada par para que cada time fique no lado oposto ao de
    `reference_oriented`. Em pares onde ambos os times têm o mesmo lado na
    referência, mantém-se o primeiro time no lado oposto e o segundo recebe
    o lado errado (violação residual de (d))."""
    sides = _sides_from_oriented(reference_oriented)
    return _orient_inverting_sides(pairs, sides)


def invert_homes(
    oriented: list[tuple[str, str]],
) -> list[tuple[str, str]]:
    """Inverte mando: (h, a) → (a, h)."""
    return [(a, h) for h, a in oriented]


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _sides_from_oriented(
    oriented: list[tuple[str, str]],
) -> dict[str, str]:
    sides: dict[str, str] = {}
    for h, a in oriented:
        sides[h] = "H"
        sides[a] = "A"
    return sides


def _orient_inverting_sides(
    pairs: list[tuple[str, str]],
    sides_ref: dict[str, str],
) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for a, b in pairs:
        sa = sides_ref.get(a)
        sb = sides_ref.get(b)
        if sa == "H" and sb == "A":
            out.append((b, a))
        elif sa == "A" and sb == "H":
            out.append((a, b))
        elif sa == "H" and sb == "H":
            out.append((b, a))
        else:
            out.append((a, b))
    return out


def _two_color_pair_union(
    r1_pairs: list[tuple[str, str]],
    r2_pairs: list[tuple[str, str]],
    teams: list[str],
    rng: random.Random,
) -> dict[str, str]:
    """2-colore o grafo formado pela união das arestas de R1 e R2.

    Esse grafo é sempre bipartido: cada vértice tem grau 2 (uma aresta de
    cada matching) e os ciclos formados alternam arestas de R1/R2, então têm
    tamanho par. A 2-coloração define `sides_r1`, e como cada aresta de R2
    liga vértices de cores opostas, R2 fica automaticamente "perfectly cut"
    em relação a `sides_r1` — i.e., (c) sai estrita."""
    adj: dict[str, list[str]] = {t: [] for t in teams}
    for a, b in r1_pairs:
        adj[a].append(b)
        adj[b].append(a)
    for a, b in r2_pairs:
        adj[a].append(b)
        adj[b].append(a)

    sides: dict[str, str] = {}
    for start in teams:
        if start in sides:
            continue
        sides[start] = "H" if rng.random() < 0.5 else "A"
        stack = [start]
        while stack:
            cur = stack.pop()
            cur_side = sides[cur]
            other = "A" if cur_side == "H" else "H"
            for neigh in adj[cur]:
                if neigh not in sides:
                    sides[neigh] = other
                    stack.append(neigh)
    return sides


def _chain_g_violations(
    team_idx_list: list[int],
    sides_sequence: list[list[int]],  # cada item: list[int] (1=H,2=A) por time
    last_side_in: list[int],
    streak_in: list[int],
    max_cons: int,
) -> int:
    """Soma violações de (g) ao aplicar uma sequência de rodadas sobre o
    estado (last_side_in, streak_in). Não muta as listas de entrada."""
    last = list(last_side_in)
    streak = list(streak_in)
    g = 0
    for round_sides in sides_sequence:
        for t in team_idx_list:
            s = round_sides[t]
            if last[t] == s:
                streak[t] += 1
                if streak[t] > max_cons:
                    g += 1
            else:
                last[t] = s
                streak[t] = 1
    return g


def _pick_r18_r19(
    remaining: list[list[tuple[str, str]]],
    sides_r1: dict[str, str],
    sides_r2: dict[str, str],
    teams_map: TeamMap,
    last_side: list[int],
    streak: list[int],
    max_cons: int,
    rng: random.Random,
) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """Atribui os 2 matchings remanescentes a R18 e R19. Considera (e)
    (R19 limpo se possível), (d) (inverter R1/R2 maximizando residual mínimo)
    e o impacto em (g) da cadeia R17→R18→R19.

    Estratégia:
      1. (e) determina quais ordens são permitidas (R19 deve ser limpo
         quando possível; senão escolhe o de menor # clássicos).
      2. Para cada ordem permitida, enumera 2^10 orientações para R18 e
         escolhe a que minimiza (d_resid_R18 + 1000·g_R17→R18). Em seguida
         enumera 2^10 orientações para R19 e escolhe a que minimiza
         (d_resid_R19 + 1000·g_R18→R19) — dado o estado pós-R18.
      3. Compara as ordens pelo custo total e escolhe a melhor.
    """
    teams = list(teams_map.keys())
    team_to_idx = {t: i for i, t in enumerate(teams)}
    n = len(teams)

    target_r18_int = [1 if sides_r1[t] == "A" else 2 for t in teams]
    target_r19_int = [1 if sides_r2[t] == "A" else 2 for t in teams]

    m_a, m_b = remaining
    clean_a = no_classico_estadual(m_a, teams_map)
    clean_b = no_classico_estadual(m_b, teams_map)

    if clean_a and not clean_b:
        orderings = [(m_b, m_a)]
    elif clean_b and not clean_a:
        orderings = [(m_a, m_b)]
    else:
        if not clean_a and not clean_b:
            cls_a = count_classicos(m_a, teams_map)
            cls_b = count_classicos(m_b, teams_map)
            if cls_a < cls_b:
                orderings = [(m_b, m_a)]
            elif cls_b < cls_a:
                orderings = [(m_a, m_b)]
            else:
                orderings = [(m_a, m_b), (m_b, m_a)]
        else:
            orderings = [(m_a, m_b), (m_b, m_a)]

    def _best_orientation_for_round(
        pairs: list[tuple[str, str]],
        target_sides: list[int],
        in_last: list[int],
        in_streak: list[int],
    ) -> tuple[list[tuple[str, str]], list[int], list[int], list[int], int]:
        """Retorna (oriented, sides_int, new_last, new_streak, cost)."""
        npairs = len(pairs)
        pairs_idx = [(team_to_idx[a], team_to_idx[b]) for a, b in pairs]
        best_cost = None
        best_mask = 0
        for mask in range(1 << npairs):
            d_resid = 0
            g_v = 0
            tmp_last = list(in_last)
            tmp_streak = list(in_streak)
            for k in range(npairs):
                ai, bi = pairs_idx[k]
                if (mask >> k) & 1:
                    home_i, away_i = ai, bi
                else:
                    home_i, away_i = bi, ai
                if target_sides[home_i] != 1:
                    d_resid += 1
                if target_sides[away_i] != 2:
                    d_resid += 1
                if tmp_last[home_i] == 1:
                    tmp_streak[home_i] += 1
                    if tmp_streak[home_i] > max_cons:
                        g_v += 1
                else:
                    tmp_last[home_i] = 1
                    tmp_streak[home_i] = 1
                if tmp_last[away_i] == 2:
                    tmp_streak[away_i] += 1
                    if tmp_streak[away_i] > max_cons:
                        g_v += 1
                else:
                    tmp_last[away_i] = 2
                    tmp_streak[away_i] = 1
            cost = 10 * d_resid + 1000 * g_v
            if best_cost is None or cost < best_cost:
                best_cost = cost
                best_mask = mask
                best_last = tmp_last
                best_streak = tmp_streak

        oriented = []
        sides_int = [0] * n
        for k in range(npairs):
            a, b = pairs[k]
            if (best_mask >> k) & 1:
                oriented.append((a, b))
                sides_int[team_to_idx[a]] = 1
                sides_int[team_to_idx[b]] = 2
            else:
                oriented.append((b, a))
                sides_int[team_to_idx[b]] = 1
                sides_int[team_to_idx[a]] = 2
        return oriented, sides_int, best_last, best_streak, best_cost  # type: ignore[return-value]

    candidates = []
    for r18_pairs, r19_pairs in orderings:
        r18_oriented, _, after_r18_last, after_r18_streak, c18 = (
            _best_orientation_for_round(
                r18_pairs, target_r18_int, last_side, streak,
            )
        )
        r19_oriented, _, _, _, c19 = _best_orientation_for_round(
            r19_pairs, target_r19_int, after_r18_last, after_r18_streak,
        )
        candidates.append((c18 + c19, r18_oriented, r19_oriented))

    best_cost = min(c[0] for c in candidates)
    best = [c for c in candidates if c[0] == best_cost]
    chosen = rng.choice(best)
    return chosen[1], chosen[2]


def _lookahead_g(
    t: int,
    t_new_side: int,         # 1=H, 2=A: lado em R(r) proposto
    last_side: list[int],
    streak: list[int],
    max_cons: int,
    r18_side: list[int],
    r19_side: list[int],
) -> int:
    """Conta novas violações de (g) que o team `t` introduz nas rodadas
    R18 e R19, dado que ele tem `t_new_side` na rodada atual (R17)."""
    g = 0
    if last_side[t] == t_new_side:
        s = streak[t] + 1
    else:
        s = 1
    last = t_new_side

    nx = r18_side[t]
    if nx == last:
        s += 1
    else:
        s = 1
        last = nx
    if s > max_cons:
        g += 1

    nx = r19_side[t]
    if nx == last:
        s += 1
    else:
        s = 1
        last = nx
    if s > max_cons:
        g += 1
    return g


def _pick_best_compat(
    remaining: list[list[tuple[str, str]]],
    sides_ref: dict[str, str],
    rng: random.Random,
    *,
    teams_map: TeamMap | None = None,
    prefer_clean: bool = False,
) -> list[tuple[str, str]]:
    """Pop e retorna o matching com mais pares "bipartite cut" em `sides_ref`.

    Se `prefer_clean=True`, restringe primeiro aos matchings sem clássicos
    estaduais; se nenhum existir, ignora o filtro.
    """
    pool = remaining
    if prefer_clean and teams_map is not None:
        clean = [m for m in pool if no_classico_estadual(m, teams_map)]
        if clean:
            pool = clean

    def compat(m: list[tuple[str, str]]) -> int:
        return sum(1 for a, b in m if sides_ref[a] != sides_ref[b])

    best_score = max(compat(m) for m in pool)
    best = [m for m in pool if compat(m) == best_score]
    chosen = rng.choice(best)
    remaining.remove(chosen)
    return chosen


# ---------------------------------------------------------------------------
# API principal
# ---------------------------------------------------------------------------

def build_matches_with_homes(
    teams_map: TeamMap,
    *,
    alpha: float = 0.3,
    seed: int = 42,
    max_consecutive: int = 2,
) -> MatchesByRound:
    """Constrói os confrontos do duplo round-robin com mando definido.

    Resolve por construção:
      (a) cada time joga 1x por rodada
      (b) cada par se enfrenta 2x com mandos invertidos (turno + returno espelhado)
      (c) alternância C/F entre R1 e R2 (best-effort: pode ter resíduo se
          o matching de R2 não for "bipartite cut" perfeito de R1)
      (d) espelho R18↔R1 e R19↔R2 (best-effort, mesma observação de (c))
      (e) R38 (espelho de R19 no turno) sem clássico estadual quando possível

    Otimiza via RCL gulosa-aleatória:
      (f) balanço casa/fora no turno
      (g) máximo `max_consecutive` jogos consecutivos em casa/fora
    """
    rng = random.Random(seed)
    teams = list(teams_map.keys())
    n = len(teams)
    if n != 20:
        raise ConstructionFailedError(
            f"Esperado 20 times; recebido {n}."
        )

    matchings = circle_method(teams)
    if len(matchings) != 19:
        raise ConstructionFailedError(
            f"circle_method retornou {len(matchings)} matchings; esperado 19."
        )

    remaining: list[list[tuple[str, str]]] = [list(m) for m in matchings]

    # -- Etapa A: âncoras R1 e R2 ------------------------------------------
    # Pega dois matchings distintos e usa 2-coloring do grafo R1 ∪ R2
    # (sempre bipartido). A 2-coloração resultante garante (c) estrita.
    # R18/R19 são decididos DEPOIS da RCL para que ela tenha liberdade
    # de manobra em (f)/(g) — atribuir matchings a essas rodadas com
    # antecedência limita drasticamente o pool de orientações disponíveis
    # nas últimas rodadas da RCL e empurra o solver para violações.
    r1_idx = rng.randrange(len(remaining))
    r1_pairs = remaining.pop(r1_idx)
    r2_idx = rng.randrange(len(remaining))
    r2_pairs = remaining.pop(r2_idx)

    sides_r1 = _two_color_pair_union(r1_pairs, r2_pairs, teams, rng)
    r1_oriented = [
        (a, b) if sides_r1[a] == "H" else (b, a) for a, b in r1_pairs
    ]
    # Em R2, mando de cada time é o oposto do de R1; pela bipartição, o par
    # tem um time H e outro A em R1 → orientação determinada.
    r2_oriented = [
        (a, b) if sides_r1[a] == "A" else (b, a) for a, b in r2_pairs
    ]
    sides_r2 = _sides_from_oriented(r2_oriented)

    # -- Estado e índices ---------------------------------------------------
    team_to_idx = {t: i for i, t in enumerate(teams)}

    homes = [0] * n
    last_side = [0] * n  # 0=indef, 1=H, 2=A
    streak = [0] * n

    def _apply_oriented(oriented: list[tuple[str, str]]) -> None:
        for h, a in oriented:
            ih = team_to_idx[h]
            ia = team_to_idx[a]
            homes[ih] += 1
            if last_side[ih] == 1:
                streak[ih] += 1
            else:
                last_side[ih] = 1
                streak[ih] = 1
            if last_side[ia] == 2:
                streak[ia] += 1
            else:
                last_side[ia] = 2
                streak[ia] = 1

    _apply_oriented(r1_oriented)
    _apply_oriented(r2_oriented)

    matches_by_round: MatchesByRound = {
        1: [Match(h, a) for h, a in r1_oriented],
        2: [Match(h, a) for h, a in r2_oriented],
    }

    # Reserva um matching limpo (sem clássico estadual) entre os
    # remanescentes para garantir que R19 possa atender (e). Se houver
    # múltiplos limpos, escolhe o de maior compat com a inversão de R2.
    clean_in_remaining = [
        m for m in remaining if no_classico_estadual(m, teams_map)
    ]
    r19_reserved: list[tuple[str, str]] | None = None
    if clean_in_remaining:
        def _r19_compat(m: list[tuple[str, str]]) -> int:
            return sum(1 for a, b in m if sides_r2[a] != sides_r2[b])
        best_compat = max(_r19_compat(m) for m in clean_in_remaining)
        best_clean = [m for m in clean_in_remaining if _r19_compat(m) == best_compat]
        r19_reserved = rng.choice(best_clean)
        remaining.remove(r19_reserved)

    remaining_idx = [
        [(team_to_idx[a], team_to_idx[b]) for a, b in m] for m in remaining
    ]

    weight_f = CONSTRUCTION_WEIGHTS["f"]
    weight_g = CONSTRUCTION_WEIGHTS["g"]

    # -- Etapa B: RCL para R3..R17 -----------------------------------------
    for r in range(3, 18):
        rem_unk = 19 - r  # rodadas R(r+1)..R19 ainda indefinidas

        unfeasible_away = [0] * n
        unfeasible_home = [0] * n
        f_base = 0
        for t in range(n):
            base = homes[t]
            ua = 1 if (base > 10 or base + rem_unk < 9) else 0
            uh = 1 if (base + 1 > 10 or base + 1 + rem_unk < 9) else 0
            unfeasible_away[t] = ua
            unfeasible_home[t] = uh
            f_base += ua

        all_candidates: list[tuple[int, int, int, float]] = []
        any_g_zero = False

        for m_idx, m_pairs in enumerate(remaining_idx):
            npairs = len(m_pairs)
            g_a_home = [0] * npairs
            g_b_home = [0] * npairs
            df_a_home = [0] * npairs
            df_b_home = [0] * npairs
            for k in range(npairs):
                a, b = m_pairs[k]
                ga = 0
                if last_side[a] == 1 and streak[a] + 1 > max_consecutive:
                    ga += 1
                if last_side[b] == 2 and streak[b] + 1 > max_consecutive:
                    ga += 1
                gb = 0
                if last_side[b] == 1 and streak[b] + 1 > max_consecutive:
                    gb += 1
                if last_side[a] == 2 and streak[a] + 1 > max_consecutive:
                    gb += 1
                g_a_home[k] = ga
                g_b_home[k] = gb
                df_a_home[k] = unfeasible_home[a] - unfeasible_away[a]
                df_b_home[k] = unfeasible_home[b] - unfeasible_away[b]

            for mask in range(1 << npairs):
                g_v = 0
                f_v = f_base
                for k in range(npairs):
                    if (mask >> k) & 1:
                        g_v += g_a_home[k]
                        f_v += df_a_home[k]
                    else:
                        g_v += g_b_home[k]
                        f_v += df_b_home[k]
                cost = weight_f * f_v + weight_g * g_v
                all_candidates.append((m_idx, mask, g_v, cost))
                if g_v == 0:
                    any_g_zero = True

        if any_g_zero:
            pool = [c for c in all_candidates if c[2] == 0]
        else:
            pool = all_candidates

        c_min = min(c[3] for c in pool)
        c_max = max(c[3] for c in pool)
        threshold = c_min + alpha * (c_max - c_min)
        rcl = [c for c in pool if c[3] <= threshold]
        chosen = rng.choice(rcl)
        m_idx_chosen, mask_chosen, _, _ = chosen

        m_pairs_str = remaining.pop(m_idx_chosen)
        remaining_idx.pop(m_idx_chosen)

        chosen_oriented_str: list[tuple[str, str]] = []
        for k, (a_str, b_str) in enumerate(m_pairs_str):
            if (mask_chosen >> k) & 1:
                chosen_oriented_str.append((a_str, b_str))
            else:
                chosen_oriented_str.append((b_str, a_str))
        _apply_oriented(chosen_oriented_str)
        matches_by_round[r] = [Match(h, a) for h, a in chosen_oriented_str]

    # -- Etapa C: R18 e R19 a partir dos 2 matchings remanescentes ---------
    if r19_reserved is not None:
        remaining.append(r19_reserved)
    if len(remaining) != 2:
        raise ConstructionFailedError(
            f"Esperado 2 matchings após R3..R17; sobrou {len(remaining)}."
        )

    r18_oriented, r19_oriented = _pick_r18_r19(
        remaining,
        sides_r1,
        sides_r2,
        teams_map,
        last_side,
        streak,
        max_consecutive,
        rng,
    )
    _apply_oriented(r18_oriented)
    _apply_oriented(r19_oriented)
    matches_by_round[18] = [Match(h, a) for h, a in r18_oriented]
    matches_by_round[19] = [Match(h, a) for h, a in r19_oriented]

    # -- Returno: espelho com mando invertido ------------------------------
    for r in range(1, 20):
        matches_by_round[r + 19] = [
            Match(m.away, m.home) for m in matches_by_round[r]
        ]

    return matches_by_round


# ---------------------------------------------------------------------------
# Parte 2 — atribuição de datas
# ---------------------------------------------------------------------------

class DateAssignmentFailedError(Exception):
    """Levantada quando não há atribuição factível respeitando descanso."""


def _check_rest(
    match: Match,
    proposed_date: date,
    last_play: dict[str, date],
    min_rest: int,
) -> bool:
    for team in (match.home, match.away):
        prev = last_play.get(team)
        if prev is not None and (proposed_date - prev).days < min_rest:
            return False
    return True


def _try_balanced_distribution(
    matches: list[Match],
    window: list[date],
    last_play: dict[str, date],
    min_rest: int,
) -> list[tuple[Match, date]] | None:
    max_per_date = ceil(len(matches) / len(window))
    date_counts: dict[date, int] = {d: 0 for d in window}
    result: list[tuple[Match, date]] = []

    for match in matches:
        best_date: date | None = None
        best_count = max_per_date + 1
        for d in window:
            if date_counts[d] >= max_per_date:
                continue
            if not _check_rest(match, d, last_play, min_rest):
                continue
            if date_counts[d] < best_count:
                best_count = date_counts[d]
                best_date = d

        if best_date is None:
            return None

        result.append((match, best_date))
        date_counts[best_date] += 1

    return result


def _try_flexible_distribution(
    matches: list[Match],
    window: list[date],
    last_play: dict[str, date],
    min_rest: int,
) -> list[tuple[Match, date]] | None:
    result: list[tuple[Match, date]] = []
    for match in matches:
        assigned = False
        for d in window:
            if _check_rest(match, d, last_play, min_rest):
                result.append((match, d))
                assigned = True
                break
        if not assigned:
            return None
    return result


def _round_prv_count(
    atribuicao: list[tuple[Match, date]],
    prev_stadium_dates: dict[str, list[date]],
    teams_map: TeamMap,
    prv_days: int,
) -> int:
    stadium_all_dates: dict[str, list[date]] = {}
    for match, d in atribuicao:
        stadium = teams_map[match.home].stadium
        if stadium not in stadium_all_dates:
            stadium_all_dates[stadium] = list(
                prev_stadium_dates.get(stadium, [])
            )
        stadium_all_dates[stadium].append(d)

    count = 0
    for dates_list in stadium_all_dates.values():
        sorted_dates = sorted(dates_list)
        for i in range(len(sorted_dates) - 1):
            if (sorted_dates[i + 1] - sorted_dates[i]).days < prv_days:
                count += 1
    return count


def _optimize_local_prv(
    atribuicao: list[tuple[Match, date]],
    prev_stadium_dates: dict[str, list[date]],
    teams_map: TeamMap,
    prv_days: int,
    last_play: dict[str, date],
    min_rest: int,
) -> list[tuple[Match, date]]:
    improved = True
    while improved:
        improved = False
        best_prv = _round_prv_count(
            atribuicao, prev_stadium_dates, teams_map, prv_days
        )
        for i in range(len(atribuicao)):
            for j in range(i + 1, len(atribuicao)):
                if atribuicao[i][1] == atribuicao[j][1]:
                    continue
                mi, di = atribuicao[i]
                mj, dj = atribuicao[j]
                if not _check_rest(mi, dj, last_play, min_rest):
                    continue
                if not _check_rest(mj, di, last_play, min_rest):
                    continue
                atribuicao[i] = (mi, dj)
                atribuicao[j] = (mj, di)
                new_prv = _round_prv_count(
                    atribuicao, prev_stadium_dates, teams_map, prv_days
                )
                if new_prv < best_prv:
                    best_prv = new_prv
                    improved = True
                else:
                    atribuicao[i] = (mi, di)
                    atribuicao[j] = (mj, dj)
    return atribuicao


def assign_dates_to_matches(
    matches_by_round: MatchesByRound,
    dates: list[date],
    teams_map: TeamMap,
    *,
    round_gap: int = 7,
    round_span: int = 3,
    prv_days: int = 5,
    min_team_rest_days: int = 3,
) -> Schedule:
    """Atribui uma data a cada jogo de cada rodada, respeitando descanso mínimo
    de time e minimizando PRVs."""
    schedule: Schedule = []
    last_play: dict[str, date] = {}
    prev_stadium_dates: dict[str, list[date]] = {}

    for r in range(1, 39):
        base_idx = (r - 1) * round_gap
        window = dates[base_idx : base_idx + round_span]

        matches = matches_by_round[r]

        atribuicao = _try_balanced_distribution(
            matches, window, last_play, min_team_rest_days
        )

        if atribuicao is None:
            atribuicao = _try_flexible_distribution(
                matches, window, last_play, min_team_rest_days
            )

        if atribuicao is None:
            raise DateAssignmentFailedError(
                f"Não foi possível atribuir datas na rodada {r} "
                "respeitando descanso."
            )

        atribuicao = _optimize_local_prv(
            atribuicao, prev_stadium_dates, teams_map, prv_days,
            last_play, min_team_rest_days,
        )

        for match, d in atribuicao:
            sm = ScheduledMatch(
                round=r,
                day=d.strftime("%d/%m/%Y"),
                home=match.home,
                away=match.away,
                stadium=teams_map[match.home].stadium,
                home_state=teams_map[match.home].state,
                away_state=teams_map[match.away].state,
            )
            schedule.append(sm)
            last_play[match.home] = d
            last_play[match.away] = d
            prev_stadium_dates.setdefault(
                teams_map[match.home].stadium, []
            ).append(d)

    return schedule


def construct_schedule(
    teams_map: TeamMap,
    dates: list[date],
    *,
    alpha: float = 0.3,
    seed: int = 42,
    round_gap: int = 7,
    round_span: int = 3,
    prv_days: int = 5,
    min_team_rest_days: int = 3,
    max_consecutive: int = 2,
) -> Schedule:
    """Pipeline completo: build_matches_with_homes → assign_dates_to_matches."""
    matches_by_round = build_matches_with_homes(
        teams_map, alpha=alpha, seed=seed, max_consecutive=max_consecutive
    )
    return assign_dates_to_matches(
        matches_by_round,
        dates,
        teams_map,
        round_gap=round_gap,
        round_span=round_span,
        prv_days=prv_days,
        min_team_rest_days=min_team_rest_days,
    )

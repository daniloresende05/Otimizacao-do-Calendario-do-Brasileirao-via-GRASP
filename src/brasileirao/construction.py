from __future__ import annotations

import random
from bisect import bisect_left
from datetime import date, timedelta
from math import ceil
from typing import Iterator

from .domain import Match, Schedule, ScheduledMatch, TeamMap
from .round_robin import bipartite_factorization, shuffle_factors

MatchesByRound = dict[int, list[Match]]

CONSTRUCTION_WEIGHTS = {
    "f": 100.0,
    "g": 300.0,
}

#: Sorteios de bipartição tentados até achar um com rodada cruzada sem
#: clássico estadual (candidata a R19, que espelha na R38 — restrição (e)).
MAX_TENTATIVAS_BIPARTICAO = 20

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
      (d) espelho R18↔R1 e R19↔R2 (resíduo mínimo estrutural: o quarteto
          R1/R2/R18/R19 é escolhido em conjunto na etapa A')
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

    # -- Etapa A': bipartição e âncoras (R1, R2, R18, R19) ------------------
    # A 1-fatoração é gerada JÁ alinhada a uma bipartição (A, B) de 10 times.
    # As 10 rodadas "cruzadas" só têm jogos ligando um time de A a um de B,
    # então quatro delas servem de âncora com o mando determinado pelo lado:
    # A manda na R1 e na R19, B manda na R2 e na R18. Isso faz (c) e (d)
    # saírem ZERADAS por construção — antes elas dependiam de achar, dentro
    # do método do círculo, dois matchings que fossem corte perfeito da
    # 2-coloração de R1 ∪ R2, o que é estruturalmente impossível: sobrava
    # sempre um piso de 4 violações de (d).
    # Quase toda bipartição deixa alguma rodada cruzada sem clássico estadual
    # (~99% dos sorteios, 2.9 em média). Poucas tentativas bastam para nunca
    # entregar (e) violada por falta de candidata limpa.
    for _ in range(MAX_TENTATIVAS_BIPARTICAO):
        cruzadas, internas, part_a, _ = bipartite_factorization(teams, rng)
        if any(no_classico_estadual(c, teams_map) for c in cruzadas):
            break
    lado_a = set(part_a)

    # A âncora que virar R19 espelha na R38, então as duas RESERVADAS para
    # R18/R19 são as cruzadas com menos clássicos — é o que preserva (e).
    # R1 e R2 não têm essa restrição e ficam com as duas seguintes.
    ordem = list(range(len(cruzadas)))
    rng.shuffle(ordem)
    ordem.sort(key=lambda k: count_classicos(cruzadas[k], teams_map))
    reserved_r18_r19 = [cruzadas[ordem[0]], cruzadas[ordem[1]]]
    r1_pairs, r2_pairs = cruzadas[ordem[2]], cruzadas[ordem[3]]

    # As 15 rodadas do miolo são as 6 cruzadas restantes mais as 9 internas.
    # Sem os flips cada uma seria "pura" (só interna ou só cruzada); os flips
    # de ciclo alternante misturam os dois tipos sem quebrar a fatoração e
    # sem tocar nas âncoras, dando diversidade ao multi-start do GRASP.
    miolo = [cruzadas[k] for k in ordem[4:]] + internas
    remaining: list[list[tuple[str, str]]] = shuffle_factors(miolo, rng)

    sides_r1 = {t: ("H" if t in lado_a else "A") for t in teams}
    r1_oriented = [
        (a, b) if sides_r1[a] == "H" else (b, a) for a, b in r1_pairs
    ]
    # Em R2, mando de cada time é o oposto do de R1; pela bipartição, o par
    # tem um time H e outro A em R1 → orientação determinada.
    r2_oriented = [
        (a, b) if sides_r1[a] == "A" else (b, a) for a, b in r2_pairs
    ]

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

    # -- Etapa C: R18 e R19 a partir dos 2 matchings reservados na A' ------
    if remaining:
        raise ConstructionFailedError(
            f"Esperado 0 matchings após R3..R17; sobrou {len(remaining)}."
        )
    # R18 espelha o mando da R1 e R19 o da R2, então o lado de cada time já
    # está decidido pela bipartição: manda quem é de B na R18 e quem é de A
    # na R19. Só resta escolher QUAL das duas âncoras reservadas vai para
    # cada rodada — critério: (e) primeiro (R19 espelha na R38), depois o
    # encadeamento de (g) em R17 → R18 → R19.
    def _orient_r18(pairs: list[tuple[str, str]]) -> list[tuple[str, str]]:
        return [(a, b) if sides_r1[a] == "A" else (b, a) for a, b in pairs]

    def _orient_r19(pairs: list[tuple[str, str]]) -> list[tuple[str, str]]:
        return [(a, b) if sides_r1[a] == "H" else (b, a) for a, b in pairs]

    first, second = reserved_r18_r19
    ordens = [(first, second), (second, first)]
    team_idx_list = list(range(n))

    def _custo_ordem(par: tuple[list, list]) -> tuple[int, int]:
        cand_r18, cand_r19 = par
        sides_seq = []
        for oriented in (_orient_r18(cand_r18), _orient_r19(cand_r19)):
            por_time = [0] * n
            for h, a in oriented:
                por_time[team_to_idx[h]] = 1
                por_time[team_to_idx[a]] = 2
            sides_seq.append(por_time)
        g_v = _chain_g_violations(
            team_idx_list, sides_seq, last_side, streak, max_consecutive
        )
        return (count_classicos(cand_r19, teams_map), g_v)

    rng.shuffle(ordens)
    melhor = min(ordens, key=_custo_ordem)
    r18_oriented = _orient_r18(melhor[0])
    r19_oriented = _orient_r19(melhor[1])
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


def _assign_single_date_round(
    matches: list[Match],
    window: list[date],
    last_play: dict[str, date],
    min_rest: int,
    prev_stadium_dates: dict[str, list[date]],
    teams_map: TeamMap,
    prv_days: int,
    round_number: int | None = None,
) -> list[tuple[Match, date]]:
    """Rodada SIMULTÂNEA: todos os jogos na MESMA data.

    Uma data da janela é viável se TODOS os jogos respeitam ``min_rest`` nela
    (i.e., todos os times a >= min_rest do seu jogo anterior). Entre as
    viáveis, escolhe a que MINIMIZA o PRV da rodada (mesma lógica de
    ``_round_prv_count`` contra ``prev_stadium_dates``); empate resolve pela
    data mais antiga (determinismo).

    NÃO passa por ``_optimize_local_prv``: ele troca datas ENTRE jogos, o que
    reintroduziria múltiplas datas na rodada.
    """
    best: tuple[int, date] | None = None
    for d in window:
        if not all(_check_rest(m, d, last_play, min_rest) for m in matches):
            continue
        atribuicao = [(m, d) for m in matches]
        prv = _round_prv_count(
            atribuicao, prev_stadium_dates, teams_map, prv_days
        )
        if best is None or prv < best[0] or (prv == best[0] and d < best[1]):
            best = (prv, d)
    if best is None:
        rotulo = f"rodada {round_number}" if round_number else "rodada"
        raise DateAssignmentFailedError(
            f"Rodada simultânea sem data viável: nenhuma data da janela "
            f"{[d.isoformat() for d in window]} da {rotulo} respeita o "
            f"descanso mínimo de {min_rest} dia(s) para todos os times."
        )
    chosen = best[1]
    return [(m, chosen) for m in matches]


def round_windows(
    dates: list[date],
    *,
    round_gap: int = 7,
    round_span: int = 3,
    n_rounds: int = 38,
) -> list[list[date]]:
    """Janela de datas de cada rodada, em termos de CALENDÁRIO.

    ``dates`` é o conjunto de datas DISPONÍVEIS (pode ter buracos: datas
    FIFA removidas, feriados etc.). Regra:

      * a rodada 1 começa na primeira data disponível;
      * a rodada r começa na primeira data disponível >= início(r-1) +
        ``round_gap`` dias — se esse dia está bloqueado, a rodada desliza
        para o próximo disponível e as seguintes seguem a partir dele;
      * a janela da rodada são as datas disponíveis nos ``round_span`` dias
        de calendário a partir do início (pode ter menos de ``round_span``
        datas se alguma estiver bloqueada).

    Com uma lista de dias consecutivos isso equivale exatamente ao
    fatiamento posicional ``dates[(r-1)*round_gap : +round_span]``. Com
    buracos, mantém as garantias de (i) span <= round_span-1 dias e (j) sem
    encavalamento, que o fatiamento posicional violaria.

    Levanta ``DateAssignmentFailedError`` se as ``n_rounds`` rodadas não
    cabem nas datas disponíveis.
    """
    available = sorted(set(dates))
    if not available:
        raise DateAssignmentFailedError("Lista de datas disponíveis vazia.")

    windows: list[list[date]] = []
    start = available[0]
    for r in range(1, n_rounds + 1):
        if r > 1:
            start = windows[-1][0] + timedelta(days=round_gap)
        idx = bisect_left(available, start)
        if idx == len(available):
            raise DateAssignmentFailedError(
                f"Rodada {r}: nenhuma data disponível a partir de "
                f"{start.isoformat()} (última disponível: "
                f"{available[-1].isoformat()}). As {n_rounds} rodadas não "
                f"cabem nas datas disponíveis."
            )
        start = available[idx]
        limit = start + timedelta(days=round_span)
        window = [d for d in available[idx : idx + round_span] if d < limit]
        windows.append(window)
    return windows


def fit_round_gap(
    dates: list[date],
    *,
    preferred_gap: int = 7,
    min_gap: int = 2,
    round_span: int = 3,
    n_rounds: int = 38,
) -> int:
    """Maior cadência <= `preferred_gap` em que as `n_rounds` rodadas cabem.

    A cadência é um PARÂMETRO do calendário, não uma restrição: (i) span da
    rodada e (j) sem encavalamento continuam valendo para qualquer gap maior
    que `round_span - 1`. Janelas curtas simplesmente exigem rodadas mais
    próximas umas das outras — é o que competições reais fazem com rodadas
    de meio de semana, só que de forma irregular.

    Levanta `DateAssignmentFailedError` se nem `min_gap` couber.
    """
    for gap in range(preferred_gap, min_gap - 1, -1):
        try:
            round_windows(
                dates, round_gap=gap, round_span=round_span, n_rounds=n_rounds
            )
            return gap
        except DateAssignmentFailedError:
            continue
    raise DateAssignmentFailedError(
        f"Nem com cadência de {min_gap} dias as {n_rounds} rodadas cabem nas "
        f"{len(dates)} datas disponíveis "
        f"({min(dates).isoformat()} a {max(dates).isoformat()})."
    )


def assign_dates_to_matches(
    matches_by_round: MatchesByRound,
    dates: list[date],
    teams_map: TeamMap,
    *,
    round_gap: int = 7,
    round_span: int = 3,
    prv_days: int = 5,
    min_team_rest_days: int = 3,
    simultaneous_rounds: frozenset[int] = frozenset({38}),
) -> Schedule:
    """Atribui uma data a cada jogo de cada rodada, respeitando descanso mínimo
    de time e minimizando PRVs.

    A janela de cada rodada vem de ``round_windows`` (baseada em calendário,
    tolerante a datas bloqueadas — ex.: datas FIFA removidas da lista).

    Rodadas em ``simultaneous_rounds`` recebem TODOS os jogos na MESMA data
    (via ``_assign_single_date_round``); as demais espalham na janela
    (balanced -> flexible -> otimização local de PRV)."""
    schedule: Schedule = []
    last_play: dict[str, date] = {}
    prev_stadium_dates: dict[str, list[date]] = {}

    windows = round_windows(
        dates, round_gap=round_gap, round_span=round_span, n_rounds=38
    )

    for r in range(1, 39):
        window = windows[r - 1]

        matches = matches_by_round[r]

        if r in simultaneous_rounds:
            atribuicao = _assign_single_date_round(
                matches, window, last_play, min_team_rest_days,
                prev_stadium_dates, teams_map, prv_days,
                round_number=r,
            )
        else:
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
    simultaneous_rounds: frozenset[int] = frozenset({38}),
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
        simultaneous_rounds=simultaneous_rounds,
    )

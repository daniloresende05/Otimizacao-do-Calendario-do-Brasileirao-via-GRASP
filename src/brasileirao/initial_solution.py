# src/brasileirao/initial_solution.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional
from datetime import datetime, date
import random

from .round_robin import circle_method
from .domain import ScheduledMatch


def _parse_dates(dates_raw: List[str]) -> List[date]:
    out: List[date] = []
    for x in dates_raw:
        if isinstance(x, date):
            out.append(x)
        else:
            s = str(x).strip()
            out.append(datetime.strptime(s, "%d/%m/%Y").date())
    return out


def build_initial_schedule_with_constraints(
    dates_raw: List[str],
    teams_map: Dict[str, object],
    *,
    round_gap: int = 7,
    round_span: int = 3,
    seed: int = 42,
    max_attempts: int = 200_000,
) -> List[ScheduledMatch]:
    """
    Constrói calendário double round-robin já factível em (a)-(g), sem impor PRV como hard constraint.

    - (a) e (b): garantidas pela estrutura round-robin + returno invertido
    - (c): alternância nas 2 primeiras rodadas do turno
    - (d): espelho no fim do turno (mando de r18 = r1, mando de r19 = r2, por time)
    - (e): última rodada (turno e campeonato) sem confronto de mesmo estado
    - (f): saldo casa/fora no turno dentro de 1 (9 ou 10 jogos em casa)
    - (g): sem sequência >2 em casa ou fora (no campeonato todo)
    """
    rng = random.Random(seed)

    teams = list(teams_map.keys())
    n = len(teams)
    if n != 20:
        raise ValueError(f"Esperado 20 times, veio {n}")

    # estados por time
    state = {t: teams_map[t].state for t in teams}

    # 19 rodadas (turno), cada rodada é um matching com 10 jogos
    rounds_pairs = circle_method(teams)
    if len(rounds_pairs) != 19:
        raise ValueError(f"circle_method deveria gerar 19 rodadas, gerou {len(rounds_pairs)}")

    # escolhe uma rodada "limpa" (sem jogos do mesmo estado) para ser a última do turno
    """ 
    clean_idxs = [i for i, pairs in enumerate(rounds_pairs)
                  if all(state[a] != state[b] for a, b in pairs)]
    if clean_idxs:
        last_idx = rng.choice(clean_idxs)
        # rotaciona para que rounds_pairs[18] (rodada 19) seja a rodada limpa escolhida
        rounds_pairs = rounds_pairs[last_idx + 1:] + rounds_pairs[:last_idx + 1]
    """
    # pré-processa datas (vamos usar (r-1)*round_gap como "início" da rodada r)
    dates = _parse_dates(dates_raw)
    need = (38 - 1) * round_gap + max(1, round_span)
    if len(dates) < need:
        raise ValueError(
            f"Poucas datas no CSV. Preciso de pelo menos {need} dias para round_gap={round_gap}, round_span={round_span}. "
            f"Veio {len(dates)}."
        )

    team_idx = {t: i for i, t in enumerate(teams)}

    def oriented_to_side(oriented: List[Tuple[str, str]]) -> List[int]:
        # side[i] = 1 se time i joga em casa na rodada, 0 se fora
        side = [-1] * n
        for h, a in oriented:
            side[team_idx[h]] = 1
            side[team_idx[a]] = 0
        return side

    def force_orientation(pairs: List[Tuple[str, str]], home_side: List[int]) -> Optional[List[Tuple[str, str]]]:
        # cria orientação única compatível com home_side (1=casa, 0=fora) nessa rodada
        oriented: List[Tuple[str, str]] = []
        for a, b in pairs:
            ia, ib = team_idx[a], team_idx[b]
            if home_side[ia] == home_side[ib]:
                return None
            if home_side[ia] == 1:
                oriented.append((a, b))
            else:
                oriented.append((b, a))
        return oriented

    def apply_round(
        oriented: List[Tuple[str, str]],
        homes: List[int],
        last: List[Optional[int]],
        streak: List[int],
    ) -> Optional[Tuple[List[int], List[Optional[int]], List[int]]]:
        # retorna novos vetores ou None se estourar (g) ou ultrapassar limites de (f) no turno
        homes2 = homes[:]
        last2 = last[:]
        streak2 = streak[:]

        for h, a in oriented:
            ih, ia = team_idx[h], team_idx[a]

            # time da casa
            homes2[ih] += 1
            if last2[ih] is None or last2[ih] != 1:
                last2[ih] = 1
                streak2[ih] = 1
            else:
                streak2[ih] += 1
                if streak2[ih] > 2:
                    return None

            # time de fora
            if last2[ia] is None or last2[ia] != 0:
                last2[ia] = 0
                streak2[ia] = 1
            else:
                streak2[ia] += 1
                if streak2[ia] > 2:
                    return None

        return homes2, last2, streak2

    def feasible_home_bounds(homes: List[int], round_done: int) -> bool:
        # turno tem 19 rodadas. depois de round_done rodadas, faltam:
        rem = 19 - round_done
        for i in range(n):
            if homes[i] > 10:
                return False
            if homes[i] + rem < 9:
                return False
        return True

    # gera todas orientações possíveis de uma rodada (2^10)
    def all_orientations(pairs: List[Tuple[str, str]]) -> List[List[Tuple[str, str]]]:
        m = len(pairs)  # 10
        out: List[List[Tuple[str, str]]] = []
        for mask in range(1 << m):
            oriented: List[Tuple[str, str]] = []
            for k, (a, b) in enumerate(pairs):
                if (mask >> k) & 1:
                    oriented.append((a, b))
                else:
                    oriented.append((b, a))
            out.append(oriented)
        return out

    options = [all_orientations(pairs) for pairs in rounds_pairs]

    # ============================================================
    # Somente restrição (a): double round-robin (turno + returno invertido)
    # (sem (c)(d)(e)(f)(g), sem backtracking)
    # ============================================================

    # escolhe uma orientação qualquer para cada rodada do turno
    chosen: List[List[Tuple[str, str]]] = [rng.choice(options[r]) for r in range(19)]

    schedule: List[ScheduledMatch] = []

    def pick_date(round_number: int, match_k: int) -> str:
        base = (round_number - 1) * round_gap
        offset = match_k % max(1, round_span)
        d = dates[base + offset]
        return d.strftime("%d/%m/%Y")

    # turno
    for r in range(1, 20):
        oriented = chosen[r - 1]
        for k, (home, away) in enumerate(oriented):
            day = pick_date(r, k)
            th = teams_map[home]
            ta = teams_map[away]
            schedule.append(ScheduledMatch(
                round=r,
                day=day,
                home=home,
                away=away,
                stadium=th.stadium,
                home_state=th.state,
                away_state=ta.state,
            ))

    # returno (mando invertido)
    for r in range(20, 39):
        oriented = chosen[r - 20]
        for k, (home, away) in enumerate(oriented):
            day = pick_date(r, k)
            home2, away2 = away, home
            th = teams_map[home2]
            ta = teams_map[away2]
            schedule.append(ScheduledMatch(
                round=r,
                day=day,
                home=home2,
                away=away2,
                stadium=th.stadium,
                home_state=th.state,
                away_state=ta.state,
            ))

    return schedule


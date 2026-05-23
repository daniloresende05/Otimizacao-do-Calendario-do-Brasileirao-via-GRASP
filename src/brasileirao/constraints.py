from __future__ import annotations

from collections import defaultdict
from typing import Callable, Dict, List, Tuple

from .domain import ConstraintViolation, Schedule, ScheduledMatch

TURNO_FIRST = 1
TURNO_LAST = 19
RETURNO_LAST = 38


def _inverse_side(side: str) -> str:
    return "away" if side == "home" else "home"


def check_a_max_one_game_per_round(schedule: Schedule) -> List[ConstraintViolation]:
    violations: List[ConstraintViolation] = []
    by_round: Dict[int, List[ScheduledMatch]] = defaultdict(list)
    for m in schedule:
        by_round[m.round].append(m)

    for r, matches in by_round.items():
        seen: set[str] = set()
        for m in matches:
            for team in (m.home, m.away):
                if team in seen:
                    violations.append(
                        ConstraintViolation(
                            constraint_id="a",
                            description=f"Time {team} aparece mais de uma vez na rodada {r}",
                            round=r,
                            team=team,
                        )
                    )
                seen.add(team)
    return violations


def check_b_double_round_robin(schedule: Schedule) -> List[ConstraintViolation]:
    """Cada par (A,B) aparece 2× no total; cada direção (home,away) no máx 1×."""
    pair_count: Dict[frozenset, int] = defaultdict(int)
    direction_count: Dict[Tuple[str, str], int] = defaultdict(int)
    for m in schedule:
        pair_count[frozenset([m.home, m.away])] += 1
        direction_count[(m.home, m.away)] += 1

    violations: List[ConstraintViolation] = []
    for pair, cnt in pair_count.items():
        if cnt != 2:
            a, b = tuple(pair)
            violations.append(
                ConstraintViolation(
                    constraint_id="b",
                    description=f"Par {a} vs {b} aparece {cnt} vezes (esperado 2)",
                )
            )
    for (h, a), cnt in direction_count.items():
        if cnt > 1:
            violations.append(
                ConstraintViolation(
                    constraint_id="b",
                    description=f"Confronto {h} (casa) vs {a} aparece {cnt} vezes (esperado no máximo 1)",
                )
            )
    return violations


def _sides_in_round(schedule: Schedule, target_round: int) -> Dict[str, str]:
    sides: Dict[str, str] = {}
    for m in schedule:
        if m.round == target_round:
            sides[m.home] = "home"
            sides[m.away] = "away"
    return sides


def check_c_first_two_rounds_alternation(schedule: Schedule) -> List[ConstraintViolation]:
    side_r1 = _sides_in_round(schedule, 1)
    side_r2 = _sides_in_round(schedule, 2)

    violations: List[ConstraintViolation] = []
    for team, s1 in side_r1.items():
        s2 = side_r2.get(team)
        if s2 is not None and s1 == s2:
            violations.append(
                ConstraintViolation(
                    constraint_id="c",
                    description=f"Time {team}: mando '{s1}' em R1 e '{s2}' em R2 (deveria alternar)",
                    round=2,
                    team=team,
                )
            )
    return violations


def check_d_last_two_rounds_mirror(schedule: Schedule) -> List[ConstraintViolation]:
    side_r1 = _sides_in_round(schedule, 1)
    side_r2 = _sides_in_round(schedule, 2)
    side_r18 = _sides_in_round(schedule, 18)
    side_r19 = _sides_in_round(schedule, 19)

    violations: List[ConstraintViolation] = []
    for team, s1 in side_r1.items():
        s18 = side_r18.get(team)
        if s18 is not None and s18 != _inverse_side(s1):
            violations.append(
                ConstraintViolation(
                    constraint_id="d",
                    description=f"Time {team}: mando em R18 ('{s18}') não é espelho de R1 ('{s1}')",
                    round=18,
                    team=team,
                )
            )
    for team, s2 in side_r2.items():
        s19 = side_r19.get(team)
        if s19 is not None and s19 != _inverse_side(s2):
            violations.append(
                ConstraintViolation(
                    constraint_id="d",
                    description=f"Time {team}: mando em R19 ('{s19}') não é espelho de R2 ('{s2}')",
                    round=19,
                    team=team,
                )
            )
    return violations


def check_e_last_round_no_same_state(schedule: Schedule) -> List[ConstraintViolation]:
    violations: List[ConstraintViolation] = []
    for m in schedule:
        if m.round == RETURNO_LAST and m.home_state == m.away_state:
            violations.append(
                ConstraintViolation(
                    constraint_id="e",
                    description=(
                        f"R{RETURNO_LAST}: {m.home} ({m.home_state}) x "
                        f"{m.away} ({m.away_state}) — mesmo estado"
                    ),
                    round=RETURNO_LAST,
                )
            )
    return violations


def check_f_home_away_balance_per_turno(schedule: Schedule) -> List[ConstraintViolation]:
    home_count: Dict[str, int] = defaultdict(int)
    away_count: Dict[str, int] = defaultdict(int)
    for m in schedule:
        if TURNO_FIRST <= m.round <= TURNO_LAST:
            home_count[m.home] += 1
            away_count[m.away] += 1

    violations: List[ConstraintViolation] = []
    for team in set(home_count) | set(away_count):
        h = home_count[team]
        a = away_count[team]
        if abs(h - a) > 1:
            violations.append(
                ConstraintViolation(
                    constraint_id="f",
                    description=(
                        f"Time {team} no turno: {h} casa, {a} fora "
                        f"(|diff| = {abs(h - a)} > 1)"
                    ),
                    team=team,
                )
            )
    return violations


def check_g_max_consecutive_home_or_away(
    schedule: Schedule, max_consecutive: int = 2
) -> List[ConstraintViolation]:
    by_team: Dict[str, List[Tuple[int, str]]] = defaultdict(list)
    for m in schedule:
        by_team[m.home].append((m.round, "home"))
        by_team[m.away].append((m.round, "away"))

    violations: List[ConstraintViolation] = []
    for team, entries in by_team.items():
        entries.sort()
        run_side: str | None = None
        run_start: int | None = None
        run_len = 0

        def flush() -> None:
            if run_len > max_consecutive and run_side is not None and run_start is not None:
                violations.append(
                    ConstraintViolation(
                        constraint_id="g",
                        description=(
                            f"Time {team}: {run_len} jogos consecutivos como "
                            f"'{run_side}' a partir de R{run_start}"
                        ),
                        round=run_start,
                        team=team,
                    )
                )

        for r, side in entries:
            if side == run_side:
                run_len += 1
            else:
                flush()
                run_side = side
                run_start = r
                run_len = 1
        flush()
    return violations


def check_h_prv(schedule: Schedule, prv_days: int = 5) -> List[ConstraintViolation]:
    from .objective import compute_prv  # local: evita ciclo de import

    result = compute_prv(schedule, prv_days=prv_days)
    violations: List[ConstraintViolation] = []
    for occ in result.occurrences:
        violations.append(
            ConstraintViolation(
                constraint_id="h",
                description=(
                    f"PRV em {occ.stadium}: {occ.match_a.day} → {occ.match_b.day} "
                    f"({occ.days_between} dias)"
                ),
                round=occ.match_b.round,
                stadium=occ.stadium,
            )
        )
    return violations


CONSTRAINT_CHECKS: List[Tuple[str, Callable[[Schedule], List[ConstraintViolation]]]] = [
    ("a", check_a_max_one_game_per_round),
    ("b", check_b_double_round_robin),
    ("c", check_c_first_two_rounds_alternation),
    ("d", check_d_last_two_rounds_mirror),
    ("e", check_e_last_round_no_same_state),
    ("f", check_f_home_away_balance_per_turno),
    ("g", check_g_max_consecutive_home_or_away),
    ("h", check_h_prv),
]


def check_all(schedule: Schedule) -> List[ConstraintViolation]:
    """Executa todas as checagens do registry e concatena resultados."""
    violations: List[ConstraintViolation] = []
    for _, check in CONSTRAINT_CHECKS:
        violations.extend(check(schedule))
    return violations

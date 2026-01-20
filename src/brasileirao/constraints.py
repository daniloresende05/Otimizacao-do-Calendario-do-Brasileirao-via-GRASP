from collections import defaultdict
from typing import List, Tuple
from .domain import ScheduledMatch, Schedule

def check_a_max_one_game_per_round(schedule: Schedule) -> List[str]:
    violations = []
    by_round = defaultdict(list)
    for m in schedule:
        by_round[m.round].append(m)

    for r, matches in by_round.items():
        seen = set()
        for m in matches:
            for t in (m.home, m.away):
                if t in seen:
                    violations.append(f"(a) Time {t} aparece mais de uma vez na rodada {r}")
                seen.add(t)
    return violations

def check_b_double_round_robin(schedule: Schedule) -> List[str]:
    """
    Checa se cada par (A,B) aparece exatamente 2 vezes no total:
    uma com A mandante e outra com B mandante.
    """
    violations = []
    pair_count = defaultdict(int)          # {frozenset({A,B}): count}
    direction_count = defaultdict(int)     # {(home,away): count}

    for m in schedule:
        pair_count[frozenset([m.home, m.away])] += 1
        direction_count[(m.home, m.away)] += 1

    for pair, cnt in pair_count.items():
        if cnt != 2:
            a, b = tuple(pair)
            violations.append(f"(b) Par {a} vs {b} aparece {cnt} vezes (esperado 2)")

    for (h, a), cnt in direction_count.items():
        if cnt > 1:
            violations.append(f"(b) Confronto {h} (casa) vs {a} aparece {cnt} vezes (esperado no max 1)")

    return violations

def check_all(schedule: Schedule) -> List[str]:
    violations = []
    violations += check_a_max_one_game_per_round(schedule)
    violations += check_b_double_round_robin(schedule)
    return violations

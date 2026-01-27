from typing import List, Tuple

Pair = Tuple[str, str]

def circle_method(teams: List[str]) -> List[List[Pair]]:
    teams = teams[:]
    n = len(teams)
    if n % 2 != 0:
        teams.append("BYE")
        n += 1

    rounds: List[List[Pair]] = []
    for _ in range(n - 1):
        pairs: List[Pair] = []
        for i in range(n // 2):
            a = teams[i]
            b = teams[n - 1 - i]
            if a != "BYE" and b != "BYE":
                pairs.append((a, b))
        rounds.append(pairs)

        # mantém o primeiro fixo e rotaciona o resto
        teams = [teams[0]] + [teams[-1]] + teams[1:-1]

    return rounds
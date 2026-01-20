from typing import List, Tuple

Pair = Tuple[str, str]

def circle_method(teams: List[str]) -> List[List[Pair]]:
    n = len(teams)
    if n < 2:
        return []
    if n % 2 != 0:
        teams = teams + ["BYE"]
        n += 1

    left = teams[: n // 2]
    right = teams[n // 2 :][::-1]

    rounds: List[List[Pair]] = []
    for _ in range(n - 1):
        pairs: List[Pair] = []
        for i in range(n // 2):
            a, b = left[i], right[i]
            if a != "BYE" and b != "BYE":
                pairs.append((a, b))
        rounds.append(pairs)

        # rotação (mantém left[0] fixo)
        fixed = left[0]
        left_rest = left[1:]
        right_rest = right

        left = [fixed] + [right_rest[0]] + left_rest[:-1]
        right = right_rest[1:] + [left_rest[-1]]
        right = right[::-1]

    return rounds

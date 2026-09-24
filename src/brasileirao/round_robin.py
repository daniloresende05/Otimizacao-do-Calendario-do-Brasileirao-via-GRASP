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

def _alternating_cycle_flip(
    f1: List[Pair], f2: List[Pair], rng
) -> Tuple[List[Pair], List[Pair]]:
    """Troca arestas entre dois fatores flipando UM ciclo alternante da união.

    A união de dois matchings perfeitos é sempre uma coleção de ciclos de
    comprimento par que alternam arestas de f1 e f2. Trocar as arestas ao
    longo de um desses ciclos devolve dois matchings perfeitos novos cobrindo
    exatamente as mesmas arestas — ou seja, a 1-fatoração continua válida.
    """
    nodes = {t for pair in f1 + f2 for t in pair}
    adj: dict[str, List[Tuple[str, int]]] = {t: [] for t in nodes}
    for a, b in f1:
        adj[a].append((b, 0))
        adj[b].append((a, 0))
    for a, b in f2:
        adj[a].append((b, 1))
        adj[b].append((a, 1))

    seen: set[str] = set()
    cycles: List[List[Tuple[str, str, int]]] = []
    for start in sorted(nodes):
        if start in seen:
            continue
        cycle: List[Tuple[str, str, int]] = []
        cur, came = start, None
        while True:
            seen.add(cur)
            options = [(n, w) for n, w in adj[cur] if (n, w) != came]
            nxt, which = options[0] if options else adj[cur][0]
            cycle.append((cur, nxt, which))
            came = (cur, which)
            cur = nxt
            if cur == start:
                break
        cycles.append(cycle)

    chosen = rng.choice(cycles)
    moved = {(tuple(sorted((u, v))), w) for u, v, w in chosen}
    new1 = [e for e in f1 if (tuple(sorted(e)), 0) not in moved]
    new1 += [e for e in f2 if (tuple(sorted(e)), 1) in moved]
    new2 = [e for e in f2 if (tuple(sorted(e)), 1) not in moved]
    new2 += [e for e in f1 if (tuple(sorted(e)), 0) in moved]
    return new1, new2


def bipartite_factorization(
    teams: List[str], rng
) -> Tuple[List[List[Pair]], List[List[Pair]], List[str], List[str]]:
    """1-fatoração de K20 alinhada a uma bipartição (A, B) de 10 times cada.

    Devolve `(cruzadas, restantes, part_a, part_b)`:

    * `cruzadas` — 10 matchings que só ligam um time de A a um de B. Juntos
      cobrem exatamente as 100 arestas entre A e B.
    * `restantes` — os outros 9 matchings, cobrindo as 45 + 45 arestas
      internas de A e de B.

    As duas listas somam 19 matchings disjuntos = uma 1-fatoração de K20.

    O ponto da construção: qualquer matching de `cruzadas` tem todo jogo com
    uma ponta em A e outra em B, então atribuir "manda quem é de A" (ou de B)
    define o mando sem ambiguidade. É isso que permite às rodadas 1, 2, 18 e
    19 satisfazerem (c) e (d) por construção, sem resíduo.

    A fatoração sai "pura": cada rodada é toda cruzada ou toda interna. Use
    `shuffle_factors` nas rodadas que não viraram âncora para misturá-las.
    """
    if len(teams) != 20:
        raise ValueError(f"Esperado 20 times; recebido {len(teams)}.")

    shuffled = list(teams)
    rng.shuffle(shuffled)
    part_a, part_b = shuffled[:10], shuffled[10:]

    cruzadas = [
        [(part_a[i], part_b[(i + k) % 10]) for i in range(10)]
        for k in range(10)
    ]
    internas_a = circle_method(part_a)
    internas_b = circle_method(part_b)
    rng.shuffle(internas_b)
    restantes = [internas_a[r] + internas_b[r] for r in range(9)]

    return cruzadas, restantes, part_a, part_b


def shuffle_factors(
    factors: List[List[Pair]], rng, *, flips: int = 60
) -> List[List[Pair]]:
    """Embaralha um conjunto de matchings disjuntos por trocas de ciclo
    alternante, preservando a união das arestas (a 1-fatoração continua
    válida). Serve para dar diversidade ao multi-start sem quebrar estrutura."""
    out = [list(f) for f in factors]
    if len(out) < 2:
        return out
    for _ in range(flips):
        i, j = rng.sample(range(len(out)), 2)
        out[i], out[j] = _alternating_cycle_flip(out[i], out[j], rng)
    return out

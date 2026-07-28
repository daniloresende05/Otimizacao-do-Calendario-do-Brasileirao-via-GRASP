"""Fase 1 — enumeração do quarteto (R1, R2, R18, R19) do círculo.

Para os 19 matchings de circle_method(teams) do dataset real, enumera todos
os pares ordenados (m_a, m_b) candidatos a (R1, R2) [19×18 = 342]:
  - 2-coloração da união m_a ∪ m_b (reuso de _two_color_pair_union);
  - para cada um dos 17 matchings restantes, conta confrontos INCOMPATÍVEIS
    (times de mesma cor → violação de (d) inevitável, qualquer orientação);
  - escolhe os 2 melhores como {R18, R19} e registra a soma de incompatíveis.

Reporta: (a) mínimo global de incompatíveis; (b) quantos pares (R1,R2)
atingem o mínimo; (c) se o mínimo é 0 ((d) exata); (d) se entre as melhores
opções há matching SEM clássico estadual disponível para R19 (necessário
para (e)); (e) quantos matchings limpos existem no total.

PORTÃO: só implementar a fase 1 conjunta se o mínimo global < 6 (valor da
construção atual, medido em diag_restricao_d.py).

SOMENTE LEITURA: nada em src/, tests/ ou data/raw/ é modificado.
"""
from __future__ import annotations

import random
import sys
from itertools import combinations
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):  # console Windows cp1252
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from brasileirao.construction import (  # noqa: E402
    _two_color_pair_union,
    count_classicos,
    no_classico_estadual,
)
from brasileirao.io import load_teams  # noqa: E402
from brasileirao.round_robin import circle_method  # noqa: E402

ROOT = Path(__file__).parents[1]


def main() -> None:
    teams_map = load_teams(str(ROOT / "data" / "raw" / "teams.csv"))
    teams = list(teams_map.keys())
    matchings = circle_method(teams)
    n_m = len(matchings)
    assert n_m == 19

    clean_idx = [
        i for i, m in enumerate(matchings) if no_classico_estadual(m, teams_map)
    ]
    print("=" * 78)
    print("[FASE 1] ENUMERAÇÃO DE QUARTETOS (R1, R2, R18, R19)")
    print("=" * 78)
    print(f"(e) Matchings SEM clássico estadual (limpos): {len(clean_idx)} "
          f"de 19 — índices {clean_idx}")

    # A partição da 2-coloração independe do rng (só os rótulos H/A mudam),
    # então um rng fixo serve para a contagem de incompatíveis.
    rng = random.Random(0)

    # candidato: (soma_incompat, classicos_r19_minimo, i_r1, j_r2, k, l)
    candidates: list[tuple[int, int, int, int, int, int]] = []

    for i in range(n_m):
        for j in range(n_m):
            if i == j:
                continue
            sides = _two_color_pair_union(
                list(matchings[i]), list(matchings[j]), teams, rng
            )
            others = [k for k in range(n_m) if k not in (i, j)]
            incompat = {
                k: sum(1 for a, b in matchings[k] if sides[a] == sides[b])
                for k in others
            }
            best_sum = None
            best_for_pair: list[tuple[int, int, int, int]] = []
            for k, l in combinations(others, 2):
                s = incompat[k] + incompat[l]
                # (e): R19 recebe o matching com MENOS clássicos do par
                cls = min(
                    count_classicos(list(matchings[k]), teams_map),
                    count_classicos(list(matchings[l]), teams_map),
                )
                if best_sum is None or s < best_sum:
                    best_sum = s
                    best_for_pair = [(s, cls, k, l)]
                elif s == best_sum:
                    best_for_pair.append((s, cls, k, l))
            # entre os empates do par (R1,R2), guarda o de menor # clássicos
            s, cls, k, l = min(best_for_pair, key=lambda t: t[1])
            candidates.append((s, cls, i, j, k, l))

    global_min = min(c[0] for c in candidates)
    at_min = [c for c in candidates if c[0] == global_min]
    with_clean_r19 = [c for c in at_min if c[1] == 0]

    print(f"\n(a) MÍNIMO GLOBAL de confrontos incompatíveis em R18+R19: "
          f"{global_min}")
    print(f"(b) Pares ordenados (R1,R2) que atingem o mínimo: "
          f"{len(at_min)} de 342")
    print(f"(c) (d) pode ser EXATA por construção: "
          f"{'SIM' if global_min == 0 else 'NÃO'}")
    print(f"(d) Opções ótimas com matching LIMPO disponível p/ R19: "
          f"{len(with_clean_r19)} de {len(at_min)}"
          f" → (e) preservável: {'SIM' if with_clean_r19 else 'NÃO'}")
    print(f"(e) Total de matchings limpos: {len(clean_idx)}")

    print("\nExemplos de quartetos ótimos (até 10):")
    print(f"  {'R1':>3} {'R2':>3} {'R18/R19':>9} {'incompat':>8} "
          f"{'min clássicos R19':>18}")
    for s, cls, i, j, k, l in with_clean_r19[:10] or at_min[:10]:
        print(f"  {i:>3} {j:>3} {f'{k},{l}':>9} {s:>8} {cls:>18}")

    print("\n" + "=" * 78)
    if global_min < 6:
        print(f"PORTÃO: LIBERADO — mínimo {global_min} < 6 (valor atual). "
              f"Implementar Fase 2.")
    else:
        print(f"PORTÃO: BLOQUEADO — mínimo {global_min} >= 6 (valor atual). "
              f"NÃO implementar.")
    print("=" * 78)


if __name__ == "__main__":
    main()

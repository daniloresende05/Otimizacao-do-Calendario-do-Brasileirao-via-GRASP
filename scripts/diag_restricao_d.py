"""Diagnóstico da restrição (d): espelhamento R18↔R1 e R19↔R2.

HIPÓTESE: a construção decide R18/R19 por ÚLTIMO (_pick_r18_r19, etapa C),
quando os CONFRONTOS dessas rodadas já estão fixados pelo que sobrou da RCL.
A enumeração de 2^10 orientações só escolhe MANDOS. Se um confronto de R18
junta dois times com o MESMO lado em R1 (ou de R19 com mesmo lado em R2),
NENHUMA orientação satisfaz (d) para esse par — exatamente 1 violação
inevitável por par incompatível.

Semântica REAL de check_d (constraints.py): para cada time,
  mando em R18 == inverso do mando em R1, e
  mando em R19 == inverso do mando em R2.

Reproduz a pipeline da CLI (seed=42, modo modesto: grasp_max_iter=10,
ils_max_iter=30) e analisa a solução final.

SOMENTE LEITURA: nada em src/, tests/ ou data/raw/ é modificado.
"""
from __future__ import annotations

import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):  # console Windows cp1252
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from brasileirao.constraints import (  # noqa: E402
    check_d_last_two_rounds_mirror,
    _inverse_side,
    _sides_in_round,
)
from brasileirao.dates import parse_day  # noqa: E402
from brasileirao.grasp import grasp  # noqa: E402
from brasileirao.ils import iterated_local_search  # noqa: E402
from brasileirao.io import load_dates, load_teams  # noqa: E402
from brasileirao.objective import evaluate  # noqa: E402
from brasileirao.round_robin import circle_method  # noqa: E402

ROOT = Path(__file__).parents[1]
SEED = 42
GRASP_MAX_ITER = 10
ILS_MAX_ITER = 30

SIDE_SHORT = {"home": "H", "away": "A"}


def _short(side: str | None) -> str:
    return SIDE_SHORT.get(side, "?") if side else "?"


def _matches_of_round(schedule, r):
    return [(m.home, m.away) for m in schedule if m.round == r]


def main() -> None:
    # ------------------------------------------------------------------
    # 1. Reproduzir a pipeline real da CLI
    # ------------------------------------------------------------------
    teams_map = load_teams(str(ROOT / "data" / "raw" / "teams.csv"))
    dates_raw = load_dates(
        str(ROOT / "data" / "raw" / "datas_20-08-2023_a_09-06-2024.csv"),
        col="Data",
    )
    dates = sorted(parse_day(s.strip()).date() for s in dates_raw)

    print("=" * 78)
    print("[1] REPRODUÇÃO DA PIPELINE "
          f"(seed={SEED}, grasp_max_iter={GRASP_MAX_ITER}, "
          f"ils_max_iter={ILS_MAX_ITER})")
    print("=" * 78)

    grasp_result = grasp(
        teams_map,
        dates,
        max_iter=GRASP_MAX_ITER,
        seed=SEED,
    )
    print(f"GRASP: melhor na iteração {grasp_result.best_iter} "
          f"(seed={grasp_result.best_seed}, alpha={grasp_result.best_alpha}) "
          f"| lex_key={grasp_result.best_evaluation.lexicographic_key()}")

    final = iterated_local_search(
        grasp_result.best_schedule,
        teams_map,
        max_iter=ILS_MAX_ITER,
        seed=SEED,
    )
    final_eval = evaluate(final)
    print(f"Final: feasible={final_eval.is_feasible} "
          f"| lex_key={final_eval.lexicographic_key()} "
          f"| PRV={final_eval.total_prv}")
    print(f"Violações por tipo: {final_eval.violations_by_type}")

    d_viols = check_d_last_two_rounds_mirror(final)
    print(f"\nViolações de (d) na solução final: {len(d_viols)}")
    if len(d_viols) == 10:
        print("→ Confirma as 10 violações reportadas na execução real.")
    else:
        print("→ ATENÇÃO: difere das 10 reportadas — verificar parâmetros.")

    # [1b] Quantas violações de (d) já saem da CONSTRUÇÃO (antes do ILS)?
    d_pre_ils = check_d_last_two_rounds_mirror(grasp_result.best_schedule)
    print(f"\n[1b] Violações de (d) na melhor solução do GRASP (PRÉ-ILS): "
          f"{len(d_pre_ils)}")
    for v in d_pre_ils:
        print(f"     R{v.round} {v.team}")

    # ------------------------------------------------------------------
    # Mapas de lado por rodada (solução final)
    # ------------------------------------------------------------------
    side_r1 = _sides_in_round(final, 1)
    side_r2 = _sides_in_round(final, 2)
    side_r18 = _sides_in_round(final, 18)
    side_r19 = _sides_in_round(final, 19)

    # ------------------------------------------------------------------
    # 2. Listar cada violação de (d): esperado vs. obtido
    # ------------------------------------------------------------------
    print("\n" + "=" * 78)
    print("[2] VIOLAÇÕES DE (d) — DETALHE (esperado = inverso da rodada-espelho)")
    print("=" * 78)
    for v in d_viols:
        if v.round == 18:
            ref_round, ref_side, got = 1, side_r1[v.team], side_r18[v.team]
        else:
            ref_round, ref_side, got = 2, side_r2[v.team], side_r19[v.team]
        print(f"  R{v.round} | {v.team:<15} "
              f"| R{ref_round}={_short(ref_side)} "
              f"→ esperado em R{v.round}: {_short(_inverse_side(ref_side))} "
              f"| obtido: {_short(got)}")

    # ------------------------------------------------------------------
    # 3. Mapa de lados de R1 e R2
    # ------------------------------------------------------------------
    print("\n" + "=" * 78)
    print("[3] MAPA DE LADOS — R1 e R2 (solução final)")
    print("=" * 78)
    print(f"  {'Time':<15} R1  R2")
    c_ok = True
    for t in sorted(teams_map):
        s1, s2 = side_r1.get(t), side_r2.get(t)
        flag = ""
        if s1 == s2:
            flag = "  <-- mesmo lado em R1 e R2 (viola (c))"
            c_ok = False
        print(f"  {t:<15} {_short(s1)}   {_short(s2)}{flag}")
    print(f"\n  (c) estrita na solução final (R2 = inverso de R1 p/ todos): "
          f"{'SIM' if c_ok else 'NÃO'}")

    # ------------------------------------------------------------------
    # 4. Compatibilidade de cada confronto de R18 e R19
    # ------------------------------------------------------------------
    # R18 espelha R1: o confronto {a,b} admite orientação que satisfaz (d)
    # sse a e b têm lados OPOSTOS em R1. Idem R19 com R2.
    print("\n" + "=" * 78)
    print("[4] CONFRONTOS DE R18/R19 × LADOS EM R1/R2")
    print("=" * 78)

    incompat_teams: dict[int, set[str]] = {18: set(), 19: set()}
    incompat_pairs: dict[int, int] = {18: 0, 19: 0}

    for r, ref_sides, ref_r in ((18, side_r1, 1), (19, side_r2, 2)):
        print(f"\n  Rodada {r} (espelha R{ref_r}):")
        for h, a in _matches_of_round(final, r):
            sh, sa = ref_sides[h], ref_sides[a]
            compat = sh != sa
            status = "COMPATÍVEL  " if compat else "INCOMPATÍVEL"
            if not compat:
                incompat_pairs[r] += 1
                incompat_teams[r].update((h, a))
            print(f"    {status} | {h} (R1={_short(side_r1[h])}, "
                  f"R2={_short(side_r2[h])}) x {a} "
                  f"(R1={_short(side_r1[a])}, R2={_short(side_r2[a])})"
                  f"  [lado em R{ref_r}: {_short(sh)} vs {_short(sa)}]")
        print(f"    → {incompat_pairs[r]} confronto(s) incompatível(is) em R{r}")

    # ------------------------------------------------------------------
    # 5. Resumo parcial: violações explicadas por pares incompatíveis
    # ------------------------------------------------------------------
    print("\n" + "=" * 78)
    print("[5] RESUMO PARCIAL — hipótese")
    print("=" * 78)
    explained = 0
    unexplained = []
    for v in d_viols:
        if v.team in incompat_teams[v.round]:
            explained += 1
        else:
            unexplained.append(v)
    total_incompat = incompat_pairs[18] + incompat_pairs[19]
    print(f"  Confrontos incompatíveis: {incompat_pairs[18]} em R18 "
          f"+ {incompat_pairs[19]} em R19 = {total_incompat}")
    print("  (cada par incompatível gera EXATAMENTE 1 violação inevitável:")
    print("   um dos dois times fica no lado errado, qualquer que seja o mando)")
    print(f"  Violações de (d): {len(d_viols)} no total")
    print(f"    explicadas por par incompatível: {explained}")
    print(f"    NÃO explicadas (orientação subótima ou efeito do ILS): "
          f"{len(unexplained)}")
    for v in unexplained:
        print(f"      - R{v.round} {v.team}")
    if explained == len(d_viols) and total_incompat == len(d_viols):
        print("\n  → HIPÓTESE CONFIRMADA: todas as violações vêm de confrontos")
        print("    estruturalmente incompatíveis fixados antes da etapa C.")
    else:
        print("\n  → Hipótese explica parte; investigar o restante.")

    # ------------------------------------------------------------------
    # 6. Viabilidade da correção: matchings do círculo compatíveis
    # ------------------------------------------------------------------
    print("\n" + "=" * 78)
    print("[6] TESTE DE VIABILIDADE — matchings do método do círculo")
    print("=" * 78)

    teams = list(teams_map.keys())
    matchings = circle_method(teams)

    # identifica qual matching foi usado em cada rodada do turno final
    round_pairset = {
        r: frozenset(frozenset(p) for p in _matches_of_round(final, r))
        for r in range(1, 20)
    }
    matching_round: dict[int, int | None] = {}
    for i, m in enumerate(matchings):
        ps = frozenset(frozenset(p) for p in m)
        matching_round[i] = next(
            (r for r, rps in round_pairset.items() if rps == ps), None
        )

    def compat_count(m, ref_sides):
        return sum(1 for a, b in m if ref_sides[a] != ref_sides[b])

    print("\n  Compatibilidade de cada matching (10/10 pares com lados opostos"
          " = COMPATÍVEL):")
    print(f"  {'#':<3} {'usado como':<12} {'vs R1 (p/ R18)':<16} "
          f"{'vs R2 (p/ R19)':<16} status")
    compat_others = []
    for i, m in enumerate(matchings):
        c1 = compat_count(m, side_r1)
        c2 = compat_count(m, side_r2)
        r_used = matching_round[i]
        used = f"R{r_used}" if r_used else "-"
        full = c1 == 10 and c2 == 10
        if full and r_used in (1, 2):
            status = "compatível, mas É R1/R2 (não reutilizável)"
        elif full:
            status = "COMPATÍVEL ✔ (candidato a R18/R19)"
            compat_others.append((i, r_used))
        else:
            status = "incompatível"
        print(f"  {i:<3} {used:<12} {c1:>2}/10{'':<10} {c2:>2}/10{'':<10} "
              f"{status}")

    print(f"\n  Matchings compatíveis EXCLUINDO R1/R2: {len(compat_others)}")
    for i, r_used in compat_others:
        pares = ", ".join(f"{a}x{b}" for a, b in matchings[i])
        print(f"    matching #{i} (hoje usado como "
              f"R{r_used if r_used else '?'}): {pares}")
    if len(compat_others) >= 2:
        print("\n  → EXISTEM ≥2 matchings compatíveis disponíveis: uma fase 1")
        print("    conjunta (escolher R1/R2/R18/R19 juntos) poderia zerar (d)")
        print("    por construção.")
    else:
        print("\n  → MENOS de 2 matchings compatíveis além de R1/R2: a correção")
        print("    exigiria escolher R1/R2 (a 2-coloração) em função de R18/R19,")
        print("    não apenas realocar matchings.")

    # ------------------------------------------------------------------
    # 6b. A 2-coloração não é única: o grafo R1 ∪ R2 decompõe em ciclos e
    #     cada ciclo pode ser "flipado" independentemente (a construção fixa
    #     um flip aleatório por componente). Existe escolha de flips que
    #     torne ≥2 OUTROS matchings compatíveis?
    # ------------------------------------------------------------------
    print("\n" + "=" * 78)
    print("[6b] E COM OUTRA 2-COLORAÇÃO DO MESMO R1 ∪ R2?")
    print("=" * 78)

    r1_pairs = _matches_of_round(final, 1)
    r2_pairs = _matches_of_round(final, 2)
    adj: dict[str, list[str]] = {t: [] for t in teams}
    for a, b in r1_pairs + r2_pairs:
        adj[a].append(b)
        adj[b].append(a)

    components: list[list[str]] = []
    seen: set[str] = set()
    for start in teams:
        if start in seen:
            continue
        comp = []
        stack = [start]
        seen.add(start)
        while stack:
            cur = stack.pop()
            comp.append(cur)
            for nb in adj[cur]:
                if nb not in seen:
                    seen.add(nb)
                    stack.append(nb)
        components.append(comp)
    print(f"  Componentes (ciclos) de R1 ∪ R2: {len(components)} "
          f"— tamanhos {[len(c) for c in components]}")

    # coloração base por BFS bipartido em cada componente
    base_color: dict[str, int] = {}
    for comp in components:
        base_color[comp[0]] = 0
        stack = [comp[0]]
        while stack:
            cur = stack.pop()
            for nb in adj[cur]:
                if nb not in base_color:
                    base_color[nb] = 1 - base_color[cur]
                    stack.append(nb)

    comp_of = {t: ci for ci, comp in enumerate(components) for t in comp}
    others = [i for i in range(19) if matching_round[i] not in (1, 2)]

    best_flips_result: tuple[int, int, list[int]] | None = None
    for flips in range(1 << len(components)):
        color = {
            t: base_color[t] ^ ((flips >> comp_of[t]) & 1) for t in teams
        }
        compat_idx = [
            i for i in others
            if all(color[a] != color[b] for a, b in matchings[i])
        ]
        if best_flips_result is None or len(compat_idx) > best_flips_result[0]:
            best_flips_result = (len(compat_idx), flips, compat_idx)

    n_best, _, idx_best = best_flips_result
    print(f"  Melhor caso sobre os {1 << len(components)} flips possíveis: "
          f"{n_best} matching(s) compatível(is) além de R1/R2")
    for i in idx_best:
        pares = ", ".join(f"{a}x{b}" for a, b in matchings[i])
        print(f"    matching #{i} (hoje R{matching_round[i]}): {pares}")
    if n_best >= 2:
        print("  → Com a MESMA escolha de R1/R2, outra coloração viabiliza")
        print("    R18/R19 sem violações estruturais de (d).")
    else:
        print("  → Nem mudando a coloração: a correção precisa escolher também")
        print("    OUTROS matchings para R1/R2 (fase 1 totalmente conjunta).")

    print("\nFIM DO DIAGNÓSTICO (somente leitura; nada foi modificado).")


if __name__ == "__main__":
    main()

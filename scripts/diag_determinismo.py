"""Diagnostico: determinismo entre seeds e efeito do "tudo hard".

Pergunta: seeds diferentes produzindo o MESMO resultado no modo tudo-hard e
(A) bug de propagacao de seed ou (B) efeito esperado do colapso do espaco
viavel quando (d) e (h) — que tem piso estrutural > 0 neste dataset — viram
hard?

Metodo: roda a pipeline (grasp -> best -> ILS) com parametros modestos
(grasp_max_iter=10, ils_max_iter=30) para 5 seeds, em duas configuracoes de
CONSTRAINT_HARDNESS (default a,b,i,j vs tudo hard), e compara lex_key, PRV e
um hash sha1 da solucao (lista ordenada de (rodada, mandante, visitante,
data)).

SOMENTE LEITURA: nao altera src/, tests/ nem data/raw/. As configuracoes de
dureza sao mutadas apenas em memoria (o dict CONSTRAINT_HARDNESS do modulo
importado), nunca no arquivo.

Uso (raiz do repo):
    PYTHONPATH=src python scripts/diag_determinismo.py
"""
from __future__ import annotations

import hashlib
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from brasileirao.dates import parse_day
from brasileirao.grasp import grasp
from brasileirao.ils import iterated_local_search
from brasileirao.io import load_dates, load_teams
from brasileirao.objective import (
    CONSTRAINT_HARDNESS,
    evaluate,
    hard_violation_summary,
)

SEEDS = [42, 1, 7, 13, 99]
GRASP_MAX_ITER = 10
ILS_MAX_ITER = 30

# Configuracoes aplicadas EM MEMORIA (o arquivo objective.py nao e tocado).
# Nao usamos reset_constraint_hardness() porque o snapshot _DEFAULT_HARDNESS
# reflete o estado atual do arquivo, que pode estar editado para tudo-True.
HARDNESS_DEFAULT = {
    "a": True, "b": True, "c": False, "d": False, "e": False,
    "f": False, "g": False, "h": False, "i": True, "j": True,
}
HARDNESS_ALL = {cid: True for cid in "abcdefghij"}


def set_hardness(config: dict[str, bool]) -> None:
    CONSTRAINT_HARDNESS.clear()
    CONSTRAINT_HARDNESS.update(config)


def solution_hash(schedule) -> str:
    """sha1 (12 hex) da lista ordenada de (rodada, mandante, visitante, data)."""
    key = sorted((m.round, m.home, m.away, m.day) for m in schedule)
    return hashlib.sha1(repr(key).encode("utf-8")).hexdigest()[:12]


def run_pipeline(teams_map, dates, seed: int):
    grasp_result = grasp(
        teams_map, dates,
        max_iter=GRASP_MAX_ITER,
        max_iter_no_improve=GRASP_MAX_ITER,  # nao parar antes das 10
        seed=seed,
    )
    final_schedule = iterated_local_search(
        grasp_result.best_schedule,
        teams_map,
        max_iter=ILS_MAX_ITER,
        max_iter_no_improve=ILS_MAX_ITER,  # nao parar antes das 30
        seed=seed,
    )
    return evaluate(final_schedule), final_schedule


def run_config(name: str, hardness: dict[str, bool], teams_map, dates):
    set_hardness(hardness)
    print(f"\n{'=' * 72}")
    print(f"CONFIG {name} | hard = "
          f"{{{', '.join(sorted(c for c, v in hardness.items() if v))}}}")
    print(f"{'=' * 72}")
    print(f"{'seed':>4} | {'lex_key':>14} | {'PRV':>3} | {'hash':>12} | "
          f"hard com violacao > 0")
    print("-" * 72)

    rows = []
    for seed in SEEDS:
        ev, sched = run_pipeline(teams_map, dates, seed)
        h = solution_hash(sched)
        viol = hard_violation_summary(ev.violations_by_type) or "-"
        rows.append((seed, ev.lexicographic_key(), ev.total_prv, h, viol))
        print(f"{seed:>4} | {str(ev.lexicographic_key()):>14} | "
              f"{ev.total_prv:>3} | {h:>12} | {viol}")

    hashes = {r[3] for r in rows}
    lexes = {r[1] for r in rows}
    print("-" * 72)
    print(f"Solucoes distintas (hash): {len(hashes)}/{len(SEEDS)} | "
          f"lex_keys distintas: {len(lexes)}/{len(SEEDS)}")
    return rows, hashes, lexes


def main() -> None:
    root = os.path.join(os.path.dirname(__file__), "..")
    teams_map = load_teams(os.path.join(root, "data", "raw", "teams.csv"))
    dates_raw = load_dates(
        os.path.join(root, "data", "raw", "datas_20-08-2023_a_09-06-2024.csv"),
        col="Data",
    )
    dates = sorted(parse_day(s.strip()).date() for s in dates_raw)
    print(f"Times: {len(teams_map)} | Datas: {len(dates)} | Seeds: {SEEDS}")
    print(f"grasp_max_iter={GRASP_MAX_ITER}, ils_max_iter={ILS_MAX_ITER}")

    _, hashes_def, lexes_def = run_config(
        "DEFAULT", HARDNESS_DEFAULT, teams_map, dates
    )
    _, hashes_all, lexes_all = run_config(
        "TUDO HARD", HARDNESS_ALL, teams_map, dates
    )

    print(f"\n{'=' * 72}")
    print("VEREDITO")
    print(f"{'=' * 72}")
    if len(hashes_def) > 1:
        print(
            "DEFAULT: seeds diferentes produzem solucoes DIFERENTES "
            f"({len(hashes_def)}/{len(SEEDS)} hashes distintos) -> a "
            "aleatoriedade e a propagacao de seed FUNCIONAM. Nao ha bug (A)."
        )
        if len(hashes_all) == 1:
            print(
                "TUDO HARD: todas as seeds convergem para a MESMA solucao -> "
                "efeito (B): com (d) e (h) hard o espaco viavel e VAZIO "
                "(pisos estruturais d>=4, PRV>0) e a chave lexicografica "
                "(hard, soft, prv) colapsa todas as buscas no mesmo "
                "'menos inviavel'."
            )
        elif len(lexes_all) == 1:
            print(
                "TUDO HARD: solucoes distintas entre seeds, mas MESMA "
                "lex_key minima -> efeito (B): as buscas atingem o mesmo "
                "piso estrutural (empate lexicografico), sem bug de seed."
            )
        else:
            print(
                "TUDO HARD: solucoes E lex_keys variam entre seeds -> o "
                "determinismo observado antes nao se reproduziu aqui; "
                "verificar os parametros da observacao original."
            )
    else:
        print(
            "DEFAULT: TODAS as seeds produziram a MESMA solucao -> ha BUG "
            "de propagacao de seed (A). Revisar: grasp.py (seed_iter), "
            "construction.py (rng) e ils.py (rng)."
        )


if __name__ == "__main__":
    main()

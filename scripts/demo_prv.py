"""Script de DIAGNOSTICO (nao e' feature de producao): mostra o PRV caindo em
cada etapa do pipeline (construcao -> GRASP+VND -> ILS) no dataset real do
Brasileirao 2023. Apenas le e roda o que ja existe em src/; nao altera nada.

Como rodar:
    PYTHONPATH=src python scripts/demo_prv.py

(no Windows/PowerShell: $env:PYTHONPATH="src"; python scripts/demo_prv.py)
"""
from __future__ import annotations

import time
from datetime import datetime

from brasileirao.construction import construct_schedule
from brasileirao.grasp import grasp
from brasileirao.io import load_dates, load_teams
from brasileirao.ils import iterated_local_search
from brasileirao.local_search import local_search
from brasileirao.objective import evaluate
from brasileirao.real_baseline import load_real_schedule_2023

# ---------------------------------------------------------------------------
# Parametros do demo (fixos e parametrizaveis aqui no topo do script)
# ---------------------------------------------------------------------------
SEED = 42

TEAMS_PATH = "data/raw/teams.csv"
DATES_PATH = "data/raw/datas_20-08-2023_a_09-06-2024.csv"
REAL_SCHEDULE_PATH = "data/raw/tabela_real_brasileirao_2023.csv"

# GRASP e ILS completos (max_iter=50 / max_iter=200, defaults de producao) sao
# lentos demais para uma demo ao vivo no dataset real de 380 jogos (cada
# chamada a local_search sozinha leva ~30s neste dataset). Por isso o demo usa
# poucas iteracoes -- ver aviso "[modo demo]" impresso mais abaixo.
GRASP_MAX_ITER = 5
GRASP_MAX_ITER_NO_IMPROVE = 5
ILS_MAX_ITER = 1
ILS_MAX_ITER_NO_IMPROVE = 1


def _fmt_reduction(before: int, after: int) -> str:
    abs_red = before - after
    pct = (abs_red / before * 100.0) if before else 0.0
    return f"{abs_red:+d} ({pct:.1f}%)" if before else "n/a"


def main() -> None:
    print("=== 1. Carregando teams + datas ===")
    teams_map = load_teams(TEAMS_PATH)
    dates_raw = load_dates(DATES_PATH)
    dates = [datetime.strptime(s, "%d/%m/%Y").date() for s in dates_raw]
    print(f"  {len(teams_map)} times, {len(dates)} datas disponiveis")

    prv_real: int | None = None
    print("\n=== 2. Baseline: tabela real CBF 2023 ===")
    real_schedule = load_real_schedule_2023(REAL_SCHEDULE_PATH, teams_map)
    real_eval = evaluate(real_schedule)
    prv_real = real_eval.total_prv
    print(f"PRV tabela real CBF 2023: {prv_real}")

    print("\n=== 3. Construcao (GRASP greedy-aleatorio, 1 chamada) ===")
    t0 = time.perf_counter()
    constructed = construct_schedule(teams_map, dates, seed=SEED)
    t_construct = time.perf_counter() - t0
    constructed_eval = evaluate(constructed)
    prv_constructed = constructed_eval.total_prv
    print(f"PRV apos construcao: {prv_constructed}  (tempo: {t_construct:.2f}s)")

    print(
        f"\n=== 4. GRASP [modo demo, {GRASP_MAX_ITER} iteracoes] "
        "(multi-start construcao + VND) ==="
    )
    print(
        "  Nota: brasileirao.grasp.grasp() e' so o loop multi-start de "
        "CONSTRUCAO (sem busca local) -- ver 'O QUE PRECISOU SER ADAPTADO' no "
        "relatorio final. O VND e' aplicado aqui manualmente sobre o melhor "
        "incumbente do GRASP para dar o numero 'construcao+VND' pedido."
    )
    t0 = time.perf_counter()
    grasp_result = grasp(
        teams_map,
        dates,
        seed=SEED,
        max_iter=GRASP_MAX_ITER,
        max_iter_no_improve=GRASP_MAX_ITER_NO_IMPROVE,
    )
    grasp_vnd_schedule = local_search(grasp_result.best_schedule, teams_map)
    t_grasp = time.perf_counter() - t0
    grasp_vnd_eval = evaluate(grasp_vnd_schedule)
    prv_grasp = grasp_vnd_eval.total_prv
    print(f"PRV apos GRASP (construcao+VND): {prv_grasp}  (tempo: {t_grasp:.2f}s)")

    print(f"\n=== 5. ILS [modo demo, {ILS_MAX_ITER} iteracao(oes)] ===")
    t0 = time.perf_counter()
    ils_schedule = iterated_local_search(
        grasp_vnd_schedule,
        teams_map,
        seed=SEED,
        max_iter=ILS_MAX_ITER,
        max_iter_no_improve=ILS_MAX_ITER_NO_IMPROVE,
    )
    t_ils = time.perf_counter() - t0
    ils_eval = evaluate(ils_schedule)
    prv_ils = ils_eval.total_prv
    print(f"PRV apos ILS: {prv_ils}  (tempo: {t_ils:.2f}s)")

    print("\n=== 6. Quadro-resumo ===")
    header = f"{'Etapa':<28}{'PRV':>8}"
    print(header)
    print("-" * len(header))
    print(f"{'Tabela real CBF 2023':<28}{prv_real:>8}")
    print(f"{'Apos construcao':<28}{prv_constructed:>8}")
    print(f"{'Apos GRASP (construcao+VND)':<28}{prv_grasp:>8}")
    print(f"{'Apos ILS':<28}{prv_ils:>8}")

    print("\nReducao total:")
    print(f"  real -> ILS:         {_fmt_reduction(prv_real, prv_ils)}")
    print(f"  construcao -> ILS:   {_fmt_reduction(prv_constructed, prv_ils)}")

    print("\n=== 7. Tempo computacional ===")
    print(f"  GRASP (construcao multi-start + VND): {t_grasp:.2f}s")
    print(f"  ILS:                                  {t_ils:.2f}s")


if __name__ == "__main__":
    main()

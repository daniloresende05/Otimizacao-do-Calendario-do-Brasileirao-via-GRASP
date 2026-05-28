"""
=================================================================
DEMONSTRACAO -- GRASP Multi-Start (sem busca local)
=================================================================

Roda o loop multi-start do GRASP, compara com construcao unica e
com a tabela real do Brasileirao 2023.

Como rodar:
   python demo_grasp.py
"""
from __future__ import annotations

import csv
import os
import statistics
import sys
from collections import defaultdict
from datetime import datetime

sys.path.insert(0, "src")

from brasileirao.construction import construct_schedule
from brasileirao.grasp import DEFAULT_ALPHA_POOL, grasp
from brasileirao.io import load_dates, load_teams
from brasileirao.objective import compute_prv, evaluate
from brasileirao.real_baseline import load_real_schedule_2023

TEAMS_PATH = "data/raw/teams.csv"
DATES_PATH = "data/raw/datas_20-08-2023_a_09-06-2024.csv"
REAL_PATH = "data/raw/tabela_real_brasileirao_2023.csv"

MAX_ITER = 50
MAX_ITER_NO_IMPROVE = 20
ALPHA_POOL = DEFAULT_ALPHA_POOL
SEED = 42
PRV_DAYS = 5
MIN_TEAM_REST_DAYS = 3


def _sep(title: str) -> None:
    print(f"\n{'=' * 70}")
    print(f"  {title}")
    print("=" * 70)


def _sides_in_round(schedule: list, r: int) -> dict[str, str]:
    sides: dict[str, str] = {}
    for m in schedule:
        if m.round == r:
            sides[m.home] = "H"
            sides[m.away] = "A"
    return sides


def main() -> None:
    # ── Etapa 0 — Baseline real 2023 ─────────────────────────────
    _sep("Etapa 0 -- Baseline real (Brasileirao 2023)")
    teams = load_teams(TEAMS_PATH)
    real_schedule = load_real_schedule_2023(REAL_PATH, teams)
    real_eval = evaluate(real_schedule, prv_days=PRV_DAYS)
    real_lex = real_eval.lexicographic_key()
    print(f"  Total jogos carregados: {len(real_schedule)}")
    print(f"  Total PRV:    {real_eval.total_prv}")
    print(f"  Total hard:   {len(real_eval.hard_constraint_violations)}")
    print(f"  Total soft:   {len(real_eval.soft_constraint_violations)}")
    print(f"  Lex key:      {real_lex}")

    # ── Etapa 1 — Configuracao ────────────────────────────────────
    _sep("Etapa 1 -- Configuracao")
    print(f"  max_iter:             {MAX_ITER}")
    print(f"  max_iter_no_improve:  {MAX_ITER_NO_IMPROVE}")
    print(f"  alpha_pool:           {ALPHA_POOL}")
    print(f"  seed:                 {SEED}")
    print(f"  prv_days:             {PRV_DAYS}")
    print(f"  min_team_rest_days:   {MIN_TEAM_REST_DAYS}")

    # ── Etapa 2 — Carga de dados ─────────────────────────────────
    _sep("Etapa 2 -- Carga de dados")
    raw_dates = load_dates(DATES_PATH)
    dates = [datetime.strptime(d, "%d/%m/%Y").date() for d in raw_dates]

    print(f"  Times carregados:  {len(teams)}")
    print(f"  Datas disponiveis: {len(dates)} ({dates[0]} a {dates[-1]})")

    stadium_teams: dict[str, list[str]] = {}
    for name, t in teams.items():
        stadium_teams.setdefault(t.stadium, []).append(name)
    shared = {s: ts for s, ts in stadium_teams.items() if len(ts) > 1}
    if shared:
        print("  Estadios compartilhados:")
        for stadium, ts in shared.items():
            print(f"    {stadium}: {', '.join(ts)}")
    else:
        print("  Nenhum estadio compartilhado.")

    # ── Etapa 3 — Baseline: construcao unica ─────────────────────
    _sep("Etapa 3 -- Baseline: construcao unica (seed=42, alpha=0.3)")
    baseline = construct_schedule(teams, dates, alpha=0.3, seed=SEED)
    baseline_eval = evaluate(baseline, prv_days=PRV_DAYS)
    baseline_lex = baseline_eval.lexicographic_key()
    print(f"  Total PRV:   {baseline_eval.total_prv}")
    print(f"  Lex key:     {baseline_lex}")
    print(f"  f(x):        {baseline_eval.total_cost:.1f}")
    print(f"  Viavel:      {'SIM' if baseline_eval.is_feasible else 'NAO'}")

    # ── Etapa 4 — Loop GRASP ─────────────────────────────────────
    _sep("Etapa 4 -- Loop GRASP")
    result = grasp(
        teams,
        dates,
        max_iter=MAX_ITER,
        max_iter_no_improve=MAX_ITER_NO_IMPROVE,
        alpha_pool=ALPHA_POOL,
        seed=SEED,
        prv_days=PRV_DAYS,
        min_team_rest_days=MIN_TEAM_REST_DAYS,
    )

    header = (
        f"  {'Iter':>4} | {'Seed':>5} | {'a':>4} | "
        f"{'Hard':>4} | {'Soft':>4} | {'PRV':>3} | {'Lex Key':>14} | Melhor?"
    )
    sep_line = (
        f"  {'-' * 4}-+-{'-' * 5}-+-{'-' * 4}-+-"
        f"{'-' * 4}-+-{'-' * 4}-+-{'-' * 3}-+-{'-' * 14}-+-{'-' * 7}"
    )
    print(header)
    print(sep_line)
    for h in result.history:
        star = "  *" if h.is_new_best else ""
        lk = h.lex_key
        print(
            f"  {h.iter_number:4d} | {h.seed:5d} | {h.alpha:.2f} | "
            f"{lk[0]:4d} | {lk[1]:4d} | {lk[2]:3d} | "
            f"({lk[0]},{lk[1]:>2d},{lk[2]:>3d})     |{star}"
        )

    # ── Etapa 5 — Resumo da trajetoria ───────────────────────────
    _sep("Etapa 5 -- Resumo da trajetoria")
    print(f"  Total de iteracoes: {result.total_iterations}")
    print(f"  Motivo da parada:   {result.stopped_by}")
    print(f"  Melhor iteracao:    {result.best_iter} (seed={result.best_seed}, alpha={result.best_alpha:.2f})")

    prvs = [h.total_prv for h in result.history]
    if len(prvs) > 1:
        print(f"\n  Distribuicao de PRV:")
        print(f"    min={min(prvs)}  max={max(prvs)}  "
              f"media={statistics.mean(prvs):.1f}  "
              f"mediana={statistics.median(prvs):.1f}  "
              f"desvio={statistics.stdev(prvs):.1f}")

    alpha_counts: dict[float, int] = {}
    for h in result.history:
        alpha_counts[h.alpha] = alpha_counts.get(h.alpha, 0) + 1
    print(f"\n  Distribuicao de alpha:")
    for a in sorted(alpha_counts):
        print(f"    alpha={a:.2f}: {alpha_counts[a]}x")

    grasp_lex = result.best_evaluation.lexicographic_key()
    print(f"\n  {'Metrica':<22} | {'Real 2023':>12} | {'Construcao':>12} | {'GRASP melhor':>12}")
    print(f"  {'-' * 22}-+-{'-' * 12}-+-{'-' * 12}-+-{'-' * 12}")
    print(f"  {'Violacoes hard':<22} | {real_lex[0]:>12} | {baseline_lex[0]:>12} | {grasp_lex[0]:>12}")
    print(f"  {'Violacoes soft estr.':<22} | {real_lex[1]:>12} | {baseline_lex[1]:>12} | {grasp_lex[1]:>12}")
    print(f"  {'Total PRV':<22} | {real_lex[2]:>12} | {baseline_lex[2]:>12} | {grasp_lex[2]:>12}")
    print(f"  {'Lex key':<22} | {str(real_lex):>12} | {str(baseline_lex):>12} | {str(grasp_lex):>12}")

    # ── Etapa 6 — Detalhamento do melhor schedule ────────────────
    _sep("Etapa 6 -- Detalhamento do melhor schedule")
    prv_result = result.best_evaluation.prv_result
    best_sched = result.best_schedule

    print("  PRV por estadio:")
    all_stadiums = sorted({sm.stadium for sm in best_sched})
    for stadium in sorted(all_stadiums, key=lambda s: -(prv_result.prv_by_stadium.get(s, 0))):
        cnt = prv_result.prv_by_stadium.get(stadium, 0)
        marker = " <" if cnt > 0 else ""
        print(f"    {stadium}: {cnt}{marker}")

    if prv_result.occurrences:
        n = min(10, len(prv_result.occurrences))
        print(f"\n  Primeiras {n} ocorrencias de PRV:")
        for occ in prv_result.occurrences[:n]:
            print(
                f"    {occ.stadium}: R{occ.match_a.round} ({occ.match_a.day}) "
                f"-> R{occ.match_b.round} ({occ.match_b.day}), "
                f"{occ.days_between} dias"
            )

    # Violacoes estruturais detalhadas
    print(f"\n  --- Violacoes de (d) -- espelho R18/R19 ---")
    s1 = _sides_in_round(best_sched, 1)
    s2 = _sides_in_round(best_sched, 2)
    s18 = _sides_in_round(best_sched, 18)
    s19 = _sides_in_round(best_sched, 19)
    d_found = False
    for team in sorted(s1.keys()):
        r1, r2 = s1.get(team, "?"), s2.get(team, "?")
        r18, r19 = s18.get(team, "?"), s19.get(team, "?")
        inv1 = "A" if r1 == "H" else "H"
        inv2 = "A" if r2 == "H" else "H"
        m18 = "ok" if r18 == inv1 else "x"
        m19 = "ok" if r19 == inv2 else "x"
        if m18 == "x" or m19 == "x":
            d_found = True
            print(f"    {team:20s} R1={r1}, R2={r2}, R18={r18} {m18}, R19={r19} {m19}")
    if not d_found:
        print("    Nenhuma violacao de (d).")

    print(f"\n  --- Violacoes de (f) -- balanco casa/fora no turno ---")
    home_count: dict[str, int] = defaultdict(int)
    away_count: dict[str, int] = defaultdict(int)
    for m in best_sched:
        if 1 <= m.round <= 19:
            home_count[m.home] += 1
            away_count[m.away] += 1
    f_found = False
    for team in sorted(set(home_count) | set(away_count)):
        h, a = home_count[team], away_count[team]
        if abs(h - a) > 1:
            f_found = True
            print(f"    {team:20s} casa={h}, fora={a} (diff={abs(h - a)})")
    if not f_found:
        print("    Nenhuma violacao de (f).")

    print(f"\n  --- Violacoes de (g) -- sequencias consecutivas ---")
    by_team: dict[str, list[tuple[int, str]]] = defaultdict(list)
    for m in best_sched:
        by_team[m.home].append((m.round, "H"))
        by_team[m.away].append((m.round, "A"))
    g_found = False
    for team in sorted(by_team):
        entries = sorted(by_team[team])
        seq = [s for _, s in entries]
        runs: list[str] = []
        run_start = 0
        for i in range(1, len(seq)):
            if seq[i] != seq[i - 1]:
                run_len = i - run_start
                if run_len > 2:
                    runs.append(
                        f"run de {run_len} '{seq[run_start]}' em "
                        f"R{entries[run_start][0]}-R{entries[i - 1][0]}"
                    )
                run_start = i
        run_len = len(seq) - run_start
        if run_len > 2:
            runs.append(
                f"run de {run_len} '{seq[run_start]}' em "
                f"R{entries[run_start][0]}-R{entries[-1][0]}"
            )
        if runs:
            g_found = True
            seq_str = " ".join(seq)
            print(f"    {team:20s} {seq_str}")
            for r in runs:
                print(f"    {'':20s}   -> {r}")
    if not g_found:
        print("    Nenhuma violacao de (g).")

    print(f"\n  {result.best_evaluation.summary()}")
    print(f"\n  Viavel: {'SIM' if result.best_evaluation.is_feasible else 'NAO'}")

    # ── Etapa 7 — Exportacao ─────────────────────────────────────
    _sep("Etapa 7 -- Exportacao")
    os.makedirs("results", exist_ok=True)

    sched_path = "results/schedule_grasp.csv"
    with open(sched_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["round", "day", "home", "away", "stadium", "home_state", "away_state"])
        for sm in best_sched:
            writer.writerow([sm.round, sm.day, sm.home, sm.away, sm.stadium, sm.home_state, sm.away_state])
    print(f"  Schedule salvo em: {sched_path}")

    hist_path = "results/grasp_history.csv"
    with open(hist_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["iter", "seed", "alpha", "total_prv", "total_cost", "is_feasible", "is_new_best"])
        for h in result.history:
            writer.writerow([h.iter_number, h.seed, h.alpha, h.total_prv, h.total_cost, h.is_feasible, h.is_new_best])
    print(f"  Historico salvo em: {hist_path}")

    comp_path = "results/comparison_summary.csv"
    with open(comp_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["source", "hard", "soft_estruturais", "total_prv", "lex_key"])
        writer.writerow(["real_2023", real_lex[0], real_lex[1], real_lex[2], str(real_lex)])
        writer.writerow(["construcao_unica", baseline_lex[0], baseline_lex[1], baseline_lex[2], str(baseline_lex)])
        writer.writerow(["grasp_melhor", grasp_lex[0], grasp_lex[1], grasp_lex[2], str(grasp_lex)])
    print(f"  Comparacao salva em: {comp_path}")

    audit_path = "results/audit_report.txt"
    print(f"  (Auditoria detalhada: python scripts/audit_violations.py -> {audit_path})")

    # ── Mensagem final ───────────────────────────────────────────
    print(f"\n{'=' * 70}")
    print("  Proxima fase: implementar busca local com as 4 vizinhancas")
    print("  (swap_days, swap_homes, swap_teams, replace_teams) e plugar")
    print("  no loop multi-start (Algoritmo 2 do TCC).")
    print("=" * 70)


if __name__ == "__main__":
    main()

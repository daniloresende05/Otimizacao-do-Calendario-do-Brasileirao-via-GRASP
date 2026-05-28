"""
Auditoria das violacoes de (d), (f), (g) no GRASP.

Para cada uma das 50 iteracoes do GRASP com seed=42:
  - Roda construcao + avaliacao
  - Calcula violacoes detalhadas de (d), (f), (g)
  - Para a iter campea (melhor lex), imprime detalhes

Uso:
    python scripts/audit_violations.py
"""
from __future__ import annotations

import csv
import os
import random
import sys
from collections import defaultdict
from datetime import datetime

sys.path.insert(0, "src")

from brasileirao.construction import construct_schedule
from brasileirao.grasp import DEFAULT_ALPHA_POOL
from brasileirao.io import load_dates, load_teams
from brasileirao.objective import evaluate

SEED = 42
MAX_ITER = 50
ALPHA_POOL = DEFAULT_ALPHA_POOL
RESULTS_DIR = "results"


def _sides_in_round(schedule: list, r: int) -> dict[str, str]:
    sides: dict[str, str] = {}
    for m in schedule:
        if m.round == r:
            sides[m.home] = "H"
            sides[m.away] = "A"
    return sides


def _detail_d(schedule: list) -> list[str]:
    s1 = _sides_in_round(schedule, 1)
    s2 = _sides_in_round(schedule, 2)
    s18 = _sides_in_round(schedule, 18)
    s19 = _sides_in_round(schedule, 19)
    lines: list[str] = []
    for team in sorted(s1.keys()):
        r1, r2 = s1.get(team, "?"), s2.get(team, "?")
        r18, r19 = s18.get(team, "?"), s19.get(team, "?")
        inv1 = "A" if r1 == "H" else "H"
        inv2 = "A" if r2 == "H" else "H"
        ok18 = "ok" if r18 == inv1 else "VIOLA"
        ok19 = "ok" if r19 == inv2 else "VIOLA"
        if ok18 == "VIOLA" or ok19 == "VIOLA":
            lines.append(
                f"    {team:20s} R1={r1} R2={r2} R18={r18}({ok18}) R19={r19}({ok19})"
            )
    return lines


def _detail_f(schedule: list) -> list[str]:
    home_count: dict[str, int] = defaultdict(int)
    away_count: dict[str, int] = defaultdict(int)
    for m in schedule:
        if 1 <= m.round <= 19:
            home_count[m.home] += 1
            away_count[m.away] += 1
    lines: list[str] = []
    for team in sorted(set(home_count) | set(away_count)):
        h, a = home_count[team], away_count[team]
        if abs(h - a) > 1:
            lines.append(f"    {team:20s} casa={h} fora={a} (diff={abs(h - a)})")
    return lines


def _detail_g(schedule: list, max_cons: int = 2) -> list[str]:
    by_team: dict[str, list[tuple[int, str]]] = defaultdict(list)
    for m in schedule:
        by_team[m.home].append((m.round, "H"))
        by_team[m.away].append((m.round, "A"))
    lines: list[str] = []
    for team in sorted(by_team):
        entries = sorted(by_team[team])
        seq = [s for _, s in entries]
        runs: list[str] = []
        run_start = 0
        for i in range(1, len(seq)):
            if seq[i] != seq[i - 1]:
                run_len = i - run_start
                if run_len > max_cons:
                    runs.append(
                        f"run de {run_len} '{seq[run_start]}' em "
                        f"R{entries[run_start][0]}-R{entries[i - 1][0]}"
                    )
                run_start = i
        run_len = len(seq) - run_start
        if run_len > max_cons:
            runs.append(
                f"run de {run_len} '{seq[run_start]}' em "
                f"R{entries[run_start][0]}-R{entries[-1][0]}"
            )
        if runs:
            seq_str = " ".join(seq)
            lines.append(f"    {team:20s} {seq_str}")
            for r in runs:
                lines.append(f"    {'':20s}   -> {r}")
    return lines


def main() -> None:
    teams = load_teams("data/raw/teams.csv")
    raw_dates = load_dates("data/raw/datas_20-08-2023_a_09-06-2024.csv")
    dates = [datetime.strptime(d, "%d/%m/%Y").date() for d in raw_dates]

    rng_alpha = random.Random(SEED)
    os.makedirs(RESULTS_DIR, exist_ok=True)

    rows: list[dict[str, object]] = []
    best_idx = -1
    best_lex: tuple[int, int, int] | None = None
    best_schedule = None
    best_eval_obj = None

    for i in range(MAX_ITER):
        seed_iter = SEED + i
        alpha = rng_alpha.choice(ALPHA_POOL)
        schedule = construct_schedule(teams, dates, alpha=alpha, seed=seed_iter)
        ev = evaluate(schedule)
        lex = ev.lexicographic_key()

        viol_d = ev.violations_by_type.get("d", 0)
        viol_f = ev.violations_by_type.get("f", 0)
        viol_g = ev.violations_by_type.get("g", 0)

        rows.append({
            "iter": i + 1,
            "seed": seed_iter,
            "alpha": alpha,
            "total_prv": ev.total_prv,
            "viol_d": viol_d,
            "viol_f": viol_f,
            "viol_g": viol_g,
            "lex_key": lex,
        })

        if best_lex is None or lex < best_lex:
            best_lex = lex
            best_idx = i
            best_schedule = schedule
            best_eval_obj = ev

    csv_path = os.path.join(RESULTS_DIR, "audit_violations.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["iter", "seed", "alpha", "total_prv", "viol_d", "viol_f", "viol_g"])
        for r in rows:
            writer.writerow([r["iter"], r["seed"], r["alpha"], r["total_prv"], r["viol_d"], r["viol_f"], r["viol_g"]])

    report_lines: list[str] = []
    report_lines.append("=" * 70)
    report_lines.append("AUDITORIA DE VIOLACOES — GRASP 50 iteracoes, seed=42")
    report_lines.append("=" * 70)
    report_lines.append("")
    report_lines.append(f"{'Iter':>4} | {'Seed':>5} | {'a':>4} | {'PRV':>3} | {'(d)':>4} | {'(f)':>4} | {'(g)':>4} | Lex Key")
    report_lines.append(f"{'-' * 4}-+-{'-' * 5}-+-{'-' * 4}-+-{'-' * 3}-+-{'-' * 4}-+-{'-' * 4}-+-{'-' * 4}-+-{'-' * 15}")
    for r in rows:
        marker = " <-- BEST" if r["iter"] == best_idx + 1 else ""
        report_lines.append(
            f"{r['iter']:4d} | {r['seed']:5d} | {r['alpha']:.2f} | {r['total_prv']:3d} | "
            f"{r['viol_d']:4d} | {r['viol_f']:4d} | {r['viol_g']:4d} | {r['lex_key']}{marker}"
        )

    report_lines.append("")
    report_lines.append("=" * 70)
    report_lines.append(f"DETALHAMENTO DA ITER CAMPEA: iter {best_idx + 1} (seed={SEED + best_idx})")
    report_lines.append(f"  Lex key: {best_lex}")
    assert best_eval_obj is not None
    report_lines.append(f"  PRV: {best_eval_obj.total_prv}")
    report_lines.append(f"  (d)={best_eval_obj.violations_by_type.get('d', 0)}  "
                        f"(f)={best_eval_obj.violations_by_type.get('f', 0)}  "
                        f"(g)={best_eval_obj.violations_by_type.get('g', 0)}")
    report_lines.append("=" * 70)

    assert best_schedule is not None

    report_lines.append("")
    report_lines.append("--- Violacoes de (d) — espelho R18/R19 ---")
    d_lines = _detail_d(best_schedule)
    if d_lines:
        report_lines.extend(d_lines)
    else:
        report_lines.append("    Nenhuma violacao de (d).")

    report_lines.append("")
    report_lines.append("--- Violacoes de (f) — balanco casa/fora no turno ---")
    f_lines = _detail_f(best_schedule)
    if f_lines:
        report_lines.extend(f_lines)
    else:
        report_lines.append("    Nenhuma violacao de (f).")

    report_lines.append("")
    report_lines.append("--- Violacoes de (g) — sequencias consecutivas ---")
    g_lines = _detail_g(best_schedule)
    if g_lines:
        report_lines.extend(g_lines)
    else:
        report_lines.append("    Nenhuma violacao de (g).")

    report_lines.append("")
    report_lines.append("=" * 70)
    report_lines.append("CONCLUSAO")
    report_lines.append("=" * 70)
    report_lines.append("")

    d_counts = [r["viol_d"] for r in rows]
    f_counts = [r["viol_f"] for r in rows]
    g_counts = [r["viol_g"] for r in rows]

    report_lines.append(f"(d) violacoes nas 50 iters: min={min(d_counts)} max={max(d_counts)} media={sum(d_counts) / len(d_counts):.1f}")
    report_lines.append(f"(f) violacoes nas 50 iters: min={min(f_counts)} max={max(f_counts)} media={sum(f_counts) / len(f_counts):.1f}")
    report_lines.append(f"(g) violacoes nas 50 iters: min={min(g_counts)} max={max(g_counts)} media={sum(g_counts) / len(g_counts):.1f}")
    report_lines.append("")
    report_lines.append("(d) eh best-effort na construcao: a orientacao de R18/R19 minimiza")
    report_lines.append("    d_residual + g_violations, mas nao garante zero. Violacoes")
    report_lines.append("    residuais sao esperadas (nao e bug). Correcao via local search.")
    report_lines.append("(f) e (g) tambem sao best-effort: a RCL penaliza mas nao bloqueia.")
    report_lines.append("    Poucas violacoes sao inerentes ao espaco de busca.")

    report_path = os.path.join(RESULTS_DIR, "audit_report.txt")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines) + "\n")

    print(f"Relatorio salvo em: {report_path}")
    print(f"CSV salvo em: {csv_path}")
    print()
    for line in report_lines[-12:]:
        print(line)


if __name__ == "__main__":
    main()

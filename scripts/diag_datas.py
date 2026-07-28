"""Diagnóstico de uso das datas do calendário.

Reproduz a pipeline da CLI (seed=42, grasp_max_iter=10, ils_max_iter=30) e
analisa quais datas do arquivo são realmente usadas pela solução final:

  1. inventário do arquivo de datas;
  2. datas usadas pela solução final;
  3. ocupação (usadas vs. vazias);
  4. distribuição por rodada + sanidade do span (regra i, <= 2 dias);
  5. jogos por dia;
  6. mapa de ocupação cronológico + maiores buracos (datas vazias seguidas).

Distinção importante (esquema de janelas de assign_dates_to_matches):
  (a) datas que o ARQUIVO tem;
  (b) datas que o MODELO torna disponíveis — a rodada r só enxerga a janela
      dates[(r-1)*round_gap : (r-1)*round_gap + round_span], round_gap=7 e
      round_span=3 nos defaults da CLI;
  (c) datas efetivamente USADAS pela solução.

SOMENTE LEITURA: nada em src/, tests/ ou data/raw/ é modificado.
"""
from __future__ import annotations

import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):  # console Windows cp1252
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from brasileirao.dates import parse_day  # noqa: E402
from brasileirao.grasp import grasp  # noqa: E402
from brasileirao.ils import iterated_local_search  # noqa: E402
from brasileirao.io import load_dates, load_teams  # noqa: E402
from brasileirao.objective import evaluate  # noqa: E402

ROOT = Path(__file__).parents[1]
SEED = 42
GRASP_MAX_ITER = 10
ILS_MAX_ITER = 30
ROUND_GAP = 7    # defaults da CLI
ROUND_SPAN = 3


def _fmt(d: date) -> str:
    return d.strftime("%d/%m/%Y")


def main() -> None:
    # ------------------------------------------------------------------
    # 1. Inventário do arquivo
    # ------------------------------------------------------------------
    teams_map = load_teams(str(ROOT / "data" / "raw" / "teams.csv"))
    dates_raw = load_dates(
        str(ROOT / "data" / "raw" / "datas_20-08-2023_a_09-06-2024.csv"),
        col="Data",
    )
    dates = sorted(parse_day(s.strip()).date() for s in dates_raw)

    print("=" * 78)
    print("[1] INVENTÁRIO DO ARQUIVO DE DATAS")
    print("=" * 78)
    print(f"  Total de datas no arquivo: {len(dates)}")
    print(f"  Primeira: {_fmt(dates[0])} | Última: {_fmt(dates[-1])}")
    print(f"  Intervalo primeira→última: {(dates[-1] - dates[0]).days} dias")

    # (b) datas que o modelo disponibiliza (janelas por rodada)
    windows: dict[int, list[date]] = {}
    for r in range(1, 39):
        base = (r - 1) * ROUND_GAP
        windows[r] = dates[base: base + ROUND_SPAN]
    model_available = sorted({d for w in windows.values() for d in w})
    print(f"\n  Datas DISPONIBILIZADAS pelo modelo "
          f"(round_gap={ROUND_GAP}, round_span={ROUND_SPAN}): "
          f"{len(model_available)} de {len(dates)}")
    short = [r for r, w in windows.items() if len(w) < ROUND_SPAN]
    if short:
        print(f"  ATENÇÃO: rodadas com janela menor que {ROUND_SPAN}: {short}")
    idx_max = (38 - 1) * ROUND_GAP + ROUND_SPAN
    print(f"  (janelas cobrem os índices 0..{idx_max - 1}; datas de índice "
          f">= {idx_max} nunca são candidatas: "
          f"{max(0, len(dates) - idx_max)} data(s))")

    # ------------------------------------------------------------------
    # 2. Pipeline real
    # ------------------------------------------------------------------
    print("\n" + "=" * 78)
    print(f"[2] PIPELINE (seed={SEED}, grasp_max_iter={GRASP_MAX_ITER}, "
          f"ils_max_iter={ILS_MAX_ITER})")
    print("=" * 78)
    g_res = grasp(teams_map, dates, max_iter=GRASP_MAX_ITER, seed=SEED)
    final = iterated_local_search(
        g_res.best_schedule, teams_map, max_iter=ILS_MAX_ITER, seed=SEED,
    )
    ev = evaluate(final)
    print(f"  Solução final: feasible={ev.is_feasible} "
          f"| lex_key={ev.lexicographic_key()} | PRV={ev.total_prv}")

    used_by_date: Counter[date] = Counter()
    dates_by_round: dict[int, set[date]] = defaultdict(set)
    for m in final:
        d = parse_day(m.day).date()
        used_by_date[d] += 1
        dates_by_round[m.round].add(d)
    used = sorted(used_by_date)

    # ------------------------------------------------------------------
    # 3. Ocupação
    # ------------------------------------------------------------------
    empty = [d for d in dates if d not in used_by_date]
    print("\n" + "=" * 78)
    print("[3] OCUPAÇÃO")
    print("=" * 78)
    print(f"  Datas usadas: {len(used)}")
    print(f"  Datas vazias (arquivo): {len(empty)}")
    print(f"  Ocupação sobre o ARQUIVO: {len(used)}/{len(dates)} "
          f"= {100 * len(used) / len(dates):.1f}%")
    print(f"  Ocupação sobre o que o MODELO disponibiliza: "
          f"{len(used)}/{len(model_available)} "
          f"= {100 * len(used) / len(model_available):.1f}%")
    print(f"  Total de jogos: {sum(used_by_date.values())} (esperado 380)")

    # ------------------------------------------------------------------
    # 4. Distribuição por rodada + sanidade do span
    # ------------------------------------------------------------------
    print("\n" + "=" * 78)
    print("[4] DATAS POR RODADA (span = última − primeira, em dias)")
    print("=" * 78)
    bad_span = []
    for r in range(1, 39):
        ds = sorted(dates_by_round[r])
        span = (ds[-1] - ds[0]).days
        flag = ""
        if span > 2:
            flag = "  <-- SPAN > 2 (violaria (i)!)"
            bad_span.append(r)
        datas_txt = ", ".join(
            f"{_fmt(d)}({used_by_date[d]}j)" for d in ds
        )
        print(f"  R{r:>2} | span {span}d | {datas_txt}{flag}")
    print(f"\n  Sanidade (i): rodadas com span > 2: "
          f"{bad_span if bad_span else 'nenhuma ✔'}")

    # ------------------------------------------------------------------
    # 5. Jogos por dia
    # ------------------------------------------------------------------
    print("\n" + "=" * 78)
    print("[5] JOGOS POR DIA")
    print("=" * 78)
    dist = Counter(used_by_date.values())
    for n_jogos in sorted(dist):
        print(f"  {dist[n_jogos]:>3} data(s) com {n_jogos} jogo(s)")
    media = sum(used_by_date.values()) / len(used)
    print(f"  Média: {media:.2f} jogos por data usada")
    top = used_by_date.most_common(5)
    print("  Dias mais carregados: "
          + "; ".join(f"{_fmt(d)} ({n}j)" for d, n in top))

    # ------------------------------------------------------------------
    # 6. Mapa de ocupação + buracos
    # ------------------------------------------------------------------
    print("\n" + "=" * 78)
    print("[6] MAPA DE OCUPAÇÃO (cronológico; '·' = data do arquivo vazia)")
    print("=" * 78)
    round_of_date: dict[date, list[int]] = defaultdict(list)
    for r, ds in dates_by_round.items():
        for d in ds:
            round_of_date[d].append(r)

    holes: list[tuple[int, date, date]] = []  # (tamanho, início, fim)
    run: list[date] = []
    for d in dates:
        if d in used_by_date:
            if run:
                holes.append((len(run), run[0], run[-1]))
                run = []
            rounds_txt = ",".join(f"R{r}" for r in sorted(round_of_date[d]))
            bars = "#" * used_by_date[d]
            print(f"  {_fmt(d)} {bars:<10} {used_by_date[d]:>2} jogo(s)  "
                  f"[{rounds_txt}]")
        else:
            run.append(d)
            print(f"  {_fmt(d)} ·")
    if run:
        holes.append((len(run), run[0], run[-1]))

    print("\n  MAIORES BURACOS (datas do arquivo vazias consecutivas):")
    holes.sort(key=lambda h: (-h[0], h[1]))
    for size, ini, fim in holes[:8]:
        cal = (fim - ini).days + 1
        print(f"    {size} data(s) vazia(s) de {_fmt(ini)} a {_fmt(fim)} "
              f"({cal} dia(s) de calendário)")

    # ------------------------------------------------------------------
    # Resumo em 3 números
    # ------------------------------------------------------------------
    print("\n" + "=" * 78)
    print("RESUMO: "
          f"arquivo {len(dates)} datas | "
          f"modelo disponibiliza {len(model_available)} | "
          f"usadas {len(used)}")
    print("=" * 78)
    print("\nFIM (somente leitura; nada foi modificado).")


if __name__ == "__main__":
    main()

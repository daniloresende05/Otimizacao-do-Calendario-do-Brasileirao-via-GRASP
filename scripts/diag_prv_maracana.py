"""Diagnóstico: quanto do PRV final é removível movendo jogos para DATAS VAZIAS?

Reproduz a pipeline da CLI (seed=42, modo modesto: grasp_max_iter=10,
ils_max_iter=30) e, para CADA ocorrência de PRV da solução final, testa se
existe uma data vazia (disponível no CSV mas sem nenhum jogo) tal que mover UM
dos dois jogos da ocorrência para ela elimina o PRV respeitando as regras já
hard/estruturais do modelo:

  - (i) span da rodada <= 2 dias  (checado com check_i_span_rodada real);
  - (j) sem encavalamento entre rodadas (check_j_sem_encavalamento real);
  - descanso mínimo de 3 dias para os dois times do jogo movido;
  - nenhum dos dois times pode já jogar na data-destino.

ANÁLISE DE TETO (otimista): cada movimento é avaliado ISOLADAMENTE sobre a
solução final; um PRV conta como removível se algum movimento viável reduz o
total de PRVs (compute_prv) — ou seja, elimina a ocorrência sem criar outra.

SOMENTE LEITURA: nada em src/, tests/ ou data/raw/ é modificado.
"""
from __future__ import annotations

import sys
from collections import Counter
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from brasileirao.constraints import (  # noqa: E402
    check_i_span_rodada,
    check_j_sem_encavalamento,
)
from brasileirao.dates import parse_day  # noqa: E402
from brasileirao.grasp import grasp  # noqa: E402
from brasileirao.ils import iterated_local_search  # noqa: E402
from brasileirao.io import load_dates, load_teams  # noqa: E402
from brasileirao.objective import compute_prv, evaluate  # noqa: E402

ROOT = Path(__file__).parents[1]
SEED = 42
PRV_DAYS = 5
MIN_REST = 3
FMT = "%d/%m/%Y"


def min_rest_ok(schedule, teams: tuple[str, str]) -> bool:
    """Descanso >= MIN_REST e sem jogo duplo no mesmo dia, para os 2 times."""
    for team in teams:
        days = sorted(
            parse_day(m.day) for m in schedule if team in (m.home, m.away)
        )
        for a, b in zip(days, days[1:]):
            if (b - a).days < MIN_REST:  # cobre também b == a (jogo duplo)
                return False
    return True


def main() -> None:
    teams_map = load_teams(str(ROOT / "data/raw/teams.csv"))
    dates_raw = load_dates(str(ROOT / "data/raw/datas_20-08-2023_a_09-06-2024.csv"))
    dates = sorted(parse_day(s.strip()).date() for s in dates_raw)

    print("== Reproduzindo a pipeline da CLI (seed=42, modo modesto) ==")
    g = grasp(teams_map, dates, max_iter=10, max_iter_no_improve=10, seed=SEED)
    final = iterated_local_search(
        g.best_schedule, teams_map, max_iter=30, max_iter_no_improve=10, seed=SEED
    )
    ev = evaluate(final, prv_days=PRV_DAYS)
    baseline_prv = ev.total_prv
    print(f"PRV pós-GRASP: {g.best_evaluation.total_prv} | "
          f"PRV final (pós-ILS): {baseline_prv} | lex_key={ev.lexicographic_key()}")

    occurrences = ev.prv_result.occurrences
    assert len(occurrences) == baseline_prv

    used_days = {m.day for m in final}
    empty_days = [d.strftime(FMT) for d in dates if d.strftime(FMT) not in used_days]
    print(f"Datas disponíveis: {len(dates)} | usadas por jogos: {len(used_days)} "
          f"| VAZIAS: {len(empty_days)}")

    removable = 0
    print(f"\n== Análise das {len(occurrences)} ocorrências de PRV ==")
    for i, occ in enumerate(occurrences, 1):
        ma, mb = occ.match_a, occ.match_b
        print(f"\nPRV #{i} — {occ.stadium} (intervalo de {occ.days_between} dias)")
        print(f"  jogo A: R{ma.round:2d} {ma.day}  {ma.home} x {ma.away}")
        print(f"  jogo B: R{mb.round:2d} {mb.day}  {mb.home} x {mb.away}")

        found: tuple[str, str, int] | None = None  # (desc do jogo, data, novo PRV)
        reasons: Counter[str] = Counter()

        for moved in (ma, mb):
            if found:
                break
            idx = final.index(moved)
            for d in empty_days:
                candidate = list(final)
                candidate[idx] = replace(moved, day=d)

                if not min_rest_ok(candidate, (moved.home, moved.away)):
                    reasons["descanso"] += 1
                    continue
                if check_i_span_rodada(candidate):
                    reasons["span"] += 1
                    continue
                if check_j_sem_encavalamento(candidate):
                    reasons["encavalamento"] += 1
                    continue
                new_prv = compute_prv(candidate, prv_days=PRV_DAYS).total_prv
                if new_prv >= baseline_prv:
                    reasons["viável mas sem ganho de PRV"] += 1
                    continue
                found = (f"R{moved.round} {moved.home} x {moved.away}", d, new_prv)
                break

        if found:
            desc, d, new_prv = found
            removable += 1
            print(f"  -> REMOVÍVEL por data vazia em {d} "
                  f"(movendo {desc}; PRV total {baseline_prv} -> {new_prv})")
        else:
            detail = ", ".join(f"{k}: {v}" for k, v in reasons.most_common())
            print(f"  -> NÃO removível (motivo — tentativas rejeitadas por: {detail})")

    structural = len(occurrences) - removable
    print("\n== RESUMO ==")
    print(f"PRVs na solução final:        {baseline_prv}")
    print(f"Removíveis por data vazia:    {removable}")
    print(f"Estruturais (sem data viável): {structural}")
    print(f"PRV mínimo teórico (teto otimista, movimentos isolados): "
          f"{baseline_prv - removable}")


if __name__ == "__main__":
    main()

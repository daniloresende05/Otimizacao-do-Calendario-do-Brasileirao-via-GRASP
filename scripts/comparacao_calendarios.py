"""Comparação entre o calendário real do Brasileirão 2023 e os calendários
gerados pelo método, em duas janelas de datas distintas.

Cenários:

1. **Real 2023** — a tabela que a CBF efetivamente usou (15/04 a 07/12/2023).
2. **Gerado, janela europeia** — 11/08/2023 a 26/05/2024, o intervalo da
   Premier League 2023/24, com as datas FIFA removidas.
3. **Gerado, janela do Brasileirão** — 15/04 a 07/12/2023, a MESMA janela do
   calendário real, para comparação direta.

Sobre a cadência (`round_gap`): ela é um PARÂMETRO, não uma restrição. As
restrições (i) span da rodada e (j) sem encavalamento continuam valendo para
qualquer cadência maior que o span. Janelas curtas apenas exigem rodadas mais
próximas. Cada cenário usa `fit_round_gap`, que escolhe a maior cadência
<= 7 dias em que as 38 rodadas cabem — e o relatório imprime qual foi.

Uso:

    .venv/Scripts/python.exe scripts/comparacao_calendarios.py
    .venv/Scripts/python.exe scripts/comparacao_calendarios.py --seed 43
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
from dataclasses import dataclass

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
)

from brasileirao.construction import fit_round_gap  # noqa: E402
from brasileirao.dates import parse_day  # noqa: E402
from brasileirao.domain import Schedule, TeamMap  # noqa: E402
from brasileirao.grasp import grasp  # noqa: E402
from brasileirao.ils import iterated_local_search  # noqa: E402
from brasileirao.io import load_dates, load_teams, remove_blocked_dates  # noqa: E402
from brasileirao.objective import evaluate  # noqa: E402
from brasileirao.real_baseline import load_real_schedule_2023  # noqa: E402

CONSTRAINT_IDS = ["a", "b", "c", "d", "e", "f", "g", "i", "j"]

CONSTRAINT_LABELS = {
    "a": "cada time joga 1x por rodada",
    "b": "duplo turno, mandos invertidos",
    "c": "R1/R2 alternam casa e fora",
    "d": "R18 espelha R1; R19 espelha R2",
    "e": "R38 sem clássico estadual",
    "f": "turno: |casa - fora| <= 1",
    "g": "máx. 2 jogos seguidos em casa/fora",
    "i": "rodada ocupa no máximo 3 dias",
    "j": "rodadas não se encavalam",
}


@dataclass
class Cenario:
    nome: str
    janela: str
    gap: str
    violacoes: dict[str, int]
    prv: int
    prv_por_estadio: dict[str, int]
    primeira_data: str
    ultima_data: str
    datas_r38: int

    @property
    def total_estruturais(self) -> int:
        return sum(self.violacoes.values())


def _carrega_datas(path: str, col: str = "Data") -> list:
    return sorted(parse_day(s.strip()).date() for s in load_dates(path, col=col))


def _resume(
    nome: str, janela: str, gap: str, schedule: Schedule, prv_days: int
) -> Cenario:
    ev = evaluate(schedule, prv_days=prv_days)
    dias = sorted({m.day for m in schedule}, key=parse_day)
    return Cenario(
        nome=nome,
        janela=janela,
        gap=gap,
        violacoes={c: ev.violations_by_type.get(c, 0) for c in CONSTRAINT_IDS},
        prv=ev.total_prv,
        prv_por_estadio=dict(ev.prv_result.prv_by_stadium),
        primeira_data=dias[0],
        ultima_data=dias[-1],
        datas_r38=len({m.day for m in schedule if m.round == 38}),
    )


def _gera(
    teams_map: TeamMap, datas: list, nome: str, janela: str, args
) -> Cenario:
    gap = fit_round_gap(
        datas, preferred_gap=args.round_gap, round_span=args.round_span
    )
    aviso = "" if gap == args.round_gap else f"  (cai de {args.round_gap} para {gap})"
    print(f"  cadência entre rodadas: {gap} dias{aviso}")

    resultado = grasp(
        teams_map,
        datas,
        max_iter=args.grasp_max_iter,
        max_iter_no_improve=args.grasp_max_iter_no_improve,
        seed=args.seed,
        round_gap=gap,
        round_span=args.round_span,
        prv_days=args.prv_days,
        min_team_rest_days=args.min_team_rest_days,
        max_consecutive=args.max_consecutive,
        simultaneous_rounds=frozenset({38}),
    )
    print(
        f"  GRASP: PRV {resultado.best_evaluation.total_prv} "
        f"| lex {resultado.best_evaluation.lexicographic_key()}"
    )
    final = iterated_local_search(
        resultado.best_schedule,
        teams_map,
        prv_days=args.prv_days,
        min_team_rest_days=args.min_team_rest_days,
        max_iter=args.ils_max_iter,
        max_iter_no_improve=args.ils_max_iter_no_improve,
        seed=args.seed,
    )
    cen = _resume(nome, janela, f"{gap} dias", final, args.prv_days)
    print(f"  ILS:   PRV {cen.prv} | estruturais {cen.total_estruturais}")
    return cen


def _imprime(cenarios: list[Cenario]) -> None:
    rotulos = [f"({cid}) {CONSTRAINT_LABELS[cid]}" for cid in CONSTRAINT_IDS]
    rotulos += ["período ocupado", "TOTAL estruturais"]
    rotulos += [f"  {e}" for c in cenarios for e in c.prv_por_estadio]
    largura = max(len(r) for r in rotulos) + 3
    col = max(len(c.nome) for c in cenarios) + 4
    col = max(col, 26)

    print("\n" + "=" * (largura + col * len(cenarios)))
    print("COMPARAÇÃO DE CALENDÁRIOS")
    print("=" * (largura + col * len(cenarios)) + "\n")

    def linha(rotulo: str, valores: list[str]) -> None:
        print(rotulo.ljust(largura) + "".join(v.ljust(col) for v in valores))

    linha("", [c.nome for c in cenarios])
    linha("janela", [c.janela for c in cenarios])
    linha("período ocupado", [f"{c.primeira_data} a {c.ultima_data}" for c in cenarios])
    linha("cadência", [c.gap for c in cenarios])
    linha("R38 numa data só",
          [("sim" if c.datas_r38 == 1 else f"não ({c.datas_r38} datas)")
           for c in cenarios])
    print()

    for cid in CONSTRAINT_IDS:
        linha(
            f"({cid}) {CONSTRAINT_LABELS[cid]}",
            [str(c.violacoes[cid]) for c in cenarios],
        )
    print()
    linha("TOTAL estruturais", [str(c.total_estruturais) for c in cenarios])
    linha("PRV", [str(c.prv) for c in cenarios])
    print()

    estadios = sorted({e for c in cenarios for e in c.prv_por_estadio})
    if estadios:
        print("PRV por estádio:")
        for e in estadios:
            linha(f"  {e}", [str(c.prv_por_estadio.get(e, 0)) for c in cenarios])
    print()


def _salva_csv(cenarios: list[Cenario], path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["metrica"] + [c.nome for c in cenarios])
        w.writerow(["janela"] + [c.janela for c in cenarios])
        w.writerow(["cadencia"] + [c.gap for c in cenarios])
        w.writerow(["datas distintas na R38"] + [c.datas_r38 for c in cenarios])
        w.writerow(
            ["periodo"] + [f"{c.primeira_data} a {c.ultima_data}" for c in cenarios]
        )
        for cid in CONSTRAINT_IDS:
            w.writerow(
                [f"({cid}) {CONSTRAINT_LABELS[cid]}"]
                + [c.violacoes[cid] for c in cenarios]
            )
        w.writerow(["TOTAL estruturais"] + [c.total_estruturais for c in cenarios])
        w.writerow(["PRV"] + [c.prv for c in cenarios])
        for e in sorted({e for c in cenarios for e in c.prv_por_estadio}):
            w.writerow([f"PRV {e}"] + [c.prv_por_estadio.get(e, 0) for c in cenarios])
    print(f"CSV gerado: {path}")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--teams", default="data/raw/teams.csv")
    p.add_argument("--real", default="data/raw/tabela_real_brasileirao_2023.csv")
    p.add_argument("--datas-europa", default="data/raw/datas_11-08-2023_a_26-05-2024.csv")
    p.add_argument("--datas-brasil", default="data/raw/datas_15-04-2023_a_07-12-2023.csv")
    p.add_argument("--fifa", default="data/raw/datas_fifas_20-08-2023_a_09-06-2024.csv")
    p.add_argument("--out", default="results/comparacao_calendarios.csv")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--grasp-max-iter", type=int, default=50)
    p.add_argument("--grasp-max-iter-no-improve", type=int, default=20)
    p.add_argument("--ils-max-iter", type=int, default=200)
    p.add_argument("--ils-max-iter-no-improve", type=int, default=20)
    p.add_argument("--round-gap", type=int, default=7)
    p.add_argument("--round-span", type=int, default=3)
    p.add_argument("--prv-days", type=int, default=5)
    p.add_argument("--min-team-rest-days", type=int, default=3)
    p.add_argument("--max-consecutive", type=int, default=2)
    args = p.parse_args()

    teams_map = load_teams(args.teams)
    fifa = _carrega_datas(args.fifa, col="DATA")

    print("[1/3] Calendário real do Brasileirão 2023")
    real = _resume(
        "Real 2023",
        "15/04 a 07/12/2023",
        "irregular",
        load_real_schedule_2023(args.real, teams_map),
        args.prv_days,
    )
    print(f"  PRV {real.prv} | estruturais {real.total_estruturais}")

    print("\n[2/3] Gerado — janela europeia (11/08/2023 a 26/05/2024)")
    datas_eu = remove_blocked_dates(_carrega_datas(args.datas_europa), fifa)
    print(f"  datas disponíveis após remover FIFA: {len(datas_eu)}")
    europa = _gera(
        teams_map, datas_eu, "Gerado — Europa", "11/08/23 a 26/05/24", args
    )

    # A janela do Brasileirão começa em abril de 2023 e o CSV de datas FIFA
    # cobre apenas a partir de 04/09/2023 — por isso não há remoção aqui.
    print("\n[3/3] Gerado — janela do Brasileirão (15/04 a 07/12/2023)")
    datas_br = _carrega_datas(args.datas_brasil)
    print(f"  datas disponíveis: {len(datas_br)} (sem remoção FIFA)")
    brasil = _gera(
        teams_map, datas_br, "Gerado — Brasil", "15/04 a 07/12/23", args
    )

    cenarios = [real, europa, brasil]
    _imprime(cenarios)
    _salva_csv(cenarios, args.out)


if __name__ == "__main__":
    main()

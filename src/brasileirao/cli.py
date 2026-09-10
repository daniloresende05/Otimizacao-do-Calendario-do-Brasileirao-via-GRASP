# src/brasileirao/cli.py
"""CLI da pipeline de produção do TCC.

Fluxo: load (io) -> grasp (multi-start de construção) -> iterated_local_search
(que já abre com um VND interno) -> evaluate -> CSV final.
"""
import argparse
import os

from .dates import parse_day
from .grasp import DEFAULT_ALPHA_POOL, grasp
from .ils import iterated_local_search
from .io import load_dates, load_teams, remove_blocked_dates, save_schedule_csv
from .objective import (
    evaluate,
    hard_constraint_ids,
    hard_violation_summary,
    set_all_hard,
)


def _warn_if_infeasible(evaluation, stage: str) -> None:
    """Aviso claro quando as restrições hard atuais não podem ser satisfeitas."""
    if evaluation.is_feasible:
        return
    print(f"\nAVISO [{stage}]: Nenhuma solução viável encontrada com as "
          f"restrições hard atuais.")
    print(f"  Restrições hard com violação > 0: "
          f"{hard_violation_summary(evaluation.violations_by_type)}")
    print("  Retornando a melhor solução encontrada (menor número de "
          "violações hard).")


def main():
    parser = argparse.ArgumentParser(
        description="Otimização do calendário do Brasileirão via GRASP+ILS",
    )
    parser.add_argument("--teams", default="data/raw/teams.csv",
                        help="teams.csv (name,stadium,state)")
    parser.add_argument("--dates", default="data/raw/datas_20-08-2023_a_09-06-2024.csv",
                        help="CSV de datas disponíveis (coluna Data em dd/mm/aaaa)")
    parser.add_argument("--date-col", default="Data",
                        help="Nome da coluna de data no CSV")
    parser.add_argument("--fifa-dates",
                        default="data/raw/datas_fifas_20-08-2023_a_09-06-2024.csv",
                        help="CSV de datas FIFA (janelas de seleção). Essas "
                             "datas são REMOVIDAS da lista de datas "
                             "disponíveis antes do GRASP.")
    parser.add_argument("--fifa-date-col", default="DATA",
                        help="Nome da coluna de data no CSV de datas FIFA")
    parser.add_argument("--no-fifa", action="store_true",
                        help="Não remove as datas FIFA (usa todas as datas "
                             "do CSV de datas disponíveis)")
    parser.add_argument("--out", default="results/schedule.csv",
                        help="CSV final (Rodada,Data,Mandante,Visitante,Estádio,PRV)")
    parser.add_argument("--seed", type=int, default=42,
                        help="Seed única, propagada para GRASP e ILS")

    grasp_group = parser.add_argument_group("GRASP")
    grasp_group.add_argument("--grasp-max-iter", type=int, default=50)
    grasp_group.add_argument("--grasp-max-iter-no-improve", type=int, default=20)
    grasp_group.add_argument("--alpha-pool", type=float, nargs="+",
                             default=DEFAULT_ALPHA_POOL,
                             help="Pool de alphas sorteados por iteração do GRASP")

    ils_group = parser.add_argument_group("ILS")
    ils_group.add_argument("--ils-max-iter", type=int, default=200)
    ils_group.add_argument("--ils-max-iter-no-improve", type=int, default=20)
    ils_group.add_argument("--perturbation-min", type=int, default=1)
    ils_group.add_argument("--perturbation-step", type=int, default=1)
    ils_group.add_argument("--perturbation-max", type=int, default=5)

    model_group = parser.add_argument_group("Modelo")
    model_group.add_argument("--prv-days", type=int, default=5,
                             help="Intervalo mínimo (dias) sem PRV no mesmo estádio")
    model_group.add_argument("--round-gap", type=int, default=7,
                             help="Dias entre o início de rodadas")
    model_group.add_argument("--round-span", type=int, default=3,
                             help="Quantos dias diferentes uma rodada pode usar")
    model_group.add_argument("--min-team-rest-days", type=int, default=3,
                             help="Descanso mínimo (dias) entre jogos de um time")
    model_group.add_argument("--max-consecutive", type=int, default=2,
                             help="Máximo de jogos consecutivos em casa/fora")
    model_group.add_argument("--simultaneous-rounds", type=int, nargs="*",
                             default=[38], metavar="RODADA",
                             help="Rodadas com todos os jogos na MESMA data "
                                  "(default: 38; passe sem valores para "
                                  "desligar)")
    model_group.add_argument("--all-hard", action="store_true",
                             help="Marca TODAS as restrições (a-j) como hard "
                                  "nesta execução (atalho experimental; o "
                                  "controle permanente é CONSTRAINT_HARDNESS "
                                  "em objective.py). Com (d) e (h) hard este "
                                  "dataset é inviável: a CLI avisa e devolve "
                                  "a melhor solução encontrada.")
    args = parser.parse_args()
    simultaneous_rounds = frozenset(args.simultaneous_rounds)

    if args.all_hard:
        set_all_hard()

    teams_map = load_teams(args.teams)
    dates_raw = load_dates(args.dates, col=args.date_col)
    dates = sorted(parse_day(s.strip()).date() for s in dates_raw)
    n_dates_total = len(dates)

    # Datas FIFA: removidas da lista ANTES do GRASP. Todo o restante da
    # pipeline (construção, busca local, avaliação) enxerga só a lista filtrada.
    fifa_removed = 0
    if not args.no_fifa:
        fifa_raw = load_dates(args.fifa_dates, col=args.fifa_date_col)
        fifa_dates = sorted(parse_day(s.strip()).date() for s in fifa_raw)
        dates = remove_blocked_dates(dates, fifa_dates)
        fifa_removed = n_dates_total - len(dates)
        if not dates:
            raise SystemExit("Nenhuma data disponível após remover as datas FIFA.")

    print(f"Times: {len(teams_map)} | Datas disponíveis: {len(dates)} "
          f"({dates[0]:%d/%m/%Y} a {dates[-1]:%d/%m/%Y}) | Seed: {args.seed}")
    if args.no_fifa:
        print("Datas FIFA: não removidas (--no-fifa)")
    else:
        print(f"Datas FIFA removidas: {fifa_removed} de {n_dates_total} "
              f"({args.fifa_dates})")
    sim_txt = (", ".join(f"R{r}" for r in sorted(simultaneous_rounds))
               if simultaneous_rounds else "nenhuma")
    print(f"Rodadas simultâneas (todos os jogos na mesma data): {sim_txt}")
    print(f"Restrições hard ativas: "
          f"{', '.join(sorted(hard_constraint_ids()))}"
          f"{' (--all-hard)' if args.all_hard else ''}")

    print(f"\n[1/2] GRASP: multi-start de construção "
          f"(max_iter={args.grasp_max_iter}, alpha_pool={args.alpha_pool})...")
    grasp_result = grasp(
        teams_map,
        dates,
        max_iter=args.grasp_max_iter,
        max_iter_no_improve=args.grasp_max_iter_no_improve,
        alpha_pool=args.alpha_pool,
        seed=args.seed,
        round_gap=args.round_gap,
        round_span=args.round_span,
        prv_days=args.prv_days,
        min_team_rest_days=args.min_team_rest_days,
        max_consecutive=args.max_consecutive,
        simultaneous_rounds=simultaneous_rounds,
    )
    grasp_eval = grasp_result.best_evaluation
    print(f"GRASP: {grasp_result.total_iterations} iterações "
          f"(parou por {grasp_result.stopped_by}); melhor na iteração "
          f"{grasp_result.best_iter} (seed={grasp_result.best_seed}, "
          f"alpha={grasp_result.best_alpha})")
    print(f"PRV após GRASP (antes do ILS): {grasp_eval.total_prv} "
          f"| lex_key={grasp_eval.lexicographic_key()}")
    _warn_if_infeasible(grasp_eval, "GRASP")

    print(f"\n[2/2] ILS: VND + perturbações sobre a melhor solução do GRASP "
          f"(max_iter={args.ils_max_iter}, "
          f"max_iter_no_improve={args.ils_max_iter_no_improve})...")
    final_schedule = iterated_local_search(
        grasp_result.best_schedule,
        teams_map,
        prv_days=args.prv_days,
        min_team_rest_days=args.min_team_rest_days,
        perturbation_min=args.perturbation_min,
        perturbation_step=args.perturbation_step,
        perturbation_max=args.perturbation_max,
        max_iter_no_improve=args.ils_max_iter_no_improve,
        max_iter=args.ils_max_iter,
        seed=args.seed,
    )
    final_eval = evaluate(final_schedule, prv_days=args.prv_days)
    print(f"PRV após ILS (final): {final_eval.total_prv} "
          f"| lex_key={final_eval.lexicographic_key()}")
    _warn_if_infeasible(final_eval, "final")

    delta = grasp_eval.total_prv - final_eval.total_prv
    print(f"Melhora do ILS sobre o GRASP: -{delta} PRV")

    print("\n" + final_eval.summary())

    for r in sorted(simultaneous_rounds):
        r_days = sorted(
            {m.day for m in final_schedule if m.round == r},
            key=parse_day,
        )
        print(f"Datas da R{r} (simultânea): {', '.join(r_days)}")

    prv_by_stadium = final_eval.prv_result.prv_by_stadium
    if prv_by_stadium:
        print("\nPRVs por estádio (apenas > 0):")
        for stadium, count in sorted(
            prv_by_stadium.items(), key=lambda kv: (-kv[1], kv[0])
        ):
            print(f"  {stadium}: {count}")

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    save_schedule_csv(final_schedule, args.out, prv_days=args.prv_days)
    print(f"\nOK! CSV gerado: {args.out}")


if __name__ == "__main__":
    main()

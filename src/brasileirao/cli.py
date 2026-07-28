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
from .io import load_dates, load_teams, save_schedule_csv
from .objective import evaluate


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
    args = parser.parse_args()

    teams_map = load_teams(args.teams)
    dates_raw = load_dates(args.dates, col=args.date_col)
    dates = sorted(parse_day(s.strip()).date() for s in dates_raw)

    print(f"Times: {len(teams_map)} | Datas disponíveis: {len(dates)} "
          f"({dates[0]:%d/%m/%Y} a {dates[-1]:%d/%m/%Y}) | Seed: {args.seed}")

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
    )
    grasp_eval = grasp_result.best_evaluation
    print(f"GRASP: {grasp_result.total_iterations} iterações "
          f"(parou por {grasp_result.stopped_by}); melhor na iteração "
          f"{grasp_result.best_iter} (seed={grasp_result.best_seed}, "
          f"alpha={grasp_result.best_alpha})")
    print(f"PRV após GRASP (antes do ILS): {grasp_eval.total_prv} "
          f"| lex_key={grasp_eval.lexicographic_key()}")

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

    delta = grasp_eval.total_prv - final_eval.total_prv
    print(f"Melhora do ILS sobre o GRASP: -{delta} PRV")

    print("\n" + final_eval.summary())

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

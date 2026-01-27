# src/brasileirao/cli.py
import argparse
import os
import pandas as pd

from .io import load_dates, load_teams
from .initial_solution import build_initial_schedule_with_constraints
from .objective import add_prv_column

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dates", required=True, help="CSV de datas (coluna Data em dd/mm/aaaa)")
    parser.add_argument("--date-col", default="Data", help="Nome da coluna de data no CSV")
    parser.add_argument("--teams", required=True, help="teams.csv (name,stadium,state)")
    parser.add_argument("--out", default="results/schedule.csv", help="CSV final (Rodada,Data,Mandante,Visitante,Estádio,PRV)")
    parser.add_argument("--prv-days", type=int, default=5, help="Intervalo PRV (dias) para cálculo")
    parser.add_argument("--round-gap", type=int, default=7, help="Dias entre o início de rodadas")
    parser.add_argument("--round-span", type=int, default=3, help="Quantos dias diferentes uma rodada pode usar")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-attempts", type=int, default=200000)
    args = parser.parse_args()

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)

    dates_raw = load_dates(args.dates, col=args.date_col)   # lista de strings dd/mm/aaaa
    teams_map = load_teams(args.teams)

    schedule = build_initial_schedule_with_constraints(
        dates_raw,
        teams_map,
        round_gap=args.round_gap,
        round_span=args.round_span,
        seed=args.seed,
        max_attempts=args.max_attempts,
    )

    df = pd.DataFrame([m.__dict__ for m in schedule])

    # calcula PRV (soft) e monta saída no formato que você quer
    df_prv = add_prv_column(df, prv_days=args.prv_days)
    df_out = df_prv.rename(columns={
        "round": "Rodada",
        "day": "Data",
        "home": "Mandante",
        "away": "Visitante",
        "stadium": "Estádio",
    })[["Rodada", "Data", "Mandante", "Visitante", "Estádio", "PRV"]].sort_values(["Rodada", "Data"])

    df_out.to_csv(args.out, index=False)

    # terminal: Estádio / PRV
    df_stadium = (
        df_out.groupby("Estádio", as_index=False)["PRV"]
        .sum()
        .sort_values("PRV", ascending=False)
    )

    print(f"\nOK! CSV gerado: {args.out}\n")
    print(df_stadium.to_string(index=False))

if __name__ == "__main__":
    main()
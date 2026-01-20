import argparse
import pandas as pd

from .io import load_dates, load_teams
from .round_robin import circle_method
from .domain import ScheduledMatch
from .constraints import check_all

def build_baseline_schedule(dates, teams_map):
    team_names = list(teams_map.keys())
    rounds_pairs = circle_method(team_names)  # 19 rodadas com 10 jogos (para 20 times)

    if len(rounds_pairs) != 19:
        raise ValueError(f"Esperava 19 rodadas no turno, veio {len(rounds_pairs)}. Times={len(team_names)}")

    # Seleciona 38 datas (turno + returno)
    if len(dates) < 38:
        raise ValueError(f"CSV de datas tem apenas {len(dates)} datas, mas precisam de 38.")

    selected_dates = dates[:38]

    schedule = []

    # Turno: rodadas 1..19
    for r_idx, pairs in enumerate(rounds_pairs, start=1):
        day = selected_dates[r_idx - 1]
        for a, b in pairs:
            home, away = a, b  # baseline (sem regras c..g ainda)
            th = teams_map[home]
            ta = teams_map[away]
            schedule.append(ScheduledMatch(
                round=r_idx,
                day=day,
                home=home,
                away=away,
                stadium=th.stadium,
                home_state=th.state,
                away_state=ta.state,
            ))

    # Returno: rodadas 20..38, mesmos pares, mando invertido
    for r_idx, pairs in enumerate(rounds_pairs, start=20):
        day = selected_dates[r_idx - 1]
        for a, b in pairs:
            home, away = b, a
            th = teams_map[home]
            ta = teams_map[away]
            schedule.append(ScheduledMatch(
                round=r_idx,
                day=day,
                home=home,
                away=away,
                stadium=th.stadium,
                home_state=th.state,
                away_state=ta.state,
            ))

    return schedule

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date-col", default="Data", help="Nome da coluna de data no CSV de datas")
    parser.add_argument("--teams", required=True, help="Caminho do teams.csv (name,stadium,state)")
    parser.add_argument("--out", default="results/schedule.csv", help="Saída do calendário")
    parser.add_argument("--date-col", default="data", help="Nome da coluna de data no CSV de datas")
    args = parser.parse_args()

    dates = load_dates(args.dates, col=args.date_col)
    teams_map = load_teams(args.teams)

    schedule = build_baseline_schedule(dates, teams_map)
    violations = check_all(schedule)

    df = pd.DataFrame([m.__dict__ for m in schedule])
    df.to_csv(args.out, index=False)

    if violations:
        print("Calendário gerado, mas com violações:")
        for v in violations:
            print("-", v)
        raise SystemExit(1)

    print(f"OK! Calendário baseline salvo em {args.out} (sem PRV, só estrutura).")

if __name__ == "__main__":
    main()

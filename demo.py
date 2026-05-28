"""Demo rápida do pipeline de construção do calendário."""
import sys
sys.path.insert(0, "src")

from datetime import datetime
from brasileirao.construction import construct_schedule
from brasileirao.io import load_teams, load_dates
from brasileirao.objective import compute_prv

teams = load_teams("data/raw/teams.csv")
raw_dates = load_dates("data/raw/datas_20-08-2023_a_09-06-2024.csv")
dates = [datetime.strptime(d, "%d/%m/%Y").date() for d in raw_dates]

schedule = construct_schedule(teams, dates, seed=42)
prv = compute_prv(schedule)

print(f"Jogos gerados: {len(schedule)}")
print(f"PRVs totais:   {prv.total_prv}")
for stadium, count in sorted(prv.prv_by_stadium.items(), key=lambda x: -x[1]):
    print(f"  {stadium}: {count}")

from __future__ import annotations

import csv
from datetime import datetime

from .domain import Schedule, ScheduledMatch, TeamMap

TEAM_NAME_MAP: dict[str, str] = {
    "Coritiba FC": "Coritiba",
    "Cuiabá-MT": "Cuiabá",
    "EC Bahia": "Bahia",
    "Vasco da Gama": "Vasco",
}


def _normalize_team(raw: str, teams_map: TeamMap) -> str:
    name = TEAM_NAME_MAP.get(raw, raw)
    if name not in teams_map:
        raise ValueError(
            f"Time '{raw}' (normalizado: '{name}') nao encontrado em teams_map. "
            f"Times disponiveis: {sorted(teams_map.keys())}"
        )
    return name


def load_real_schedule_2023(
    csv_path: str,
    teams_map: TeamMap,
) -> Schedule:
    """Carrega tabela real do Brasileirao 2023 no formato canonico.

    Normalizacoes:
      - Nomes de times: aplica TEAM_NAME_MAP, confirma em teams_map.
      - Estadio: usa teams_map[home].stadium (ignora CSV).
      - home_state/away_state: usa teams_map (ignora CSV).
      - day: converte ISO (YYYY-MM-DD) para dd/mm/yyyy.
    """
    schedule: Schedule = []
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            home = _normalize_team(row["home"].strip(), teams_map)
            away = _normalize_team(row["away"].strip(), teams_map)
            day_iso = row["day"].strip()
            day_br = datetime.strptime(day_iso, "%Y-%m-%d").strftime("%d/%m/%Y")
            schedule.append(
                ScheduledMatch(
                    round=int(row["round"]),
                    day=day_br,
                    home=home,
                    away=away,
                    stadium=teams_map[home].stadium,
                    home_state=teams_map[home].state,
                    away_state=teams_map[away].state,
                )
            )
    return schedule

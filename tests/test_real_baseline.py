"""Testes para carregamento do baseline real (Brasileirao 2023)."""
from __future__ import annotations

from brasileirao.io import load_teams
from brasileirao.objective import evaluate
from brasileirao.real_baseline import load_real_schedule_2023

TEAMS_PATH = "data/raw/teams.csv"
REAL_PATH = "data/raw/tabela_real_brasileirao_2023.csv"


def _teams():
    return load_teams(TEAMS_PATH)


def test_loads_380_matches() -> None:
    schedule = load_real_schedule_2023(REAL_PATH, _teams())
    assert len(schedule) == 380


def test_38_rounds() -> None:
    schedule = load_real_schedule_2023(REAL_PATH, _teams())
    rounds: dict[int, int] = {}
    for sm in schedule:
        rounds[sm.round] = rounds.get(sm.round, 0) + 1
    assert sorted(rounds.keys()) == list(range(1, 39))
    for r in range(1, 39):
        assert rounds[r] == 10


def test_all_teams_in_map() -> None:
    teams = _teams()
    schedule = load_real_schedule_2023(REAL_PATH, teams)
    all_teams = {sm.home for sm in schedule} | {sm.away for sm in schedule}
    for t in all_teams:
        assert t in teams, f"Time '{t}' nao encontrado em teams_map"


def test_stadium_from_teams_map() -> None:
    teams = _teams()
    schedule = load_real_schedule_2023(REAL_PATH, teams)
    for sm in schedule:
        assert sm.stadium == teams[sm.home].stadium, (
            f"Estadio de {sm.home}: esperado '{teams[sm.home].stadium}', "
            f"obtido '{sm.stadium}'"
        )


def test_can_evaluate() -> None:
    schedule = load_real_schedule_2023(REAL_PATH, _teams())
    result = evaluate(schedule)
    assert result.total_prv >= 0

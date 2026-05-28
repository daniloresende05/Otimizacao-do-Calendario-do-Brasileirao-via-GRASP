"""Testes para o loop multi-start do GRASP."""
from __future__ import annotations

from datetime import date, timedelta

from brasileirao.domain import Team, TeamMap
from brasileirao.grasp import grasp


def _make_teams() -> TeamMap:
    states = [
        "SP", "RJ", "SP", "SP", "RJ", "RJ",
        "MG", "MG", "PR", "PR",
        "RS", "RS", "BA", "BA", "CE",
        "CE", "PE", "MT", "SC", "GO",
    ]
    return {
        f"T{i:02d}": Team(name=f"T{i:02d}", stadium=f"E{i:02d}", state=states[i])
        for i in range(20)
    }


def _make_dates(n: int = 300) -> list[date]:
    start = date(2023, 8, 20)
    return [start + timedelta(days=i) for i in range(n)]


def test_reproducibility() -> None:
    teams, dates = _make_teams(), _make_dates()
    a = grasp(teams, dates, seed=42, max_iter=5)
    b = grasp(teams, dates, seed=42, max_iter=5)
    assert a.best_evaluation.lexicographic_key() == b.best_evaluation.lexicographic_key()
    assert a.best_seed == b.best_seed


def test_best_no_worse_than_first() -> None:
    result = grasp(_make_teams(), _make_dates(), seed=42, max_iter=10)
    first_key = result.history[0].lex_key
    assert result.best_evaluation.lexicographic_key() <= first_key


def test_stops_by_max_iter() -> None:
    result = grasp(
        _make_teams(), _make_dates(),
        seed=42, max_iter=3, max_iter_no_improve=100,
    )
    assert result.total_iterations == 3
    assert result.stopped_by == "max_iter"


def test_stops_by_no_improve() -> None:
    result = grasp(
        _make_teams(), _make_dates(),
        seed=42, max_iter=100, max_iter_no_improve=2,
    )
    assert result.total_iterations < 100
    assert result.stopped_by == "max_iter_no_improve"


def test_alpha_variability() -> None:
    result = grasp(_make_teams(), _make_dates(), seed=42, max_iter=20)
    alphas_used = {h.alpha for h in result.history}
    assert len(alphas_used) > 1


def test_seed_derivation() -> None:
    base_seed = 42
    result = grasp(_make_teams(), _make_dates(), seed=base_seed, max_iter=5)
    for i, h in enumerate(result.history):
        assert h.seed == base_seed + i


def test_history_length() -> None:
    result = grasp(_make_teams(), _make_dates(), seed=42, max_iter=10)
    assert len(result.history) == result.total_iterations

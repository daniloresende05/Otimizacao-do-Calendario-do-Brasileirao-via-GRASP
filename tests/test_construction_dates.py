"""Testes para atribuição de datas (Parte 2 da construção)."""
from __future__ import annotations

from datetime import date, datetime, timedelta

from brasileirao.construction import construct_schedule
from brasileirao.domain import Team, TeamMap
from brasileirao.objective import compute_prv


def _make_teams() -> TeamMap:
    """20 times sintéticos (mesma fixture de test_construction_matches)."""
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


# ---------------------------------------------------------------------------
# 1. Pipeline end-to-end: 380 jogos, 38 rodadas × 10
# ---------------------------------------------------------------------------

def test_pipeline_end_to_end() -> None:
    schedule = construct_schedule(_make_teams(), _make_dates(), seed=42)
    assert len(schedule) == 380
    rounds: dict[int, int] = {}
    for sm in schedule:
        rounds[sm.round] = rounds.get(sm.round, 0) + 1
    assert sorted(rounds.keys()) == list(range(1, 39))
    for r in range(1, 39):
        assert rounds[r] == 10


# ---------------------------------------------------------------------------
# 2. Todas as partidas têm datas válidas
# ---------------------------------------------------------------------------

def test_all_matches_have_dates() -> None:
    schedule = construct_schedule(_make_teams(), _make_dates(), seed=42)
    for sm in schedule:
        assert sm.day
        datetime.strptime(sm.day, "%d/%m/%Y")


# ---------------------------------------------------------------------------
# 3. Descanso mínimo entre jogos consecutivos de cada time
# ---------------------------------------------------------------------------

def test_team_rest_respected() -> None:
    min_rest = 3
    schedule = construct_schedule(
        _make_teams(), _make_dates(), seed=42, min_team_rest_days=min_rest
    )
    team_dates: dict[str, list[date]] = {}
    for sm in schedule:
        d = datetime.strptime(sm.day, "%d/%m/%Y").date()
        team_dates.setdefault(sm.home, []).append(d)
        team_dates.setdefault(sm.away, []).append(d)

    for team, ds in team_dates.items():
        ds_sorted = sorted(ds)
        for i in range(len(ds_sorted) - 1):
            gap = (ds_sorted[i + 1] - ds_sorted[i]).days
            assert gap >= min_rest, (
                f"Time {team}: gap de {gap} dias entre "
                f"{ds_sorted[i]} e {ds_sorted[i + 1]}"
            )


# ---------------------------------------------------------------------------
# 4. Datas dentro da janela da rodada
# ---------------------------------------------------------------------------

def test_dates_within_window() -> None:
    dates = _make_dates()
    round_gap = 7
    round_span = 3
    schedule = construct_schedule(
        _make_teams(), dates, seed=42,
        round_gap=round_gap, round_span=round_span,
    )
    for sm in schedule:
        d = datetime.strptime(sm.day, "%d/%m/%Y").date()
        base_idx = (sm.round - 1) * round_gap
        window_start = dates[base_idx]
        window_end = dates[base_idx + round_span - 1]
        assert window_start <= d <= window_end, (
            f"Rodada {sm.round}: jogo em {d}, "
            f"janela [{window_start}, {window_end}]"
        )


# ---------------------------------------------------------------------------
# 5. Reprodutibilidade
# ---------------------------------------------------------------------------

def test_reproducibility() -> None:
    teams = _make_teams()
    dates = _make_dates()
    a = construct_schedule(teams, dates, seed=42)
    b = construct_schedule(teams, dates, seed=42)
    assert len(a) == len(b)
    for sa, sb in zip(a, b):
        assert sa == sb


# ---------------------------------------------------------------------------
# 6. compute_prv funciona no schedule produzido
# ---------------------------------------------------------------------------

def test_prv_calculable() -> None:
    schedule = construct_schedule(_make_teams(), _make_dates(), seed=42)
    result = compute_prv(schedule)
    assert result.total_prv >= 0

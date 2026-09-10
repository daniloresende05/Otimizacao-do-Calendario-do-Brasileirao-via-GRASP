"""Datas FIFA: remoção da lista de datas e janelas baseadas em calendário.

A CLI remove as datas FIFA da lista de datas disponíveis ANTES do GRASP.
Para isso funcionar sem quebrar (i) span da rodada e (j) sem encavalamento,
``assign_dates_to_matches`` passou a calcular as janelas por CALENDÁRIO
(``round_windows``) em vez de fatiar a lista por posição.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

from brasileirao.construction import (
    DateAssignmentFailedError,
    construct_schedule,
    round_windows,
)
from brasileirao.dates import parse_day
from brasileirao.domain import Team, TeamMap
from brasileirao.io import load_dates, load_teams, remove_blocked_dates
from brasileirao.objective import evaluate

TEAMS_PATH = "data/raw/teams.csv"
DATES_PATH = "data/raw/datas_20-08-2023_a_09-06-2024.csv"
FIFA_PATH = "data/raw/datas_fifas_20-08-2023_a_09-06-2024.csv"


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


START = date(2023, 8, 20)


def _consecutive(n: int = 300) -> list[date]:
    return [START + timedelta(days=i) for i in range(n)]


def _blocked_window(first_day: int, length: int = 9) -> list[date]:
    """Simula uma janela FIFA de ``length`` dias a partir do dia ``first_day``."""
    return [START + timedelta(days=first_day + k) for k in range(length)]


def _day(sm) -> date:
    return datetime.strptime(sm.day, "%d/%m/%Y").date()


# ---------------------------------------------------------------------------
# remove_blocked_dates
# ---------------------------------------------------------------------------

def test_remove_blocked_dates_remove_exatas_e_preserva_ordem() -> None:
    dates = _consecutive(30)
    blocked = _blocked_window(10, 5) + [date(1999, 1, 1)]  # 1 fora da lista
    out = remove_blocked_dates(dates, blocked)
    assert len(out) == 25
    assert out == sorted(out)
    assert not (set(out) & set(blocked))
    assert set(out) | set(blocked[:5]) == set(dates)


# ---------------------------------------------------------------------------
# round_windows
# ---------------------------------------------------------------------------

def test_round_windows_consecutivo_equivale_ao_fatiamento_posicional() -> None:
    dates = _consecutive()
    windows = round_windows(dates, round_gap=7, round_span=3)
    assert len(windows) == 38
    for r, w in enumerate(windows, 1):
        base = (r - 1) * 7
        assert w == dates[base : base + 3]


def test_round_windows_desliza_para_depois_do_bloqueio() -> None:
    blocked = _blocked_window(21)  # dias 21..29 bloqueados: cobre o início da R4
    dates = remove_blocked_dates(_consecutive(), blocked)
    windows = round_windows(dates, round_gap=7, round_span=3)

    assert windows[2][0] == START + timedelta(14)          # R3 não é afetada
    assert windows[3][0] == START + timedelta(30)          # R4 desliza p/ dia 30
    assert windows[3] == [START + timedelta(30 + k) for k in range(3)]
    assert windows[4][0] == START + timedelta(37)          # R5 segue 7 dias depois

    blocked_set = set(blocked)
    for r, w in enumerate(windows, 1):
        assert w, f"R{r} sem datas"
        assert not (set(w) & blocked_set), f"R{r} usa data bloqueada"
        assert (w[-1] - w[0]).days <= 2, f"R{r} span > 2 dias"
        if r > 1:
            assert (w[0] - windows[r - 2][0]).days >= 7


def test_round_windows_janela_parcial_quando_bloqueio_cai_no_meio() -> None:
    # bloqueia só o dia 15 (2º dia da janela da R3)
    dates = remove_blocked_dates(_consecutive(), [START + timedelta(15)])
    windows = round_windows(dates, round_gap=7, round_span=3)
    assert windows[2] == [START + timedelta(14), START + timedelta(16)]
    assert windows[3][0] == START + timedelta(21)  # cadência não desliza


def test_round_windows_erro_quando_rodadas_nao_cabem() -> None:
    with pytest.raises(DateAssignmentFailedError, match="Rodada"):
        round_windows(_consecutive(100), round_gap=7, round_span=3)


# ---------------------------------------------------------------------------
# construct_schedule com datas bloqueadas
# ---------------------------------------------------------------------------

def test_construct_schedule_com_bloqueio_respeita_restricoes_de_calendario() -> None:
    blocked = _blocked_window(21) + _blocked_window(120)
    dates = remove_blocked_dates(_consecutive(320), blocked)
    schedule = construct_schedule(_make_teams(), dates, seed=42)

    assert len(schedule) == 380
    blocked_set = set(blocked)
    assert not any(_day(sm) in blocked_set for sm in schedule)

    ev = evaluate(schedule)
    assert ev.violations_by_type["i"] == 0, "span da rodada > 2 dias"
    assert ev.violations_by_type["j"] == 0, "rodadas encavaladas"
    assert ev.violations_by_type["a"] == 0 and ev.violations_by_type["b"] == 0


def test_construct_schedule_consecutivo_nao_muda_com_round_windows() -> None:
    """Regressão: com dias consecutivos o calendário gerado é o mesmo de antes
    (mesma seed => mesmas datas do fatiamento posicional)."""
    dates = _consecutive()
    schedule = construct_schedule(_make_teams(), dates, seed=42)
    for sm in schedule:
        base = (sm.round - 1) * 7
        assert dates[base] <= _day(sm) <= dates[base + 2]


# ---------------------------------------------------------------------------
# Dataset real: CSV de datas menos CSV de datas FIFA
# ---------------------------------------------------------------------------

def test_dataset_real_sem_datas_fifa_gera_calendario_viavel() -> None:
    teams = load_teams(TEAMS_PATH)
    all_dates = sorted(parse_day(s.strip()).date() for s in load_dates(DATES_PATH))
    fifa = sorted(parse_day(s.strip()).date()
                  for s in load_dates(FIFA_PATH, col="DATA"))
    dates = remove_blocked_dates(all_dates, fifa)

    assert len(fifa) == 43
    assert len(dates) == len(all_dates) - 43

    schedule = construct_schedule(teams, dates, seed=42)
    fifa_set = set(fifa)
    used = {_day(sm) for sm in schedule}
    assert not (used & fifa_set), "jogo marcado em data FIFA"
    assert max(used) <= dates[-1]

    ev = evaluate(schedule)
    assert ev.violations_by_type["i"] == 0
    assert ev.violations_by_type["j"] == 0
    assert ev.is_feasible

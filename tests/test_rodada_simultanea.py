"""Testes da RODADA SIMULTÂNEA (Bloco 1 — escritos ANTES da implementação).

Contrato alvo (Bloco 2):

    construct_schedule(..., simultaneous_rounds: frozenset[int] = frozenset({38}))

  Para cada rodada r em ``simultaneous_rounds``, TODOS os jogos de r caem na
  MESMA data, escolhida entre as datas viáveis da janela (as que respeitam
  ``min_team_rest_days`` para todos os times) como a que MINIMIZA PRV.
  Rodadas fora do conjunto mantêm o comportamento atual (espalham).

Suposição documentada (CA-S5): a lógica de datas vive em
``assign_dates_to_matches`` (``construct_schedule`` delega a ela), portanto o
parâmetro ``simultaneous_rounds`` também é exposto ali — é o único ponto onde
o caminho de data-única pode ser testado isoladamente com um micro-cenário.

Nota (CA-S6): ``FROZEN_ROUNDS`` = {1,2,18,19,20,21,37,38} e AMBOS os
geradores (``swap_days`` e ``swap_homes``) pulam rodadas congeladas; a
perturbação do ILS reutiliza esses geradores. Logo a busca local nunca toca
as datas da R38 — os testes CA-S6 verificam essa proteção diretamente.

Enquanto o Bloco 2 não existir, CA-S1, CA-S2 e CA-S5 DEVEM falhar
(comportamento antigo espalha a R38; o parâmetro novo gera ``TypeError``).
"""
from __future__ import annotations

import random
from dataclasses import replace
from datetime import date, datetime, timedelta

import pytest

from brasileirao.construction import assign_dates_to_matches, construct_schedule
from brasileirao.domain import Match, Schedule, ScheduledMatch, Team, TeamMap
from brasileirao.ils import iterated_local_search
from brasileirao.local_search import local_search, swap_days, swap_homes
from brasileirao.objective import compute_prv, evaluate

MIN_REST = 3


# ---------------------------------------------------------------------------
# Fixtures sintéticas (CA-S7: rápidas; mesma convenção de test_construction_*)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def teams20() -> TeamMap:
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


@pytest.fixture(scope="module")
def dates300() -> list[date]:
    start = date(2023, 8, 20)
    return [start + timedelta(days=i) for i in range(300)]


@pytest.fixture(scope="module")
def schedule_default(teams20: TeamMap, dates300: list[date]) -> Schedule:
    """Construção com DEFAULTS — pós-Bloco 2, a R38 já sai simultânea."""
    return construct_schedule(teams20, dates300, seed=42,
                              min_team_rest_days=MIN_REST)


def _days_of_round(schedule: Schedule, r: int) -> set[str]:
    return {m.day for m in schedule if m.round == r}


def _matches_of_round(schedule: Schedule, r: int) -> list[ScheduledMatch]:
    return [m for m in schedule if m.round == r]


# ---------------------------------------------------------------------------
# CA-S1: default → os 10 jogos da R38 na MESMA data
# ---------------------------------------------------------------------------

def test_ca_s1_r38_data_unica_por_default(schedule_default: Schedule) -> None:
    r38 = _matches_of_round(schedule_default, 38)
    assert len(r38) == 10
    days = _days_of_round(schedule_default, 38)
    assert len(days) == 1, (
        f"R38 deveria ter data única (rodada simultânea default); "
        f"encontrou {sorted(days)}"
    )


# ---------------------------------------------------------------------------
# CA-S2: é PARÂMETRO, não hardcode de rodada 38
# ---------------------------------------------------------------------------

def test_ca_s2a_conjunto_com_r19_e_r38(
    teams20: TeamMap, dates300: list[date]
) -> None:
    schedule = construct_schedule(
        teams20, dates300, seed=42, min_team_rest_days=MIN_REST,
        simultaneous_rounds=frozenset({19, 38}),
    )
    for r in (19, 38):
        days = _days_of_round(schedule, r)
        assert len(days) == 1, (
            f"R{r} ∈ simultaneous_rounds deveria ter data única; "
            f"encontrou {sorted(days)}"
        )


def test_ca_s2b_conjunto_vazio_volta_a_espalhar(
    teams20: TeamMap, dates300: list[date]
) -> None:
    schedule = construct_schedule(
        teams20, dates300, seed=42, min_team_rest_days=MIN_REST,
        simultaneous_rounds=frozenset(),
    )
    days = _days_of_round(schedule, 38)
    assert len(days) > 1, (
        "Com simultaneous_rounds vazio a R38 deve voltar ao comportamento "
        f"antigo (espalhar em mais de uma data); encontrou {sorted(days)}"
    )


# ---------------------------------------------------------------------------
# CA-S3: descanso mínimo entre R37 e R38 preservado
# ---------------------------------------------------------------------------

def test_ca_s3_descanso_r37_r38(schedule_default: Schedule) -> None:
    day_r37: dict[str, date] = {}
    for m in _matches_of_round(schedule_default, 37):
        d = datetime.strptime(m.day, "%d/%m/%Y").date()
        day_r37[m.home] = d
        day_r37[m.away] = d
    for m in _matches_of_round(schedule_default, 38):
        d38 = datetime.strptime(m.day, "%d/%m/%Y").date()
        for team in (m.home, m.away):
            gap = (d38 - day_r37[team]).days
            assert gap >= MIN_REST, (
                f"Time {team}: apenas {gap} dia(s) entre R37 e R38 "
                f"(mínimo {MIN_REST})"
            )


# ---------------------------------------------------------------------------
# CA-S4: solução viável; (i) span e (j) encavalamento ok
# ---------------------------------------------------------------------------

def test_ca_s4_viabilidade_e_regras_de_calendario(
    schedule_default: Schedule,
) -> None:
    ev = evaluate(schedule_default)
    assert ev.is_feasible
    assert ev.violations_by_type.get("i", 0) == 0, "span de rodada violado"
    assert ev.violations_by_type.get("j", 0) == 0, "rodadas encavalaram"


# ---------------------------------------------------------------------------
# CA-S5: entre as datas viáveis, a escolhida é a de MENOR PRV
# ---------------------------------------------------------------------------

def test_ca_s5_data_unica_escolhida_minimiza_prv() -> None:
    """Micro-cenário no nível de assign_dates_to_matches (ver suposição no
    docstring do módulo).

    4 times; T1 e T3 COMPARTILHAM estádio. Rodadas 1..37 têm um único jogo
    T1xT2 (mando alternado, então o estádio compartilhado só é usado em
    rodadas ímpares — gaps de 14 dias, sem PRV). R38 = T3xT4 (times que
    nunca jogaram → as 3 datas da janela são viáveis quanto ao descanso).

    Com round_gap=7/round_span=3 e datas consecutivas, a R37 cai no índice
    252 e a janela da R38 é {259, 260, 261}. Com prv_days=8:
      - dia 259 → 7 dias após o último uso do estádio compartilhado → 1 PRV;
      - dias 260/261 → 8/9 dias → 0 PRV.
    O guloso atual pegaria 259 (primeira data viável). O caminho de
    data-única deve escolher 260 ou 261 (mínimo PRV).
    """
    teams: TeamMap = {
        "T1": Team(name="T1", stadium="Compartilhado", state="SP"),
        "T2": Team(name="T2", stadium="E2", state="RJ"),
        "T3": Team(name="T3", stadium="Compartilhado", state="MG"),
        "T4": Team(name="T4", stadium="E4", state="RS"),
    }
    base = date(2024, 1, 1)
    dates = [base + timedelta(days=i) for i in range(262)]

    matches_by_round: dict[int, list[Match]] = {}
    for r in range(1, 38):
        matches_by_round[r] = (
            [Match("T1", "T2")] if r % 2 == 1 else [Match("T2", "T1")]
        )
    matches_by_round[38] = [Match("T3", "T4")]

    schedule = assign_dates_to_matches(
        matches_by_round,
        dates,
        teams,
        round_gap=7,
        round_span=3,
        prv_days=8,
        min_team_rest_days=3,
        simultaneous_rounds=frozenset({38}),
    )

    # pré-condição do cenário: R37 (ímpar, estádio compartilhado) no dia 252
    (m37,) = _matches_of_round(schedule, 37)
    assert datetime.strptime(m37.day, "%d/%m/%Y").date() == base + timedelta(252)

    days = _days_of_round(schedule, 38)
    assert len(days) == 1
    chosen = datetime.strptime(next(iter(days)), "%d/%m/%Y").date()
    viaveis_sem_prv = {base + timedelta(260), base + timedelta(261)}
    assert chosen in viaveis_sem_prv, (
        f"Data escolhida {chosen} gera PRV; deveria ser uma de "
        f"{sorted(viaveis_sem_prv)} (menor PRV)"
    )
    assert compute_prv(schedule, prv_days=8).total_prv == 0


# ---------------------------------------------------------------------------
# CA-S6: busca local e ILS não desfazem a simultaneidade da R38
# ---------------------------------------------------------------------------

def _teams4() -> TeamMap:
    return {
        "A": Team(name="A", stadium="EA", state="SP"),
        "B": Team(name="B", stadium="EB", state="RJ"),
        "C": Team(name="C", stadium="EC", state="MG"),
        "D": Team(name="D", stadium="ED", state="RS"),
    }


def _sm(r: int, day: str, home: str, away: str, teams: TeamMap) -> ScheduledMatch:
    return ScheduledMatch(
        round=r, day=day, home=home, away=away,
        stadium=teams[home].stadium,
        home_state=teams[home].state,
        away_state=teams[away].state,
    )


def _small_schedule_with_r38_simultanea(teams: TeamMap) -> Schedule:
    """R36/R37 móveis (datas distintas → swap_days tem vizinhos), R38
    congelada e simultânea. Descansos >= 3 dias por construção."""
    return [
        _sm(36, "01/01/2023", "A", "B", teams),
        _sm(36, "02/01/2023", "C", "D", teams),
        _sm(37, "08/01/2023", "B", "C", teams),
        _sm(37, "09/01/2023", "A", "D", teams),
        _sm(38, "16/01/2023", "A", "C", teams),
        _sm(38, "16/01/2023", "B", "D", teams),
    ]


def test_ca_s6_local_search_e_ils_preservam_r38() -> None:
    teams = _teams4()
    schedule = _small_schedule_with_r38_simultanea(teams)
    # não-vácuo: a busca tem movimentos legais fora da R38
    assert swap_days(schedule, teams, min_team_rest_days=MIN_REST)

    after_ls = local_search(schedule, teams, min_team_rest_days=MIN_REST)
    assert _days_of_round(after_ls, 38) == {"16/01/2023"}

    after_ils = iterated_local_search(
        schedule, teams,
        min_team_rest_days=MIN_REST,
        max_iter=5, max_iter_no_improve=3,
        perturbation_max=2, seed=7,
    )
    assert _days_of_round(after_ils, 38) == {"16/01/2023"}


def test_ca_s6_geradores_e_perturbacao_nao_tocam_r38_no_schedule_real(
    schedule_default: Schedule, teams20: TeamMap
) -> None:
    """Sobre o schedule real: força a R38 para data única (pós-Bloco 2 já
    vem assim; o collapse vira no-op) e verifica que NENHUM vizinho de
    swap_days/swap_homes nem a perturbação do ILS alteram as datas da R38.
    Evita rodar o VND completo no schedule de 380 jogos (CA-S7)."""
    target = max(_days_of_round(schedule_default, 38),
                 key=lambda s: datetime.strptime(s, "%d/%m/%Y"))
    forged: Schedule = [
        replace(m, day=target) if m.round == 38 else m
        for m in schedule_default
    ]

    neighbors_days = swap_days(forged, teams20, min_team_rest_days=MIN_REST)
    neighbors_homes = swap_homes(forged, teams20, min_team_rest_days=MIN_REST)
    assert neighbors_days and neighbors_homes  # não-vácuo
    for neighbor in neighbors_days + neighbors_homes:
        assert _days_of_round(neighbor, 38) == {target}

    from brasileirao.ils import perturb
    perturbed = perturb(
        forged, teams20, k=5, rng=random.Random(3),
        min_team_rest_days=MIN_REST,
    )
    assert _days_of_round(perturbed, 38) == {target}

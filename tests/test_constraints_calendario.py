"""Testes (SDD, escritos ANTES da implementação) das DUAS restrições HARD de
calendário a serem adicionadas em ``brasileirao.constraints``:

REGRA 1 — span da rodada <= 3 dias::

    check_span_rodada(schedule, teams_map) -> int   # nº de rodadas que violam

REGRA 2 — sem encavalamento entre rodadas consecutivas::

    check_sem_encavalamento(schedule, teams_map) -> int  # nº de pares (r, r+1) que violam

Ambas puras (sem I/O, sem mutação), retornando CONTAGEM de violações, no mesmo
padrão das ``check_*`` já existentes.

Enquanto as funções não existirem, os testes que dependem delas FALHAM (é o
esperado nesta pré-fase). A importação é feita LAZY (dentro de cada teste) para
que a coleção do arquivo não quebre por inteiro e cada teste falhe
individualmente com uma mensagem clara.
"""
from __future__ import annotations

from datetime import datetime

import pytest

from brasileirao.domain import ScheduledMatch, Team, TeamMap

TEAMS_PATH = "data/raw/teams.csv"
REAL_PATH = "data/raw/tabela_real_brasileirao_2023.csv"
DATES_PATH = "data/raw/datas_20-08-2023_a_09-06-2024.csv"


# ---------------------------------------------------------------------------
# Importação lazy das funções sob teste (ainda não existem nesta pré-fase)
# ---------------------------------------------------------------------------

def _check_span_rodada():
    from brasileirao.constraints import check_span_rodada
    return check_span_rodada


def _check_sem_encavalamento():
    from brasileirao.constraints import check_sem_encavalamento
    return check_sem_encavalamento


# ---------------------------------------------------------------------------
# Helpers de fixture
# ---------------------------------------------------------------------------

def _teams() -> TeamMap:
    return {t: Team(name=t, stadium=f"S{t}", state=f"ST_{t}") for t in "ABCDEFGH"}


def _sm(tm: TeamMap, r: int, day: str, home: str, away: str) -> ScheduledMatch:
    return ScheduledMatch(
        round=r, day=day, home=home, away=away,
        stadium=tm[home].stadium, home_state=tm[home].state,
        away_state=tm[away].state,
    )


# ===========================================================================
# REGRA 1 — check_span_rodada
# ===========================================================================

def test_span_viola_quando_rodada_espalhada_mais_de_3_dias():
    check_span_rodada = _check_span_rodada()
    tm = _teams()
    # rodada 1: 01/08 e 06/08 -> span de 5 dias corridos (> 3) -> viola
    sched = [
        _sm(tm, 1, "01/08/2023", "A", "B"),
        _sm(tm, 1, "06/08/2023", "C", "D"),
    ]
    assert check_span_rodada(sched, tm) >= 1


def test_span_nao_viola_dentro_de_3_dias():
    check_span_rodada = _check_span_rodada()
    tm = _teams()
    # rodada 1: 01/08, 02/08, 03/08 -> span de 2 dias -> ok
    sched = [
        _sm(tm, 1, "01/08/2023", "A", "B"),
        _sm(tm, 1, "02/08/2023", "C", "D"),
        _sm(tm, 1, "03/08/2023", "E", "F"),
    ]
    assert check_span_rodada(sched, tm) == 0


def test_span_borda_3_dias_calendario_permitido():
    check_span_rodada = _check_span_rodada()
    tm = _teams()
    # "span <= 3 dias de calendário" == diferença <= 2 (dias D, D+1, D+2).
    # 01/08 e 03/08 -> diferença 2 -> permitido (== 0)
    sched = [
        _sm(tm, 1, "01/08/2023", "A", "B"),
        _sm(tm, 1, "03/08/2023", "C", "D"),
    ]
    assert check_span_rodada(sched, tm) == 0


def test_span_borda_diferenca_3_viola():
    check_span_rodada = _check_span_rodada()
    tm = _teams()
    # 01/08 e 04/08 -> diferença 3 (4 dias de calendário) -> VIOLA (trava a fronteira)
    sched = [
        _sm(tm, 1, "01/08/2023", "A", "B"),
        _sm(tm, 1, "04/08/2023", "C", "D"),
    ]
    assert check_span_rodada(sched, tm) >= 1


def test_span_conta_por_rodada():
    check_span_rodada = _check_span_rodada()
    tm = _teams()
    # rodada 1 espalhada (01/08 a 06/08, diferença 5) -> viola;
    # rodada 2 compacta (10/08 a 11/08, diferença 1) -> ok.
    # deve contar EXATAMENTE 1 rodada violando (nem 2, nem bool).
    sched = [
        _sm(tm, 1, "01/08/2023", "A", "B"),
        _sm(tm, 1, "06/08/2023", "C", "D"),
        _sm(tm, 2, "10/08/2023", "A", "C"),
        _sm(tm, 2, "11/08/2023", "B", "D"),
    ]
    assert check_span_rodada(sched, tm) == 1


# ===========================================================================
# REGRA 2 — check_sem_encavalamento
# ===========================================================================

def test_encavalamento_viola_quando_rodada_seguinte_comeca_antes():
    check_sem_encavalamento = _check_sem_encavalamento()
    tm = _teams()
    # rodada 2 tem um jogo em 09/08, ANTES do jogo de rodada 1 (10/08) -> viola
    sched = [
        _sm(tm, 1, "10/08/2023", "A", "B"),
        _sm(tm, 1, "10/08/2023", "C", "D"),
        _sm(tm, 2, "09/08/2023", "A", "C"),
        _sm(tm, 2, "12/08/2023", "B", "D"),
    ]
    assert check_sem_encavalamento(sched, tm) >= 1


def test_encavalamento_nao_viola_em_ordem_estrita():
    check_sem_encavalamento = _check_sem_encavalamento()
    tm = _teams()
    # rodada 1 (01-02/08) toda antes da rodada 2 (05-06/08) -> ok
    sched = [
        _sm(tm, 1, "01/08/2023", "A", "B"),
        _sm(tm, 1, "02/08/2023", "C", "D"),
        _sm(tm, 2, "05/08/2023", "A", "C"),
        _sm(tm, 2, "06/08/2023", "B", "D"),
    ]
    assert check_sem_encavalamento(sched, tm) == 0


def test_encavalamento_borda_dia_seguinte_permitido():
    check_sem_encavalamento = _check_sem_encavalamento()
    tm = _teams()
    # última de r1 = 03/08 ; primeira de r2 = 04/08 (dia seguinte) -> estritamente depois -> ok
    sched = [
        _sm(tm, 1, "02/08/2023", "A", "B"),
        _sm(tm, 1, "03/08/2023", "C", "D"),
        _sm(tm, 2, "04/08/2023", "A", "C"),
        _sm(tm, 2, "05/08/2023", "B", "D"),
    ]
    assert check_sem_encavalamento(sched, tm) == 0


def test_encavalamento_mesmo_dia_na_fronteira_viola():
    check_sem_encavalamento = _check_sem_encavalamento()
    tm = _teams()
    # r1 tem jogo em 03/08 e r2 tem jogo em 03/08 (MESMO DIA na fronteira).
    # a regra exige "toda data de r ESTRITAMENTE antes de toda data de r+1",
    # então o mesmo dia VIOLA.
    sched = [
        _sm(tm, 1, "02/08/2023", "A", "B"),
        _sm(tm, 1, "03/08/2023", "C", "D"),
        _sm(tm, 2, "03/08/2023", "A", "C"),
        _sm(tm, 2, "04/08/2023", "B", "D"),
    ]
    assert check_sem_encavalamento(sched, tm) >= 1


# ===========================================================================
# REGRESSÃO (integração, pode ser mais lento) — a construção respeita as duas
# regras novas no dataset real (round_span=3, round_gap=7).
# ===========================================================================

def test_construcao_continua_viavel_com_novas_hard():
    check_span_rodada = _check_span_rodada()
    check_sem_encavalamento = _check_sem_encavalamento()

    from brasileirao.construction import construct_schedule
    from brasileirao.io import load_dates, load_teams

    teams = load_teams(TEAMS_PATH)
    dates = [datetime.strptime(s, "%d/%m/%Y").date() for s in load_dates(DATES_PATH)]

    schedule = construct_schedule(teams, dates, seed=42)

    n_span = check_span_rodada(schedule, teams)
    n_enc = check_sem_encavalamento(schedule, teams)
    assert n_span == 0, f"construção violou span<=3 em {n_span} rodada(s)"
    assert n_enc == 0, f"construção encavalou {n_enc} par(es) de rodadas consecutivas"


# ===========================================================================
# MEDIÇÃO DO BASELINE (informativo) — NÃO deve reprovar a suíte; só coleta o dado.
# ===========================================================================

def test_baseline_real_medicao_calendario():
    check_span_rodada = _check_span_rodada()
    check_sem_encavalamento = _check_sem_encavalamento()

    try:
        from brasileirao.io import load_teams
        from brasileirao.real_baseline import load_real_schedule_2023
    except ImportError:
        pytest.skip("carregador do baseline real (load_real_schedule_2023) não encontrado")

    teams = load_teams(TEAMS_PATH)
    schedule = load_real_schedule_2023(REAL_PATH, teams)

    n_span = check_span_rodada(schedule, teams)
    n_enc = check_sem_encavalamento(schedule, teams)

    print(
        f"\n[BASELINE CBF 2023] rodadas com span>3 dias: {n_span} | "
        f"pares de rodadas encavaladas: {n_enc}"
    )

    # asserts triviais: só garantem que são contagens; o teste SEMPRE passa (uma
    # vez que as checks existam) — o objetivo é COLETAR os números, não reprovar.
    assert n_span >= 0
    assert n_enc >= 0

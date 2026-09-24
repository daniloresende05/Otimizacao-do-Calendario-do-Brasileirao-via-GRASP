"""Testes do controle CONSTRAINT_HARDNESS (dureza configurável das restrições)."""
from __future__ import annotations

import logging
from datetime import date, timedelta

import pytest

from brasileirao.domain import ScheduledMatch, Team, TeamMap
from brasileirao.grasp import grasp
from brasileirao.objective import (
    CONSTRAINT_HARDNESS,
    HARD_CONSTRAINTS,
    evaluate,
    hard_constraint_ids,
    hard_violation_summary,
    reset_constraint_hardness,
    set_all_hard,
)


@pytest.fixture(autouse=True)
def _restore_hardness():
    """Garante que mutações em CONSTRAINT_HARDNESS não vazem entre testes."""
    yield
    reset_constraint_hardness()


def _m(
    round_: int,
    day: str,
    home: str,
    away: str,
    stadium: str,
    home_state: str = "X",
    away_state: str = "X",
) -> ScheduledMatch:
    return ScheduledMatch(
        round=round_,
        day=day,
        home=home,
        away=away,
        stadium=stadium,
        home_state=home_state,
        away_state=away_state,
    )


def _schedule_violating_g() -> list[ScheduledMatch]:
    """Double round-robin de 4 times, limpo em (a)/(b) mas com A 3x em casa (g)."""
    return [
        _m(1, "01/06/2024", "A", "B", "SA"),
        _m(2, "08/06/2024", "A", "C", "SA"),
        _m(3, "15/06/2024", "A", "D", "SA"),
        _m(4, "22/06/2024", "B", "A", "SB"),
        _m(5, "29/06/2024", "C", "A", "SC"),
        _m(6, "06/07/2024", "D", "A", "SD"),
        _m(7, "13/07/2024", "B", "C", "SB"),
        _m(8, "20/07/2024", "B", "D", "SB"),
        _m(9, "27/07/2024", "C", "D", "SC"),
        _m(10, "03/08/2024", "C", "B", "SC"),
        _m(11, "10/08/2024", "D", "B", "SD"),
        _m(12, "17/08/2024", "D", "C", "SD"),
    ]


# ----------------------------------------------------------------------
# (a) default preservado
# ----------------------------------------------------------------------

def test_default_hard_set_unchanged():
    assert hard_constraint_ids() == {"a", "b", "i", "j"}
    assert HARD_CONSTRAINTS == {"a", "b", "i", "j"}
    assert CONSTRAINT_HARDNESS == {
        "a": True, "b": True, "c": False, "d": False, "e": False,
        "f": False, "g": False, "h": False, "i": True, "j": True,
    }


def test_default_soft_violation_keeps_feasible():
    result = evaluate(_schedule_violating_g())
    assert result.is_feasible is True
    assert result.violations_by_type["g"] >= 1


# ----------------------------------------------------------------------
# (b) marcar soft como hard muda is_feasible
# ----------------------------------------------------------------------

def test_marking_g_hard_blocks_feasibility():
    CONSTRAINT_HARDNESS["g"] = True
    result = evaluate(_schedule_violating_g())
    assert result.is_feasible is False
    assert any(v.constraint_id == "g" for v in result.hard_constraint_violations)
    assert result.lexicographic_key()[0] > 0


@pytest.mark.parametrize("cid", ["c", "d", "e", "f", "g", "h"])
def test_structural_constraints_can_become_hard(cid: str):
    CONSTRAINT_HARDNESS[cid] = True
    assert cid in hard_constraint_ids()
    # Schedule limpo continua viável mesmo com o conjunto hard ampliado.
    clean = [
        _m(1, "01/06/2024", "A", "B", "S_A", "MG", "SP"),
        _m(2, "08/06/2024", "B", "A", "S_B", "SP", "MG"),
    ]
    assert evaluate(clean).is_feasible is True


def test_marking_h_hard_counts_prv_as_hard():
    CONSTRAINT_HARDNESS["h"] = True
    # 2 jogos no mesmo estádio com 3 dias de intervalo -> 1 PRV -> (h) viola.
    schedule = [
        _m(1, "01/06/2024", "A", "B", "S1"),
        _m(2, "04/06/2024", "A", "C", "S1"),
    ]
    result = evaluate(schedule)
    assert result.is_feasible is False
    assert any(v.constraint_id == "h" for v in result.hard_constraint_violations)


def test_set_all_hard_and_reset():
    set_all_hard()
    assert all(CONSTRAINT_HARDNESS.values())
    assert hard_constraint_ids() == set("abcdefghij")
    assert HARD_CONSTRAINTS == set("abcdefghij")
    reset_constraint_hardness()
    assert hard_constraint_ids() == {"a", "b", "i", "j"}
    assert HARD_CONSTRAINTS == {"a", "b", "i", "j"}


def test_hard_violation_summary_format():
    set_all_hard()
    assert hard_violation_summary({"d": 4, "h": 6, "a": 0, "c": 1}) == "c=1, d=4, h=6"


# ----------------------------------------------------------------------
# (c) tudo hard: GRASP termina, retorna a melhor (menor hard) e avisa
# ----------------------------------------------------------------------

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


def test_all_hard_grasp_warns_and_returns_best(caplog):
    set_all_hard()
    with caplog.at_level(logging.WARNING, logger="brasileirao.grasp"):
        result = grasp(
            _make_teams(), _make_dates(),
            seed=42, max_iter=3, max_iter_no_improve=100,
        )
    # Termina respeitando max_iter (sem loop infinito) e devolve a melhor.
    assert result.total_iterations == 3
    assert result.best_schedule
    best = result.best_evaluation
    # Com tudo hard, a construção não zera c-h -> inviável e aviso emitido.
    assert best.is_feasible is False
    assert any(
        "Nenhuma solucao viavel" in rec.getMessage() for rec in caplog.records
    )
    # O aviso lista as restrições hard com violação > 0.
    summary = hard_violation_summary(best.violations_by_type)
    assert summary
    assert any(summary in rec.getMessage() for rec in caplog.records)
    # A melhor retornada tem o menor hard entre as iterações do histórico.
    assert best.lexicographic_key()[0] == min(h.lex_key[0] for h in result.history)


def test_all_hard_deterministic():
    set_all_hard()
    a = grasp(_make_teams(), _make_dates(), seed=42, max_iter=3)
    b = grasp(_make_teams(), _make_dates(), seed=42, max_iter=3)
    assert a.best_evaluation.lexicographic_key() == b.best_evaluation.lexicographic_key()
    assert a.best_seed == b.best_seed

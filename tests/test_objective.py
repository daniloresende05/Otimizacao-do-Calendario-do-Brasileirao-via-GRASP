from __future__ import annotations

import pandas as pd
import pytest

from brasileirao.domain import (
    ConstraintViolation,
    EvaluationResult,
    PRVResult,
    ScheduledMatch,
)
from brasileirao.objective import (
    DEFAULT_WEIGHTS,
    HARD_CONSTRAINTS,
    add_prv_column,
    compute_prv,
    evaluate,
)


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


def _two_team_double_robin() -> list[ScheduledMatch]:
    """Schedule mínimo trivialmente válido em (a)–(h)."""
    return [
        _m(1, "01/06/2024", "A", "B", "S_A", "MG", "SP"),
        _m(2, "08/06/2024", "B", "A", "S_B", "SP", "MG"),
    ]


# ----------------------------------------------------------------------
# compute_prv
# ----------------------------------------------------------------------

def test_prv_zero():
    schedule = [
        _m(1, "01/06/2024", "A", "B", "S1"),
        _m(2, "08/06/2024", "A", "C", "S1"),
    ]
    result = compute_prv(schedule, prv_days=5)
    assert result.total_prv == 0
    assert result.occurrences == []
    assert result.prv_by_stadium == {}


def test_prv_one():
    schedule = [
        _m(1, "01/06/2024", "A", "B", "S1"),
        _m(2, "04/06/2024", "A", "C", "S1"),
    ]
    result = compute_prv(schedule, prv_days=5)
    assert result.total_prv == 1
    assert len(result.occurrences) == 1
    assert result.prv_by_stadium == {"S1": 1}
    assert result.occurrences[0].days_between == 3


def test_prv_multiple_stadiums():
    schedule = [
        _m(1, "01/06/2024", "A", "B", "S1"),
        _m(2, "03/06/2024", "C", "D", "S2"),
    ]
    assert compute_prv(schedule, prv_days=5).total_prv == 0


def test_prv_three_consecutive():
    schedule = [
        _m(1, "01/06/2024", "A", "B", "S1"),
        _m(2, "04/06/2024", "A", "C", "S1"),
        _m(3, "09/06/2024", "A", "D", "S1"),
    ]
    result = compute_prv(schedule, prv_days=5)
    assert result.total_prv == 1
    assert result.prv_by_stadium == {"S1": 1}


# ----------------------------------------------------------------------
# evaluate — casos básicos preservados
# ----------------------------------------------------------------------

def test_evaluate_feasible_schedule():
    result = evaluate(_two_team_double_robin())
    assert result.is_feasible is True
    assert result.hard_constraint_violations == []
    assert result.soft_constraint_violations == []
    assert result.total_prv == 0
    assert result.total_cost == 0


def test_evaluate_violates_a():
    schedule = [
        _m(1, "01/06/2024", "A", "B", "S_A"),
        _m(1, "01/06/2024", "A", "C", "S_A"),
    ]
    result = evaluate(schedule)
    assert result.is_feasible is False
    assert any(v.constraint_id == "a" for v in result.hard_constraint_violations)


def test_evaluate_total_cost():
    # 2 PRVs + 1 violação de (a); demais limpas para 4 partidas no mesmo estádio.
    schedule = [
        _m(1, "01/06/2024", "A", "B", "S"),
        _m(1, "04/06/2024", "A", "C", "S"),
        _m(2, "07/06/2024", "B", "A", "S"),
        _m(3, "14/06/2024", "C", "A", "S"),
    ]
    result = evaluate(schedule)
    assert result.total_prv == 2
    assert result.violations_by_type["a"] == 1
    assert result.violations_by_type["b"] == 0
    # w["prv"]*2 + w["a"]*1 + (h tem peso 0) = 102.
    assert result.total_cost == 2 * 1 + 1 * 100


# ----------------------------------------------------------------------
# evaluate — novos casos cobrindo o registry
# ----------------------------------------------------------------------

def test_evaluate_uses_constraint_registry():
    # (c): A em casa em R1 e R2 — só o registry novo enxerga.
    schedule = [
        _m(1, "01/06/2024", "A", "B", "S"),
        _m(2, "08/06/2024", "A", "C", "S"),
    ]
    result = evaluate(schedule)
    assert result.violations_by_type.get("c", 0) >= 1
    assert result.total_cost > 0


def test_evaluate_hard_vs_soft_separation():
    schedule = [
        _m(1, "01/06/2024", "A", "B", "S"),
        _m(1, "01/06/2024", "A", "C", "S"),     # (a)
        _m(5, "01/07/2024", "X", "Y", "S2"),
        _m(6, "08/07/2024", "X", "Z", "S2"),
        _m(7, "15/07/2024", "X", "W", "S2"),    # (g) X 3× home
    ]
    result = evaluate(schedule)
    assert result.is_feasible is False
    assert any(v.constraint_id == "a" for v in result.hard_constraint_violations)
    assert any(v.constraint_id == "g" for v in result.soft_constraint_violations)
    # (g) nunca pode entrar em hard
    assert all(v.constraint_id != "g" for v in result.hard_constraint_violations)


def test_evaluate_only_soft_is_feasible():
    # Double round-robin completo de 4 times com A em casa nas 3 primeiras rodadas
    # (viola (g) sem violar (a) ou (b)).
    schedule = [
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
    result = evaluate(schedule)
    assert result.is_feasible is True
    assert result.violations_by_type["a"] == 0
    assert result.violations_by_type["b"] == 0
    assert result.violations_by_type["g"] >= 1
    assert result.total_cost > 0


def test_evaluate_custom_weights():
    # Schedule com (a) violado. Mudar w["a"] muda o custo linearmente.
    schedule = [
        _m(1, "01/06/2024", "A", "B", "S"),
        _m(1, "01/06/2024", "A", "C", "S"),
    ]
    default_result = evaluate(schedule)
    custom_result = evaluate(schedule, weights={"a": 50.0})
    count_a = default_result.violations_by_type["a"]
    expected_delta = (50.0 - DEFAULT_WEIGHTS["a"]) * count_a
    assert custom_result.total_cost - default_result.total_cost == pytest.approx(
        expected_delta
    )


def test_evaluate_prv_not_double_counted():
    # 3 jogos no mesmo estádio com 3 dias entre cada -> 2 PRVs.
    schedule = [
        _m(1, "01/06/2024", "A", "B", "S"),
        _m(2, "04/06/2024", "C", "A", "S"),
        _m(3, "07/06/2024", "B", "C", "S"),
    ]
    # Zera todos os pesos de restrição; só "prv" deve contribuir.
    zero_weights: dict[str, float] = {
        cid: 0.0 for cid in ("a", "b", "c", "d", "e", "f", "g", "h")
    }
    zero_weights["prv"] = 1.0
    result = evaluate(schedule, weights=zero_weights)
    assert result.total_prv == 2
    assert result.violations_by_type["h"] == 2
    # Sem peso em (h), só w["prv"]*2 entra.
    assert result.total_cost == 2.0


def test_evaluate_clean_schedule():
    result = evaluate(_two_team_double_robin())
    assert result.is_feasible is True
    assert result.hard_constraint_violations == []
    assert result.soft_constraint_violations == []
    assert result.total_cost == 0
    # Registry deve ter rodado todas as 8 verificações.
    assert set(result.violations_by_type.keys()) == {"a", "b", "c", "d", "e", "f", "g", "h"}
    assert all(c == 0 for c in result.violations_by_type.values())


def test_default_weights_h_is_zero():
    # (h) é informativo; peso 0 evita dupla contagem com w["prv"].
    assert DEFAULT_WEIGHTS["h"] == 0.0


def test_hard_constraints_set():
    assert HARD_CONSTRAINTS == {"a", "b"}


def test_summary_contains_key_lines():
    result = evaluate(_two_team_double_robin())
    text = result.summary()
    assert "is_feasible" in text
    assert "total_cost" in text
    assert "violations_by_type" in text


# ----------------------------------------------------------------------
# add_prv_column (deprecated, retrocompat)
# ----------------------------------------------------------------------

def test_deprecated_add_prv_column_still_works():
    df = pd.DataFrame(
        [
            {
                "round": 1,
                "day": "01/06/2024",
                "home": "A",
                "away": "B",
                "stadium": "S1",
                "home_state": "X",
                "away_state": "X",
            },
            {
                "round": 2,
                "day": "04/06/2024",
                "home": "A",
                "away": "C",
                "stadium": "S1",
                "home_state": "X",
                "away_state": "X",
            },
        ]
    )
    with pytest.warns(DeprecationWarning):
        out = add_prv_column(df, prv_days=5)
    assert "PRV" in out.columns
    assert int(out["PRV"].sum()) == 1


# ----------------------------------------------------------------------
# lexicographic_key / is_better_than
# ----------------------------------------------------------------------

def _make_eval(
    n_hard: int,
    n_soft: int,
    total_prv: int,
) -> EvaluationResult:
    hard = [ConstraintViolation(constraint_id="a", description="t") for _ in range(n_hard)]
    soft = [ConstraintViolation(constraint_id="d", description="t") for _ in range(n_soft)]
    return EvaluationResult(
        total_cost=0.0,
        total_prv=total_prv,
        prv_result=PRVResult(total_prv=total_prv, occurrences=[], prv_by_stadium={}),
        hard_constraint_violations=hard,
        soft_constraint_violations=soft,
        violations_by_type={},
    )


def test_lex_hard_wins():
    a = _make_eval(n_hard=1, n_soft=0, total_prv=0)
    b = _make_eval(n_hard=0, n_soft=0, total_prv=100)
    assert b.is_better_than(a)
    assert not a.is_better_than(b)


def test_lex_soft_wins():
    a = _make_eval(n_hard=0, n_soft=5, total_prv=0)
    b = _make_eval(n_hard=0, n_soft=4, total_prv=100)
    assert b.is_better_than(a)
    assert not a.is_better_than(b)


def test_lex_prv_wins_when_tied():
    a = _make_eval(n_hard=0, n_soft=3, total_prv=20)
    b = _make_eval(n_hard=0, n_soft=3, total_prv=10)
    assert b.is_better_than(a)
    assert not a.is_better_than(b)


def test_lex_exact_tie():
    a = _make_eval(n_hard=0, n_soft=3, total_prv=10)
    b = _make_eval(n_hard=0, n_soft=3, total_prv=10)
    assert not a.is_better_than(b)
    assert not b.is_better_than(a)

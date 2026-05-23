from __future__ import annotations

from brasileirao.constraints import (
    CONSTRAINT_CHECKS,
    check_a_max_one_game_per_round,
    check_all,
    check_b_double_round_robin,
    check_c_first_two_rounds_alternation,
    check_d_last_two_rounds_mirror,
    check_e_last_round_no_same_state,
    check_f_home_away_balance_per_turno,
    check_g_max_consecutive_home_or_away,
    check_h_prv,
)
from brasileirao.domain import ScheduledMatch


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


# ----------------------------------------------------------------------
# (a)
# ----------------------------------------------------------------------

def test_a_violates():
    schedule = [
        _m(1, "01/06/2024", "A", "B", "S"),
        _m(1, "01/06/2024", "A", "C", "S"),
    ]
    v = check_a_max_one_game_per_round(schedule)
    assert len(v) == 1
    assert v[0].constraint_id == "a"
    assert v[0].round == 1
    assert v[0].team == "A"


def test_a_clean():
    schedule = [
        _m(1, "01/06/2024", "A", "B", "S"),
        _m(1, "01/06/2024", "C", "D", "S"),
    ]
    assert check_a_max_one_game_per_round(schedule) == []


# ----------------------------------------------------------------------
# (b)
# ----------------------------------------------------------------------

def test_b_violates():
    schedule = [_m(1, "01/06/2024", "A", "B", "S")]
    v = check_b_double_round_robin(schedule)
    assert any(x.constraint_id == "b" for x in v)


def test_b_clean():
    schedule = [
        _m(1, "01/06/2024", "A", "B", "S_A"),
        _m(20, "08/06/2024", "B", "A", "S_B"),
    ]
    assert check_b_double_round_robin(schedule) == []


# ----------------------------------------------------------------------
# (c)
# ----------------------------------------------------------------------

def test_c_violates():
    # Time A em casa em R1 e em casa em R2 -> não alterna.
    schedule = [
        _m(1, "01/06/2024", "A", "B", "S"),
        _m(2, "08/06/2024", "A", "C", "S"),
    ]
    v = check_c_first_two_rounds_alternation(schedule)
    assert len(v) == 1
    assert v[0].constraint_id == "c"
    assert v[0].team == "A"


def test_c_clean():
    schedule = [
        _m(1, "01/06/2024", "A", "B", "S"),
        _m(2, "08/06/2024", "C", "A", "S"),
    ]
    assert check_c_first_two_rounds_alternation(schedule) == []


# ----------------------------------------------------------------------
# (d)
# ----------------------------------------------------------------------

def test_d_violates():
    # A em casa em R1; deveria ser fora em R18 mas está em casa -> viola.
    schedule = [
        _m(1, "01/06/2024", "A", "B", "S"),
        _m(18, "01/10/2024", "A", "C", "S"),
    ]
    v = check_d_last_two_rounds_mirror(schedule)
    assert len(v) == 1
    assert v[0].constraint_id == "d"
    assert v[0].team == "A"
    assert v[0].round == 18


def test_d_clean():
    # A em casa em R1; fora em R18 -> espelho correto.
    schedule = [
        _m(1, "01/06/2024", "A", "B", "S"),
        _m(18, "01/10/2024", "C", "A", "S"),
    ]
    assert check_d_last_two_rounds_mirror(schedule) == []


# ----------------------------------------------------------------------
# (e)
# ----------------------------------------------------------------------

def test_e_violates():
    schedule = [
        _m(
            38, "01/12/2024", "Galo", "Cruzeiro", "Mineirao",
            home_state="MG", away_state="MG",
        ),
    ]
    v = check_e_last_round_no_same_state(schedule)
    assert len(v) == 1
    assert v[0].constraint_id == "e"
    assert v[0].round == 38


def test_e_clean():
    schedule = [
        _m(
            38, "01/12/2024", "Galo", "Santos", "Mineirao",
            home_state="MG", away_state="SP",
        ),
    ]
    assert check_e_last_round_no_same_state(schedule) == []


# ----------------------------------------------------------------------
# (f)
# ----------------------------------------------------------------------

def test_f_violates():
    # Time A: 11 jogos em casa + 8 fora no turno -> |diff|=3 > 1.
    schedule = [
        _m(r, "01/06/2024", "A", f"B{r}", "S") for r in range(1, 12)
    ] + [
        _m(r, "01/06/2024", f"C{r}", "A", "S") for r in range(12, 20)
    ]
    v = check_f_home_away_balance_per_turno(schedule)
    a_violations = [x for x in v if x.team == "A"]
    assert len(a_violations) == 1
    assert a_violations[0].constraint_id == "f"


def test_f_clean():
    # Time A: 10 casa + 9 fora -> |diff|=1, ok.
    schedule = [
        _m(r, "01/06/2024", "A", f"B{r}", "S") for r in range(1, 11)
    ] + [
        _m(r, "01/06/2024", f"C{r}", "A", "S") for r in range(11, 20)
    ]
    v = check_f_home_away_balance_per_turno(schedule)
    a_violations = [x for x in v if x.team == "A"]
    assert a_violations == []


# ----------------------------------------------------------------------
# (g)
# ----------------------------------------------------------------------

def test_g_violates():
    # Time A em casa em R5, R6, R7 -> run de 3 -> viola.
    schedule = [
        _m(5, "01/07/2024", "A", "B", "S"),
        _m(6, "08/07/2024", "A", "C", "S"),
        _m(7, "15/07/2024", "A", "D", "S"),
    ]
    v = check_g_max_consecutive_home_or_away(schedule)
    a_violations = [x for x in v if x.team == "A"]
    assert len(a_violations) == 1
    assert a_violations[0].constraint_id == "g"
    assert a_violations[0].round == 5


def test_g_clean():
    # Time A: 2 em casa (R5,R6) + 1 fora (R7) -> ok.
    schedule = [
        _m(5, "01/07/2024", "A", "B", "S"),
        _m(6, "08/07/2024", "A", "C", "S"),
        _m(7, "15/07/2024", "D", "A", "S"),
    ]
    v = check_g_max_consecutive_home_or_away(schedule)
    a_violations = [x for x in v if x.team == "A"]
    assert a_violations == []


# ----------------------------------------------------------------------
# (h)
# ----------------------------------------------------------------------

def test_h_violates():
    schedule = [
        _m(1, "01/06/2024", "A", "B", "S"),
        _m(2, "04/06/2024", "A", "C", "S"),
    ]
    v = check_h_prv(schedule, prv_days=5)
    assert len(v) == 1
    assert v[0].constraint_id == "h"
    assert v[0].stadium == "S"
    assert v[0].round == 2


def test_h_clean():
    schedule = [
        _m(1, "01/06/2024", "A", "B", "S"),
        _m(2, "08/06/2024", "A", "C", "S"),
    ]
    assert check_h_prv(schedule, prv_days=5) == []


# ----------------------------------------------------------------------
# check_all + registry
# ----------------------------------------------------------------------

def test_check_all_aggregates():
    # Schedule mistura (a) em R1 e (g) em R5-R7 para o time X.
    schedule = [
        _m(1, "01/06/2024", "A", "B", "S"),
        _m(1, "01/06/2024", "A", "C", "S"),  # (a)
        _m(5, "01/07/2024", "X", "Y", "S2"),
        _m(6, "08/07/2024", "X", "Z", "S2"),
        _m(7, "15/07/2024", "X", "W", "S2"),  # (g) X 3x home
    ]
    v = check_all(schedule)
    ids = {x.constraint_id for x in v}
    assert "a" in ids
    assert "g" in ids


def test_check_all_clean():
    # Double round-robin de 2 times: trivialmente válido para (a)-(h).
    schedule = [
        _m(1, "01/06/2024", "A", "B", "S_A", home_state="MG", away_state="SP"),
        _m(20, "08/06/2024", "B", "A", "S_B", home_state="SP", away_state="MG"),
    ]
    assert check_all(schedule) == []


def test_registry_has_all_eight_checks():
    ids = [cid for cid, _ in CONSTRAINT_CHECKS]
    assert ids == ["a", "b", "c", "d", "e", "f", "g", "h"]

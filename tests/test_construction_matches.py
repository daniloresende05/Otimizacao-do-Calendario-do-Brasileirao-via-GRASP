"""Testes para src/brasileirao/construction.py (Parte 1: confrontos e mandos).

Os tests de (a), (b), (c), (e) são estritos (zero violações).
Os tests de (d), (g) verificam bounds empíricos documentados na spec — a
construção é best-effort nessas restrições e a Parte 3 (local search) é
que refina.
"""
from __future__ import annotations

from collections import Counter

import pytest

from brasileirao.construction import build_matches_with_homes
from brasileirao.domain import Match, Team, TeamMap


def _make_teams() -> TeamMap:
    """20 times sintéticos com 6 estados distintos (alguns repetidos para
    permitir matchings limpos e clássicos estaduais)."""
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


def _serialize(m: dict[int, list[Match]]) -> tuple:
    return tuple(
        (r, tuple((mm.home, mm.away) for mm in m[r])) for r in sorted(m)
    )


def _sides_in_round(matches: list[Match]) -> dict[str, str]:
    out: dict[str, str] = {}
    for mm in matches:
        out[mm.home] = "H"
        out[mm.away] = "A"
    return out


# ---------------------------------------------------------------------------
# 1. reproducibility
# ---------------------------------------------------------------------------

def test_reproducibility():
    teams = _make_teams()
    a = build_matches_with_homes(teams, seed=42)
    b = build_matches_with_homes(teams, seed=42)
    assert _serialize(a) == _serialize(b)


# ---------------------------------------------------------------------------
# 2. diferent seeds differ
# ---------------------------------------------------------------------------

def test_different_seeds_differ():
    teams = _make_teams()
    outs = {
        _serialize(build_matches_with_homes(teams, seed=s))
        for s in (1, 2, 3, 4, 5)
    }
    assert len(outs) >= 4


# ---------------------------------------------------------------------------
# 3. total matches
# ---------------------------------------------------------------------------

def test_total_matches():
    teams = _make_teams()
    m = build_matches_with_homes(teams, seed=42)
    total = sum(len(v) for v in m.values())
    assert total == 380


# ---------------------------------------------------------------------------
# 4. 38 rodadas × 10 partidas
# ---------------------------------------------------------------------------

def test_38_rounds_10_matches_each():
    teams = _make_teams()
    m = build_matches_with_homes(teams, seed=42)
    assert sorted(m.keys()) == list(range(1, 39))
    for r in range(1, 39):
        assert len(m[r]) == 10


# ---------------------------------------------------------------------------
# 5. (a) cada time joga 1x por rodada
# ---------------------------------------------------------------------------

def test_constraint_a_satisfied():
    teams = _make_teams()
    m = build_matches_with_homes(teams, seed=42)
    for r in range(1, 39):
        seen: set[str] = set()
        for mm in m[r]:
            assert mm.home not in seen, f"R{r}: {mm.home} aparece 2x"
            assert mm.away not in seen, f"R{r}: {mm.away} aparece 2x"
            seen.add(mm.home)
            seen.add(mm.away)
        assert len(seen) == 20


# ---------------------------------------------------------------------------
# 6. (b) double round-robin: cada par 2x, cada direção 1x
# ---------------------------------------------------------------------------

def test_constraint_b_satisfied():
    teams = _make_teams()
    m = build_matches_with_homes(teams, seed=42)
    direction_count: Counter[tuple[str, str]] = Counter()
    pair_count: Counter[frozenset[str]] = Counter()
    for r in range(1, 39):
        for mm in m[r]:
            direction_count[(mm.home, mm.away)] += 1
            pair_count[frozenset([mm.home, mm.away])] += 1
    for pair, c in pair_count.items():
        assert c == 2, f"Par {pair} aparece {c}x (esperado 2)"
    for direction, c in direction_count.items():
        assert c == 1, f"Direção {direction} aparece {c}x (esperado 1)"


# ---------------------------------------------------------------------------
# 7. (c) alternância R1 ↔ R2
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("seed", [42, 43, 44, 7, 2024])
def test_constraint_c_satisfied(seed):
    teams = _make_teams()
    m = build_matches_with_homes(teams, seed=seed)
    s1 = _sides_in_round(m[1])
    s2 = _sides_in_round(m[2])
    assert set(s1.keys()) == set(s2.keys()) == set(teams.keys())
    for t in teams:
        assert s1[t] != s2[t], f"Time {t}: mesmo mando em R1 e R2"


# ---------------------------------------------------------------------------
# 8. (d) espelho R18↔R1, R19↔R2 — estrito
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("seed", [42, 43, 44, 7, 2024])
def test_constraint_d_satisfied(seed):
    """(d) sai ZERADA por construção desde que as quatro âncoras venham de
    rodadas cruzadas da bipartição: todo jogo delas liga um time de A a um de
    B, então o lado de cada time fica determinado e o espelho é exato.

    Antes deste gerador, (d) tinha um piso estrutural de 4 violações — o
    método do círculo não contém dois matchings que sejam corte perfeito da
    2-coloração de R1 ∪ R2. Ver test_bipartite_factorization.py."""
    teams = _make_teams()
    m = build_matches_with_homes(teams, seed=seed)
    s1 = _sides_in_round(m[1])
    s2 = _sides_in_round(m[2])
    s18 = _sides_in_round(m[18])
    s19 = _sides_in_round(m[19])
    viol = [t for t in teams if s18[t] == s1[t]]
    viol += [t for t in teams if s19[t] == s2[t]]
    assert not viol, f"(d) violada para {viol}"


# ---------------------------------------------------------------------------
# 9. (e) R38 sem clássico estadual
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("seed", [42, 43, 44, 7, 2024])
def test_constraint_e_satisfied(seed):
    teams = _make_teams()
    m = build_matches_with_homes(teams, seed=seed)
    classicos = sum(
        1 for mm in m[38]
        if teams[mm.home].state == teams[mm.away].state
    )
    assert classicos == 0, f"R38 tem {classicos} clássicos estaduais"


# ---------------------------------------------------------------------------
# 10. (g) poucas violações (bound empírico)
# ---------------------------------------------------------------------------

def test_constraint_g_few_violations():
    """Meta é zero; tolerância empírica para a fase de construção. A
    Parte 3 (local search) é que refina."""
    teams = _make_teams()
    m = build_matches_with_homes(teams, seed=42)
    by_team: dict[str, list[str]] = {}
    for r in range(1, 39):
        for mm in m[r]:
            by_team.setdefault(mm.home, []).append("H")
            by_team.setdefault(mm.away, []).append("A")
    viol = 0
    for seq in by_team.values():
        run = 1
        for i in range(1, len(seq)):
            if seq[i] == seq[i - 1]:
                run += 1
                if run > 2:
                    viol += 1
            else:
                run = 1
    assert viol <= 25, f"(g) violou {viol} vezes (bound=25)"


# ---------------------------------------------------------------------------
# 11. alpha=0 + mesma seed → mesma saída
# ---------------------------------------------------------------------------

def test_alpha_zero_is_deterministic_per_seed():
    teams = _make_teams()
    a = build_matches_with_homes(teams, alpha=0.0, seed=42)
    b = build_matches_with_homes(teams, alpha=0.0, seed=42)
    assert _serialize(a) == _serialize(b)


# ---------------------------------------------------------------------------
# 12. alpha=1 + seeds diferentes → maior dispersão
# ---------------------------------------------------------------------------

def test_alpha_one_is_more_random():
    teams = _make_teams()
    outs = {
        _serialize(build_matches_with_homes(teams, alpha=1.0, seed=s))
        for s in (11, 12, 13, 14, 15)
    }
    assert len(outs) == 5

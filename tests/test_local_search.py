"""Testes (SDD, escritos ANTES do módulo) para a busca local VND.

Módulo alvo: src/brasileirao/local_search.py (hoje vazio).

Contrato da função principal (a implementar):

    def local_search(
        schedule, teams_map, *,
        neighborhoods=None,            # default ["swap_homes", "swap_days"]
        weights=None, prv_days=5, max_consecutive=2,
        min_team_rest_days=3, max_iter_no_improve=50, seed=42,
    ) -> Schedule

Decisões fixas refletidas aqui:
  * VND com lista ORDENADA de vizinhanças; best-improvement dentro de cada uma;
    ao melhorar em qualquer vizinhança, REINICIA da primeira.
  * Vizinhanças v1: swap_homes (inverte o mando das DUAS pernas de um confronto,
    preservando o duplo turno) e swap_days (troca a data entre dois jogos da
    MESMA rodada, respeitando descanso).
  * Âncoras congeladas: rounds {1,2,18,19,20,21,37,38} nunca são tocadas.
  * "Melhor" = EvaluationResult.is_better_than (lexicográfico
    (hard, soft_estruturais, total_prv)).

Símbolos esperados no módulo:
  local_search, swap_homes, swap_days, descend, NEIGHBORHOODS, FROZEN_ROUNDS
"""
from __future__ import annotations

from datetime import datetime

import pytest

from brasileirao.domain import ScheduledMatch, Team, TeamMap
from brasileirao.objective import compute_prv, evaluate

from brasileirao.local_search import (  # noqa: E402  (import do módulo sob teste)
    FROZEN_ROUNDS,
    NEIGHBORHOODS,
    descend,
    local_search,
    swap_days,
    swap_homes,
)

FMT = "%d/%m/%Y"
ANCHORS = frozenset({1, 2, 18, 19, 20, 21, 37, 38})


# ---------------------------------------------------------------------------
# Helpers de fixture
# ---------------------------------------------------------------------------

def _teams(stadiums: dict[str, str]) -> TeamMap:
    """TeamMap onde cada time tem `stadium` = stadiums[t] e estado único."""
    return {t: Team(name=t, stadium=st, state=f"ST_{t}") for t, st in stadiums.items()}


def _sm(tm: TeamMap, r: int, day: str, home: str, away: str) -> ScheduledMatch:
    return ScheduledMatch(
        round=r,
        day=day,
        home=home,
        away=away,
        stadium=tm[home].stadium,
        home_state=tm[home].state,
        away_state=tm[away].state,
    )


def _parse(day: str) -> datetime:
    return datetime.strptime(day, FMT)


def _unordered_pairs(schedule):
    return sorted(tuple(sorted((m.home, m.away))) for m in schedule)


def _min_rest_gap(schedule) -> int:
    by_team: dict[str, list[datetime]] = {}
    for m in schedule:
        d = _parse(m.day)
        by_team.setdefault(m.home, []).append(d)
        by_team.setdefault(m.away, []).append(d)
    gaps = []
    for ds in by_team.values():
        ds.sort()
        gaps.extend((b - a).days for a, b in zip(ds, ds[1:]))
    return min(gaps) if gaps else 10**9


def _any_improves(schedule, tm, gen, *, min_team_rest_days: int = 3) -> bool:
    """True sse alguma vizinha gerada por `gen` é melhor que `schedule`."""
    base = evaluate(schedule)
    return any(
        evaluate(nb).is_better_than(base)
        for nb in gen(schedule, tm, frozen_rounds=FROZEN_ROUNDS,
                      min_team_rest_days=min_team_rest_days)
    )


def _descend_local(schedule, tm, gen, *, min_team_rest_days: int = 3):
    """Best-improvement completo em UMA vizinhança — motor-INDEPENDENTE.

    Reimplementado no teste apenas para montar o contrafactual do CA10
    (a "passada única sem reinício"), sem depender do motor do VND.
    """
    cur = schedule
    while True:
        cur_ev = evaluate(cur)
        best = None
        best_ev = cur_ev
        for nb in gen(cur, tm, frozen_rounds=FROZEN_ROUNDS,
                      min_team_rest_days=min_team_rest_days):
            ev = evaluate(nb)
            if ev.is_better_than(best_ev):
                best, best_ev = nb, ev
        if best is None:
            return cur
        cur = best


# --- Fixture A: viável, com âncoras + núcleo móvel com PRV removível ---------
# Rounds 1,2,20,21 são âncoras (pares E/F e G/H, longe no tempo, sem PRV).
# Rounds 4,5,6,23,24,25 são móveis (duplo round-robin de A,B,C,D) e contêm
# exatamente 1 PRV que a busca local consegue eliminar (chave (0,0,1)->(0,0,0)).

def _fixture_anchors_and_improvable():
    tm = _teams({t: f"S{t}" for t in "ABCDEFGH"})
    sched = [
        # âncoras (frozen) — não podem ser tocadas
        _sm(tm, 1, "01/08/2023", "E", "F"),
        _sm(tm, 2, "05/08/2023", "F", "E"),
        _sm(tm, 20, "20/03/2024", "G", "H"),
        _sm(tm, 21, "24/03/2024", "H", "G"),
        # núcleo móvel (viável, PRV=1)
        _sm(tm, 4, "13/09/2023", "D", "C"),
        _sm(tm, 4, "14/09/2023", "B", "A"),
        _sm(tm, 5, "18/09/2023", "B", "D"),
        _sm(tm, 5, "19/09/2023", "A", "C"),
        _sm(tm, 6, "24/09/2023", "D", "A"),
        _sm(tm, 6, "25/09/2023", "C", "B"),
        _sm(tm, 23, "23/01/2024", "A", "B"),
        _sm(tm, 23, "25/01/2024", "C", "D"),
        _sm(tm, 24, "01/02/2024", "B", "C"),
        _sm(tm, 24, "02/02/2024", "A", "D"),
        _sm(tm, 25, "05/02/2024", "C", "A"),
        _sm(tm, 25, "06/02/2024", "D", "B"),
    ]
    return sched, tm


# --- Fixture B: groundshare (A,B,E,G no MESMO estádio SX) --------------------
# Viável, soft=0, PRV=1. swap_homes NÃO consegue reduzir (fica preso);
# um único swap_days elimina o PRV (1->0). Serve para CA9 (swap_days elimina)
# e CA10 (reinício: N1 preso, N2 melhora, VND volta a N1).

def _fixture_shared_stadium():
    tm = _teams({"A": "SX", "B": "SX", "E": "SX", "G": "SX",
                 "C": "SC", "D": "SD", "F": "SF", "H": "SH"})
    sched = [
        _sm(tm, 22, "01/01/2024", "A", "C"),
        _sm(tm, 22, "01/01/2024", "D", "B"),
        _sm(tm, 23, "10/01/2024", "B", "D"),
        _sm(tm, 23, "10/01/2024", "C", "A"),
        _sm(tm, 24, "24/01/2024", "E", "F"),   # E@SX 24/01
        _sm(tm, 24, "22/01/2024", "H", "G"),
        _sm(tm, 25, "28/01/2024", "F", "E"),
        _sm(tm, 25, "28/01/2024", "G", "H"),   # G@SX 28/01  -> PRV SX (24 vs 28)
    ]
    return sched, tm


# --- Fixture C: VND-reinício (o cenário-chave do CA10) ----------------------
# Viável, soft_estruturais=0, PRV=2, descanso >= 3 em S0. Propriedades (todas
# reverificadas por busca aleatória computacional após (i)/(j) virarem HARD;
# ver scratchpad de verificação em tests/ — não versionado):
#   * swap_homes (1ª vizinhança) NÃO melhora S0 (fica preso);
#   * um swap_days (2ª vizinhança) remove 1 PRV -> S1 com chave (0,0,1);
#   * em S1, swap_homes AGORA melhora (remove o 2º PRV) -> (0,0,0).
# Logo, uma passada única SEM reinício para em (0,0,1); só o VND com reinício
# chega a (0,0,0). Times T0..T7; groundshares SX={T0,T1,T6}, SW={T3,T4,T5,T7}.

def _fixture_vnd_restart():
    tm = _teams({
        "T0": "SX", "T1": "SX", "T2": "SY", "T3": "SW",
        "T4": "SW", "T5": "SW", "T6": "SX", "T7": "SW",
    })
    sched = [
        _sm(tm, 22, "06/01/2024", "T4", "T5"),
        _sm(tm, 22, "08/01/2024", "T3", "T2"),
        _sm(tm, 23, "14/01/2024", "T6", "T7"),
        _sm(tm, 23, "16/01/2024", "T2", "T3"),
        _sm(tm, 24, "20/01/2024", "T7", "T6"),
        _sm(tm, 24, "22/01/2024", "T1", "T0"),
        _sm(tm, 25, "26/01/2024", "T0", "T1"),
        _sm(tm, 25, "27/01/2024", "T5", "T4"),
    ]
    return sched, tm


# ---------------------------------------------------------------------------
# Sanidade das fixtures (não são os CA, mas protegem os testes)
# ---------------------------------------------------------------------------

def test_fixture_anchors_is_feasible_with_one_prv():
    sched, _ = _fixture_anchors_and_improvable()
    ev = evaluate(sched)
    assert ev.is_feasible
    assert ev.lexicographic_key() == (0, 0, 1)


def test_fixture_shared_is_feasible_with_one_prv():
    sched, _ = _fixture_shared_stadium()
    ev = evaluate(sched)
    assert ev.is_feasible
    assert ev.lexicographic_key() == (0, 0, 1)


def test_fixture_vnd_restart_sanity():
    sched, tm = _fixture_vnd_restart()
    ev = evaluate(sched)
    assert ev.is_feasible
    assert ev.lexicographic_key() == (0, 0, 2)
    assert _min_rest_gap(sched) >= 3
    # a 1ª vizinhança gera vizinhos, mas nenhum melhora S0 (P1 não-vacuo)
    assert swap_homes(sched, tm, frozen_rounds=FROZEN_ROUNDS, min_team_rest_days=3)
    assert not _any_improves(sched, tm, swap_homes)


# ---------------------------------------------------------------------------
# CA1 — invariante central: nunca piora (sobre várias seeds)
# ---------------------------------------------------------------------------

def test_ca1_never_worse_over_seeds():
    sched, tm = _fixture_anchors_and_improvable()
    before = evaluate(sched)
    for seed in (1, 7, 42, 123, 2024):
        out = local_search(sched, tm, seed=seed)
        after = evaluate(out)
        # melhor OU empate — nunca pior
        assert not before.is_better_than(after), (
            f"seed={seed}: resultado {after.lexicographic_key()} "
            f"pior que entrada {before.lexicographic_key()}"
        )


# ---------------------------------------------------------------------------
# CA2 — restrições hard preservadas (viável continua viável)
# ---------------------------------------------------------------------------

def test_ca2_feasibility_preserved():
    sched, tm = _fixture_anchors_and_improvable()
    assert evaluate(sched).is_feasible
    out = local_search(sched, tm)
    assert evaluate(out).is_feasible


# ---------------------------------------------------------------------------
# CA3 — soft_estruturais não piora
# ---------------------------------------------------------------------------

def test_ca3_soft_structural_not_worse():
    sched, tm = _fixture_anchors_and_improvable()
    before = evaluate(sched).lexicographic_key()[1]
    out = local_search(sched, tm)
    after = evaluate(out).lexicographic_key()[1]
    assert after <= before


# ---------------------------------------------------------------------------
# CA4 — PRV não sobe
# ---------------------------------------------------------------------------

def test_ca4_prv_not_increased():
    sched, tm = _fixture_anchors_and_improvable()
    before = compute_prv(sched).total_prv
    out = local_search(sched, tm)
    after = compute_prv(out).total_prv
    assert after <= before


# ---------------------------------------------------------------------------
# CA5 — âncoras intactas
# ---------------------------------------------------------------------------

def test_ca5_anchors_untouched():
    sched, tm = _fixture_anchors_and_improvable()
    out = local_search(sched, tm)
    before = sorted(repr(m) for m in sched if m.round in ANCHORS)
    after = sorted(repr(m) for m in out if m.round in ANCHORS)
    assert before == after
    # e a busca de fato mexeu em algo (para não passar por vacuidade)
    assert evaluate(out).lexicographic_key() != evaluate(sched).lexicographic_key()


# ---------------------------------------------------------------------------
# CA6 — mesmos confrontos (multiconjunto de {home,away})
# ---------------------------------------------------------------------------

def test_ca6_same_matchups_multiset():
    sched, tm = _fixture_anchors_and_improvable()
    out = local_search(sched, tm)
    assert _unordered_pairs(out) == _unordered_pairs(sched)
    assert len(out) == len(sched)


# ---------------------------------------------------------------------------
# CA7 — descanso mínimo mantido
# ---------------------------------------------------------------------------

def test_ca7_min_rest_respected():
    sched, tm = _fixture_anchors_and_improvable()
    out = local_search(sched, tm, min_team_rest_days=3)
    assert _min_rest_gap(out) >= 3


# ---------------------------------------------------------------------------
# CA8 — determinismo (mesma seed -> saída idêntica)
# ---------------------------------------------------------------------------

def test_ca8_deterministic():
    sched, tm = _fixture_anchors_and_improvable()
    a = local_search(sched, tm, seed=7)
    b = local_search(sched, tm, seed=7)
    assert a == b


# ---------------------------------------------------------------------------
# CA9 — micro-cenário: um PRV eliminável por um único swap_days
# ---------------------------------------------------------------------------

def test_ca9_single_swap_days_removes_prv():
    sched, tm = _fixture_shared_stadium()
    assert compute_prv(sched).total_prv == 1
    # apenas a vizinhança swap_days:
    out = local_search(sched, tm, neighborhoods=["swap_days"])
    assert compute_prv(out).total_prv == 0
    assert evaluate(out).is_feasible
    # o VND completo (default) também elimina
    out_default = local_search(sched, tm)
    assert compute_prv(out_default).total_prv == 0


def test_ca9_swap_homes_alone_cannot_fix():
    # confirma que é MESMO o swap_days que resolve (swap_homes sozinho não)
    sched, tm = _fixture_shared_stadium()
    out = local_search(sched, tm, neighborhoods=["swap_homes"])
    assert compute_prv(out).total_prv == 1  # preso


# ---------------------------------------------------------------------------
# CA10 — VND-reinício (teste-chave): a melhora na 2ª vizinhança ABRE uma melhora
# na 1ª; o VND com reinício captura esse ganho e supera a passada única.
# ---------------------------------------------------------------------------

def test_ca10_restart_beats_single_pass():
    """Cenário onde uma melhora em swap_days (2ª vizinhança) ABRE uma melhora em
    swap_homes (1ª vizinhança). Uma passada única SEM reinício
    (swap_homes -> swap_days) para em (0,0,1); o VND com reinício deve VOLTAR à
    swap_homes e capturar o 2º ganho, chegando a algo estritamente melhor."""
    s0, tm = _fixture_vnd_restart()
    ev0 = evaluate(s0)
    assert ev0.is_feasible and ev0.lexicographic_key()[1] == 0
    assert compute_prv(s0).total_prv >= 2

    # P1: em S0, a 1ª vizinhança (swap_homes) não tem nenhuma melhora.
    assert not _any_improves(s0, tm, swap_homes)

    # Contrafactual "passada única sem reinício": descida em swap_homes (nada,
    # por P1) seguida de descida em swap_days. É o melhor que se alcança sem
    # jamais voltar à 1ª vizinhança.
    single_pass = _descend_local(_descend_local(s0, tm, swap_homes), tm, swap_days)
    ev_single = evaluate(single_pass)
    assert ev_single.is_better_than(ev0)  # swap_days de fato melhorou

    # P3 (o coração do CA10): após a melhora de swap_days, swap_homes AGORA
    # melhora — a oportunidade só existe por causa do reinício.
    assert _any_improves(single_pass, tm, swap_homes), (
        "cenário inválido: swap_homes não abre após o swap_days"
    )

    # O VND completo (com reinício) precisa superar a passada única sem reinício.
    out = local_search(s0, tm)  # ordem default [swap_homes, swap_days]
    assert evaluate(out).is_better_than(ev_single), (
        "VND com reinício deveria superar a passada única sem reinício "
        f"({evaluate(out).lexicographic_key()} vs {ev_single.lexicographic_key()})"
    )


def test_ca10b_restart_returns_to_first_neighborhood(monkeypatch):
    """Cenário: swap_homes está em ótimo local (não melhora), swap_days melhora.
    O VND deve então VOLTAR à swap_homes (reinício). Instrumentamos as
    vizinhanças para registrar a ordem em que são geradas e verificamos que
    "swap_homes" é re-explorada DEPOIS de "swap_days" ter sido explorada."""
    sched, tm = _fixture_shared_stadium()

    calls: list[str] = []

    def _wrap(name):
        real = NEIGHBORHOODS[name]

        def wrapped(*args, **kwargs):
            calls.append(name)
            return real(*args, **kwargs)

        return wrapped

    monkeypatch.setitem(NEIGHBORHOODS, "swap_homes", _wrap("swap_homes"))
    monkeypatch.setitem(NEIGHBORHOODS, "swap_days", _wrap("swap_days"))

    out = local_search(sched, tm)  # ordem default [swap_homes, swap_days]

    assert "swap_homes" in calls and "swap_days" in calls
    first_days = calls.index("swap_days")
    # existe uma exploração de swap_homes APÓS a primeira de swap_days => reinício
    assert any(name == "swap_homes" for name in calls[first_days + 1:]), (
        f"VND não reiniciou na 1ª vizinhança após melhora na 2ª; ordem={calls}"
    )
    # e o resultado é de fato melhor que a entrada
    assert evaluate(out).is_better_than(evaluate(sched))


# ---------------------------------------------------------------------------
# CA11 — o retorno é ótimo local em TODAS as vizinhanças
# ---------------------------------------------------------------------------

def test_ca11_result_is_joint_local_optimum():
    sched, tm = _fixture_anchors_and_improvable()
    out = local_search(sched, tm)
    out_eval = evaluate(out)
    for gen in (swap_homes, swap_days):
        for neigh in gen(out, tm, frozen_rounds=FROZEN_ROUNDS, min_team_rest_days=3):
            assert not evaluate(neigh).is_better_than(out_eval), (
                f"{gen.__name__} ainda tem vizinho melhor -> não é ótimo local"
            )


# ---------------------------------------------------------------------------
# CA12 — rápido (< 5s) — cenários pequenos, sem dataset real de 380 jogos
# ---------------------------------------------------------------------------

def test_ca12_runs_fast():
    import time

    sched, tm = _fixture_anchors_and_improvable()
    sched2, tm2 = _fixture_shared_stadium()
    t0 = time.perf_counter()
    for seed in range(10):
        local_search(sched, tm, seed=seed)
        local_search(sched2, tm2, seed=seed)
    elapsed = time.perf_counter() - t0
    assert elapsed < 5.0, f"busca local lenta demais: {elapsed:.2f}s"


# ---------------------------------------------------------------------------
# Contratos das vizinhanças e do motor auxiliar (unidades pequenas)
# ---------------------------------------------------------------------------

def test_swap_homes_preserves_dates_and_pairs_and_skips_anchors():
    sched, tm = _fixture_anchors_and_improvable()
    neighbors = swap_homes(sched, tm, frozen_rounds=FROZEN_ROUNDS, min_team_rest_days=3)
    assert neighbors, "swap_homes deveria gerar ao menos um vizinho"
    all_days = sorted(m.day for m in sched)
    for nb in neighbors:
        # swap_homes nunca altera datas nem toca âncoras
        assert sorted(m.day for m in nb) == all_days
        assert _unordered_pairs(nb) == _unordered_pairs(sched)
        anchors_before = sorted(repr(m) for m in sched if m.round in ANCHORS)
        anchors_after = sorted(repr(m) for m in nb if m.round in ANCHORS)
        assert anchors_before == anchors_after


def test_swap_days_respects_rest_and_only_swaps_within_round():
    sched, tm = _fixture_shared_stadium()
    neighbors = swap_days(sched, tm, frozen_rounds=FROZEN_ROUNDS, min_team_rest_days=3)
    assert neighbors
    for nb in neighbors:
        # descanso mínimo respeitado em todo vizinho gerado
        assert _min_rest_gap(nb) >= 3
        # mandos e pares intactos (swap_days só mexe em datas)
        assert _unordered_pairs(nb) == _unordered_pairs(sched)


def test_descend_reaches_local_optimum_in_single_neighborhood():
    sched, tm = _fixture_shared_stadium()
    out = descend(sched, tm, "swap_days")
    out_eval = evaluate(out)
    for neigh in swap_days(out, tm, frozen_rounds=FROZEN_ROUNDS, min_team_rest_days=3):
        assert not evaluate(neigh).is_better_than(out_eval)

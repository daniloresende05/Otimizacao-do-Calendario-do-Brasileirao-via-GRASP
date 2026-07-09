"""Testes (SDD) para o Iterated Local Search (ILS).

Módulo alvo: src/brasileirao/ils.py.

Contrato da função principal:

    def iterated_local_search(
        schedule, teams_map, *,
        neighborhoods=None, weights=None, prv_days=5, min_team_rest_days=3,
        perturbation_min=1, perturbation_step=1, perturbation_max=5,
        max_iter_no_improve=20, max_iter=200, seed=42,
    ) -> Schedule

Decisões fixas refletidas aqui:
  * ILS = VND -> repete[ perturba -> VND -> aceita ] -> melhor global.
  * Aceitação BETTER-ONLY; "melhor" = EvaluationResult.is_better_than.
  * Perturbação: k movimentos aleatórios (swap_homes/swap_days), aceitos mesmo
    piorando; respeitam âncoras {1,2,18,19,20,21,37,38} e validade.
  * Força CRESCENTE kp: k começa em perturbation_min; sobe perturbation_step a
    cada iteração sem melhora; volta ao mínimo ao melhorar; nunca passa de
    perturbation_max.

Símbolos esperados no módulo:
  iterated_local_search, perturb, next_k (helper da força kp)
"""
from __future__ import annotations

from datetime import datetime

from brasileirao.domain import ScheduledMatch, Team, TeamMap
from brasileirao.objective import compute_prv, evaluate
from brasileirao.local_search import FROZEN_ROUNDS, local_search, swap_homes, swap_days

from brasileirao.ils import iterated_local_search, perturb

FMT = "%d/%m/%Y"
ANCHORS = frozenset({1, 2, 18, 19, 20, 21, 37, 38})


# ---------------------------------------------------------------------------
# Helpers de fixture
# ---------------------------------------------------------------------------

def _teams(stadiums: dict[str, str]) -> TeamMap:
    return {t: Team(name=t, stadium=st, state=f"ST_{t}") for t, st in stadiums.items()}


def _sm(tm: TeamMap, r: int, day: str, home: str, away: str) -> ScheduledMatch:
    return ScheduledMatch(
        round=r, day=day, home=home, away=away,
        stadium=tm[home].stadium, home_state=tm[home].state,
        away_state=tm[away].state,
    )


def _unordered_pairs(schedule):
    return sorted(tuple(sorted((m.home, m.away))) for m in schedule)


def _all_days(schedule):
    return sorted(m.day for m in schedule)


def _min_rest_gap(schedule) -> int:
    by_team: dict[str, list[datetime]] = {}
    for m in schedule:
        d = datetime.strptime(m.day, FMT)
        by_team.setdefault(m.home, []).append(d)
        by_team.setdefault(m.away, []).append(d)
    gaps = []
    for ds in by_team.values():
        ds.sort()
        gaps.extend((b - a).days for a, b in zip(ds, ds[1:]))
    return min(gaps) if gaps else 10**9


def _anchors_repr(schedule):
    return sorted(repr(m) for m in schedule if m.round in ANCHORS)


# --- Fixture A: viável, com âncoras + núcleo móvel (PRV=1) -------------------
# Igual ao fixture do VND: rounds 1,2,20,21 são âncoras; núcleo em 4,5,6,23,24,25.
# Serve às invariantes CA1..CA8 (âncoras não-vacuosas).

def _fixture_anchors_and_improvable():
    tm = _teams({t: f"S{t}" for t in "ABCDEFGH"})
    sched = [
        _sm(tm, 1, "01/08/2023", "E", "F"),
        _sm(tm, 2, "05/08/2023", "F", "E"),
        _sm(tm, 20, "20/03/2024", "G", "H"),
        _sm(tm, 21, "24/03/2024", "H", "G"),
        _sm(tm, 4, "11/09/2023", "D", "C"),
        _sm(tm, 4, "14/09/2023", "B", "A"),
        _sm(tm, 5, "18/09/2023", "B", "D"),
        _sm(tm, 5, "19/09/2023", "A", "C"),
        _sm(tm, 6, "24/09/2023", "D", "A"),
        _sm(tm, 6, "28/09/2023", "C", "B"),
        _sm(tm, 23, "23/01/2024", "A", "B"),
        _sm(tm, 23, "25/01/2024", "C", "D"),
        _sm(tm, 24, "01/02/2024", "B", "C"),
        _sm(tm, 24, "02/02/2024", "A", "D"),
        _sm(tm, 25, "05/02/2024", "C", "A"),
        _sm(tm, 25, "06/02/2024", "D", "B"),
    ]
    return sched, tm


# --- Fixture B: ILS escapa (o cenário-chave do CA9) -------------------------
# Viável, soft=0, min_rest>=3, PRV=3. O VND (com reinício) TRAVA em (0,0,3);
# perturbação + VND alcança algo estritamente melhor (verificado empiricamente
# para todas as seeds 0..9; ver scratchpad/explore_ils.py).

def _fixture_ils_escapes():
    tm = _teams({"T0": "SW", "T1": "SW", "T2": "SX", "T3": "SZ",
                 "T4": "SW", "T5": "SW", "T6": "SZ", "T7": "SW"})
    sched = [
        _sm(tm, 22, "17/01/2024", "T0", "T1"),
        _sm(tm, 24, "14/01/2024", "T1", "T0"),
        _sm(tm, 25, "03/01/2024", "T2", "T3"),
        _sm(tm, 24, "14/01/2024", "T3", "T2"),
        _sm(tm, 23, "09/02/2024", "T4", "T5"),
        _sm(tm, 22, "10/01/2024", "T5", "T4"),
        _sm(tm, 25, "07/01/2024", "T6", "T7"),
        _sm(tm, 23, "13/01/2024", "T7", "T6"),
    ]
    return sched, tm


# ---------------------------------------------------------------------------
# Sanidade das fixtures
# ---------------------------------------------------------------------------

def test_fixture_anchors_sanity():
    sched, _ = _fixture_anchors_and_improvable()
    ev = evaluate(sched)
    assert ev.is_feasible
    assert ev.lexicographic_key() == (0, 0, 1)
    assert _min_rest_gap(sched) >= 3


def test_fixture_ils_escapes_sanity():
    sched, tm = _fixture_ils_escapes()
    ev = evaluate(sched)
    assert ev.is_feasible
    assert ev.lexicographic_key()[1] == 0
    assert _min_rest_gap(sched) >= 3
    # o VND sozinho NÃO consegue melhorar S (é um ótimo local subótimo)
    assert not evaluate(local_search(sched, tm)).is_better_than(ev)
    assert compute_prv(local_search(sched, tm)).total_prv >= 1


# ---------------------------------------------------------------------------
# CA1 — invariante: nunca pior que a entrada (várias seeds)
# ---------------------------------------------------------------------------

def test_ca1_never_worse_over_seeds():
    sched, tm = _fixture_anchors_and_improvable()
    before = evaluate(sched)
    for seed in (1, 7, 42, 123, 2024):
        out = iterated_local_search(sched, tm, seed=seed)
        after = evaluate(out)
        assert not before.is_better_than(after), (
            f"seed={seed}: {after.lexicographic_key()} pior que {before.lexicographic_key()}"
        )


# ---------------------------------------------------------------------------
# CA2 — viabilidade preservada
# ---------------------------------------------------------------------------

def test_ca2_feasibility_preserved():
    sched, tm = _fixture_anchors_and_improvable()
    assert evaluate(sched).is_feasible
    out = iterated_local_search(sched, tm)
    assert evaluate(out).is_feasible


# ---------------------------------------------------------------------------
# CA3 — não piora hard nem soft_estruturais
# ---------------------------------------------------------------------------

def test_ca3_hard_and_soft_not_worse():
    sched, tm = _fixture_anchors_and_improvable()
    before = evaluate(sched).lexicographic_key()
    out = iterated_local_search(sched, tm)
    after = evaluate(out).lexicographic_key()
    assert after[0] <= before[0]  # hard
    assert after[1] <= before[1]  # soft_estruturais


# ---------------------------------------------------------------------------
# CA4 — âncoras intactas
# ---------------------------------------------------------------------------

def test_ca4_anchors_untouched():
    sched, tm = _fixture_anchors_and_improvable()
    out = iterated_local_search(sched, tm)
    assert _anchors_repr(out) == _anchors_repr(sched)


# ---------------------------------------------------------------------------
# CA5 — mesmo multiconjunto de confrontos {home,away}
# ---------------------------------------------------------------------------

def test_ca5_same_matchups_multiset():
    sched, tm = _fixture_anchors_and_improvable()
    out = iterated_local_search(sched, tm)
    assert _unordered_pairs(out) == _unordered_pairs(sched)
    assert len(out) == len(sched)


# ---------------------------------------------------------------------------
# CA6 — descanso mínimo respeitado; datas dentro da janela
# ---------------------------------------------------------------------------

def test_ca6_min_rest_and_dates_in_window():
    sched, tm = _fixture_anchors_and_improvable()
    out = iterated_local_search(sched, tm, min_team_rest_days=3)
    assert _min_rest_gap(out) >= 3
    # nenhuma data nova é criada (só permutação das datas existentes)
    assert _all_days(out) == _all_days(sched)


# ---------------------------------------------------------------------------
# CA7 — determinismo (mesma seed -> saída idêntica, incluindo a perturbação)
# ---------------------------------------------------------------------------

def test_ca7_deterministic():
    sched, tm = _fixture_ils_escapes()
    a = iterated_local_search(sched, tm, seed=7)
    b = iterated_local_search(sched, tm, seed=7)
    assert a == b


# ---------------------------------------------------------------------------
# CA8 — a perturbação perturba: sobre um ótimo local, produz algo DIFERENTE,
# viável e com âncoras intactas.
# ---------------------------------------------------------------------------

def test_ca8_perturbation_perturbs():
    import random

    sched, tm = _fixture_anchors_and_improvable()
    star = local_search(sched, tm)  # ótimo local do VND
    for seed in (1, 2, 3, 4, 5):
        # k=1 garante ao menos um movimento aplicado -> difere do ótimo local
        p1 = perturb(star, tm, 1, random.Random(seed))
        assert p1 != star
        for k in (1, 2, 3):
            p = perturb(star, tm, k, random.Random(seed))
            assert evaluate(p).is_feasible
            assert _anchors_repr(p) == _anchors_repr(star)
            assert _unordered_pairs(p) == _unordered_pairs(star)


# ---------------------------------------------------------------------------
# CA9 (teste-chave) — o ILS escapa e melhora: estritamente melhor que o VND só.
# ---------------------------------------------------------------------------

def test_ca9_ils_escapes_local_optimum():
    sched, tm = _fixture_ils_escapes()
    vnd_only = evaluate(local_search(sched, tm))

    strictly_better = False
    for seed in range(8):
        out_ev = evaluate(iterated_local_search(sched, tm, seed=seed))
        # nunca pior que o VND sozinho
        assert not vnd_only.is_better_than(out_ev), f"seed={seed}: ILS piorou vs VND"
        if out_ev.is_better_than(vnd_only):
            strictly_better = True
    assert strictly_better, (
        "ILS deveria escapar do ótimo local do VND e ficar estritamente melhor "
        "em ao menos uma seed"
    )


# ---------------------------------------------------------------------------
# CA10 — força crescente (regra kp): sobe sem melhora, reseta ao melhorar,
# nunca passa de perturbation_max. Testa o helper puro `next_k`.
# ---------------------------------------------------------------------------

def test_ca10_increasing_force_schedule():
    from brasileirao.ils import next_k  # helper da força kp (bloco do motor)

    kmin, kstep, kmax = 1, 1, 5
    kw = dict(perturbation_min=kmin, perturbation_step=kstep, perturbation_max=kmax)

    # sem melhora -> sobe um passo
    assert next_k(kmin, improved=False, **kw) == kmin + kstep
    # ao melhorar -> volta ao mínimo (mesmo partindo de um k alto)
    assert next_k(4, improved=True, **kw) == kmin
    # aplicações sucessivas sem melhora saturam em kmax (nunca passam)
    k = kmin
    for _ in range(20):
        k = next_k(k, improved=False, **kw)
        assert k <= kmax
    assert k == kmax
    # partindo já do máximo, permanece no máximo
    assert next_k(kmax, improved=False, **kw) == kmax

    # passo maior que 1 também satura corretamente
    assert next_k(4, improved=False, perturbation_min=1, perturbation_step=3,
                  perturbation_max=5) == 5


# ---------------------------------------------------------------------------
# CA11 — parada: termina e respeita max_iter (max_iter=0 => só o VND inicial).
# ---------------------------------------------------------------------------

def test_ca11_stops_and_respects_max_iter():
    sched, tm = _fixture_ils_escapes()
    # com 0 iterações de perturbação, o resultado é exatamente o VND inicial
    out0 = iterated_local_search(sched, tm, max_iter=0)
    assert evaluate(out0).lexicographic_key() == evaluate(local_search(sched, tm)).lexicographic_key()
    # um número pequeno de iterações também termina (não roda para sempre)
    out = iterated_local_search(sched, tm, max_iter=5, seed=1)
    assert evaluate(out).is_feasible


# ---------------------------------------------------------------------------
# CA12 — rápido (< 5s) em cenários pequenos
# ---------------------------------------------------------------------------

def test_ca12_runs_fast():
    import time

    s1, tm1 = _fixture_anchors_and_improvable()
    s2, tm2 = _fixture_ils_escapes()
    t0 = time.perf_counter()
    for seed in range(5):
        iterated_local_search(s1, tm1, seed=seed)
        iterated_local_search(s2, tm2, seed=seed)
    elapsed = time.perf_counter() - t0
    assert elapsed < 5.0, f"ILS lento demais: {elapsed:.2f}s"

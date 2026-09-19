"""Testes do gerador de confrontos alinhado a uma bipartição.

O ponto que estes testes guardam: as rodadas "cruzadas" só têm jogos entre um
time de A e um de B. É essa propriedade que faz (c) e (d) saírem por construção
nas rodadas 1, 2, 18 e 19 — sem o piso de 4 violações que o método do círculo
puro impõe.
"""
import random
from itertools import combinations

import pytest

from brasileirao.round_robin import (
    bipartite_factorization,
    circle_method,
    shuffle_factors,
)

TEAMS = [f"T{i:02d}" for i in range(20)]


def _assert_one_factorization(factors, teams):
    """Valida que `factors` é uma 1-fatoração de K_n: cada rodada é um matching
    perfeito e cada confronto aparece exatamente uma vez no conjunto todo."""
    n = len(teams)
    assert len(factors) == n - 1

    visto: dict[tuple[str, str], int] = {}
    for idx, fator in enumerate(factors):
        assert len(fator) == n // 2, f"fator {idx} não é matching perfeito"
        cobertos: set[str] = set()
        for a, b in fator:
            assert a not in cobertos and b not in cobertos, (
                f"fator {idx}: time repetido na mesma rodada"
            )
            cobertos |= {a, b}
            chave = tuple(sorted((a, b)))
            assert chave not in visto, (
                f"confronto {chave} repetido (fatores {visto[chave]} e {idx})"
            )
            visto[chave] = idx
        assert cobertos == set(teams)

    assert len(visto) == n * (n - 1) // 2


@pytest.mark.parametrize("seed", [0, 42, 7, 1234])
def test_e_uma_1_fatoracao_de_k20(seed):
    rng = random.Random(seed)
    cruzadas, restantes, _, _ = bipartite_factorization(TEAMS, rng)
    _assert_one_factorization(cruzadas + restantes, TEAMS)


@pytest.mark.parametrize("seed", [0, 42, 7, 1234])
def test_cruzadas_sempre_ligam_lados_opostos(seed):
    """A propriedade que zera (c) e (d): nenhuma aresta dentro de A ou de B."""
    rng = random.Random(seed)
    cruzadas, _, part_a, part_b = bipartite_factorization(TEAMS, rng)

    assert len(part_a) == len(part_b) == 10
    assert set(part_a) | set(part_b) == set(TEAMS)
    assert not set(part_a) & set(part_b)

    lado = {t: "A" for t in part_a} | {t: "B" for t in part_b}
    assert len(cruzadas) == 10
    for idx, fator in enumerate(cruzadas):
        monocromaticos = [(a, b) for a, b in fator if lado[a] == lado[b]]
        assert not monocromaticos, (
            f"rodada cruzada {idx} tem jogo entre times do mesmo lado: "
            f"{monocromaticos}"
        )


@pytest.mark.parametrize("seed", [0, 42, 7])
def test_ha_pelo_menos_quatro_cruzadas_para_as_ancoras(seed):
    rng = random.Random(seed)
    cruzadas, _, _, _ = bipartite_factorization(TEAMS, rng)
    assert len(cruzadas) >= 4


@pytest.mark.parametrize("seed", [0, 42, 7, 1234])
def test_shuffle_preserva_a_fatoracao(seed):
    """Os flips de ciclo alternante mudam as rodadas mas não a união das
    arestas — a 1-fatoração continua válida."""
    rng = random.Random(seed)
    cruzadas, restantes, _, _ = bipartite_factorization(TEAMS, rng)
    ancoras, miolo = cruzadas[:4], cruzadas[4:] + restantes

    embaralhado = shuffle_factors(miolo, rng, flips=60)
    _assert_one_factorization(ancoras + embaralhado, TEAMS)

    antes = {tuple(sorted(e)) for f in miolo for e in f}
    depois = {tuple(sorted(e)) for f in embaralhado for e in f}
    assert antes == depois, "os flips não podem criar nem perder confrontos"


@pytest.mark.parametrize("seed", [0, 42, 7])
def test_shuffle_nao_toca_nas_ancoras(seed):
    rng = random.Random(seed)
    cruzadas, restantes, part_a, _ = bipartite_factorization(TEAMS, rng)
    ancoras = cruzadas[:4]
    copia = [list(f) for f in ancoras]

    shuffle_factors(cruzadas[4:] + restantes, rng, flips=60)

    assert [list(f) for f in ancoras] == copia
    lado_a = set(part_a)
    for fator in ancoras:
        for a, b in fator:
            assert (a in lado_a) != (b in lado_a)


@pytest.mark.parametrize("seed", [0, 42, 7])
def test_shuffle_mistura_o_miolo(seed):
    """Sem os flips, toda rodada do miolo é 100% interna ou 100% cruzada.
    Com eles, as rodadas passam a misturar os dois tipos de confronto."""
    rng = random.Random(seed)
    cruzadas, restantes, part_a, _ = bipartite_factorization(TEAMS, rng)
    lado_a = set(part_a)
    miolo = shuffle_factors(cruzadas[4:] + restantes, rng, flips=60)

    def e_mista(fator):
        cruz = sum(1 for a, b in fator if (a in lado_a) != (b in lado_a))
        return 0 < cruz < len(fator)

    assert sum(1 for f in miolo if e_mista(f)) >= 10


def test_circle_method_continua_intacto():
    """O gerador novo reusa o método do círculo nos dois K10 — ele precisa
    continuar valendo para 10 times."""
    dez = TEAMS[:10]
    _assert_one_factorization(circle_method(dez), dez)


@pytest.mark.parametrize("seed", [0, 42, 7])
def test_metodo_do_circulo_nao_alcanca_zero_em_d(seed):
    """Regressão do diagnóstico: no método do círculo puro sobre 20 times,
    fixados R1 e R2, todo outro fator tem ao menos 2 jogos entre times da
    mesma cor — daí o piso de 4 violações de (d) que motivou este gerador."""
    fatores = circle_method(TEAMS)

    def duas_cores(m1, m2):
        adj: dict[str, list[str]] = {t: [] for t in TEAMS}
        for a, b in m1 + m2:
            adj[a].append(b)
            adj[b].append(a)
        cor: dict[str, int] = {}
        for t in TEAMS:
            if t in cor:
                continue
            cor[t] = 0
            pilha = [t]
            while pilha:
                cur = pilha.pop()
                for viz in adj[cur]:
                    if viz not in cor:
                        cor[viz] = 1 - cor[cur]
                        pilha.append(viz)
        return cor

    rng = random.Random(seed)
    i, j = rng.sample(range(19), 2)
    cor = duas_cores(fatores[i], fatores[j])
    perfil = sorted(
        sum(1 for a, b in fatores[k] if cor[a] == cor[b])
        for k in range(19)
        if k not in (i, j)
    )
    assert min(perfil) == 2
    assert min(x + y for x, y in combinations(perfil, 2)) == 4

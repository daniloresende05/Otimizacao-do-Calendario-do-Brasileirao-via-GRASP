# Spec — Construção, Parte 1 (confrontos e mandos, sem datas)

## 1. Objetivo

Decidir, para o turno (R1–R19), **quem joga contra quem em cada rodada
e quem é mandante**. O returno (R20–R38) é o turno espelhado com mando
invertido. Não há atribuição de datas nesta fase.

Restrições resolvidas por construção: **(a), (b), (c), (d)**.
Restrições atendidas best-effort por seleção de matching: **(e)**.
Restrições otimizadas via RCL: **(f), (g)**.
PRV / (h) não entra — datas vêm na Parte 2.

## 2. Decisão chave — (d) estrita via 1-fatoração alinhada à bipartição

### O problema que existia

A versão anterior sorteava R1 e R2 entre os 19 matchings do `circle_method`,
2-coloria o grafo `R1 ∪ R2` e procurava, entre os 17 restantes, dois matchings
que fossem "corte perfeito" dessa coloração para servirem de R18 e R19.

Esses dois matchings **não existem**. Encadeando (c) e (d):

- (c) diz `lado_R2(T) = ¬lado_R1(T)`;
- (d) diz `lado_R18(T) = ¬lado_R1(T)` e `lado_R19(T) = ¬lado_R2(T)`.

Chamando de **A** o conjunto dos times que mandam na R1 e de **B** o resto,
todo time de A precisa visitar na R18, logo o mandante de cada jogo da R18 tem
de sair de B. Ou seja: **as quatro rodadas-âncora precisam ser matchings que
atravessam a bipartição (A, B)** — nenhuma aresta dentro de A ou dentro de B.
É uma condição sobre os CONFRONTOS, não sobre o mando: nenhuma orientação e
nenhum movimento de busca local conserta uma aresta monocromática.

E o método do círculo não oferece essas rodadas. Duas propriedades, ambas
verificadas por enumeração exaustiva em `tests/test_bipartite_factorization.py`:

1. Para 20 times, `R_a ∪ R_b` é **sempre um único ciclo hamiltoniano**. Logo a
   2-coloração é única a menos de troca global de rótulos — não havia
   liberdade de coloração a explorar.
2. Fixados R1 e R2, o perfil de arestas monocromáticas dos 17 fatores restantes
   é invariante: `[2,2,2,2,4,4,4,4,6,6,6,6,8,8,8,8,10]`. Nenhum chega a zero.

Daí o piso de **4 violações** de (d) (2 + 2), atingido por 2.052 dos 46.512
quartetos possíveis. Embaralhar a ordem dos times não altera nada: renomear
vértices não muda a estrutura da 1-fatoração.

### A solução adotada

A bipartição deixa de ser consequência do sorteio de R1/R2 e passa a ser a
**variável de projeto**. `bipartite_factorization` gera a 1-fatoração de K20 já
alinhada a ela:

- sorteia A e B com 10 times cada;
- **10 rodadas cruzadas** `C_k = {(a_i, b_{i+k mod 10})}`, cobrindo as 100
  arestas entre A e B;
- **9 rodadas internas** `N_r`, unindo uma 1-fatoração de K10 em A com uma em B,
  cobrindo as 45 + 45 arestas internas.

Total: 19 rodadas, 190 confrontos, cada par exatamente uma vez.

Quatro rodadas cruzadas viram as âncoras, e o mando sai direto do lado:

| rodada | manda |
|---|---|
| R1  | quem é de A |
| R2  | quem é de B |
| R18 | quem é de B |
| R19 | quem é de A |

Como toda aresta de uma rodada cruzada tem uma ponta em A e outra em B, o
mandante é único e bem definido. **(c) e (d) saem zeradas por construção**, sem
busca, sem custo e sem desempate — do mesmo jeito que (a) e (b) já saíam.

O `circle_method` continua em uso: agora ele fatora os dois K10 internos.

## 3. Decisão chave — (e) e a diversidade do miolo

**(e)** — R38 espelha R19, então a âncora que vira R19 precisa ser uma rodada
cruzada sem clássico estadual. Cerca de 99% dos sorteios de bipartição oferecem
ao menos uma (2,9 em média); `MAX_TENTATIVAS_BIPARTICAO = 20` cobre o resto. As
duas cruzadas com menos clássicos são reservadas para R18/R19, e R1/R2 ficam com
as duas seguintes — R1 e R2 não têm restrição de clássico.

**Diversidade** — a fatoração sai "pura": cada rodada do miolo seria ou toda
interna ou toda cruzada. `shuffle_factors` aplica trocas de ciclo alternante
entre as 15 rodadas não-âncora. A união de dois matchings perfeitos é uma
coleção de ciclos de tamanho par alternando os dois; trocar as arestas ao longo
de um ciclo devolve dois matchings perfeitos cobrindo as mesmas arestas. A
1-fatoração continua válida, as âncoras não são tocadas, e as rodadas do miolo
passam a misturar confrontos internos e cruzados.

Isso substitui, com vantagem, o antigo item de trabalho futuro "embaralhar a
ordem dos times antes do método do círculo", que pelo argumento da seção 2 não
produziria diversidade nenhuma em (d).

## 4. Decisão chave — quase-hard (g) na RCL

Na RCL para R3..R17, filtramos candidatos que **não introduzem** violação
de (g). Só se nenhum candidato sem (g) existir é que aceitamos candidatos
com (g) > 0. Peso de (g) na função de custo: **300** (vs. 100 de (f)).

## 6. Algoritmo

```
rng = Random(seed)
cruzadas, internas, part_a, _ = bipartite_factorization(teams, rng)
```

### Âncoras (R1, R2, R18, R19)

1. Repete `bipartite_factorization` até alguma das 10 cruzadas não ter
   clássico estadual (máx. `MAX_TENTATIVAS_BIPARTICAO`).
2. Ordena as cruzadas por nº de clássicos. As duas primeiras ficam
   reservadas para R18/R19; a terceira e a quarta viram R1 e R2.
3. `sides_r1[T] = "H" se T ∈ A senão "A"`. Orienta R1 por `sides_r1` e R2
   pela inversão — ambas estritas, porque toda aresta de uma cruzada liga
   A a B.
4. Miolo = as 6 cruzadas restantes + as 9 internas, passadas por
   `shuffle_factors` (trocas de ciclo alternante). São os 15 matchings que
   a RCL vai consumir em R3..R17.

### RCL para R3..R17 (15 rodadas)

Para cada `r ∈ {3, ..., 17}`:

```
rem_unk = 19 - r
# (f) projetada: cada time T deve terminar o turno com home_count ∈ {9, 10}.
# Aceita candidatos com até alpha·(c_max - c_min) acima do melhor custo.

candidatos = []
for matching in remaining:
    for orientacao in enumerate(2^10):
        f_v, g_v = projetar(state, orientacao, rem_unk)
        custo = 100*f_v + 300*g_v
        candidatos.append((matching_idx, mask, g_v, custo))

# Quase-hard (g)
sem_g = [c for c in candidatos if c.g_v == 0]
pool = sem_g if sem_g else candidatos

c_min, c_max = min/max custo em pool
rcl = [c for c in pool if c.custo <= c_min + alpha·(c_max - c_min)]
escolhido = rng.choice(rcl)
state.apply(escolhido)
```

Otimizações implementadas no inner loop:
- Conversão de times para índices `int` (acesso O(1) por lista).
- Pré-cálculo de `pair_g0`, `pair_g1`, `df0`, `df1` por par.
- Soma incremental por máscara de bits.

### Atribuição de R18 e R19

A orientação não é mais uma busca: o lado de cada time já está fixado pela
bipartição — manda quem é de B na R18 e quem é de A na R19. Resta só decidir
qual das duas âncoras reservadas vai para cada rodada, por critério
lexicográfico `(nº de clássicos do candidato a R19, violações de (g) na cadeia
R17 → R18 → R19)`. Empates resolvidos por `rng`.

A enumeração das 2¹⁰ orientações e o termo `d_resid` desapareceram: não há
resíduo de (d) a minimizar.

### Returno

```
for r in 1..19:
    matches_by_round[r + 19] = [Match(away, home) for Match(home, away) in matches_by_round[r]]
```

(b) por construção.

## 7. Custos auxiliares

### Projected violations de (f)

(f) é `|home_count - away_count| <= 1` no turno. Como cada time joga 19
jogos, `home_count ∈ {9, 10}` é o intervalo factível.

Após aplicar rodada `r` em sequência, time `T` jogou `r` jogos. Sobram
`19 − r` rodadas (incluindo R18, R19 desconhecidos nessa fase).

Time `T` está **projetado unfeasible** se:
- `home_count(T) > 10`, **ou**
- `home_count(T) + (19 − r) < 9`.

`f_v` = nº de times projetados unfeasible **após** essa rodada.

### Projected violations de (g)

Para cada `(home, away)` da orientação simulada:
- Se o time já tinha o mesmo `last_side`, incrementa `streak`. Senão,
  reseta para 1.
- Se `streak` excede `max_consecutive`, conta +1 em `g_v`.

## 8. API

```python
MatchesByRound = dict[int, list[Match]]  # 1..38 -> 10 Match cada

def build_matches_with_homes(
    teams_map: TeamMap,
    *,
    alpha: float = 0.3,
    seed: int = 42,
    max_consecutive: int = 2,
) -> MatchesByRound
```

Levanta `ConstructionFailedError` se o número de times não for 20 ou se o
pool de matchings esgotar antes de completar 19 rodadas.

## 9. Não-feito nesta fase

- Datas / PRV / (h).
- Integração com `cli.py`.
- Local search (próxima fase do GRASP).

## 10. Bounds empíricos para os testes

Como (f) e (g) são best-effort, os testes correspondentes assertam contra
limites empíricos:

- (a), (b), (c), (d), (e): **zero violações** (estritas), verificadas em
  várias seeds.
- (f): até 10 violações no turno.
- (g): até 25 violações no campeonato (meta é zero; tolerância empírica
  para a fase de construção. A local search da Parte 3 do GRASP é quem
  vai refinar).

## 11. Extensão futura

Parte 2 receberá um `MatchesByRound` e atribuirá datas a cada jogo,
otimizando PRV e descanso entre jogos. A assinatura de
`build_matches_with_homes` não muda.

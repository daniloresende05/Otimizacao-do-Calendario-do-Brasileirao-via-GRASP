# Spec — Construção, Parte 1 (confrontos e mandos, sem datas)

## 1. Objetivo

Decidir, para o turno (R1–R19), **quem joga contra quem em cada rodada
e quem é mandante**. O returno (R20–R38) é o turno espelhado com mando
invertido. Não há atribuição de datas nesta fase.

Restrições resolvidas por construção: **(a), (b), (c)**.
Restrições atendidas best-effort por seleção de matching: **(d), (e)**.
Restrições otimizadas via RCL: **(f), (g)**.
PRV / (h) não entra — datas vêm na Parte 2.

## 2. Decisão chave — interpretação de (d)

A spec original do orientando descrevia uma "implementação prática"
reusando o matching de R1 em R18 (e de R2 em R19) com mando trocado.
Essa simplificação foi **descartada** porque quebra (b): se R18 reusa
os pares de R1, o par `(A, B)` joga em R1, R18, R20 (=inverso de R1)
e R37 (=inverso de R18), 4 vezes no campeonato.

**Interpretação adotada:**

- R1 e R2 usam matchings distintos do `circle_method`.
- R18 e R19 também usam matchings distintos, escolhidos **depois** da
  RCL ter ocorrido para R3..R17.
- (d) é aplicada **por time**:
  - `side_R18(T) ≈ inverso de side_R1(T)`
  - `side_R19(T) ≈ inverso de side_R2(T)`
- A orientação de R18/R19 é decidida por enumeração das 2¹⁰ opções,
  minimizando um custo agregado de **(d) residual + impacto em (g)**
  da cadeia R17→R18→R19. Em geral, (d) tem violações residuais porque
  os matchings remanescentes raramente são "perfectly bipartite cuts"
  de `sides_r1`/`sides_r2`.

Com essa interpretação, (b) sai por construção (19 matchings distintos
no turno + returno invertido).

## 3. Decisão chave — (c) estrita via 2-coloring

R1 e R2 são tratados juntos: pegamos dois matchings distintos `M_{r1}`
e `M_{r2}`, formamos o grafo `M_{r1} ∪ M_{r2}` (cada vértice com grau 2,
ciclos alternantes de comprimento par → sempre bipartido) e fazemos uma
2-coloração. Cada componente conexa permite duas 2-colorações; sorteamos
uma delas com `rng.random()`.

A 2-coloração determina `sides_r1`; R1 é orientado de acordo, e R2 é
orientado pela inversão (sempre estrita por construção: cada par de R2
tem um time H e um A em R1).

Com isso, **(c) sai estrita** (sem violações residuais).

## 4. Decisão chave — quase-hard (g) na RCL

Na RCL para R3..R17, filtramos candidatos que **não introduzem** violação
de (g). Só se nenhum candidato sem (g) existir é que aceitamos candidatos
com (g) > 0. Peso de (g) na função de custo: **300** (vs. 100 de (f)).

## 5. Decisão chave — reserva de matching limpo para R19

Antes da RCL, **um matching limpo** (sem clássicos estaduais, prioritário
para maior compat com `sides_r2`) é retirado do pool e reservado. Depois
da RCL para R3..R17, ele volta junto com o último matching restante e
ambos são submetidos à seleção R18/R19. Isso garante que R19 quase sempre
seja limpo (ou seja, **(e) atendida** quando há matching limpo disponível
no `circle_method`).

## 6. Algoritmo

```
rng = Random(seed)
matchings = circle_method(teams)           # 19 matchings de 10 pares
```

### Âncoras (R1, R2)

1. Sorteia `r1_idx`, `r2_idx` distintos. Remove ambos do pool.
2. 2-colore o grafo `R1 ∪ R2` → `sides_r1`. Orienta R1 e R2 por essa
   atribuição.

### Reserva para R19

3. Se há matching limpo entre os 17 restantes, escolhe um (max compat
   com `sides_r2`) e move para `r19_reserved`.

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

Reinserimos `r19_reserved` em `remaining`. Os 2 matchings finais são
designados a R18 e R19 por:

1. Determinação da ordem permitida (R19 prefere limpo; se ambos limpos,
   ambas ordens; se um único limpo, esse vira R19; se nenhum limpo, o
   de menor # clássicos vira R19).
2. Para cada ordem permitida, enumeração das 2¹⁰ orientações de R18 e
   escolha da que minimiza `10·d_resid + 1000·g_violations_chain` (a
   cadeia inclui a transição R17→R18). Aplica-se a orientação e
   repete-se para R19 (cadeia R18→R19).
3. A ordem com menor custo total vence; empates resolvidos por `rng`.

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

Levanta `ConstructionFailedError` se `circle_method` não devolver 19
matchings (ex.: número de times != 20) ou se o pool de matchings esgotar
antes de completar 19 rodadas.

## 9. Não-feito nesta fase

- Datas / PRV / (h).
- Integração com `cli.py`.
- Local search (próxima fase do GRASP).

## 10. Bounds empíricos para os testes

Como (d) e (g) são best-effort, os testes correspondentes assertam contra
limites empíricos:

- (a), (b), (c), (e): **zero violações** (estritas).
- (d): até 20 violações (residuais por estrutura dos matchings do
  `circle_method` — perfectly bipartite cuts em R18/R19 são raros).
- (f): até 10 violações no turno.
- (g): até 25 violações no campeonato (meta é zero; tolerância empírica
  para a fase de construção. A local search da Parte 3 do GRASP é quem
  vai refinar).

## 11. Extensão futura

Parte 2 receberá um `MatchesByRound` e atribuirá datas a cada jogo,
otimizando PRV e descanso entre jogos. A assinatura de
`build_matches_with_homes` não muda.

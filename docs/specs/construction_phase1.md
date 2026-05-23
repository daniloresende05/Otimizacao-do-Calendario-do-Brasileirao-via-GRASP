# Spec — Construção, Parte 1 (confrontos e mandos, sem datas)

## 1. Objetivo

Decidir, para o turno (R1–R19), **quem joga contra quem em cada rodada
e quem é mandante**. O returno (R20–R38) é o turno espelhado com mando
invertido. Não há atribuição de datas nesta fase.

Restrições resolvidas por construção: **(a), (b), (c), (d), (e)**.
Restrições otimizadas via RCL: **(f), (g)**.
PRV / (h) não entra — datas vêm na Parte 2.

## 2. Decisão chave — interpretação de (d)

A spec da fase em prompt do orientando descrevia uma "implementação
prática" reusando o matching de R1 em R18 (e de R2 em R19) com mando
trocado. Essa simplificação foi **descartada** porque quebra (b): se
R18 reusa os pares de R1, o par `(A, B)` joga em R1, R18, R20 (=inverso
de R1) e R37 (=inverso de R18), 4 vezes no campeonato.

**Interpretação adotada (confirmada com o orientando):**

- R1, R2, R18, R19 usam **4 matchings distintos** dentre os 19 do
  `circle_method`.
- (d) é aplicada **por time**:
  - `side_R18(T) = inverso de side_R1(T)`
  - `side_R19(T) = inverso de side_R2(T)`
- O matching de R18/R19 é escolhido para **maximizar compatibilidade**
  com a orientação desejada. Se algum par tiver os dois times com o
  mesmo lado desejado, um deles "ganha" a preferência e o outro entra
  como violação residual de (d).

Com essa interpretação, (b) sai por construção (19 matchings distintos
no turno + returno invertido).

## 3. Decisão chave — quase-hard (g) na RCL

Na fase RCL para R3–R17, filtramos candidatos que **não introduzem**
violação de (g). Só se nenhum candidato sem (g) existir é que aceitamos
candidatos com (g). Peso de (g) no custo da construção: **300** (vs.
100 das outras soft) — penaliza fortemente quando não há escapatória.

## 4. Algoritmo

```
rng = Random(seed)
matchings = circle_method(teams)         # 19 matchings de 10 pares
```

### Âncoras

1. **R1**: matching aleatório dos 19. Orientação aleatória balanceada
   (cada par sorteia mando independentemente — 10 home/10 away sai
   automático).
2. **R2**: dos 18 restantes, escolhe o matching com **maior compat**
   (compat = nº de pares cujos dois times têm mando oposto em R1).
   Orienta cada par para que cada time fique no lado oposto ao de R1.
3. **R19**: dos 17 restantes, filtra **matchings limpos** (sem clássico
   estadual). Dentre os limpos, escolhe o de maior compat com a
   inversão desejada (side_R19 = inverso de side_R2). Se nenhum limpo
   existir, fallback: matching com menos clássicos (registra warning).
4. **R18**: dos 16 restantes, escolhe o de maior compat com inversão de
   R1.

### RCL para R3–R17 (15 rodadas)

Para cada `r ∈ {3, ..., 17}`, na ordem:

```
candidatos = []
for matching in matchings_restantes:
    for orientacao in enumerate_orientations(matching):    # 1024 = 2^10
        f_v, g_v = projected_violations(state, orientacao, r, max_consecutive)
        custo = 100 * f_v + 300 * g_v
        candidatos.append((matching, orientacao, custo, g_v))

# Filtro quase-hard de (g)
sem_g = [c for c in candidatos if c.g_v == 0]
pool = sem_g if sem_g else candidatos

# RCL classica
c_min, c_max = min/max custo em pool
threshold = c_min + alpha * (c_max - c_min)
rcl = [c for c in pool if c.custo <= threshold]
escolhido = rng.choice(rcl)
```

`state.apply(escolhido)` atualiza:
- `homes_in_turno[time]`
- `last_side[time]`, `streak[time]` (para detectar (g) na próxima rodada)

### Returno

```
for r in 1..19:
    matches_by_round[r + 19] = [Match(away, home) for Match(home, away) in matches_by_round[r]]
```

(b) por construção.

## 5. Custos auxiliares

### Projected violations de (f)

(f) é `|home_count - away_count| <= 1` no turno. Como cada time joga 19
jogos no turno, `home_count ∈ {9, 10}` é o intervalo factível.

Após aplicar rodada `r` em sequência, time `T` jogou `r` jogos no
turno (cada time joga em toda rodada). Sobram `19 − r` rodadas.

Time `T` está **projetado unfeasible** se:
- `home_count(T) > 10` — não consegue mais derrubar pra ≤ 10, **ou**
- `home_count(T) + (19 − r) < 9` — não consegue mais subir pra ≥ 9.

`f_v` = nº de times projetados unfeasible **após** essa rodada.

### Projected violations de (g)

Para cada `(home, away)` da orientação simulada:
- Se o time já tinha o mesmo `last_side`, incrementa `streak`. Senão,
  reseta para 1.
- Se `streak` excede `max_consecutive`, conta +1 em `g_v`.

`g_v` = nº de times que **passariam** do limite ao aplicar essa rodada.

## 6. API

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
matchings (ex.: número de times != 20).

## 7. Não-feito nesta fase

- Datas / PRV / (h).
- Integração com `cli.py`.
- Local search (próxima fase do GRASP).

## 8. Extensão futura

Parte 2 receberá um `MatchesByRound` e atribuirá datas a cada jogo,
otimizando PRV e descanso entre jogos. A assinatura de
`build_matches_with_homes` não muda.

# Spec — Restrições (`constraints.py`)

## 1. Restrições

| ID  | Descrição                                                                                  | Tipo |
|-----|--------------------------------------------------------------------------------------------|------|
| (a) | Cada time joga 1× por rodada                                                               | hard |
| (b) | Cada par de times se enfrenta 2× com mandos invertidos (double round-robin)                | hard |
| (c) | Nas 2 primeiras rodadas do turno, cada time alterna casa/fora                              | soft |
| (d) | 2 últimas rodadas do turno = espelho das 2 primeiras (mando inverso por time)              | soft |
| (e) | Última rodada do campeonato (R38) sem confronto entre times do mesmo estado                | soft |
| (f) | No turno, `|jogos_casa − jogos_fora| ≤ 1` por time                                          | soft |
| (g) | Máximo 2 jogos consecutivos em casa ou fora (campeonato inteiro)                           | soft |
| (h) | PRV: intervalo ≥ 5 dias entre jogos no mesmo estádio                                       | soft |

A classificação hard/soft acima é a referência. A política de
factibilidade (qual entra em `hard_constraint_violations`) é definida em
`docs/specs/objective.md` e implementada em `evaluate()`. **Esta fase só
move a verificação**; a política hard/soft propriamente dita migra para
`evaluate()` na próxima micro-fase.

## 2. Convenções

- Brasileirão: 38 rodadas.
  - **Turno** = rodadas 1–19.
  - **Returno** = rodadas 20–38.
- 2 primeiras rodadas do turno: R1, R2.
- 2 últimas rodadas do turno: R18, R19.
- Última rodada do campeonato: R38.

## 3. Decisões de design

- **Cada restrição é uma função pura** `Schedule → list[ConstraintViolation]`.
- **(h) delega para `compute_prv` de `objective.py`** para não duplicar
  lógica de PRV. A importação é **local dentro da função** para evitar
  ciclo de import (módulo `objective.py` importa `check_a`/`check_b` de
  `constraints.py`).
- **Registry `CONSTRAINT_CHECKS`** lista pares `(id, função)`. Função
  `check_all` itera o registry e concatena. O registry é o ponto de
  extensão único: para adicionar uma restrição (i), basta criar
  `check_i_...` e estender a lista.
- **`ConstraintViolation` estruturado**: usa `description: str` para
  texto humano, `round/team/stadium: Optional[...]` para filtros e
  relatórios estruturados.

## 4. Detalhes por restrição

### (a) Cada time joga 1× por rodada
Agrupa por rodada. Para cada rodada, marca como visto cada time citado
(como mandante ou visitante). Repetição gera uma violação por ocorrência
duplicada com `round` e `team` preenchidos.

### (b) Double round-robin
- `pair_count[frozenset({A,B})] == 2` (par aparece exatamente 2×).
- `direction_count[(home, away)] ≤ 1` (cada orientação no máximo 1×).
Cada desvio gera uma violação `constraint_id="b"`.

### (c) Alternância em R1–R2
Para cada time, comparar mando em R1 e R2. Se `side_r1 == side_r2`,
violação `(c, team)`.

### (d) Espelho R18–R19 ↔ R1–R2
Para cada time:
- `side_r18 = inverse(side_r1)` ?
- `side_r19 = inverse(side_r2)` ?
Cada desvio gera uma violação `(d, team, round={18|19})`.

### (e) R38 sem confronto intra-estado
Filtrar jogos da R38. Se `home_state == away_state`, violação `(e, round=38)`.

### (f) Balanço casa/fora no turno
Contar jogos como mandante e visitante apenas no turno (R1–R19). Se
`|casa − fora| > 1`, violação `(f, team)`.

### (g) Máx. 2 consecutivos casa/fora
Para cada time, ordenar suas partidas por rodada e detectar runs (séries
de mesmo lado). Toda run de comprimento maior que `max_consecutive`
gera **uma** violação com `round = primeira rodada da run`.

### (h) PRV
Delega para `compute_prv(schedule, prv_days)`. Cada `PRVOccurrence` vira
uma `ConstraintViolation(constraint_id="h", stadium=..., round=match_b.round)`.

## 5. API

```python
def check_a_max_one_game_per_round(schedule: Schedule) -> list[ConstraintViolation]
def check_b_double_round_robin(schedule: Schedule) -> list[ConstraintViolation]
def check_c_first_two_rounds_alternation(schedule: Schedule) -> list[ConstraintViolation]
def check_d_last_two_rounds_mirror(schedule: Schedule) -> list[ConstraintViolation]
def check_e_last_round_no_same_state(schedule: Schedule) -> list[ConstraintViolation]
def check_f_home_away_balance_per_turno(schedule: Schedule) -> list[ConstraintViolation]
def check_g_max_consecutive_home_or_away(
    schedule: Schedule, max_consecutive: int = 2
) -> list[ConstraintViolation]
def check_h_prv(schedule: Schedule, prv_days: int = 5) -> list[ConstraintViolation]

CONSTRAINT_CHECKS: list[tuple[str, Callable[[Schedule], list[ConstraintViolation]]]]
def check_all(schedule: Schedule) -> list[ConstraintViolation]
```

## 6. Extensão

Adicionar restrição (i):

1. Implementar `check_i_...(schedule) -> list[ConstraintViolation]`.
2. Anexar `("i", check_i_...)` ao final de `CONSTRAINT_CHECKS`.
3. Adicionar peso `"i"` ao default em `objective.py`.
4. Documentar aqui a classificação hard/soft.

# Spec — Função objetivo (`objective.py`)

## 1. Definição

Seja `x` um *schedule* (lista de `ScheduledMatch`). A função objetivo é

```
f(x) = Σ_e PRV_e(x)  +  Σ_c w_c · inv_c(x)
```

onde:

- `PRV_e(x)` é o número de **pares de risco em estádio** `e`: pares de
  jogos consecutivos no mesmo estádio cujo intervalo (em dias) é
  estritamente menor que `prv_days` (default `5`).
- `inv_c(x)` é o número de violações da restrição `c`.
- `w_c` é o peso da restrição `c`.

## 2. Política de factibilidade

- As restrições **(a)** (no máximo um jogo por time por rodada) e **(b)**
  (double round-robin) são **hard**: contribuem para
  `hard_constraint_violations` e bloqueiam `is_feasible`.
- **PRV** e as demais restrições são **soft**: contribuem para o custo
  via pesos, mas **não** bloqueiam `is_feasible`.
- `EvaluationResult.is_feasible` é `True` sse `hard_constraint_violations`
  estiver vazio.

## 3. Pesos default

```python
DEFAULT_WEIGHTS = {
    "prv": 1.0,
    "a": 100.0, "b": 100.0, "c": 100.0, "d": 100.0,
    "e": 100.0, "f": 100.0, "g": 100.0,
    "h": 0.0,   # ver §7
}
HARD_CONSTRAINTS = {"a", "b"}
```

Pesos faltantes em `weights=...` herdam de `DEFAULT_WEIGHTS`.

### Por que `w["h"] = 0` por default

A restrição (h) é a checagem registrada de PRV: ela retorna uma
`ConstraintViolation` por ocorrência. Mas o custo de PRV já é
contabilizado pelo termo `w["prv"] * total_prv`. Para evitar dupla
contagem, o peso default de (h) é zero. (h) permanece no registry como
**registro informativo** — `violations_by_type["h"]` ainda reporta a
contagem.

## 4. Cálculo de PRV

Para cada estádio `e`:

1. Filtrar jogos com `match.stadium == e`.
2. Ordenar por data (parsing de `match.day` no formato `"%d/%m/%Y"`).
3. Percorrer pares consecutivos `(m_i, m_{i+1})`. Se
   `(date_{i+1} - date_i).days < prv_days`, registrar uma
   `PRVOccurrence` e incrementar `prv_by_stadium[e]`.

`total_prv` = soma de `prv_by_stadium.values()`.

## 5. Decisão de modelagem — datas

- O parsing de data **fica em `compute_prv`**, on-the-fly, via
  `datetime.strptime(match.day, "%d/%m/%Y")`.
- **Não** se introduz um campo `date: datetime` em `ScheduledMatch`
  nesta fase. Manter `ScheduledMatch.day: str` como única fonte de
  verdade.
- Justificativa: o gargalo de avaliação não é o parsing; preservar a
  imutabilidade/frozen do dataclass é mais valioso que micro-otimizar.

## 6. API

```python
def compute_prv(schedule: Schedule, prv_days: int = 5) -> PRVResult
def evaluate(
    schedule: Schedule,
    weights: dict[str, float] | None = None,
    prv_days: int = 5,
) -> EvaluationResult
```

`evaluate` agrega:

- `compute_prv(schedule, prv_days)` → PRV.
- Itera `CONSTRAINT_CHECKS` (de `constraints.py`); para cada
  `(constraint_id, check_fn)` chama `check_fn(schedule)` (passando
  `prv_days` quando `constraint_id == "h"`).
- `constraint_id ∈ HARD_CONSTRAINTS` → entra em
  `hard_constraint_violations`; demais → `soft_constraint_violations`.
- `violations_by_type[constraint_id] = len(violations)` é preenchido
  para todas as 8 restrições.

```
total_cost = w["prv"] * total_prv
           + Σ_c w[c] * violations_by_type[c]
```

(`w["h"] = 0` por default — ver §3.)

## 7. Compatibilidade

- `add_prv_column(df, prv_days=5)` permanece em `objective.py` em **uma
  única** definição. Internamente chama `compute_prv` e remonta o
  DataFrame. Emite `DeprecationWarning` na primeira linha.
- `cli.py` continua chamando `add_prv_column` por enquanto.

## 8. Extensão futura

Para adicionar uma restrição (i):

1. Implementar `check_i_...(schedule) -> list[ConstraintViolation]` em
   `constraints.py` e anexá-lo a `CONSTRAINT_CHECKS`.
2. Adicionar peso `"i"` em `DEFAULT_WEIGHTS` em `objective.py`.
3. Se hard, incluir `"i"` em `HARD_CONSTRAINTS`.

Nenhuma mudança em `evaluate()` é necessária — ele consome o registry.

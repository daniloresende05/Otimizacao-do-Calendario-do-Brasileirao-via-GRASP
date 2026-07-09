# Codebase Overview — Otimização do Calendário do Brasileirão via GRASP

> Documento gerado por inspeção **somente-leitura** do código atual.
> Objetivo: servir de base factual para a especificação do módulo de busca local
> (`local_search.py`), que **ainda não foi implementado** (ver §8).
>
> Convenção: assinaturas, campos de dataclass e cabeçalhos de CSV são copiados
> **verbatim**. Onde algo não existe, está escrito explicitamente "não presente".

---

## 1. Estrutura de diretórios

Árvore relevante (ignorando `.venv`, `__pycache__`, `.git`, `.pytest_cache`, `*.egg-info`):

```
.
├── pyproject.toml
├── README.md
├── LICENSE
├── demo.py
├── demo_grasp.py
├── data/
│   └── raw/
│       ├── confrontos_brasileirao_2023.csv
│       ├── datas_20-08-2023_a_09-06-2024.csv
│       ├── tabela_real_brasileirao_2023.csv
│       └── teams.csv
├── docs/
│   ├── explicacao_codigo.md
│   ├── codebase-overview.md          (este arquivo)
│   └── specs/
│       ├── audit.md
│       ├── baseline_real.md
│       ├── constraints.md
│       ├── construction_phase1.md
│       ├── construction_phase2.md
│       ├── grasp.md
│       ├── lexicographic.md
│       └── objective.md
├── results/
│   ├── audit_report.txt
│   ├── audit_violations.csv
│   ├── comparison_summary.csv
│   ├── grasp_history.csv
│   ├── schedule.csv
│   └── schedule_grasp.csv
├── scripts/
│   └── audit_violations.py
├── src/
│   └── brasileirao/
│       ├── __init__.py               (vazio, 0 bytes)
│       ├── cli.py
│       ├── constraints.py
│       ├── construction.py
│       ├── domain.py
│       ├── grasp.py
│       ├── initial_solution.py
│       ├── io.py
│       ├── local_search.py           (VAZIO, 0 bytes — ver §8)
│       ├── objective.py
│       ├── real_baseline.py
│       └── round_robin.py
└── tests/
    ├── test_constraints.py
    ├── test_construction_dates.py
    ├── test_construction_matches.py
    ├── test_grasp.py
    ├── test_objective.py
    ├── test_real_baseline.py
    └── test_round_robin.py
```

---

## 2. `pyproject.toml`

```toml
[build-system]
requires = ["setuptools"]
build-backend = "setuptools.build_meta"

[project]
name = "brasileirao"
version = "0.0.0"
dependencies = ["pandas"]

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- **Versão de Python exigida:** **não presente** (não há `requires-python`).
- **Dependências:** apenas `pandas`.
- **Layout do pacote:** `src/` layout (pacote `brasileirao` em `src/brasileirao`).
- **Entry points / `console_scripts`:** **não presente**. Não há `[project.scripts]`
  no `pyproject.toml` nem entry points no `egg-info`. A CLI é executada por módulo
  (ex.: `python -m brasileirao.cli ...`), não por um comando instalado.

---

## 3. Modelo de domínio (`src/brasileirao/domain.py`) — SEÇÃO CRÍTICA

Todas as dataclasses do domínio são `@dataclass(frozen=True)` (imutáveis).

### `Team` — frozen
| Campo | Tipo |
|---|---|
| `name` | `str` |
| `stadium` | `str` |
| `state` | `str` |

### `Match` — frozen
| Campo | Tipo |
|---|---|
| `home` | `str` (nome do time mandante) |
| `away` | `str` (nome do time visitante) |

`Match` representa apenas um confronto com mando, **sem data e sem rodada**. É a
unidade produzida por `build_matches_with_homes` (ver §6).

### `ScheduledMatch` — frozen
| Campo | Tipo | Observação |
|---|---|---|
| `round` | `int` | rodada 1..38 |
| `day` | `str` | data como **string**; comentário do código diz `"2023-08-20"`, mas na prática o pipeline grava no formato `dd/mm/YYYY` (ver §5/§6) |
| `home` | `str` | nome do mandante |
| `away` | `str` | nome do visitante |
| `stadium` | `str` | estádio do mandante |
| `home_state` | `str` | UF do mandante |
| `away_state` | `str` | UF do visitante |

### `PRVOccurrence` — frozen
| Campo | Tipo |
|---|---|
| `stadium` | `str` |
| `match_a` | `ScheduledMatch` (jogo anterior) |
| `match_b` | `ScheduledMatch` (jogo posterior) |
| `days_between` | `int` |

### `PRVResult` — frozen
| Campo | Tipo |
|---|---|
| `total_prv` | `int` |
| `occurrences` | `List[PRVOccurrence]` |
| `prv_by_stadium` | `Dict[str, int]` |

### `ConstraintViolation` — frozen
| Campo | Tipo | Default |
|---|---|---|
| `constraint_id` | `str` | — (ex.: `"a"`..`"h"`) |
| `description` | `str` | — |
| `round` | `Optional[int]` | `None` |
| `team` | `Optional[str]` | `None` |
| `stadium` | `Optional[str]` | `None` |

### `EvaluationResult` — frozen
| Campo | Tipo |
|---|---|
| `total_cost` | `float` |
| `total_prv` | `int` |
| `prv_result` | `PRVResult` |
| `hard_constraint_violations` | `List[ConstraintViolation]` |
| `soft_constraint_violations` | `List[ConstraintViolation]` |
| `violations_by_type` | `Dict[str, int]` |

Métodos / propriedades de `EvaluationResult`:
- `is_feasible` (property) → `bool`: `True` sse não há violações hard.
- `lexicographic_key() -> Tuple[int, int, int]`: retorna `(hard_count,
  soft_estruturais, total_prv)`, onde `soft_estruturais` conta violações soft com
  `constraint_id != "h"`. **Menor tupla = melhor.**
- `is_better_than(other: EvaluationResult) -> bool`: `True` sse a chave lexicográfica
  de `self` é estritamente menor que a de `other`.
- `summary() -> str`: texto multilinha legível.

### Aliases de tipo (definidos no módulo)
```python
Schedule = List[ScheduledMatch]
TeamMap  = Dict[str, Team]
```

**Como uma `Schedule` é representada na prática:** é uma **`list` plana de
`ScheduledMatch`** (não agrupada por rodada). Cada `ScheduledMatch` carrega sua
própria `round`. Um calendário completo do Brasileirão tem **380** elementos
(38 rodadas × 10 jogos).

**O que `TeamMap` mapeia:** `dict[str, Team]` — chave = **nome do time** (`str`),
valor = objeto `Team` com os campos `name`, `stadium`, `state`. É a fonte canônica de
`stadium` e `state` usada em toda a construção e avaliação.

---

## 4. Restrições (`src/brasileirao/constraints.py`)

Constantes do módulo: `TURNO_FIRST = 1`, `TURNO_LAST = 19`, `RETURNO_LAST = 38`.

Cada função recebe uma `Schedule` e **retorna uma lista de `ConstraintViolation`**
(lista vazia = sem violação). Não há funções que retornem `bool` ou contagem `int`
diretamente — todas retornam `List[ConstraintViolation]`.

| Função | Assinatura | Restrição | Retorno |
|---|---|---|---|
| `check_a_max_one_game_per_round` | `(schedule: Schedule) -> List[ConstraintViolation]` | (a) cada time joga no máx. 1× por rodada | `List[ConstraintViolation]` |
| `check_b_double_round_robin` | `(schedule: Schedule) -> List[ConstraintViolation]` | (b) cada par 2× no total; cada direção (casa,fora) no máx. 1× | `List[ConstraintViolation]` |
| `check_c_first_two_rounds_alternation` | `(schedule: Schedule) -> List[ConstraintViolation]` | (c) mando alterna entre R1 e R2 | `List[ConstraintViolation]` |
| `check_d_last_two_rounds_mirror` | `(schedule: Schedule) -> List[ConstraintViolation]` | (d) R18 é espelho de R1 e R19 de R2 (mando invertido por time) | `List[ConstraintViolation]` |
| `check_e_last_round_no_same_state` | `(schedule: Schedule) -> List[ConstraintViolation]` | (e) R38 (`RETURNO_LAST`) sem confronto de mesmo estado | `List[ConstraintViolation]` |
| `check_f_home_away_balance_per_turno` | `(schedule: Schedule) -> List[ConstraintViolation]` | (f) no turno (R1–R19), `|casa − fora| ≤ 1` por time | `List[ConstraintViolation]` |
| `check_g_max_consecutive_home_or_away` | `(schedule: Schedule, max_consecutive: int = 2) -> List[ConstraintViolation]` | (g) no máx. `max_consecutive` jogos consecutivos como mandante/visitante | `List[ConstraintViolation]` |
| `check_h_prv` | `(schedule: Schedule, prv_days: int = 5) -> List[ConstraintViolation]` | (h) PRV: jogos consecutivos no mesmo estádio com intervalo `< prv_days` | `List[ConstraintViolation]` |

Registry e agregador:
```python
CONSTRAINT_CHECKS: List[Tuple[str, Callable[[Schedule], List[ConstraintViolation]]]]
# ordem: [("a", ...), ("b", ...), ("c", ...), ("d", ...),
#         ("e", ...), ("f", ...), ("g", ...), ("h", ...)]

def check_all(schedule: Schedule) -> List[ConstraintViolation]:
    """Executa todas as checagens do registry e concatena resultados."""
```

**Pureza:** todas as funções de checagem são **puras** — sem I/O, sem mutação do
`schedule` de entrada nem de estado global. Usam apenas estruturas locais
(`defaultdict`, `set`, listas locais). Detalhe de implementação: `check_h_prv` faz
um `from .objective import compute_prv` **local** (dentro da função) para evitar
ciclo de import; isso não introduz I/O.

Helpers internos (não exportados como API de restrição): `_inverse_side(side)`,
`_sides_in_round(schedule, target_round)`.

---

## 5. Função objetivo (`src/brasileirao/objective.py`)

### Constantes / parâmetros do módulo
```python
HARD_CONSTRAINTS: set[str] = {"a", "b"}

DEFAULT_WEIGHTS: dict[str, float] = {
    "prv": 1.0,
    "a": 100.0,
    "b": 100.0,
    "c": 100.0,
    "d": 100.0,
    "e": 100.0,
    "f": 100.0,
    "g": 100.0,
    "h": 0.0,   # peso 0 por design: PRV já contabilizado por w["prv"]*total_prv
}

_DATE_FMT = "%d/%m/%Y"   # formato em que `ScheduledMatch.day` é parseado
```

### Como `f(x)` é montada
```
total_cost = w["prv"] * total_prv  +  Σ_c  w[c] * |violations_c|
```
onde `c` percorre todos os `constraint_id` do registry `CONSTRAINT_CHECKS` (a..h).
Pesos faltantes herdam de `DEFAULT_WEIGHTS` (`{**DEFAULT_WEIGHTS, **(weights or {})}`).
Como `w["h"] = 0.0` por padrão, a restrição (h) **não** é somada duas vezes — o custo
de PRV entra exclusivamente pelo termo `w["prv"] * total_prv`.

### Como o PRV é contado (regra exata)
`compute_prv` agrupa os jogos **por estádio** (`match.stadium`). Para cada estádio,
ordena os jogos por `(data, rodada)` e percorre **pares consecutivos** `(earlier,
later)`. Se `(later.day − earlier.day).days < prv_days`, conta **1 PRV** e registra
uma `PRVOccurrence`. `total_prv` = soma sobre todos os estádios.

> Observação importante para a busca local: o PRV é medido entre **jogos
> consecutivos no mesmo estádio ao longo de todo o campeonato** (não por rodada),
> usando a data como string parseada com `_DATE_FMT = "%d/%m/%Y"`. O limiar
> default é `prv_days = 5` (intervalo **estritamente menor** que 5 dias gera PRV).

### Assinaturas públicas
```python
def compute_prv(schedule: Schedule, prv_days: int = 5) -> PRVResult: ...

def evaluate(
    schedule: Schedule,
    weights: dict[str, float] | None = None,
    prv_days: int = 5,
) -> EvaluationResult: ...

def add_prv_column(df: "pd.DataFrame", prv_days: int = 5) -> "pd.DataFrame":
    """DEPRECATED: use compute_prv(schedule)."""
```

`evaluate` itera `CONSTRAINT_CHECKS`: para `"h"` chama `check_fn(schedule,
prv_days=prv_days)`, para as demais `check_fn(schedule)`. Distribui as violações em
`hard` (ids em `HARD_CONSTRAINTS`) e `soft`, preenche `violations_by_type[id] = len(...)`
e devolve um `EvaluationResult`.

`add_prv_column` é a única função do módulo que toca pandas (import local, sob
`DeprecationWarning`); `pandas` é referenciado só em `TYPE_CHECKING` no escopo de módulo.

---

## 6. Construção

Há **dois** construtores no código:

### 6.1 `construction.py` (construtor GRASP atual — usado por `grasp.py`)

Assinaturas públicas:
```python
def build_matches_with_homes(
    teams_map: TeamMap,
    *,
    alpha: float = 0.3,
    seed: int = 42,
    max_consecutive: int = 2,
) -> MatchesByRound: ...

def assign_dates_to_matches(
    matches_by_round: MatchesByRound,
    dates: list[date],
    teams_map: TeamMap,
    *,
    round_gap: int = 7,
    round_span: int = 3,
    prv_days: int = 5,
    min_team_rest_days: int = 3,
) -> Schedule: ...

def construct_schedule(
    teams_map: TeamMap,
    dates: list[date],
    *,
    alpha: float = 0.3,
    seed: int = 42,
    round_gap: int = 7,
    round_span: int = 3,
    prv_days: int = 5,
    min_team_rest_days: int = 3,
    max_consecutive: int = 2,
) -> Schedule: ...
```

**Alias de tipo:** `MatchesByRound = dict[int, list[Match]]`.

**Formato de saída de `build_matches_with_homes`:** um `dict[int, list[Match]]`
mapeando **rodada (1..38) → lista de 10 `Match`** (com mando já definido, sem data).
Resolve por construção (a) e (b); trata (c)(d)(e) como best-effort/estrito conforme o
caso; otimiza (f)/(g) via RCL gulosa-aleatória parametrizada por `alpha`. O returno
(R20–R38) é o espelho do turno com mando invertido:
`Match(home=m.away, away=m.home)`.

**Formato de saída de `assign_dates_to_matches`:** uma `Schedule`
(`list[ScheduledMatch]`, 380 elementos). Atribui uma `date` a cada `Match`
respeitando descanso mínimo de time (`min_team_rest_days`) e minimizando PRV via uma
busca local **interna e restrita a datas** (`_optimize_local_prv`, troca de datas
entre jogos da mesma rodada). O campo `day` é gravado como `d.strftime("%d/%m/%Y")`.

`construct_schedule` é o pipeline: `build_matches_with_homes` → `assign_dates_to_matches`.

Constante do módulo:
```python
CONSTRUCTION_WEIGHTS = {"f": 100.0, "g": 300.0}
```

**Exceções de domínio definidas em `construction.py`:**
- `class ConstructionFailedError(Exception)` — construção esgota matchings sem
  completar as 19 rodadas.
- `class DateAssignmentFailedError(Exception)` — não há atribuição factível
  respeitando descanso.

Funções auxiliares públicas notáveis (úteis para uma futura busca local sobre mandos):
`enumerate_all_orientations`, `no_classico_estadual`, `count_classicos`,
`orient_randomly`, `orient_by_inversion`, `invert_homes`.

> Nota: o `_optimize_local_prv` aqui é um 2-swap **de datas dentro de uma rodada**
> embutido na atribuição; **não** é o módulo de busca local global (`local_search.py`),
> que continua vazio (§8).

### 6.2 `initial_solution.py` (construtor legado — usado pela CLI)

```python
def build_initial_schedule_with_constraints(
    dates_raw: List[str],
    teams_map: Dict[str, object],
    *,
    round_gap: int = 7,
    round_span: int = 3,
    seed: int = 42,
    max_attempts: int = 200_000,
) -> List[ScheduledMatch]: ...
```

Apesar do docstring mencionar (a)–(g), a implementação atual gera apenas um
double round-robin com orientação **aleatória** por rodada (garante (a)/(b);
o bloco que escolhia rodada "limpa" e o backtracking de (c)–(g) estão **comentados**).
Levanta `ValueError` (não as exceções de domínio acima) em entradas inválidas.
É o construtor que a **CLI** chama (ver §10), enquanto o **GRASP** usa
`construct_schedule` de `construction.py`.

---

## 7. GRASP (`src/brasileirao/grasp.py`)

### Estruturas
```python
DEFAULT_ALPHA_POOL: list[float] = [0.1, 0.2, 0.3, 0.4]

@dataclass(frozen=True)
class GRASPIteration:
    iter_number: int
    seed: int
    alpha: float
    total_prv: int
    total_cost: float
    is_feasible: bool
    is_new_best: bool
    lex_key: tuple[int, int, int]

@dataclass
class GRASPResult:
    best_schedule: Schedule
    best_evaluation: EvaluationResult
    best_iter: int
    best_seed: int
    best_alpha: float
    total_iterations: int
    stopped_by: str            # "max_iter" | "max_iter_no_improve"
    history: list[GRASPIteration] = field(default_factory=list)
```

### Laço principal
```python
def grasp(
    teams_map: TeamMap,
    dates: list[date],
    *,
    max_iter: int = 50,
    max_iter_no_improve: int = 20,
    alpha_pool: list[float] | None = None,
    seed: int = 42,
    round_gap: int = 7,
    round_span: int = 3,
    prv_days: int = 5,
    min_team_rest_days: int = 3,
    max_consecutive: int = 2,
    weights: dict[str, float] | None = None,
) -> GRASPResult: ...
```

Comportamento (docstring: *"Loop multi-start do GRASP (Algoritmo 1, **sem busca
local**)"*):

1. Para `i` em `range(max_iter)`: `seed_iter = seed + i`,
   `alpha_iter = rng_alpha.choice(pool)`.
2. Chama **`construct_schedule(teams_map, dates, alpha=alpha_iter, seed=seed_iter,
   round_gap=..., round_span=..., prv_days=..., min_team_rest_days=...,
   max_consecutive=...)`** → `schedule`.
3. `avaliacao = evaluate(schedule, weights=weights, prv_days=prv_days)`.
4. Compara por `avaliacao.is_better_than(best_eval)` (chave lexicográfica).
5. Atualiza melhor / contador `iter_no_improve`; registra `GRASPIteration` no
   `history`; para se `iter_no_improve >= max_iter_no_improve`.

### Onde a busca local se conectaria
**Não presente.** Não há chamada, placeholder, import nem hook para busca local em
`grasp.py`. O ponto de inserção natural seria **entre o passo 2 (construção) e o passo
3 (avaliação)** do laço — isto é, refinar `schedule` antes de `evaluate`. Hoje o fluxo
é construção → avaliação direto.

### Protocols / interfaces
**Não presente.** Não existe nenhum `Protocol`, ABC ou type alias de estratégia
(ex.: `ConstructionStrategy`, `LocalSearchOperator`) em `grasp.py` nem em nenhum outro
módulo do pacote.

---

## 8. Busca local (`src/brasileirao/local_search.py`)

**Existe o arquivo, mas está completamente VAZIO (0 bytes).** Sem código, sem stub,
sem docstring, sem imports, sem TODO. Nada está implementado.

(O único "local search" presente no código é `_optimize_local_prv` dentro de
`construction.py`, que apenas troca **datas** entre jogos da mesma rodada durante a
atribuição — ver §6.1. Não é um operador de vizinhança sobre a `Schedule` global.)

---

## 9. I/O (`src/brasileirao/io.py`)

```python
def load_dates(path: str, col: str = "Data") -> list[str]: ...
def load_teams(path: str) -> TeamMap: ...
def load_matches(path: str, home_col: str = "Mandante", away_col: str = "Visitante"): ...
def select_round_dates(dates_str: list[str], n_rounds: int = 38, gap_days: int = 7) -> list[str]: ...
```

- `load_dates`: lê CSV, exige a coluna `col` (default `"Data"`), retorna as datas como
  **lista de strings** (`dd/mm/aaaa`), sem parsing.
- `load_teams`: lê CSV, **exige as colunas `{"name", "stadium", "state"}`**, constrói
  `TeamMap` (`dict[name -> Team]`).
- `load_matches`: exige colunas `home_col`/`away_col` (defaults `"Mandante"`,
  `"Visitante"`), retorna um `DataFrame` com essas duas colunas como `str`.
- `select_round_dates`: dado o vetor de datas, seleciona `n_rounds` datas espaçadas por
  `gap_days` dias, retornando strings `dd/mm/aaaa`.

**`pandas`:** `io.py` importa `pandas` no topo do módulo. **Não é o único módulo que
usa pandas:** `cli.py` importa `pandas as pd` no topo; `objective.py` usa pandas em
import **local** dentro de `add_prv_column` (e em `TYPE_CHECKING`); vários testes
importam pandas. `real_baseline.py` usa o módulo `csv` da stdlib (não pandas).

### Formato exato dos CSVs

**`data/raw/confrontos_brasileirao_2023.csv`** (380 linhas de dados + cabeçalho;
arquivo com BOM UTF-8):
```
Mandante,Visitante
Fluminense,Athletico-PR
Botafogo,América-MG
Internacional,Palmeiras
```

**`data/raw/datas_20-08-2023_a_09-06-2024.csv`** (295 datas + cabeçalho; BOM UTF-8):
```
Data
20/08/2023
21/08/2023
22/08/2023
...
08/06/2024
09/06/2024
```
Intervalo: **20/08/2023 → 09/06/2024**, 295 datas (uma por dia, formato `dd/mm/aaaa`).

**`data/raw/teams.csv`** (20 times + cabeçalho; BOM UTF-8) — colunas exigidas por
`load_teams`:
```
name,stadium,state
Palmeiras,Allianz Parque,SP
Flamengo,Maracanã,RJ
Corinthians,Neo Química Arena,SP
São Paulo,Morumbi,SP
```

**`data/raw/tabela_real_brasileirao_2023.csv`** (380 jogos + cabeçalho) — lido por
`real_baseline.load_real_schedule_2023` (datas em ISO `YYYY-MM-DD`, normalizadas para
`dd/mm/yyyy`; `stadium`/`state` do CSV são ignorados e substituídos pelo `TeamMap`):
```
round,day,home,away,stadium,home_state,away_state
1,2023-04-15,Athletico-PR,Goiás,Ligga Arena,PR,GO
1,2023-04-16,Flamengo,Coritiba FC,Estádio Jornalista Mário Filho,RJ,
```

**`results/schedule.csv`** (saída da CLI) — cabeçalho verbatim:
```
Rodada,Data,Mandante,Visitante,Estádio,PRV
1,20/08/2023,Sport,Palmeiras,Ilha do Retiro,0
1,20/08/2023,Ceará,São Paulo,Castelão,0
```
(Há também `results/schedule_grasp.csv`, `results/grasp_history.csv`,
`results/comparison_summary.csv`, `results/audit_violations.csv` e
`results/audit_report.txt`, gerados por scripts/demos; não inspecionados em detalhe
aqui pois fora do escopo da spec de busca local.)

---

## 10. CLI (`src/brasileirao/cli.py`)

Executável via `python -m brasileirao.cli` (sem `console_script`). Argumentos via
`argparse`:

| Argumento | Tipo | Default | Descrição |
|---|---|---|---|
| `--dates` | `str` | **obrigatório** | CSV de datas (coluna `Data` em dd/mm/aaaa) |
| `--date-col` | `str` | `"Data"` | nome da coluna de data no CSV |
| `--teams` | `str` | **obrigatório** | `teams.csv` (`name,stadium,state`) |
| `--out` | `str` | `"results/schedule.csv"` | CSV final |
| `--prv-days` | `int` | `5` | intervalo PRV (dias) |
| `--round-gap` | `int` | `7` | dias entre o início de rodadas |
| `--round-span` | `int` | `3` | quantos dias diferentes uma rodada pode usar |
| `--seed` | `int` | `42` | semente RNG |
| `--max-attempts` | `int` | `200000` | tentativas máximas da construção |

> A CLI atual chama **`build_initial_schedule_with_constraints`** (`initial_solution.py`,
> §6.2) e `add_prv_column`/`evaluate`. **Não** expõe os parâmetros do GRASP
> (`alpha`, `max_iter`, `max_iter_no_improve`, `max_consecutive`,
> `min_team_rest_days`, `alpha_pool`, `weights`) — o GRASP (`grasp.py`) é acionado
> programaticamente / por demos, não pela CLI. Logo, dos parâmetros citados no pedido,
> a CLI expõe `seed`, `round_gap`, `round_span`, `prv_days`; **não** expõe `alpha`,
> `min_team_rest_days` nem `max_consecutive`.

---

## 11. Parâmetros e constantes mágicas (consolidado)

| Constante / parâmetro | Valor default | Módulo |
|---|---|---|
| `TURNO_FIRST` | `1` | `constraints.py` |
| `TURNO_LAST` | `19` | `constraints.py` |
| `RETURNO_LAST` | `38` | `constraints.py` |
| `max_consecutive` (param de `check_g`) | `2` | `constraints.py` |
| `prv_days` (param de `check_h`) | `5` | `constraints.py` |
| `HARD_CONSTRAINTS` | `{"a", "b"}` | `objective.py` |
| `DEFAULT_WEIGHTS` | `{prv:1.0, a..g:100.0, h:0.0}` | `objective.py` |
| `_DATE_FMT` | `"%d/%m/%Y"` | `objective.py` |
| `prv_days` (param) | `5` | `objective.py` |
| `CONSTRUCTION_WEIGHTS` | `{"f": 100.0, "g": 300.0}` | `construction.py` |
| `alpha` | `0.3` | `construction.py` |
| `seed` | `42` | `construction.py` / `grasp.py` / `cli.py` / `initial_solution.py` |
| `max_consecutive` | `2` | `construction.py` / `grasp.py` |
| `round_gap` | `7` | `construction.py` / `grasp.py` / `cli.py` / `initial_solution.py` |
| `round_span` | `3` | `construction.py` / `grasp.py` / `cli.py` / `initial_solution.py` |
| `prv_days` | `5` | `construction.py` / `grasp.py` / `cli.py` |
| `min_team_rest_days` | `3` | `construction.py` / `grasp.py` |
| `DEFAULT_ALPHA_POOL` | `[0.1, 0.2, 0.3, 0.4]` | `grasp.py` |
| `max_iter` | `50` | `grasp.py` |
| `max_iter_no_improve` | `20` | `grasp.py` |
| `max_attempts` | `200_000` | `cli.py` / `initial_solution.py` |
| `TEAM_NAME_MAP` | `{Coritiba FC→Coritiba, Cuiabá-MT→Cuiabá, EC Bahia→Bahia, Vasco da Gama→Vasco}` | `real_baseline.py` |
| `BYE` (sentinela ímpar) | `"BYE"` | `round_robin.py` |

---

## 12. Testes (`tests/`)

| Arquivo | Cobre |
|---|---|
| `test_constraints.py` | Todas as checagens (a)–(h) e `check_all`/`CONSTRAINT_CHECKS`. |
| `test_construction_dates.py` | Parte 2 da construção: `construct_schedule` + atribuição de datas e PRV (`compute_prv`). |
| `test_construction_matches.py` | Parte 1 da construção: `build_matches_with_homes` (a/b/c/e estritos; d/g best-effort). |
| `test_grasp.py` | Loop multi-start `grasp` (history, best, critérios de parada). |
| `test_objective.py` | `compute_prv`, `evaluate`, `DEFAULT_WEIGHTS`, `HARD_CONSTRAINTS`, `add_prv_column`. |
| `test_real_baseline.py` | `load_real_schedule_2023` (380 jogos) + avaliação do baseline real. |
| `test_round_robin.py` | `circle_method` (20 times → 19 rodadas de 10 jogos). |

**Comando para rodar:** `pytest -q` (configurado em `[tool.pytest.ini_options]`,
`testpaths = ["tests"]`).

> ⚠️ Importante: `pytest -q` **falha na coleta** (`ModuleNotFoundError: No module
> named 'brasileirao'`) porque o pacote não está instalado em modo editável no
> ambiente atual. Com o `src/` no caminho de import (`PYTHONPATH=src pytest -q`, ou
> após `pip install -e .`) o resultado é:
>
> ```
> 71 passed in 31.67s
> ```

---

## 13. Dados de entrada (`data/raw/`)

| Arquivo | Cabeçalho (verbatim) | Linhas de exemplo | Contagens |
|---|---|---|---|
| `confrontos_brasileirao_2023.csv` | `Mandante,Visitante` | `Fluminense,Athletico-PR` / `Botafogo,América-MG` / `Internacional,Palmeiras` | 380 confrontos (BOM UTF-8) |
| `datas_20-08-2023_a_09-06-2024.csv` | `Data` | `20/08/2023` / `21/08/2023` / `22/08/2023` | 295 datas; intervalo 20/08/2023 → 09/06/2024 (1 por dia) |
| `teams.csv` | `name,stadium,state` | `Palmeiras,Allianz Parque,SP` / `Flamengo,Maracanã,RJ` / `Corinthians,Neo Química Arena,SP` | 20 times |
| `tabela_real_brasileirao_2023.csv` | `round,day,home,away,stadium,home_state,away_state` | `1,2023-04-15,Athletico-PR,Goiás,Ligga Arena,PR,GO` / `1,2023-04-16,Flamengo,Coritiba FC,Estádio Jornalista Mário Filho,RJ,` | 380 jogos; datas em ISO `YYYY-MM-DD` |

---

## 14. Lacunas e pontos de extensão (para a busca local)

**O que falta para a busca local existir:**

1. **`src/brasileirao/local_search.py` está vazio** — todo o módulo precisa ser
   escrito do zero. Não há stub, função, classe nem assinatura de referência.
2. **Não há `Protocol`/interface** de operador de busca local em lugar nenhum
   (confirmado em §7). Se a spec quiser uma abstração (`LocalSearchOperator`,
   `Neighborhood`, etc.), ela é nova.
3. **`grasp.py` não chama busca local** e não tem ponto de extensão pronto: seria
   preciso editar o laço de `grasp()` para inserir o refinamento.

**Onde a busca local precisaria se plugar (assinatura que `grasp.py` esperaria chamar):**

No laço de `grasp()`, hoje:
```python
schedule = construct_schedule(...)          # (passo 2)
avaliacao = evaluate(schedule, weights=weights, prv_days=prv_days)   # (passo 3)
```
O encaixe natural é entre esses dois passos, com um operador que receba uma
`Schedule` (e o contexto de avaliação) e devolva uma `Schedule` melhorada. Assinatura
plausível, **a ser definida pela spec** (nada disso existe no código hoje):
```python
def local_search(
    schedule: Schedule,
    teams_map: TeamMap,
    *,
    weights: dict[str, float] | None = None,
    prv_days: int = 5,
    max_consecutive: int = 2,
    min_team_rest_days: int = 3,
    # ... critérios de parada do operador
) -> Schedule: ...
```
Insumos já disponíveis e reutilizáveis pela busca local:
- **Avaliação/objetivo:** `objective.evaluate` (retorna `EvaluationResult` com
  `lexicographic_key`/`is_better_than`) e `objective.compute_prv`.
- **Restrições incrementais:** funções `check_*` em `constraints.py` (todas puras,
  retornam `List[ConstraintViolation]`).
- **Representação:** `Schedule = list[ScheduledMatch]` (frozen) — operadores de
  vizinhança precisarão reconstruir `ScheduledMatch` (imutável) ao mover datas/mandos.
- **Helpers de orientação de mando:** `enumerate_all_orientations`, `invert_homes`,
  `orient_by_inversion`, `no_classico_estadual`, `count_classicos` em `construction.py`.
- **Critério de comparação:** lexicográfico `(hard, soft_estruturais, total_prv)` via
  `EvaluationResult` (menor é melhor).

---

## Arquivos lidos para montar este documento

- `c:\Users\Danilo\Desktop\Otimizacao-do-Calendario-do-Brasileirao-via-GRASP\pyproject.toml`
- `...\src\brasileirao\__init__.py`
- `...\src\brasileirao\domain.py`
- `...\src\brasileirao\constraints.py`
- `...\src\brasileirao\objective.py`
- `...\src\brasileirao\construction.py`
- `...\src\brasileirao\initial_solution.py`
- `...\src\brasileirao\grasp.py`
- `...\src\brasileirao\local_search.py`
- `...\src\brasileirao\io.py`
- `...\src\brasileirao\cli.py`
- `...\src\brasileirao\round_robin.py`
- `...\src\brasileirao\real_baseline.py`
- `...\src\brasileirao.egg-info\` (SOURCES/requires/top_level — verificação de entry points)
- `...\tests\test_constraints.py`, `test_construction_dates.py`,
  `test_construction_matches.py`, `test_grasp.py`, `test_objective.py`,
  `test_real_baseline.py`, `test_round_robin.py`
- `...\data\raw\confrontos_brasileirao_2023.csv`
- `...\data\raw\datas_20-08-2023_a_09-06-2024.csv`
- `...\data\raw\teams.csv`
- `...\data\raw\tabela_real_brasileirao_2023.csv`
- `...\results\schedule.csv`

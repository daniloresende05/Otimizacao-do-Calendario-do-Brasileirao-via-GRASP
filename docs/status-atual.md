# Status atual do projeto — retrato fiel (2026-07-22)

> Documento gerado por inspeção somente-leitura do repositório. Assinaturas e nomes
> copiados verbatim do código. Onde algo não existe, está escrito "não existe".

## Resumo git

- **Branch:** `main` (up to date com `origin/main`)
- **Alterações não commitadas:** nenhuma — working tree limpo (`nothing to commit, working tree clean`)
- **Últimos commits (`git log --oneline -15`):**
  ```
  975622b Merge origin/main: reconcilia divergencia (mantem arvore sem .venv/__pycache__)
  6484ea2 Alteracoes das movimentacoes e limpeza de artefatos
  ff82ac9 Remove .venv do versionamento e adiciona .gitignore
  37907f8 Alterações das movimentações
  1f294ab Busca Local, movimentos e ILS
  d07cf13 Finalizando o GRASP
  b4598f7 Minha mensagem
  3a4335d Segunda parte: Primeira restrição
  6d60ec6 Segunda parte do projeto, entendendo o código e implementando
  d3e442a estrutura inicial do projeto
  ```
  (Total de 10 commits no histórico — o `-15` não trouxe mais que isso.)

---

## 1. Suíte de testes

Comando: `PYTHONPATH=src pytest -q`

**Resultado: `1 failed, 115 passed in 51.92s`** — a suíte **NÃO está 100% verde**.

- **Skipped:** nenhum (0).
- **Failed:** 1.

### Teste vermelho

| Teste | Motivo |
|---|---|
| `tests/test_ils.py::test_ca12_runs_fast` | **Falha de performance (timing), não de correção.** O teste roda 5 seeds × 2 fixtures de `iterated_local_search` e exige `elapsed < 5.0s`. Mediu **5.36s** → `AssertionError: ILS lento demais: 5.36s` (`assert 5.358... < 5.0`). É um limite de tempo apertado que estourou nesta máquina; a lógica do ILS executou até o fim. Provável flakiness dependente de hardware/carga. |

Os demais 115 testes passam.

---

## 2. Módulos em `src/brasileirao/`

Todos os arquivos abaixo **existem**. Nenhum está vazio ou é stub, **exceto `__init__.py`**.

### `__init__.py`
- **Existe, vazio** (1 linha em branco / sem conteúdo). Sem re-exports.

### `domain.py` — implementado
Modelos de dados (dataclasses `frozen`). Responsabilidade: tipos do domínio e a estrutura de avaliação.
- Dataclasses: `Team(name, stadium, state)`, `Match(home, away)`, `ScheduledMatch(round, day, home, away, stadium, home_state, away_state)`, `PRVOccurrence`, `PRVResult`, `ConstraintViolation`, `EvaluationResult`.
- Aliases: `Schedule = List[ScheduledMatch]`, `TeamMap = Dict[str, Team]`.
- Métodos/propriedades públicas de `EvaluationResult`:
  - `is_feasible` (property) `-> bool`  — `True` se não há violações hard.
  - `lexicographic_key(self) -> Tuple[int, int, int]` — `(hard, soft_estruturais, prv)`; soft_estruturais **exclui** `constraint_id == "h"`.
  - `is_better_than(self, other: "EvaluationResult") -> bool` — estritamente melhor (lex `<`).
  - `summary(self) -> str`.

### `round_robin.py` — implementado
Responsabilidade: gerar as 19 rodadas do turno (método do círculo).
- `def circle_method(teams: List[str]) -> List[List[Pair]]` — `Pair = Tuple[str, str]`.

### `io.py` — implementado
Responsabilidade: carregar CSVs de datas/times/confrontos (via pandas) e selecionar datas de rodada.
- `def load_dates(path: str, col: str = "Data") -> list[str]`
- `def load_teams(path: str) -> TeamMap`
- `def load_matches(path: str, home_col: str = "Mandante", away_col: str = "Visitante")`
- `def select_round_dates(dates_str: list[str], n_rounds: int = 38, gap_days: int = 7) -> list[str]`

### `construction.py` — implementado (núcleo da construção GRASP)
Responsabilidade: construir confrontos com mando (duplo round-robin) via RCL gulosa-aleatória e atribuir datas minimizando PRV. **Nota:** o arquivo estava selecionado no editor do usuário.
Funções públicas:
- `def enumerate_all_orientations(pairs: list[tuple[str, str]]) -> Iterator[list[tuple[str, str]]]`
- `def no_classico_estadual(pairs: list[tuple[str, str]], teams_map: TeamMap) -> bool`
- `def count_classicos(pairs: list[tuple[str, str]], teams_map: TeamMap) -> int`
- `def orient_randomly(pairs: list[tuple[str, str]], rng: random.Random) -> list[tuple[str, str]]`
- `def orient_by_inversion(pairs: list[tuple[str, str]], reference_oriented: list[tuple[str, str]]) -> list[tuple[str, str]]`
- `def invert_homes(oriented: list[tuple[str, str]]) -> list[tuple[str, str]]`
- `def build_matches_with_homes(teams_map: TeamMap, *, alpha: float = 0.3, seed: int = 42, max_consecutive: int = 2) -> MatchesByRound`
- `def assign_dates_to_matches(matches_by_round: MatchesByRound, dates: list[date], teams_map: TeamMap, *, round_gap: int = 7, round_span: int = 3, prv_days: int = 5, min_team_rest_days: int = 3) -> Schedule`
- `def construct_schedule(teams_map: TeamMap, dates: list[date], *, alpha: float = 0.3, seed: int = 42, round_gap: int = 7, round_span: int = 3, prv_days: int = 5, min_team_rest_days: int = 3, max_consecutive: int = 2) -> Schedule`
- Exceções: `class ConstructionFailedError(Exception)`, `class DateAssignmentFailedError(Exception)`.
- (Helpers privados: `_two_color_pair_union`, `_pick_r18_r19`, `_pick_best_compat`, `_try_balanced_distribution`, `_try_flexible_distribution`, `_optimize_local_prv`, etc.)

### `initial_solution.py` — implementado, mas **parcial/legado**
Responsabilidade declarada na docstring: construir calendário factível em (a)-(g). **Porém o código efetivo garante apenas (a)/(b)**: um bloco que escolheria rodada "limpa" está comentado, e o comentário no corpo diz `Somente restrição (a): double round-robin ... (sem (c)(d)(e)(f)(g), sem backtracking)`. Escolhe orientação aleatória por rodada (`rng.choice`). É o construtor usado pela **CLI** (não o `construction.py`).
- `def build_initial_schedule_with_constraints(dates_raw: List[str], teams_map: Dict[str, object], *, round_gap: int = 7, round_span: int = 3, seed: int = 42, max_attempts: int = 200_000) -> List[ScheduledMatch]`
  - Contém helpers internos definidos mas **não usados** no caminho ativo (`force_orientation`, `apply_round`, `feasible_home_bounds`, `oriented_to_side`) — resquícios de uma versão com backtracking.

### `constraints.py` — implementado
Responsabilidade: checagens (a)-(j). Ver seção 3.
Funções públicas (checagens):
- `def check_a_max_one_game_per_round(schedule: Schedule) -> List[ConstraintViolation]`
- `def check_b_double_round_robin(schedule: Schedule) -> List[ConstraintViolation]`
- `def check_c_first_two_rounds_alternation(schedule: Schedule) -> List[ConstraintViolation]`
- `def check_d_last_two_rounds_mirror(schedule: Schedule) -> List[ConstraintViolation]`
- `def check_e_last_round_no_same_state(schedule: Schedule) -> List[ConstraintViolation]`
- `def check_f_home_away_balance_per_turno(schedule: Schedule) -> List[ConstraintViolation]`
- `def check_g_max_consecutive_home_or_away(schedule: Schedule, max_consecutive: int = 2) -> List[ConstraintViolation]`
- `def check_h_prv(schedule: Schedule, prv_days: int = 5) -> List[ConstraintViolation]`
- `def check_i_span_rodada(schedule: Schedule) -> List[ConstraintViolation]`
- `def check_j_sem_encavalamento(schedule: Schedule) -> List[ConstraintViolation]`
- `def check_span_rodada(schedule: Schedule, teams_map: TeamMap | None = None) -> int` (wrapper de contagem de `check_i`)
- `def check_sem_encavalamento(schedule: Schedule, teams_map: TeamMap | None = None) -> int` (wrapper de contagem de `check_j`)
- `def check_all(schedule: Schedule) -> List[ConstraintViolation]`
- Registry: `CONSTRAINT_CHECKS` (lista de `(id, fn)` de "a" a "j").

### `objective.py` — implementado
Responsabilidade: função-objetivo `f(x)`, contagem de PRV, avaliação lexicográfica.
- `def compute_prv(schedule: Schedule, prv_days: int = 5) -> PRVResult`
- `def evaluate(schedule: Schedule, weights: dict[str, float] | None = None, prv_days: int = 5) -> EvaluationResult`
- `def add_prv_column(df: "pd.DataFrame", prv_days: int = 5) -> "pd.DataFrame"` — **marcada DEPRECATED** (emite `DeprecationWarning`); ainda usada pela CLI.
- Constantes: `HARD_CONSTRAINTS: set[str] = {"a", "b", "i", "j"}`, `DEFAULT_WEIGHTS` (com `"h": 0.0`).

### `local_search.py` (VND) — implementado
Responsabilidade: busca local Variable Neighborhood Descent. Ver seção 4.
- `def swap_homes(schedule, teams_map, *, frozen_rounds=FROZEN_ROUNDS, min_team_rest_days=3) -> list[Schedule]`
- `def swap_days(schedule, teams_map, *, frozen_rounds=FROZEN_ROUNDS, min_team_rest_days=3) -> list[Schedule]`
- `def descend(schedule, teams_map, neighborhood, *, weights=None, prv_days=5, min_team_rest_days=3) -> Schedule`
- `def local_search(schedule, teams_map, *, neighborhoods=None, weights=None, prv_days=5, max_consecutive=2, min_team_rest_days=3, max_iter_no_improve=50, seed=42) -> Schedule`
- Constantes: `FROZEN_ROUNDS = frozenset({1, 2, 18, 19, 20, 21, 37, 38})`, `DEFAULT_NEIGHBORHOODS = ["swap_homes", "swap_days"]`, `NEIGHBORHOODS = {"swap_homes": swap_homes, "swap_days": swap_days}`.

### `ils.py` — implementado
Responsabilidade: Iterated Local Search como pós-otimização; usa o VND como caixa-preta.
- `def perturb(schedule, teams_map, k, rng, *, neighborhoods=None, min_team_rest_days=3) -> Schedule`
- `def next_k(k, *, improved, perturbation_min, perturbation_step, perturbation_max) -> int`
- `def iterated_local_search(schedule, teams_map, *, neighborhoods=None, weights=None, prv_days=5, min_team_rest_days=3, perturbation_min=1, perturbation_step=1, perturbation_max=5, max_iter_no_improve=20, max_iter=200, seed=42) -> Schedule`

### `grasp.py` — implementado
Responsabilidade: loop multi-start do GRASP (Algoritmo 1). **Sem busca local** (só construção + avaliação).
- `def grasp(teams_map, dates, *, max_iter=50, max_iter_no_improve=20, alpha_pool=None, seed=42, round_gap=7, round_span=3, prv_days=5, min_team_rest_days=3, max_consecutive=2, weights=None) -> GRASPResult`
- Dataclasses: `GRASPIteration` (frozen), `GRASPResult`.
- Constante: `DEFAULT_ALPHA_POOL = [0.1, 0.2, 0.3, 0.4]`.

### `real_baseline.py` — implementado
Ver seção 7.
- `def load_real_schedule_2023(csv_path: str, teams_map: TeamMap) -> Schedule`
- `TEAM_NAME_MAP: dict[str, str]` (normalização de nomes).

### `cli.py` — implementado
Ver seção 5.
- `def main()` — ponto de entrada do argparse.

---

## 3. Restrições implementadas (`constraints.py`)

| id | Função | Verifica |
|---|---|---|
| **a** | `check_a_max_one_game_per_round` | Cada time joga no máximo 1× por rodada. |
| **b** | `check_b_double_round_robin` | Cada par se enfrenta 2× no total; cada direção (casa,fora) no máximo 1×. |
| **c** | `check_c_first_two_rounds_alternation` | Mando alterna entre R1 e R2 (quem foi casa em R1, é fora em R2). |
| **d** | `check_d_last_two_rounds_mirror` | R18 é espelho (mando invertido) de R1; R19 espelho de R2. |
| **e** | `check_e_last_round_no_same_state` | Na R38 (última do returno) não há confronto de mesmo estado. |
| **f** | `check_f_home_away_balance_per_turno` | No turno (R1-R19), `|casa - fora| <= 1` por time. |
| **g** | `check_g_max_consecutive_home_or_away` | No máximo `max_consecutive` (default 2) jogos consecutivos como mandante/visitante. |
| **h** | `check_h_prv` | Conta PRVs (delega a `compute_prv`); intervalo `< prv_days` no mesmo estádio. |
| **i** | `check_i_span_rodada` | Span da rodada `<= 2` dias (janela de 3 dias de calendário: D, D+1, D+2). |
| **j** | `check_j_sem_encavalamento` | Rodadas consecutivas não encavalam: maior data de `r` deve ser **estritamente** anterior à menor de `r+1` (mesmo dia na fronteira viola). |

### Hard vs. soft (`objective.py`)
- **`HARD_CONSTRAINTS = {"a", "b", "i", "j"}`** → contam para `hard_constraint_violations`.
- **Soft** (peso default 100.0, exceto h=0.0): `c, d, e, f, g, h`.
- **Confirmação pedida:** `check_i_span_rodada` (regra i / `span_rodada`) e `check_j_sem_encavalamento` (regra j / `sem_encavalamento`) **estão presentes E são HARD** (ambos em `HARD_CONSTRAINTS`). Existem também os wrappers de contagem `check_span_rodada` e `check_sem_encavalamento`.
- Detalhe da chave lex: `lexicographic_key()` = `(hard, soft_estruturais, total_prv)`, onde `soft_estruturais` conta soft **exceto** `h` (PRV entra separado como 3º componente).

---

## 4. Movimentos / vizinhanças da busca local (`local_search.py`)

Existem **dois** movimentos (v1), registrados em `NEIGHBORHOODS`:

1. **`swap_homes`** — para cada confronto (par de times), inverte o mando de **todas as pernas** simultaneamente (preserva o duplo turno / constraint b). Não altera datas. Pula confrontos que toquem rodada congelada; descarta vizinhos que violem `min_team_rest_days`.

2. **`swap_days`** — troca a **data** entre dois jogos **da mesma rodada**.

### Resposta à pendência: `swap_days` move para datas VAZIAS ou só permuta datas em uso?
**Só permuta datas já em uso.** Confirmado no código ([local_search.py:181-216](../src/brasileirao/local_search.py#L181-L216)): itera pares de jogos `(i, j)` da mesma rodada e chama `_swap_days_between`, que faz `neighbor[i] = _with_day(schedule[i], schedule[j].day)` e vice-versa — apenas **troca** as duas datas existentes entre si. A própria docstring afirma: *"como só permuta datas já presentes, nenhum jogo sai da janela"*. **NÃO existe** movimento que realoque um jogo para uma data vazia/livre da janela. → **Essa pendência (swap_days para datas vazias) NÃO foi feita.**

Detalhes do motor VND:
- `FROZEN_ROUNDS = {1, 2, 18, 19, 20, 21, 37, 38}` — âncoras nunca tocadas por nenhum movimento.
- `descend`: best-improvement em UMA vizinhança até ótimo local.
- `local_search`: percorre `DEFAULT_NEIGHBORHOODS` em ordem; se uma melhora, volta à primeira; determinístico (best-improvement, `seed` aceito só por contrato).

---

## 5. Pipeline de execução — como as peças se conectam HOJE

### O que a CLI (`cli.py`) realmente executa
`main()` faz:
1. `load_dates` + `load_teams` (io.py).
2. `build_initial_schedule_with_constraints(...)` — **de `initial_solution.py`**, ou seja, o construtor **legado que só garante (a)/(b)** (orientação aleatória, sem (c)-(g)).
3. `add_prv_column(df, ...)` (**função DEPRECATED**) para marcar PRV, renomeia colunas, salva CSV.
4. `evaluate(schedule, ...)` e imprime `summary()`.

### Conexões e o que está solto
- **A CLI NÃO usa `construction.py`, NÃO usa `grasp()`, NÃO usa `local_search`/VND, NÃO usa `iterated_local_search`.** Ela roda apenas o construtor legado + PRV + avaliação.
- **`grasp()` NÃO chama busca local** — é só o loop multi-start de construção (`construct_schedule` + `evaluate`). Isso é explícito na docstring: *"Loop multi-start do GRASP (Algoritmo 1, **sem busca local**)"*.
- **`iterated_local_search` NÃO é chamado em nenhum fluxo de produção** (nem `cli.py`, nem `grasp.py`). É invocado apenas por:
  - `tests/test_ils.py`
  - `scripts/demo_prv.py` (script de diagnóstico)
- **`local_search` (VND)** também não está no fluxo de produção; é chamado por `tests/` e por `scripts/demo_prv.py` (onde é aplicado **manualmente** sobre o melhor do GRASP).

**Resumo:** o encadeamento "produção" real hoje = **CLI → construtor legado (a/b) → PRV → evaluate**. Todo o miolo do método (construção GRASP de `construction.py`, GRASP multi-start, VND, ILS) existe e é testado, mas **está desconectado** — só se conecta ponta a ponta dentro do script de demo `scripts/demo_prv.py`, não na CLI.

---

## 6. Scripts e demos

- **`scripts/demo_prv.py`** — script de **diagnóstico** (não é produção). Encadeia o pipeline completo no dataset real 2023: baseline real → `construct_schedule` → `grasp` (modo demo, poucas iters) → `local_search` (VND aplicado manualmente sobre o melhor do GRASP) → `iterated_local_search` (ILS). Imprime PRV em cada etapa e um quadro-resumo. **É o único lugar que conecta construção→GRASP→VND→ILS ponta a ponta.** Usa `max_iter` reduzido porque cada `local_search` no dataset real leva ~30s.
- **`scripts/audit_violations.py`** — auditoria: roda 50 iterações do GRASP (seed=42), tabula violações de (d), (f), (g) por iteração, detalha a iteração campeã e grava `results/audit_violations.csv` + `results/audit_report.txt`.
- **`demo.py`** (raiz) — demo rápida: `construct_schedule(seed=42)` + `compute_prv`, imprime PRV por estádio.
- **`demo_grasp.py`** (raiz) — demo do GRASP multi-start (50 iters): compara real 2023 × construção única × melhor do GRASP, detalha violações (d)/(f)/(g), exporta `results/schedule_grasp.csv`, `results/grasp_history.csv`, `results/comparison_summary.csv`. Mensagem final ainda diz *"Proxima fase: implementar busca local com as 4 vizinhancas (swap_days, swap_homes, swap_teams, replace_teams)"* — indício de que o plano previa 4 movimentos (só 2 existem).

---

## 7. Baseline real da CBF

**Existe**, em `src/brasileirao/real_baseline.py`:
- `def load_real_schedule_2023(csv_path: str, teams_map: TeamMap) -> Schedule`
- **Retorna:** uma `Schedule` (lista de `ScheduledMatch`) da tabela real do Brasileirão 2023.
- Normalizações: aplica `TEAM_NAME_MAP` aos nomes e confirma em `teams_map`; usa `stadium`/estados de `teams_map` (ignora os do CSV); converte `day` de ISO (`YYYY-MM-DD`) para `dd/mm/YYYY`.
- CSV esperado: `data/raw/tabela_real_brasileirao_2023.csv` (referenciado por `demo_prv.py`, `demo_grasp.py`, `audit`). Testado em `tests/test_real_baseline.py`.

---

## 8. Pendências visíveis no código (TODO/FIXME/etc.)

Busca por `TODO|FIXME|PROVIS|XXX|HACK|stub|placeholder|WIP|pendente|não implementado` no repo (excluindo `.venv`):

- **Nenhum marcador `TODO`/`FIXME`/`XXX`/`HACK` real no código-fonte de `src/`.** Os hits do grep foram falsos positivos (palavras como "todo"/"todos" em português dentro de docstrings).
- Pendências **implícitas** (não marcadas como TODO, mas evidentes):
  - `initial_solution.py`: bloco de escolha de rodada "limpa" **comentado**; comentário `Somente restrição (a) ... (sem (c)(d)(e)(f)(g), sem backtracking)`. Helpers `force_orientation`/`apply_round`/`feasible_home_bounds` definidos e não usados.
  - `objective.add_prv_column`: marcada **DEPRECATED** mas ainda usada pela CLI.
  - `demo_grasp.py` (mensagem final): menciona 4 vizinhanças planejadas (`swap_days, swap_homes, swap_teams, replace_teams`) — só 2 existem.
- **`docs/codebase-overview.md` está DESATUALIZADO:** afirma que `local_search.py` está "completamente VAZIO (0 bytes)" e que não há busca local — isso **não é mais verdade** (VND e ILS estão implementados e testados). Tratar esse doc como histórico, não como retrato atual.

---

## 9. Lista consolidada de "o que falta" (evidenciado pelo código)

1. **Integração ILS → produção:** `iterated_local_search` não é chamado por `cli.py` nem por `grasp.py`; só por testes e pelo script de demo. Falta plugá-lo no fluxo real.
2. **Integração VND → GRASP:** `grasp()` não chama `local_search`. O "GRASP+busca local" (Algoritmo 2) só acontece manualmente dentro de `demo_prv.py`. Falta o GRASP chamar o VND internamente.
3. **CLI desatualizada:** `cli.py` usa o construtor **legado** `build_initial_schedule_with_constraints` (só (a)/(b)) em vez de `construct_schedule` / `grasp` / VND / ILS. A CLI não expõe o método real do TCC.
4. **`swap_days` com datas vazias: NÃO feito.** Hoje só permuta datas já em uso dentro da rodada; não realoca jogo para data livre da janela.
5. **Movimentos de vizinhança faltantes:** o plano (mensagem em `demo_grasp.py`) previa `swap_teams` e `replace_teams` além de `swap_homes`/`swap_days`. Só os 2 primeiros existem.
6. **`initial_solution.py` incompleto:** docstring promete (a)-(g), mas o caminho ativo garante só (a)/(b); lógica de (c)-(g)/backtracking está comentada ou morta.
7. **`add_prv_column` DEPRECATED ainda em uso** na CLI — substituir por `compute_prv`.
8. **Teste vermelho de performance:** `test_ca12_runs_fast` estoura o limite de 5s (mediu 5.36s). Falta ou otimizar o ILS ou relaxar/ajustar o limite do teste.
9. **Doc `codebase-overview.md` obsoleto** — descreve estado anterior (local_search vazio); precisa ser reescrito ou marcado como histórico.

---

## Arquivos lidos para este relatório

- `src/brasileirao/__init__.py`
- `src/brasileirao/domain.py`
- `src/brasileirao/round_robin.py`
- `src/brasileirao/io.py`
- `src/brasileirao/initial_solution.py`
- `src/brasileirao/construction.py`
- `src/brasileirao/constraints.py`
- `src/brasileirao/objective.py`
- `src/brasileirao/local_search.py`
- `src/brasileirao/ils.py`
- `src/brasileirao/grasp.py`
- `src/brasileirao/real_baseline.py`
- `src/brasileirao/cli.py`
- `scripts/demo_prv.py`
- `scripts/audit_violations.py`
- `demo.py`
- `demo_grasp.py`

Comandos executados (somente-leitura): `git status`, `git log --oneline -15`, `PYTHONPATH=src pytest -q`, e greps por marcadores TODO/FIXME.
</content>
</invoke>

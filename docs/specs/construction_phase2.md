# Spec — Construção, Parte 2 (atribuição de datas)

## Status: Esboço

Refinamentos futuros incluem dia da semana, gap variável entre rodadas, e
regras de segunda-feira. Este esboço valida o pipeline end-to-end.

## 1. Objetivo

Receber um `MatchesByRound` (saída da Parte 1) e uma lista de `date` e
produzir um `Schedule` (lista de `ScheduledMatch`) atribuindo uma data a
cada jogo.

## 2. Restrições

- **Hard**: cada time tem >= `min_team_rest_days` (default 3) dias entre
  partidas consecutivas. Atribuições que violam são descartadas.
- **Soft (objetivo)**: minimizar total de PRVs (jogos no mesmo estádio com
  intervalo < `prv_days` dias, default 5).

Nenhuma outra restrição é tratada nesta fase.

## 3. Estratégia — Opção A (determinística com otimização local)

### 3.1. Janela por rodada

Para rodada `r` (1–38), a janela de datas é:

```
base_idx = (r - 1) * round_gap
janela = dates[base_idx : base_idx + round_span]
```

Default: `round_gap=7`, `round_span=3` → janela de 3 dias consecutivos,
com 7 dias entre inícios de rodada.

### 3.2. Distribuição balanceada

Distribui os 10 jogos da rodada de forma balanceada (`ceil(10/round_span)`
por data). Para cada jogo, escolhe a data com menos jogos atribuídos que
respeite o descanso mínimo de ambos os times.

Se nenhuma data válida com capacidade existe para algum jogo, cai para
distribuição flexível.

### 3.3. Distribuição flexível (fallback)

Aceita distribuição desbalanceada: para cada jogo, atribui a primeira data
da janela que respeite descanso. Se nenhuma data serve, levanta
`DateAssignmentFailedError`.

### 3.4. Otimização local (2-opt intra-rodada)

Após distribuir, tenta trocar datas entre pares de jogos na rodada. Aceita
a troca se:
- reduz PRV total na rodada (contra o histórico de jogos já atribuídos)
- não viola descanso de nenhum time

Itera até nenhuma troca melhorar.

## 4. API

```python
def assign_dates_to_matches(
    matches_by_round: MatchesByRound,
    dates: list[date],
    teams_map: TeamMap,
    *,
    round_gap: int = 7,
    round_span: int = 3,
    prv_days: int = 5,
    min_team_rest_days: int = 3,
) -> Schedule

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
) -> Schedule
```

`construct_schedule` orquestra Parte 1 (`build_matches_with_homes`) +
Parte 2 (`assign_dates_to_matches`).

## 5. Não-feito nesta fase

- Preferência por dia da semana (sábado/domingo).
- Gap variável entre rodadas.
- Regras de segunda-feira / sexta-feira.
- Integração com `cli.py`.

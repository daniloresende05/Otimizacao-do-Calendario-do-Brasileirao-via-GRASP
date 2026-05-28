# Spec — Baseline Real (Brasileirao 2023)

## Objetivo

Comparar os schedules gerados pelo GRASP com a tabela real do Brasileirao 2023
para ter um ponto de referencia concreto.

## Arquivo de entrada

`data/raw/tabela_real_brasileirao_2023.csv` — 380 jogos, 38 rodadas, 20 times.

## Normalizacoes aplicadas

1. **Nomes de times**: `TEAM_NAME_MAP` mapeia nomes do CSV para nomes canonicos
   do `teams.csv`:
   - "Coritiba FC" -> "Coritiba"
   - "Cuiaba-MT" -> "Cuiaba"
   - "EC Bahia" -> "Bahia"
   - "Vasco da Gama" -> "Vasco"

2. **Estadio**: IGNORA o estadio do CSV; usa `teams_map[home].stadium`.
   Motivo: o GRASP atribui 1 estadio por time; comparacao justa exige isso.

3. **home_state / away_state**: usa `teams_map`, ignora CSV.

4. **Datas**: converte ISO (YYYY-MM-DD) para dd/mm/yyyy.

## Atualizacao do teams.csv

O `teams.csv` foi atualizado para o elenco do Brasileirao 2023:
- Removidos: Ceara, Vitoria, Sport (nao participaram em 2023).
- Adicionados: America-MG, Goias, RB Bragantino.

Estadio compartilhado apos atualizacao: apenas Maracana (Flamengo + Fluminense).

## API

```python
def load_real_schedule_2023(csv_path: str, teams_map: TeamMap) -> Schedule
```

Levanta `ValueError` se algum time nao casa com `teams_map`.

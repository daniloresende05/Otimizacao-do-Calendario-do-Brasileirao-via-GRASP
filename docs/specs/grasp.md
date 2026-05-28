# Spec — GRASP Multi-Start (sem busca local)

## 1. Objetivo

Implementar o loop multi-start classico do GRASP (Algoritmo 1 do TCC):
rodar N construcoes com seeds diferentes, guardar a melhor. Busca local
sera adicionada em fase futura.

## 2. Criterios de parada

Ambos ativos, o que ocorrer primeiro:

- `max_iter` (default 50): numero maximo de iteracoes.
- `max_iter_no_improve` (default 20): iteracoes consecutivas sem melhora
  no melhor custo.

## 3. Alpha variavel (Reactive GRASP simplificado)

Cada iteracao escolhe alpha aleatoriamente de `alpha_pool` (default
`[0.1, 0.2, 0.3, 0.4]`). O RNG para escolha de alpha e inicializado com
`seed`, garantindo reprodutibilidade.

## 4. Seeds derivadas

Iteracao `i` usa `seed_iter = seed + i`. Isso garante reprodutibilidade
total: rodar duas vezes com `--seed 42 --max-iter 50` gera exatamente as
mesmas 50 trajetorias.

## 5. Avaliacao

Cada schedule construido e avaliado por `evaluate(schedule, weights, prv_days)`.
O melhor e o de menor `total_cost`. Empates favorecem a iteracao anterior
(criterio `<` estrito para "novo melhor").

## 6. Nao-feito nesta fase

- Busca local (vizinhancas swap_days, swap_homes, swap_teams, replace_teams).
- Integracao com `cli.py`.
- Paralelismo.

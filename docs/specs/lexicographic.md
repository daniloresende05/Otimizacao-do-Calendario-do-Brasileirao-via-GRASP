# Spec — Comparacao Lexicografica

## Motivacao

A funcao objetivo escalar (`total_cost = w[prv]*prv + sum(w[c]*violations[c])`)
mistura hard constraints, soft constraints e PRV com pesos arbitrarios. Isso
permite trade-offs indesejaveis: o GRASP pode preferir uma solucao com mais PRV
se ela tiver menos violacoes de (d)/(f)/(g) — mas o orientando quer priorizar
lexicograficamente.

## Decisao

Comparar solucoes por tupla hierarquica:

```
(hard_count, soft_estruturais_count, prv_count)
```

- `hard_count`: violacoes de (a), (b).
- `soft_estruturais_count`: violacoes de (c), (d), (e), (f), (g) — exclui (h).
- `prv_count`: total_prv.

Comparacao: tupla menor vence, lexicograficamente.

## O que muda

- `EvaluationResult.lexicographic_key()` retorna a tupla.
- `EvaluationResult.is_better_than(other)` compara via `<` em tuplas.
- `grasp()` usa `is_better_than` em vez de `total_cost <`.
- `total_cost` permanece como indicador resumido mas nao e criterio de selecao.

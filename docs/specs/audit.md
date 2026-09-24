# Spec — Auditoria de Violacoes

## Objetivo

Investigar por que (d), (f), (g) aparecem violadas no melhor schedule do GRASP
e determinar se sao bugs ou comportamento esperado.

## Hipoteses

**H1: (d) bug na construcao.** A construcao deveria fazer R18 = inverso de R1 e
R19 = inverso de R2. Se aparecem violacoes, pode ser que a construcao nao esta
fazendo isso corretamente.

**H2: (d) bug no checker.** A funcao `check_d_last_two_rounds_mirror` pode estar
contando errado.

**H3: (f) e (g) sao esperadas.** A RCL penaliza mas nao bloqueia violacoes.
Poucas violacoes sao inerentes ao espaco de busca.

## Metodologia

O script `scripts/audit_violations.py` roda as 50 iteracoes do GRASP e:
1. Conta violacoes de (d), (f), (g) por iteracao.
2. Detalha cada violacao na iteracao campea.
3. Exporta CSV e relatorio textual.

## Conclusao

(d) eh estrita na construcao desde a troca do gerador de confrontos: as
quatro ancoras vem de rodadas cruzadas da biparticao, entao o mando de cada
time e determinado pelo lado e o espelho e exato. Esta auditoria descreve o
comportamento ANTERIOR, em que (d) era best-effort com piso estrutural de 4
violacoes. Ver `construction_phase1.md` §2.

(f) e (g) tambem sao best-effort. A RCL filtra candidatos sem (g) quando
possiveis, e penaliza (f) no custo, mas nao bloqueia. Poucas violacoes sao
inerentes ao espaco de busca.

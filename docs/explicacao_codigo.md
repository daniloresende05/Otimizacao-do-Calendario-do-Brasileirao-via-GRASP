# Explicacao do codigo — Guia de defesa

## Parte 1 — Fundamentos do GRASP

### 1.1 O que e GRASP em uma frase?

GRASP (Greedy Randomized Adaptive Search Procedure) e uma metaheuristica que
repete varias vezes: construir uma solucao de forma gulosa-aleatoria, depois
melhorar com busca local, e guardar a melhor solucao encontrada.

### 1.2 Por que GRASP e nao programacao inteira ou outra metaheuristica?

O problema de montar o calendario do Brasileirao (Sport Scheduling Problem) e
NP-dificil — resolver por programacao inteira com 380 jogos e dezenas de
restricoes ficaria inviavel em tempo razoavel. GRASP e uma escolha classica
para scheduling esportivo (Ribeiro, 2012; Resende & Ribeiro, 2010) e e o
metodo proposto no TCC. Alternativas como Algoritmos Geneticos ou Simulated
Annealing seriam possiveis, mas GRASP tem a vantagem de separar claramente
construcao e melhoria.

### 1.3 O que e a RCL (Lista Restrita de Candidatos)?

E um filtro que seleciona os "bons o suficiente" a cada passo da construcao.
Em vez de escolher sempre o melhor candidato (guloso puro), a RCL pega todos
os candidatos cujo custo esta ate α% acima do melhor. Exemplo com 4
candidatos de custo [100, 150, 200, 300] e α=0.3:

- c_min=100, c_max=300, threshold = 100 + 0.3*(300-100) = 160
- RCL = {100, 150} (custos <= 160)
- Escolhe um deles aleatoriamente.

Isso esta em `src/brasileirao/construction.py:557-561`.

### 1.4 O que e o α e como ele afeta o algoritmo?

α controla a "aleatoriedade" da construcao. Parametro na linha
`src/brasileirao/construction.py:387`.

- α=0: threshold = c_min. Escolhe sempre o melhor → determinismo total (guloso
  puro). Mesma seed = mesma solucao.
- α=0.5: aceita candidatos ate 50% acima do melhor → diversidade media.
- α=1: threshold = c_max. Aceita qualquer candidato → aleatorio total.

Quanto maior α, mais diversas sao as solucoes geradas. Isso importa no loop
multi-start porque solucoes diversas exploram regioes diferentes do espaco de
busca.

### 1.5 O que e seed e por que ela importa?

Seed e a semente do gerador de numeros aleatorios
(`src/brasileirao/construction.py:404`). Com a mesma seed, o algoritmo faz
exatamente as mesmas escolhas aleatorias e produz exatamente a mesma solucao.
Isso garante reprodutibilidade: qualquer pessoa pode rodar o codigo e obter
os mesmos resultados.

No loop multi-start, a iteracao i usa seed = seed_base + i
(`src/brasileirao/grasp.py:74`). Isso gera 50 trajetorias diferentes mas
reprodutiveis: rodar duas vezes com `seed=42, max_iter=50` produz exatamente
as mesmas 50 solucoes.

## Parte 2 — Construcao da solucao

### 2.1 O que faz o `circle_method`?

Gera os 19 matchings (conjuntos de 10 jogos cada) de um round-robin simples
para 20 times. Codigo em `src/brasileirao/round_robin.py:5-25`.

O algoritmo funciona assim: coloque os 20 times em duas filas de 10, uma em
frente a outra. Cada time joga contra quem esta na sua frente. Isso da 10
pares (1 rodada). Depois, fixe o primeiro time e rotacione todos os outros
uma posicao. Repita 19 vezes — cada par se enfrenta exatamente uma vez.

```
Rodada 1:  T1-T20  T2-T19  T3-T18  ...  T10-T11
           (fixa T1, rotaciona T2..T20)
Rodada 2:  T1-T19  T20-T18  T2-T17  ...  T9-T11
           ...
```

### 2.2 Por que fixar R1, R2, R18, R19 antes das outras rodadas?

Para garantir duas restricoes por construcao:

- **(c)** Todo time que jogou em casa em R1 joga fora em R2 e vice-versa.
  Conseguimos isso fazendo uma 2-coloracao do grafo R1 ∪ R2
  (`src/brasileirao/construction.py:432`).
- **(d)** R18 deve ter mandos opostos a R1 (e R19 opostos a R2). Decidimos
  R18/R19 depois da RCL para R3-R17 com enumeracao de 2^10 orientacoes
  (`src/brasileirao/construction.py:584`).

### 2.3 Como a construcao decide o mando em R1?

Usa 2-coloracao (`src/brasileirao/construction.py:432-434`). Os matchings de
R1 e R2 formam um grafo bipartido (cada time tem grau 2). A 2-coloracao
atribui "H" ou "A" a cada time. A escolha de qual cor e H e qual e A e
aleatoria por componente conexa, o que da diversidade entre seeds.

### 2.4 Como R2 e construida a partir de R1?

Cada time que jogou em casa em R1 joga fora em R2 (e vice-versa). Como a
2-coloracao garante que cada par de R2 tem um time H e um time A na coloracao
de R1, a orientacao de R2 esta determinada: o time que era H em R1 vira A em
R2 (`src/brasileirao/construction.py:438-439`).

### 2.5 Por que enumeramos as 1024 orientacoes?

Cada rodada tem 10 jogos. Para cada jogo, existem 2 mandos possiveis (A manda
ou B manda). Sao 2^10 = 1024 orientacoes. Para cada uma, calculamos o custo
em (f) (balanco casa/fora) e (g) (sequencias consecutivas). As orientacoes
com custo dentro do threshold da RCL viram candidatas, e sorteamos uma.

Na pratica, primeiro filtramos as que nao violam (g); so se nenhuma existir e
que aceitamos violacoes de (g) (`src/brasileirao/construction.py:552-555`).
Os pesos sao w_f=100, w_g=300 (`src/brasileirao/construction.py:13-16`).
Para mudar, altere `CONSTRUCTION_WEIGHTS` nessas linhas.

### 2.6 O que e `round_gap` e `round_span`? (PERGUNTA RECORRENTE)

Sao parametros de como as datas sao distribuidas. Definidos em
`src/brasileirao/construction.py:746-747`.

- **round_gap=7** — o inicio de cada rodada esta 7 dias apos o inicio da
  rodada anterior. A rodada 1 comeca na data 0 do calendario; a rodada 2
  comeca na data 7; a rodada 3 na data 14, etc.
- **round_span=3** — os 10 jogos de cada rodada podem acontecer em ate 3 dias
  consecutivos a partir do inicio da rodada.

Exemplo concreto: se o calendario comeca em 20/08/2023, a rodada 1 usa as
datas [20/08, 21/08, 22/08]. A rodada 2 usa [27/08, 28/08, 29/08]. O gap
entre o ultimo dia possivel de uma rodada (22/08) e o primeiro da seguinte
(27/08) e de 5 dias, o que garante os 3 dias minimos de descanso.

### 2.7 Como a Parte 2 (atribuicao de datas) funciona?

Codigo em `src/brasileirao/construction.py:741-799`. Para cada rodada r:

1. Calcula a janela de datas: 3 dias consecutivos comecando em
   `dates[(r-1)*7]`.
2. Distribui os 10 jogos de forma balanceada (~4, 3, 3 jogos por dia),
   verificando que cada time tem pelo menos 3 dias desde seu ultimo jogo.
3. Aplica 2-opt local: tenta trocar datas entre pares de jogos na rodada;
   aceita a troca se reduz PRV sem violar descanso
   (`src/brasileirao/construction.py:710-738`).

## Parte 3 — Funcao objetivo

### 3.1 O que e PRV?

PRV (Partidas com Reuso de Venue) conta quantos pares de jogos consecutivos
no mesmo estadio tem intervalo menor que 5 dias. Exemplo: se Flamengo joga
no Maracana em 20/08 e Fluminense joga no Maracana em 22/08, isso e 1 PRV
(intervalo de 2 dias < 5). Codigo em `src/brasileirao/objective.py:47-76`.

### 3.2 Quais restricoes sao hard e quais sao soft? Por que?

| ID  | Restricao                           | Tipo | Por que             |
|-----|-------------------------------------|------|---------------------|
| (a) | Max 1 jogo por time por rodada      | Hard | Regra do campeonato |
| (b) | Double round-robin (cada par 2x)    | Hard | Regra do campeonato |
| (c) | Alternancia R1/R2                   | Soft | Qualidade do calendario |
| (d) | Espelho R18-R1, R19-R2              | Soft | Qualidade do calendario |
| (e) | Ultima rodada sem classico estadual | Soft | Qualidade do calendario |
| (f) | Balanco casa/fora no turno          | Soft | Equidade competitiva |
| (g) | Max 2 consecutivos casa/fora        | Soft | Equidade competitiva |
| (h) | PRV (venue reuse)                   | Soft | Logistica de estadio |

Definido em `src/brasileirao/objective.py:23`.

### 3.3 Como duas solucoes sao comparadas? (CRITICO — mudou recentemente)

Usamos comparacao **lexicografica** em 3 niveis. Dadas duas solucoes A e B,
comparamos as tuplas:

```
A = (qtd_violacoes_hard, qtd_violacoes_soft_estruturais, total_PRV)
B = (qtd_violacoes_hard, qtd_violacoes_soft_estruturais, total_PRV)
```

Primeiro compara hard: quem tem menos violacoes hard e melhor. Empate? Compara
soft estruturais (c+d+e+f+g). Empate de novo? Compara PRV. Implementado em
`src/brasileirao/domain.py:67-80`.

Antes usavamos uma soma ponderada f(x) = w_prv * PRV + sum(w_c * violacoes_c).
O problema: pesos arbitrarios permitiam que o GRASP preferisse uma solucao com
mais PRV se ela tivesse menos violacoes de (d). Com lexicografico, primeiro
zeramos os problemas estruturais, depois minimizamos PRV.

O f(x) escalar ainda e calculado (`src/brasileirao/objective.py:112`) e
aparece na saida como "termometro", mas **nao e usado para decidir qual
solucao e melhor**.

### 3.4 Os pesos w_c importam? (PERGUNTA-ARMADILHA)

Com a comparacao lexicografica, os pesos **nao afetam** qual solucao o GRASP
escolhe como melhor. A decisao e feita pela tupla (hard, soft, PRV), nao pelo
f(x). Os pesos so servem para calcular o f(x) escalar, que aparece como
indicador visual na tabela de iteracoes. Estao definidos em
`src/brasileirao/objective.py:28-38`. Mudar os pesos muda o numero f(x) na
saida, mas nao muda o resultado do GRASP.

### 3.5 Por que 5 dias de PRV e 3 dias de descanso?

- **5 dias de PRV**: intervalo minimo entre jogos no mesmo estadio para nao
  contar como reuso. Vem da referencia operacional do Brasileirao.
- **3 dias de descanso**: intervalo minimo entre jogos consecutivos de um
  mesmo time. Referencia da pratica do futebol brasileiro.

Para alterar: parametros `prv_days` e `min_team_rest_days` em
`src/brasileirao/construction.py:748-749` e `src/brasileirao/grasp.py:55-56`.

## Parte 4 — Loop GRASP (multi-start)

### 4.1 Qual e o algoritmo do GRASP em pseudo-codigo?

```
melhor = None
para i de 1 ate max_iter:
    alpha = escolher_aleatorio([0.1, 0.2, 0.3, 0.4])
    solucao = construir_schedule(seed=42+i, alpha=alpha)
    avaliar(solucao)
    se solucao melhor que melhor (lexicografico):
        melhor = solucao
    se nao_melhorou em 20 iteracoes seguidas:
        parar
retornar melhor
```

Codigo: `src/brasileirao/grasp.py:45-136`.

### 4.2 Qual o criterio de parada?

Dois criterios, o que ocorrer primeiro (`src/brasileirao/grasp.py:49-50`):

- **max_iter=50**: numero maximo de iteracoes.
- **max_iter_no_improve=20**: se 20 iteracoes seguidas nao encontrarem
  solucao melhor, para. Indica convergencia.

### 4.3 Por que α variavel (Reactive GRASP simplificado)?

Cada iteracao sorteia α de [0.1, 0.2, 0.3, 0.4]
(`src/brasileirao/grasp.py:14,75`). α pequeno gera solucoes mais gulosas
(parecidas com a melhor local), α grande gera solucoes mais diversas.
Variar α explora regioes diferentes do espaco de busca. Inspirado em Resende
& Ribeiro (2010).

### 4.4 Como o "melhor" e atualizado a cada iteracao?

Usa `is_better_than` (comparacao lexicografica), **nao** `total_cost`
(`src/brasileirao/grasp.py:90`). Se a nova solucao tem tupla (hard, soft,
PRV) menor que a melhor atual, ela vira a nova melhor e reseta o contador de
iteracoes sem melhora.

## Parte 5 — Comparacao experimental

### 5.1 O que e o "baseline"? Com o que comparamos?

Temos 3 pontos de comparacao:

1. **Tabela real do Brasileirao 2023**: 380 jogos que de fato aconteceram. E o
   "piso" de qualidade — um calendario feito por humanos.
2. **Construcao unica**: uma unica execucao de `construct_schedule` com α=0.3
   e seed=42. Mostra o que a construcao sozinha produz.
3. **GRASP melhor**: a melhor solucao encontrada pelo loop multi-start em 50
   (ou menos) iteracoes. Mostra o ganho de rodar multiplas construcoes.

### 5.2 A tabela real do Brasileirao 2023 tem 36 PRVs. Como sabemos disso?

Carregamos o CSV `data/raw/tabela_real_brasileirao_2023.csv` com a funcao
`load_real_schedule_2023` (`src/brasileirao/real_baseline.py:27`). Essa funcao
normaliza nomes de times (ex: "EC Bahia" vira "Bahia") usando o mapa em
`src/brasileirao/real_baseline.py:8-13`. Crucialmente, **ignoramos o estadio
do CSV** e usamos o estadio do `teams_map` para cada mandante. Motivo: o GRASP
atribui um estadio fixo por time, entao a comparacao so e justa se a tabela
real usar a mesma premissa.

### 5.3 Qual o resultado atual e como interpreta-lo?

```
Metrica               | Real 2023  | Construcao unica | GRASP melhor
----------------------+------------+------------------+-------------
Violacoes hard        |     0      |        0         |       0
Violacoes soft estr.  |     0      |       34         |      17
Total PRV             |    36      |        7         |       8
Lex key               | (0, 0, 36) |    (0, 34, 7)    |  (0, 17, 8)
```

- A tabela real tem zero violacoes estruturais (feita por humanos respeitando
  todas as regras), mas 36 PRVs — os humanos nao otimizaram esse criterio.
- O GRASP encontra schedules com ~4.5x menos PRV (8 vs 36), mas com 17
  violacoes soft que a busca local futura vai tentar reduzir.
- A construcao unica tem 34 violacoes soft (pior que o GRASP com 17), mostrando
  que o loop multi-start ajuda a encontrar construcoes com menos violacoes.

## Parte 6 — O que ainda falta (preempcao de pergunta)

### 6.1 A busca local ainda nao esta implementada. Por que?

Estrategia deliberada: primeiro validamos que a construcao + multi-start
funciona (produz schedules viaveis com PRV reduzido), depois adicionamos
busca local. As 4 vizinhancas planejadas:

- **swap_days**: trocar datas de dois jogos (ataca PRV diretamente).
- **swap_homes**: trocar mando de um jogo (ataca (f) e (g)).
- **swap_teams**: trocar times entre dois jogos da mesma rodada (ataca (d)).
- **replace_teams**: substituir um matching inteiro em uma rodada (ataca (d)
  e (e) de forma mais agressiva).

A auditoria ja feita (`scripts/audit_violations.py`) mostra exatamente quais
violacoes cada vizinhanca deve resolver.

### 6.2 Por que a iteracao campea ainda tem 17 violacoes soft?

A auditoria mostrou (nas 50 iteracoes, com o dataset real):

- **(d)** min=4, max=22, media=13 violacoes. E best-effort: a construcao
  enumera 2^10 orientacoes para R18/R19, mas os matchings remanescentes
  raramente sao "cortes bipartidos perfeitos". Nao e bug — e limitacao
  estrutural. A vizinhanca swap_teams vai atacar isso.
- **(f)** min=3, max=10. A RCL penaliza desequilibrio mas nao bloqueia.
- **(g)** min=1, max=19. Mesmo raciocinio.

### 6.3 Por que ainda nao usamos Path-Relinking ou Reactive GRASP completo?

Sao extensoes do GRASP basico. O TCC propoe o GRASP classico como fundacao.
O α variavel ja e uma simplificacao do Reactive GRASP (escolha aleatoria em
vez de probabilidades adaptativas). Path-Relinking (combinar duas solucoes
boas para encontrar intermediarias melhores) fica como trabalho futuro.

## Parte 7 — Perguntas-armadilha esperadas

### 7.1 "Esse codigo voce escreveu sozinho?"

Resposta honesta: o orientando especificou o problema, definiu as decisoes de
design, e revisou cada fase. O codigo foi escrito com auxilio de IA, mas o
orientando entende cada decisao e cada arquivo. Tres decisoes que foram do
orientando:

1. Priorizacao das restricoes (c)/(d)/(g) na construcao — definiu que (d) e
   best-effort e (g) e quase-hard.
2. Comparacao lexicografica em vez de escalar — identificou que a soma
   ponderada produzia trade-offs indesejaveis.
3. Uso da tabela real 2023 como baseline — proposta para ter comparacao
   honesta com a pratica.

### 7.2 "Quanto tempo demora pra rodar?"

Medicoes empiricas nesta maquina (Python 3.11, Windows 10):

- **Construcao unica**: ~0.3 segundo.
- **GRASP 50 iteracoes** (parou na 21 por convergencia): ~7.2 segundos.

A busca local vai aumentar o tempo por iteracao (cada iteracao vai ter
centenas/milhares de movimentos locais), mas o tempo total deve ficar na
ordem de minutos, nao horas.

### 7.3 "Por que Python e nao Julia/C++?"

O foco do TCC e correacao e clareza do algoritmo, nao performance. Python
permite prototipagem rapida e o orientando tem familiaridade com a linguagem.
O tempo de execucao atual (7s para 50 iteracoes) esta muito abaixo de
qualquer gargalo pratico. Se performance virar problema com a busca local,
a estrutura modular do codigo permite migrar funcoes criticas para Cython ou
reescrever em Julia sem mudar a arquitetura.

## Inconsistencias encontradas

Nenhuma inconsistencia entre codigo e especificacoes foi encontrada durante
a leitura.

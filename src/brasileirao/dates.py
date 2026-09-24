"""Parse único (e cacheado) do campo ``ScheduledMatch.day``.

Centraliza o formato ``dd/mm/YYYY`` e o parse usado por
:mod:`brasileirao.constraints`, :mod:`brasileirao.objective` e
:mod:`brasileirao.local_search`, que antes mantinham três cópias idênticas
de ``_parse_day``.

O cache existe porque ``parse_day`` é uma função pura sobre uma string
imutável (mesma entrada → mesmo ``datetime``, também imutável) e o
VND/ILS reavalia a mesma agenda milhares de vezes: um calendário tem
poucas dezenas de datas distintas, mas ``datetime.strptime`` chegava a
ser chamado ~79 mil vezes numa única execução do ILS (~80% do tempo).
Sem limite de tamanho: o universo de chaves é o conjunto de datas do
campeonato, pequeno e finito.
"""
from __future__ import annotations

from datetime import datetime
from functools import lru_cache

#: Formato de data usado em ``ScheduledMatch.day``.
DATE_FMT = "%d/%m/%Y"


@lru_cache(maxsize=None)
def parse_day(day: str) -> datetime:
    """Converte o campo ``day`` (``dd/mm/YYYY``) em ``datetime``."""
    return datetime.strptime(day, DATE_FMT)

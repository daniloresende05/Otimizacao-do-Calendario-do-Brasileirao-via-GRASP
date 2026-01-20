from __future__ import annotations
from dataclasses import dataclass
from typing import List, Dict, Tuple

@dataclass(frozen=True)
class Team:
    name: str
    stadium: str
    state: str

@dataclass(frozen=True)
class Match:
    home: str
    away: str

@dataclass(frozen=True)
class ScheduledMatch:
    round: int
    day: str          # data como string (ex: "2023-08-20") ou o formato que vier do CSV
    home: str
    away: str
    stadium: str
    home_state: str
    away_state: str

Schedule = List[ScheduledMatch]
TeamMap = Dict[str, Team]

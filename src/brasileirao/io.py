import pandas as pd
from .domain import Team, TeamMap

def load_dates(path: str, col: str = "Data") -> list[str]:
    df = pd.read_csv(path)
    if col not in df.columns:
        raise ValueError(f"Coluna '{col}' não encontrada em {path}. Colunas: {list(df.columns)}")
    # mantém como string pra não ter dor com parsing agora
    return df[col].astype(str).tolist()

def load_teams(path: str) -> TeamMap:
    df = pd.read_csv(path)
    required = {"name", "stadium", "state"}
    if not required.issubset(df.columns):
        raise ValueError(f"teams.csv precisa ter {required}. Colunas: {list(df.columns)}")
    teams = {}
    for _, row in df.iterrows():
        t = Team(name=str(row["name"]), stadium=str(row["stadium"]), state=str(row["state"]))
        teams[t.name] = t
    return teams

def load_matches(path: str, home_col: str = "Mandante", away_col: str = "Visitante"):
    df = pd.read_csv(path)
    if home_col not in df.columns or away_col not in df.columns:
        raise ValueError(
            f"CSV de confrontos precisa ter colunas '{home_col}' e '{away_col}'. "
            f"Colunas: {list(df.columns)}"
        )
    return df[[home_col, away_col]].astype(str)

def select_round_dates(dates_str: list[str], n_rounds: int = 38, gap_days: int = 7) -> list[str]:
    """
    Seleciona n_rounds datas a partir de dates_str (dd/mm/yyyy), espaçando por gap_days.
    Como o seu CSV tem todos os dias do intervalo, sempre vai existir data >= alvo.
    """
    dates_dt = pd.to_datetime(pd.Series(dates_str), dayfirst=True, errors="coerce")
    if dates_dt.isna().any():
        bad = pd.Series(dates_str)[dates_dt.isna()].head(5).tolist()
        raise ValueError(f"Datas inválidas no CSV. Exemplos: {bad}")

    dates_dt = dates_dt.sort_values().reset_index(drop=True)
    start = dates_dt.iloc[0]

    selected = [start]
    for i in range(1, n_rounds):
        target = start + pd.Timedelta(days=i * gap_days)
        nxt = dates_dt[dates_dt >= target].iloc[0]
        selected.append(nxt)

    return [d.strftime("%d/%m/%Y") for d in selected]
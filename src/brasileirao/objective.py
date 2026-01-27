import pandas as pd

def add_prv_column(df: pd.DataFrame, prv_days: int = 5) -> pd.DataFrame:
    df = df.copy()

    # tenta converter day -> datetime (aceita vários formatos)
    dt = pd.to_datetime(df["day"], dayfirst=True, errors="coerce", infer_datetime_format=True)
    if dt.isna().any():
        bad = df.loc[dt.isna(), "day"].head(5).tolist()
        raise ValueError(f"Não consegui converter algumas datas da coluna 'day'. Exemplos: {bad}")

    df["day_dt"] = dt
    df = df.sort_values(["stadium", "day_dt", "round"], kind="stable")

    df["prev_day_dt"] = df.groupby("stadium")["day_dt"].shift(1)
    df["diff_days"] = (df["day_dt"] - df["prev_day_dt"]).dt.days
    df["PRV"] = ((df["diff_days"].notna()) & (df["diff_days"] < prv_days)).astype(int)

    return df

def add_prv_column(df: pd.DataFrame, prv_days: int = 5) -> pd.DataFrame:
    df = df.copy()
    df["day_dt"] = pd.to_datetime(df["day"], dayfirst=True, errors="coerce")
    if df["day_dt"].isna().any():
        bad = df.loc[df["day_dt"].isna(), "day"].head(5).tolist()
        raise ValueError(f"Não consegui converter algumas datas da coluna 'day'. Exemplos: {bad}")

    df = df.sort_values(["stadium", "day_dt", "round"], kind="stable")
    df["prev_day_dt"] = df.groupby("stadium")["day_dt"].shift(1)
    df["diff_days"] = (df["day_dt"] - df["prev_day_dt"]).dt.days
    df["PRV"] = ((df["diff_days"].notna()) & (df["diff_days"] < prv_days)).astype(int)
    return df
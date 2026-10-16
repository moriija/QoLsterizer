"""Loads the long-format table (one row per Distrito x Período) and slices it by year.
No imputation or missing-value handling happens here: incomplete data raises an error."""
import pandas as pd


def load_all(cfg: dict) -> pd.DataFrame:
    """Reads the CSV: drops the stray index column, adds an int `_year`, converts features to float."""
    d = cfg["data"]
    df = pd.read_csv(d["path"], sep=d["sep"])
    df = df.loc[:, ~df.columns.str.startswith("Unnamed")]       # index column written by to_csv
    df[d["id_col"]] = df[d["id_col"]].astype(str).str.strip()
    df["_year"] = df[d["year_col"]].astype(str).str.extract(r"(\d{4})")[0].astype(int)

    feats = [c for c in df.columns if c not in (d["id_col"], d["year_col"], "_year")]
    df[feats] = df[feats].apply(pd.to_numeric, errors="coerce").astype(float)

    dup = df.duplicated([d["id_col"], "_year"]).sum()
    if dup:
        raise ValueError(f"{dup} duplicated (Distrito, Período) rows")
    return df


def resolve_years(cfg: dict, df: pd.DataFrame) -> list[int]:
    y = cfg["years"]
    return sorted(df["_year"].unique().tolist()) if y == "all" else list(y)


def get_year(cfg: dict, df: pd.DataFrame, year: int, columns: list[str] | None = None,
             check_missing: bool = True) -> pd.DataFrame:
    """Feature matrix (index = district) for one year.

    Applies only `include_cols` / `exclude_cols` from the config. Pass `columns` to force the same
    feature set as another year (used by the 'reference' strategy). Raises if any NaN is present.
    """
    d = cfg["data"]
    sub = df[df["_year"] == year].set_index(d["id_col"]).drop(columns=[d["year_col"], "_year"])
    if columns is not None:
        sub = sub.reindex(columns=columns)
    else:
        if d.get("include_cols"):
            missing = [c for c in d["include_cols"] if c not in sub.columns]
            if missing:
                raise ValueError(f"include_cols not found in data: {missing}")
            sub = sub[list(d["include_cols"])]
        sub = sub.drop(columns=[c for c in d.get("exclude_cols", []) if c in sub.columns])

    if check_missing and sub.isna().any().any():
        na = sub.isna().sum()
        na = na[na > 0].sort_values(ascending=False)
        raise ValueError(
            f"[{year}] {len(na)} column(s) contain missing values; impute upstream or list them in "
            f"data.exclude_cols.\n{na.to_string()}")
    return sub

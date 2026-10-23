"""OPTIONAL step 0. Reports on (and re-saves) the preprocessed CSV (e.g. sel4_full.csv: ';'-separated, one row per
Distrito x Período, stray index column) into a clean DataFrame, prints a quality report and saves it.

    python clustering/prepare_data.py --config clustering/config.yaml [--year 2023] [--out data/processed/features.csv]

run.py reads the CSV from data/processed directly, so this script is only needed if you want the report
or a cleaned file. To use its output, set `data.path` in config.yaml to the saved file.
It can also be imported:  from prepare_data import build_dataframe
"""
import argparse
from pathlib import Path

import pandas as pd

from src.config import load_config
from src.data import load_all, get_year


def build_dataframe(cfg: dict) -> pd.DataFrame:
    """Clean long-format DataFrame: columns = [Período, Distrito, <features...>]."""
    df = load_all(cfg)
    d = cfg["data"]
    return df.drop(columns="_year").sort_values([d["year_col"], d["id_col"]]).reset_index(drop=True)


def report(cfg: dict, df: pd.DataFrame, year: int | None):
    d = cfg["data"]
    print(f"shape: {df.shape} | years: {df[d['year_col']].min()}-{df[d['year_col']].max()} "
          f"| districts: {df[d['id_col']].nunique()}")
    if year is not None:
        full = load_all(cfg)
        X = get_year(cfg, full, year, check_missing=False)
        miss = full[full["_year"] == year].drop(columns=[d["id_col"], d["year_col"], "_year"]).isna().mean()
        print(f"\n[{year}] feature matrix after filters: {X.shape}")
        print("missing fraction (top 8):")
        print(miss.sort_values(ascending=False).head(8).round(3).to_string())
        print(f"rows with any NaN: {int(X.isna().any(axis=1).sum())} / {len(X)}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="clustering/config.yaml")
    ap.add_argument("--year", type=int, default=None, help="also report on the matrix for this year")
    ap.add_argument("--out", default="data/processed/features.csv")
    a = ap.parse_args()
    cfg = load_config(a.config)
    df = build_dataframe(cfg)
    report(cfg, df, a.year)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(a.out, sep=cfg["data"]["sep"], index=False)
    print(f"\nsaved -> {a.out}")

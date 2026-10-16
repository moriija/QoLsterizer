"""Loads and validates config.yaml."""
import yaml

from .adapters import REGISTRY as CLUSTERERS
from .reducers import REGISTRY as REDUCERS


def load_config(path: str) -> dict:
    cfg = yaml.safe_load(open(path, encoding="utf-8"))

    for key in ("data", "years", "clusterers", "reducers", "optuna", "evaluation", "registry", "mlflow"):
        if key not in cfg:
            raise ValueError(f"config: missing section '{key}'")

    unknown = [c for c in cfg["clusterers"] if c not in CLUSTERERS]
    if unknown:
        raise ValueError(f"config: unknown clusterer(s) {unknown}. Available: {sorted(CLUSTERERS)}")
    unknown = [r for r in cfg["reducers"] if r not in REDUCERS]
    if unknown:
        raise ValueError(f"config: unknown reducer(s) {unknown}. Available: {sorted(REDUCERS)}")
    if cfg["optuna"]["n_trials"] < 1:
        raise ValueError("config: optuna.n_trials must be >= 1")
    if cfg["multi_year"]["strategy"] not in ("per_year", "reference"):
        raise ValueError("config: multi_year.strategy must be per_year or reference")

    cfg.setdefault("search_space", {})
    cfg["data"].setdefault("include_cols", None)
    cfg["data"].setdefault("exclude_cols", [])
    return cfg

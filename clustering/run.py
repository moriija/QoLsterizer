"""Entry point:  python run.py --config config.yaml"""
import argparse
import tempfile
from pathlib import Path

import mlflow
import numpy as np
import pandas as pd

from src.adapters import REGISTRY as CLUSTERERS
from src.config import load_config
from src.data import load_all, resolve_years, get_year
from src.registry import maybe_register
from src.search import run_study


def describe_reducer(pipe, names):
    """Returns (features kept by the filter, PCA loadings DataFrame or None)."""
    red = pipe.named_steps["reducer"]
    keep, pca = None, None
    if hasattr(red, "filter_"):
        keep, pca = red.filter_.keep_, red.pca_
    elif hasattr(red, "keep_"):
        keep = red.keep_
    elif hasattr(red, "components_"):
        pca = red
    kept = list(names) if keep is None else [n for n, k in zip(names, keep) if k]
    loadings = None
    if pca is not None:
        loadings = pd.DataFrame(pca.components_.T, index=kept,
                                columns=[f"PC{i+1}" for i in range(pca.components_.shape[0])])
    return kept, loadings


def labels_frame(adapter, pipe, X, labels):
    out = pd.DataFrame({"cluster": labels}, index=X.index)
    P = adapter.predict_proba(pipe, X)
    if P is not None:
        out["confidence"] = P.max(axis=1)
    return out


def log_study(study, name, tmp):
    p = Path(tmp) / f"trials_{name}.csv"
    study.trials_dataframe().to_csv(p, index=False)
    mlflow.log_artifact(str(p), artifact_path="optuna")


def run_year(cfg, X, year, tmp):
    """Search all clusterers on one year, pick the winner by the same objective, log + gate-register."""
    results = {}
    for name in cfg["clusterers"]:
        study, pipe, params, metrics = run_study(name, X, cfg)
        log_study(study, name, tmp)
        if pipe is None:
            print(f"[{year}] {name}: no valid trial"); continue
        results[name] = (pipe, params, metrics)
        mlflow.log_metric(f"best_objective_{name}", metrics["objective"])
        print(f"[{year}] {name:14s} objective={metrics['objective']:.3f} "
              f"sil={metrics.get('silhouette', float('nan')):.3f} stab={metrics['stability']:.3f} "
              f"k={metrics['n_clusters']} feasible={metrics['feasible']}")

    if not results:
        raise RuntimeError(f"No clusterer produced a valid model for {year}")
    win = max(results, key=lambda n: results[n][2]["objective"])
    pipe, params, metrics = results[win]
    adapter = CLUSTERERS[win]

    # ---- log winner ----
    mlflow.set_tags({"year": year, "winner": win, "supports_predict": adapter.supports_predict})
    mlflow.log_params({f"best_{k}": v for k, v in params.items()})
    mlflow.log_metrics({k: v for k, v in metrics.items() if isinstance(v, (int, float)) and not isinstance(v, bool)})
    mlflow.log_dict({"violations": metrics["violations"]}, "constraints.json")

    kept, loadings = describe_reducer(pipe, X.columns)
    mlflow.log_dict({"input_features": list(X.columns), "features_after_filter": kept}, "features.json")
    if loadings is not None:
        p = Path(tmp) / "pca_loadings.csv"; loadings.to_csv(p); mlflow.log_artifact(str(p))

    labels = np.asarray(adapter.train_labels(pipe, X))
    lf = labels_frame(adapter, pipe, X, labels)
    p = Path(tmp) / "labels.csv"; lf.to_csv(p); mlflow.log_artifact(str(p))

    info = mlflow.sklearn.log_model(pipe, artifact_path="model")   # full pipeline = one artifact
    reg = maybe_register(info.model_uri, f"{cfg['registry']['model_name']}_{year}", metrics, cfg)
    mlflow.set_tags({"registered": reg["registered"], "registration_reason": reg["reason"]})
    print(f"[{year}] winner={win} | registration: {reg}")
    return win, pipe, lf


def apply_to_year(adapter, pipe, X, year, tmp):
    """'reference' strategy: reuse the reference-year model on another year (drift check)."""
    if not adapter.supports_predict:
        print(f"[{year}] skipped: {adapter.name} has no predict()"); return
    lab = adapter.predict(pipe, X)
    lf = labels_frame(adapter, pipe, X, lab)
    p = Path(tmp) / f"labels_{year}.csv"; lf.to_csv(p); mlflow.log_artifact(str(p))
    share = pd.Series(lab).value_counts(normalize=True).sort_index()
    mlflow.log_dict(share.round(4).to_dict(), f"cluster_share_{year}.json")


def main(path):
    cfg = load_config(path)
    mlflow.set_tracking_uri(cfg["mlflow"]["tracking_uri"])
    mlflow.set_experiment(cfg["mlflow"]["experiment"])

    df = load_all(cfg)
    years = resolve_years(cfg, df)
    strategy = cfg["multi_year"]["strategy"]
    ref = cfg["multi_year"]["reference_year"]

    with mlflow.start_run(run_name="batch"), tempfile.TemporaryDirectory() as tmp:
        mlflow.set_tags({"years": str(years), "strategy": strategy})
        mlflow.log_dict(cfg, "config.json")

        search_years = [ref] if strategy == "reference" else years
        ref_cols = None
        fitted = {}
        for y in search_years:
            X = get_year(cfg, df, y)
            print(f"\n=== {y}: {X.shape[0]} districts x {X.shape[1]} features ===")
            ref_cols = list(X.columns)
            with mlflow.start_run(run_name=f"year={y}", nested=True):
                win, pipe, _ = run_year(cfg, X, y, tmp)
                fitted[y] = (win, pipe)

        if strategy == "reference":
            win, pipe = fitted[ref]
            for y in [y for y in years if y != ref]:
                with mlflow.start_run(run_name=f"apply year={y}", nested=True):
                    mlflow.set_tags({"year": y, "reference_year": ref})
                    apply_to_year(CLUSTERERS[win], pipe, get_year(cfg, df, y, columns=ref_cols), y, tmp)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="clustering/config.yaml")
    main(ap.parse_args().config)

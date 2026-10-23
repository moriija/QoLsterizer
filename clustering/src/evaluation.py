"""Evaluation: internal metrics + bootstrap stability + hard constraints -> one composite score.

No train/test split (too few rows per year): stability under subsampling plays the 'held-out' role.
Works for any adapter, with or without .predict.
"""
import numpy as np
from sklearn.base import clone
from sklearn.metrics import (silhouette_score, davies_bouldin_score,
                             calinski_harabasz_score, adjusted_rand_score)


def _internal(Z, labels):
    mask = labels != -1                              # drop HDBSCAN noise
    n_clusters = len(set(labels[mask]))
    out = {"n_clusters": n_clusters, "noise_fraction": float(1 - mask.mean())}
    if n_clusters >= 2 and mask.sum() > n_clusters:
        out["silhouette"] = float(silhouette_score(Z[mask], labels[mask]))
        out["davies_bouldin"] = float(davies_bouldin_score(Z[mask], labels[mask]))
        out["calinski_harabasz"] = float(calinski_harabasz_score(Z[mask], labels[mask]))
        sizes = np.bincount(labels[mask])
        sizes = sizes[sizes > 0]
        out["min_cluster_size"] = int(sizes.min())
        out["max_cluster_share"] = float(sizes.max() / mask.sum())
    return out


def _stability(pipe, adapter, X, ref_labels, n_boot, frac, seed):
    """Mean ARI between reference labels and labels from refits on random subsamples."""
    rng = np.random.default_rng(seed)
    aris = []
    for _ in range(n_boot):
        idx = np.sort(rng.choice(len(X), size=int(frac * len(X)), replace=False))
        try:
            p = clone(pipe).fit(X.iloc[idx])
            lab = adapter.train_labels(p, X.iloc[idx])
            aris.append(adjusted_rand_score(ref_labels[idx], lab))
        except Exception:
            continue
    return float(np.mean(aris)) if aris else 0.0


def evaluate(pipe, adapter, X, cfg, seed=42) -> dict:
    """`pipe` must already be fit on X. Returns metrics, constraint violations, objective."""
    ev = cfg["evaluation"]
    labels = np.asarray(adapter.train_labels(pipe, X))
    Z = pipe[:-1].transform(X)
    m = _internal(Z, labels)
    m["stability"] = _stability(pipe, adapter, X, labels, ev["n_bootstrap"], ev["subsample_frac"], seed)

    if adapter.supports_soft:
        P = adapter.predict_proba(pipe, X)
        m["mean_max_proba"] = float(P.max(axis=1).mean())
        m["mean_entropy"] = float((-(P * np.log(P + 1e-12)).sum(axis=1)).mean())

    c = ev["constraints"]
    viol = []
    if "silhouette" not in m:
        viol.append("degenerate_clustering")
    else:
        if m["min_cluster_size"] < c["min_cluster_size"]: viol.append("min_cluster_size")
        if m["max_cluster_share"] > c["max_cluster_share"]: viol.append("max_cluster_share")
        if m["noise_fraction"] > c["max_noise_fraction"]: viol.append("noise_fraction")
        if m["stability"] < c["min_stability"]: viol.append("stability")
        if not (c["min_clusters"] <= m["n_clusters"] <= c["max_clusters"]): viol.append("n_clusters")
    m["violations"] = viol
    m["feasible"] = not viol

    w = ev["weights"]
    if "silhouette" in m:
        composite = (w["silhouette"] * (m["silhouette"] + 1) / 2
                     + w["davies_bouldin"] / (1 + m["davies_bouldin"])
                     + w["stability"] * m["stability"])
    else:
        composite = 0.0
    # feasible -> composite in [0,1]; infeasible -> negative, still ordered by stability for the sampler
    m["objective"] = composite if m["feasible"] else -1.0 + 0.5 * m["stability"]
    return m

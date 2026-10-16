"""Clusterer adapters: the interface any clustering algorithm must implement.

To add a new algorithm: subclass ClustererAdapter, set the flags, implement
param_space(trial, space) and build(params, seed), add it to REGISTRY, then add a section for it
under `search_space` in config.yaml and list it under `clusterers`.
`space` is that section of the YAML (a dict); missing keys fall back to defaults below.
"""
from abc import ABC, abstractmethod
import numpy as np
from sklearn.cluster import KMeans, AgglomerativeClustering, HDBSCAN
from sklearn.mixture import GaussianMixture

from .space import suggest


class ClustererAdapter(ABC):
    name: str
    supports_predict: bool = True    # estimator has .predict on new data
    supports_soft: bool = False      # estimator has .predict_proba

    @abstractmethod
    def param_space(self, trial, space: dict) -> dict: ...

    @abstractmethod
    def build(self, params: dict, seed: int): ...

    # --- operate on a fitted sklearn Pipeline whose last step is 'clusterer' ---
    def fit(self, pipe, X):
        return pipe.fit(X)

    def train_labels(self, pipe, X) -> np.ndarray:
        """Hard labels for the data the pipeline was fit on (-1 = noise)."""
        return pipe.predict(X) if self.supports_predict else pipe[-1].labels_

    def predict(self, pipe, X) -> np.ndarray:
        if not self.supports_predict:
            raise NotImplementedError(f"{self.name} cannot predict on new data")
        return pipe.predict(X)

    def predict_proba(self, pipe, X):
        return pipe.predict_proba(X) if self.supports_soft else None


class KMeansAdapter(ClustererAdapter):
    name = "kmeans"

    def param_space(self, trial, space):
        return {
            "k": suggest(trial, "k", space.get("k", [2, 10])),
            "n_init": suggest(trial, "n_init", space.get("n_init", 20)),
            "init": suggest(trial, "init", space.get("init", "k-means++")),
        }

    def build(self, p, seed):
        return KMeans(n_clusters=p["k"], n_init=p["n_init"], init=p["init"], random_state=seed)


class GMMAdapter(ClustererAdapter):
    name = "gmm"
    supports_soft = True

    def param_space(self, trial, space):
        return {
            "k": suggest(trial, "k", space.get("k", [2, 10])),
            "covariance_type": suggest(trial, "covariance_type",
                                       space.get("covariance_type", ["spherical", "diag", "tied"])),
        }  # 'full' omitted by default: ~96 rows can't support full covariances

    def build(self, p, seed):
        return GaussianMixture(n_components=p["k"], covariance_type=p["covariance_type"],
                               n_init=5, reg_covar=1e-4, random_state=seed)


class AgglomerativeAdapter(ClustererAdapter):
    name = "agglomerative"
    supports_predict = False

    def param_space(self, trial, space):
        return {"k": suggest(trial, "k", space.get("k", [2, 10])),
                "linkage": suggest(trial, "linkage", space.get("linkage", ["ward", "average", "complete"]))}

    def build(self, p, seed):
        return AgglomerativeClustering(n_clusters=p["k"], linkage=p["linkage"])


class HDBSCANAdapter(ClustererAdapter):
    name = "hdbscan"
    supports_predict = False

    def param_space(self, trial, space):
        return {"min_cluster_size": suggest(trial, "min_cluster_size", space.get("min_cluster_size", [4, 20])),
                "min_samples": suggest(trial, "min_samples", space.get("min_samples", [1, 8]))}

    def build(self, p, seed):
        return HDBSCAN(min_cluster_size=p["min_cluster_size"], min_samples=p["min_samples"], copy=True)


REGISTRY = {a.name: a for a in (KMeansAdapter(), GMMAdapter(), AgglomerativeAdapter(), HDBSCANAdapter())}

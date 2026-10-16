"""Feature selection / dimensionality reduction slot.

Each reducer spec exposes:
    param_space(trial, space) -> dict   Optuna-tunable params; names MUST be prefixed with the spec
                                        name (Optuna forbids one name having different ranges)
    build(params)             -> sklearn transformer
To plug in the engineer's method: write a spec, add it to REGISTRY, add a section under
`search_space` in config.yaml and list it under `reducers`.
"""
import numpy as np
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.decomposition import PCA

from .space import suggest


class Passthrough(BaseEstimator, TransformerMixin):
    def fit(self, X, y=None):
        self.n_features_in_ = np.asarray(X).shape[1]   # a fitted attribute, or sklearn says "not fitted"
        return self

    def transform(self, X):
        return np.asarray(X)


class CorrFilter(BaseEstimator, TransformerMixin):
    """Drops one feature of every pair with |r| > threshold (fit on train only). None = keep all."""

    def __init__(self, threshold=None):
        self.threshold = threshold

    def fit(self, X, y=None):
        X = np.asarray(X)
        keep = np.ones(X.shape[1], dtype=bool)
        if self.threshold is not None:
            with np.errstate(invalid="ignore", divide="ignore"):
                corr = np.abs(np.corrcoef(X, rowvar=False))
            corr = np.nan_to_num(corr)
            np.fill_diagonal(corr, 0)
            for i in range(X.shape[1]):
                if keep[i]:
                    keep[(corr[i] > self.threshold) & (np.arange(X.shape[1]) > i)] = False
        self.keep_ = keep
        return self

    def transform(self, X):
        return np.asarray(X)[:, self.keep_]


class FilterPCA(BaseEstimator, TransformerMixin):
    """Optional correlation filter followed by PCA; n_components is capped to what the data allows."""

    def __init__(self, threshold=None, n_components=5):
        self.threshold = threshold
        self.n_components = n_components

    def fit(self, X, y=None):
        self.filter_ = CorrFilter(self.threshold).fit(X)
        Xf = self.filter_.transform(X)
        n = self.n_components
        if isinstance(n, (int, np.integer)):
            n = max(1, min(int(n), Xf.shape[1], Xf.shape[0] - 1))
        self.pca_ = PCA(n_components=n, svd_solver="full", random_state=0).fit(Xf)
        return self

    def transform(self, X):
        return self.pca_.transform(self.filter_.transform(X))


class NoneSpec:
    name = "none"

    def param_space(self, trial, space):
        return {}

    def build(self, p):
        return Passthrough()


class PCASpec:
    name = "pca"

    def param_space(self, trial, space):
        return {"pca__n_components": suggest(trial, "pca__n_components", space.get("n_components", [2, 12]))}

    def build(self, p):
        return FilterPCA(None, p["pca__n_components"])


class CorrPCASpec:
    name = "corr_pca"

    def param_space(self, trial, space):
        return {
            "corr_pca__corr_thr": suggest(trial, "corr_pca__corr_thr", space.get("corr_thr", [0.7, 0.95])),
            "corr_pca__n_components": suggest(trial, "corr_pca__n_components", space.get("n_components", [2, 10])),
        }

    def build(self, p):
        return FilterPCA(p["corr_pca__corr_thr"], p["corr_pca__n_components"])


class CorrOnlySpec:
    name = "corr_only"

    def param_space(self, trial, space):
        return {"corr_only__corr_thr": suggest(trial, "corr_only__corr_thr", space.get("corr_thr", [0.6, 0.95]))}

    def build(self, p):
        return CorrFilter(p["corr_only__corr_thr"])


REGISTRY = {s.name: s for s in (NoneSpec(), PCASpec(), CorrPCASpec(), CorrOnlySpec())}

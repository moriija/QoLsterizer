"""Builds the sklearn Pipeline: scale -> reduce -> cluster.
Input must be complete (no NaN): missing values are handled upstream by the data team."""
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler, RobustScaler, PowerTransformer

from .adapters import REGISTRY as CLUSTERERS
from .reducers import REGISTRY as REDUCERS
from .space import suggest

SCALERS = {"standard": StandardScaler, "robust": RobustScaler, "power": PowerTransformer}


def suggest_and_build(trial, clusterer_name: str, cfg: dict, seed: int):
    """Samples every hyperparameter from the trial (ranges from config) -> (pipeline, params)."""
    ss = cfg.get("search_space", {})
    adapter = CLUSTERERS[clusterer_name]

    scaler_name = suggest(trial, "scaler", ss.get("scaler", ["standard", "robust", "power"]))
    red_name = suggest(trial, "reducer", cfg["reducers"])
    red_params = REDUCERS[red_name].param_space(trial, ss.get(red_name, {}))
    clu_params = adapter.param_space(trial, ss.get(clusterer_name, {}))

    pipe = Pipeline([
        ("scaler", SCALERS[scaler_name]()),
        ("reducer", REDUCERS[red_name].build(red_params)),
        ("clusterer", adapter.build(clu_params, seed)),
    ])
    return pipe, {"scaler": scaler_name, "reducer": red_name, **red_params, **clu_params}

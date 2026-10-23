"""Optuna search: one study per clusterer, jointly tuning scaler + reducer + clusterer hyperparameters."""
import optuna
from optuna.trial import FixedTrial

from .adapters import REGISTRY as CLUSTERERS
from .evaluation import evaluate
from .pipeline import suggest_and_build

optuna.logging.set_verbosity(optuna.logging.WARNING)


def run_study(clusterer_name: str, X, cfg: dict):
    seed = cfg["optuna"]["seed"]
    adapter = CLUSTERERS[clusterer_name]

    def objective(trial):
        try:
            pipe, _ = suggest_and_build(trial, clusterer_name, cfg, seed)
            adapter.fit(pipe, X)
            m = evaluate(pipe, adapter, X, cfg, seed)
        except Exception as e:                      # invalid combos (e.g. too few features) -> skip
            trial.set_user_attr("error", repr(e))
            raise optuna.TrialPruned()
        for k, v in m.items():
            trial.set_user_attr(k, v)
        return m["objective"]

    study = optuna.create_study(direction="maximize", sampler=optuna.samplers.TPESampler(seed=seed),
                                study_name=f"{clusterer_name}")
    study.optimize(objective, n_trials=cfg["optuna"]["n_trials"])

    completed = [t for t in study.trials if t.state == optuna.trial.TrialState.COMPLETE]
    if not completed:
        return study, None, None, None

    # refit the best configuration on the full year of data
    best = study.best_trial
    pipe, params = suggest_and_build(FixedTrial(best.params), clusterer_name, cfg, seed)
    adapter.fit(pipe, X)
    metrics = evaluate(pipe, adapter, X, cfg, seed)
    return study, pipe, params, metrics

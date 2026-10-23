"""Registration gate + MLflow model registry."""
import mlflow
from mlflow.tracking import MlflowClient


def champion_objective(model_name: str, alias: str):
    client = MlflowClient()
    try:
        mv = client.get_model_version_by_alias(model_name, alias)
    except Exception:
        return None
    run = client.get_run(mv.run_id)
    return run.data.metrics.get("objective")


def passes_gate(metrics: dict, cfg: dict) -> tuple[bool, str]:
    g = cfg["registry"]["gate"]
    if not metrics["feasible"]:
        return False, f"infeasible: {metrics['violations']}"
    if metrics["silhouette"] < g["min_silhouette"]:
        return False, f"silhouette {metrics['silhouette']:.3f} < {g['min_silhouette']}"
    if metrics["stability"] < g["min_stability"]:
        return False, f"stability {metrics['stability']:.3f} < {g['min_stability']}"
    return True, "ok"


def maybe_register(model_uri: str, model_name: str, metrics: dict, cfg: dict) -> dict:
    """Call inside the active run that logged `model_uri`. Registers only if gate passes and beats champion."""
    r = cfg["registry"]
    ok, why = passes_gate(metrics, cfg)
    if not ok:
        return {"registered": False, "reason": why}

    champ = champion_objective(model_name, r["alias"])
    if champ is not None and metrics["objective"] < champ + r["min_improvement"]:
        return {"registered": False,
                "reason": f"does not beat champion ({metrics['objective']:.3f} vs {champ:.3f})"}

    mv = mlflow.register_model(model_uri, model_name)
    MlflowClient().set_registered_model_alias(model_name, r["alias"], mv.version)
    return {"registered": True, "version": mv.version, "reason": "ok"}

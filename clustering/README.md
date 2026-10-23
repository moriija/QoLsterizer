# Clustering pipeline (districts of São Paulo)

Stage 4 of the repo (see the top-level README). Input: `data/processed/sel4_full.csv`, produced by `preprocessing/preprocess.py`.
All commands below are run **from the repository root**.

```
[optional] clustering/prepare_data.py   CSV -> clean DataFrame + quality report
clustering/run.py:  Optuna search (scaler + reducer + clusterer, jointly)
         -> fit -> evaluate (internal metrics + stability + constraints)
         -> gate -> MLflow registry
```

```
config.yaml          all settings (years, clusterers, reducers, constraints, gate, MLflow)
prepare_data.py      optional step 0
run.py               entry point
src/config.py        loads + validates config.yaml
src/space.py         YAML range syntax -> Optuna suggestions
src/data.py          loading + per-year slicing
src/pipeline.py      scale -> reduce -> cluster (one sklearn Pipeline)
src/reducers.py      feature selection / dimensionality reduction slot (plug the engineer's method here)
src/adapters.py      clusterer interface + KMeans, GMM, Agglomerative, HDBSCAN
src/search.py        Optuna study per clusterer
src/evaluation.py    metrics, bootstrap stability, constraints, composite objective
src/registry.py      registration gate + champion comparison
../data/processed/   input CSV (sel4_full.csv) / output of prepare_data.py
../preprocessing/    produces the input CSV from the raw ObservaSampa files
```

```
pip install -r requirements.txt
python clustering/prepare_data.py --year 2023      # optional
python clustering/run.py --config clustering/config.yaml
mlflow ui --backend-store-uri ./mlruns
```

Add a clusterer: subclass `ClustererAdapter` in `src/adapters.py`, add to `REGISTRY`, list in `config.yaml`.
Add a reducer: write a spec with `param_space(trial)` / `build(params)` in `src/reducers.py`, add to `REGISTRY`, list in `config.yaml`.

All settings (data columns, years, clusterers, reducers, search ranges, metrics weights, constraints, gate, MLflow) live in `config.yaml`; currently only `kmeans` is enabled.

The pipeline does no imputation: data must arrive complete (NaNs raise an error listing the columns).

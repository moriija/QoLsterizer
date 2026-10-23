"""Turns a YAML search-space spec into an Optuna suggestion (or a fixed value)."""


def _is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def suggest(trial, name: str, spec):
    if isinstance(spec, dict) and "choices" in spec:
        return trial.suggest_categorical(name, list(spec["choices"]))
    if isinstance(spec, (list, tuple)):
        if len(spec) == 2 and all(_is_num(v) for v in spec):
            lo, hi = spec
            if isinstance(lo, int) and isinstance(hi, int):
                return trial.suggest_int(name, lo, hi)
            return trial.suggest_float(name, float(lo), float(hi))
        return trial.suggest_categorical(name, list(spec))
    return spec  # scalar -> fixed

import numpy as np, pandas as pd
from scipy.stats import median_abs_deviation as mad, iqr

PATH = "./normalizado/sel4_full.csv"
MAX_MISSING = 0.65      # keep variables with <= this fraction of NaN
N_PERM = 100

# ---- data
df = pd.read_csv(PATH, sep=";", index_col=0).drop(columns=["Período", "Distrito"])
df = df.loc[:, df.isna().mean() <= MAX_MISSING].dropna()
X, cols = df.to_numpy(float), list(df.columns)
print(X.shape)

# ---- normalizations
def safe(s, alt=1.0):
    return np.where(s > 1e-12, s, alt)

def mean_norm(X): return (X - X.mean(0)) / safe(np.ptp(X, 0))
def minmax(X):    return (X - X.min(0)) / safe(np.ptp(X, 0))
def standard(X):  return (X - X.mean(0)) / safe(X.std(0, ddof=1))
def robust(X):    return (X - np.median(X, 0)) / safe(iqr(X, axis=0), X.std(0, ddof=1))

def spatial_median(X, it=300, tol=1e-8):
    m = np.median(X, 0)
    for _ in range(it):
        w = 1 / np.maximum(np.linalg.norm(X - m, axis=1), tol)
        m2 = (X * w[:, None]).sum(0) / w.sum()
        if np.linalg.norm(m2 - m) < tol: break
        m = m2
    return m

def sscm(X):
    Z = (X - np.median(X, 0)) / safe(mad(X, axis=0, scale="normal"), X.std(0, ddof=1))
    Zc = Z - spatial_median(Z)
    n = np.linalg.norm(Zc, axis=1, keepdims=True)
    S = Zc / np.where(n == 0, 1, n)
    _, V = np.linalg.eigh(S.T @ S / len(S))
    V = V[:, ::-1]
    lam = mad(Zc @ V, axis=0, scale="normal") ** 2   # robust variances
    o = np.argsort(lam)[::-1]
    return lam[o], V[:, o]

def classic(Z):
    Zc = Z - Z.mean(0)
    _, s, Vt = np.linalg.svd(Zc, full_matrices=False)
    return s**2 / (len(Z) - 1), Vt.T

methods = {
    "mean_norm": lambda X: classic(mean_norm(X)),
    "minmax":    lambda X: classic(minmax(X)),
    "standard":  lambda X: classic(standard(X)),
    "robust":    lambda X: classic(robust(X)),
    "sscm":      sscm,
}

# ---- parallel analysis: shuffle each column, keep eigenvalues' 95th percentile
rng = np.random.default_rng(0)
def pa_threshold(fn, X):
    null = []
    for _ in range(N_PERM):
        Xp = np.column_stack([rng.permutation(c) for c in X.T])
        null.append(fn(Xp)[0][:min(X.shape)])
    return np.percentile(null, 95, axis=0)

# ---- run
rows = []
for name, fn in methods.items():
    lam, V = fn(X)
    ratio = lam / lam.sum()
    cum = ratio.cumsum()
    thr = pa_threshold(fn, X)
    k_pa = int(np.argmax(lam <= thr)) if (lam <= thr).any() else len(lam)
    rows.append(dict(method=name, produced=len(lam),
                     k80=int(np.searchsorted(cum, .80)) + 1,
                     k90=int(np.searchsorted(cum, .90)) + 1,
                     k_gt_mean=int((lam > lam.mean()).sum()),
                     k_parallel=k_pa,
                     pc1_pct=round(100 * ratio[0], 1)))
    print(f"\n{name}: top PCs (parallel analysis = {k_pa})")
    for j in range(max(k_pa, 1)):
        top = np.argsort(-np.abs(V[:, j]))[:3]
        print(f"  PC{j+1} [{100*ratio[j]:.1f}%]:",
              "; ".join(f"{cols[i][:35]} ({V[i, j]:+.2f})" for i in top))

print("\n", pd.DataFrame(rows).set_index("method"))
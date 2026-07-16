# delab practices — Python

Idioms and tooling for the seven core principles in `../SKILL.md`. Defaults
below are lab recommendations; where a tool is named, it's a strong default you
may swap if a project already standardized on something else.

**Default stack:** `uv` (env + packaging), `ruff` (lint + format), `pytest`
(tests), type hints on public functions, `pathlib` for paths, `joblib` or
`functools` for caching, `numpy`/`pandas`/`polars` for vectorized data work.

---

## 1. Package & environment management

Use `uv` with a `pyproject.toml`. Commit both `pyproject.toml` and `uv.lock`.

```bash
uv init myproject && cd myproject
uv add numpy pandas
uv run python analysis.py     # runs in the project's isolated, locked env
```

❌ **Before** — undeclared, global, unreproducible

```python
# "just pip install whatever's missing" — nothing is recorded
import numpy, pandas, scipy   # which versions? nobody knows
# $ pip install numpy   (into the base environment)
```

✅ **After** — declared and locked in `pyproject.toml`

```toml
[project]
name = "spike-analysis"
requires-python = ">=3.11"
dependencies = [
    "numpy>=1.26",
    "pandas>=2.2",
    "scipy>=1.13",
]
```

A collaborator runs `uv sync` and gets the exact same environment.

## 2. Functional code

Keep computation pure; push I/O, globals, and plotting to the edges.

❌ **Before** — reads a global, mutates a global, plots, all in one

```python
RESULTS = {}

def analyze():
    df = pd.read_csv("session.csv")          # hidden I/O
    RESULTS["mean_rt"] = df["rt"].mean()     # mutates global
    plt.plot(df["rt"]); plt.show()           # side effect
```

✅ **After** — a pure core you can test, with I/O at the call site

```python
def mean_rt(trials: pd.DataFrame) -> float:
    """Mean reaction time over valid trials."""
    return trials.loc[trials["valid"], "rt"].mean()

# edges: the caller does the I/O and plotting
trials = pd.read_csv(path)
rt = mean_rt(trials)          # pure, deterministic, testable
```

## 3. Cache expensive local results

Cache to disk keyed on inputs so unchanged work isn't repeated. `joblib.Memory`
handles the hashing and invalidation for you.

❌ **Before** — recomputes a 20-minute step on every run

```python
def load_features(session_id):
    raw = read_raw(session_id)          # slow every single time
    return extract_features(raw)        # slow every single time
```

✅ **After** — memoized to disk, keyed on the arguments

```python
from joblib import Memory

memory = Memory(location=".cache", verbose=0)   # .cache is git-ignored

@memory.cache
def load_features(session_id: str) -> pd.DataFrame:
    raw = read_raw(session_id)
    return extract_features(raw)
```

Change the arguments (or the function body) and joblib recomputes; otherwise it
returns the cached result in milliseconds.

## 4. Map / vectorize instead of hand-rolled loops

❌ **Before** — manual pre-allocate-and-fill loop

```python
zscored = np.empty_like(rates)
for i in range(len(rates)):
    zscored[i] = (rates[i] - rates.mean()) / rates.std()   # mean/std recomputed each iter!
```

✅ **After** — vectorized, correct, and ~100× faster

```python
zscored = (rates - rates.mean()) / rates.std()
```

For non-array work, prefer a comprehension over an accumulator loop:

```python
# instead of: out = []; for s in sessions: out.append(load(s))
features = [load_features(s) for s in sessions]
```

## 5. Small, single-purpose functions

❌ **Before** — one function loads, cleans, models, and plots

```python
def do_everything(path):
    df = pd.read_csv(path)
    df = df[df.rt > 0]
    df["log_rt"] = np.log(df.rt)
    model = smf.ols("log_rt ~ coherence", df).fit()
    plt.scatter(df.coherence, df.log_rt); plt.plot(...)
    return model
```

✅ **After** — small, named, composable steps

```python
def load_trials(path: Path) -> pd.DataFrame: ...
def clean(trials: pd.DataFrame) -> pd.DataFrame: ...
def fit_rt_model(trials: pd.DataFrame) -> RegressionResults: ...
def plot_rt(trials: pd.DataFrame, ax) -> None: ...

trials = clean(load_trials(path))
model = fit_rt_model(trials)
```

## 6. Test-driven development

Write the test first with `pytest`, watch it fail, then implement.

```python
# test_rt.py  — write this BEFORE mean_rt exists
def test_mean_rt_ignores_invalid():
    trials = pd.DataFrame({"rt": [1.0, 3.0, 99.0],
                           "valid": [True, True, False]})
    assert mean_rt(trials) == 2.0
```

```bash
uv run pytest            # red → implement mean_rt → green
```

Every bug fixed gets a regression test that reproduces it first.

## 7. Never store secrets or hard-coded paths

❌ **Before** — credentials and an absolute path baked into source

```python
DB = connect("postg:https://admin:hunter2@10.0.0.5/spikes")   # secret in git forever
DATA = "/Users/jane/Dropbox/lab/data/session.csv"     # runs on exactly one machine
```

✅ **After** — read from the environment / configurable roots

```python
import os
from pathlib import Path

DB_URL = os.environ["SPIKES_DB_URL"]                  # set outside the repo
DATA_ROOT = Path(os.environ.get("LAB_DATA", "~/data")).expanduser()
session = DATA_ROOT / "session.csv"
```

Commit a `.env.example` listing the variable *names* (never values), and add
`.env` and `.cache/` to `.gitignore`.

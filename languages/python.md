# delab practices — Python

Idioms and tooling for the core principles in `../SKILL.md`. Defaults
below are lab recommendations; where a tool is named, it's a strong default you
may swap if a project already standardized on something else.

**Default stack:** `uv` (env + packaging), `ruff` (lint + format), `pytest`
(tests), type hints on public functions, `pathlib` for paths, `joblib` or
`functools` for caching, `numpy`/`pandas`/`polars` for vectorized data work,
`pydantic` / `pydantic-settings` for config and boundary validation.

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

> **Why `uv`, not `conda`?** A conda-only project isn't `pip install`-able, so
> your library can't be used as a dependency by anyone outside conda — the main
> reason we avoid it. On top of that: `uv.lock` is a cross-platform lockfile
> with hashes that actually reproduces on another machine (a `conda env export`
> bakes in platform-specific build strings and often breaks); uv is seconds-fast
> so throwaway envs are practical; and one tool replaces pip, virtualenv, poetry,
> and pyenv — it even installs Python itself (`uv python install`), which was
> often the only reason to reach for conda. *Honest caveat:* conda's real edge is
> shipping non-Python binaries (CUDA, GDAL, some bio/geo stacks). Most scientific
> packages now ship PyPI wheels, but if a project genuinely needs conda-only
> binaries, that's the exception.

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

**`map` isn't only about speed — it's about clarity.** Fitting a GLM per subject
won't get faster, but factoring the loop body into a named function still wins.
Watch it improve in two steps:

❌ **Before** — the loop body inlines filtering, fitting, and unpacking

```python
results = {}
for i in range(len(subjids)):
    d = big_df[big_df.subjid == subjids[i]]
    m = fit_glm(d)
    results[i] = {"p": pvalue(m), "b": coef(m)}
```

🟡 **Better** — extract a small, testable function; the loop just calls it

```python
def fit_subject(subjid: str) -> dict:
    d = big_df[big_df.subjid == subjid]
    m = fit_glm(d)
    return {"p": pvalue(m), "b": coef(m)}

results = {s: fit_subject(s) for s in subjids}
```

✅ **Best** — map the function over the inputs

```python
results = list(map(fit_subject, subjids))
```

Now `fit_subject` can be unit-tested on one subject, reused elsewhere, and even
run in parallel — none of which is possible when the logic is trapped in a loop
body. (If you'd rather not have `fit_subject` reach for the global `big_df`,
pass it in and bind it: `map(partial(fit_subject, big_df), subjids)` — see
principle 2.)

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

**Use synthetic fixtures, not real data.** The test above builds its own tiny
`DataFrame` — no session file on disk — so it passes on a fresh clone and in CI.
Never point a test at `/data/...`; construct the minimal input inline or with a
`pytest` fixture.

## 7. Never store secrets or hard-coded paths

❌ **Before** — credentials and an absolute path baked into source

```python
DB = connect("postg:https://admin:hunter2@10.0.0.5/spikes")   # secret in git forever
DATA = "/Users/jane/Dropbox/lab/data/session.csv"     # runs on exactly one machine
```

✅ **After** — typed, validated config with `pydantic-settings`

```python
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LAB_", env_file=".env")

    db_url: str                                  # required: errors loudly if unset
    data_root: Path = Path("~/data").expanduser()

settings = Settings()                            # reads env / .env, validates types
session = settings.data_root / "session.csv"     # a Path, guaranteed
```

`Settings()` fails immediately with a clear message if `LAB_DB_URL` is missing,
instead of a `KeyError` surfacing deep in the analysis. Commit a `.env.example`
listing the variable *names* (never values), and add `.env` and `.cache/` to
`.gitignore`.

> **Where pydantic belongs:** the *boundaries* — config, experiment/analysis
> parameters, and metadata loaded from files, CLI, or an API. A typed config
> object also beats threading a dozen loose keyword arguments through your
> functions (principle 2). Don't wrap per-row data or numpy arrays in pydantic
> models — that's the wrong tool and it will be slow.

## 8. Separate I/O, analysis, and plotting

Three layers, three functions: load the data, compute on it, draw it.

❌ **Before** — one function loads, computes, and plots

```python
def behavior_figure(subjid):
    df = pd.read_csv(f"/data/{subjid}.csv")          # I/O + hard-coded path
    perf = df.groupby("session")["correct"].mean()   # analysis
    plt.figure()
    plt.plot(perf)                                    # plotting — own figure only
    plt.savefig(f"{subjid}.png")
```

You can't test the analysis without a file, the path exists on one machine, and
the plot can never be one panel of a bigger figure.

✅ **After** — I/O, analysis, and a plot that accepts an `ax`

```python
# --- I/O layer: load, with cache-or-compute (principle 3) ---
def get_behavior(subjid: str) -> pd.DataFrame:
    data = load_from_cache(subjid)
    if data is None:                       # cache miss: do the work once, save it
        data = compute_behavior(subjid)
        save_to_cache(subjid, data)
    return data

# --- analysis layer: pure, testable, no I/O or plotting ---
def session_performance(trials: pd.DataFrame) -> pd.Series:
    return trials.groupby("session")["correct"].mean()

# --- plotting layer: takes an ax, makes its own only if none is given ---
def plot_behavior(subjid: str, ax: plt.Axes | None = None) -> plt.Axes:
    perf = session_performance(get_behavior(subjid))
    if ax is None:
        _, ax = plt.subplots()
    ax.plot(perf.index, perf.values, marker="o")
    ax.set(xlabel="session", ylabel="P(correct)")
    return ax
```

Because `plot_behavior` accepts an `ax`, single-subject panels compose into a
grid with no changes:

```python
fig, axs = plt.subplots(1, 3, sharey=True)
for ax, subj in zip(axs, subjects):
    plot_behavior(subj, ax=ax)
```

> The manual cache-or-compute branch in `get_behavior` is exactly what
> `joblib.Memory` (principle 3) automates — reach for the hand-written version
> only when you need custom cache logic.

## 9. Fail loudly

❌ **Before** — a silent fallback hides a real problem

```python
def load_weight(subjid):
    try:
        return db.get_weight(subjid)
    except Exception:
        return 0.0          # a missing weight now looks like a 0 g animal
```

✅ **After** — let it fail where the problem actually is

```python
def load_weight(subjid: str) -> float:
    weight = db.get_weight(subjid)              # raises if the subject is missing
    if weight <= 0:
        raise ValueError(f"implausible weight {weight!r} g for {subjid!r}")
    return weight
```

A bare `except: pass` or a stand-in `0.0`/`NaN` turns a five-minute bug into a
wrong figure you trust for a month. Use a fallback only when it's a deliberate,
documented choice — and say why in a comment.

## 10. Comments explain the present, not the history

❌ **Before** — changelog and planning noise

```python
# changed from mean to median on 2026-05 (see analysis_plan.md, chunk 3)
# used to crash on empty input, fixed now
rate = np.median(counts) / window
```

✅ **After** — the invariant and the non-obvious why

```python
# median, not mean: a few giant ISIs from bursting would skew the mean
rate = np.median(counts) / window
```

The reader may not have your commit log, tickets, or session notes — comment the
code that's in front of them. The same goes for commit messages.

## 11. Optimize only when needed — and parallelize at the coarsest level

Correctness and clarity first. When something really is too slow, **profile
before you optimize** — `python -m cProfile`, `%timeit` in a notebook,
`line_profiler` for a hot function, or `py-spy` to sample a running process.
Usually the fix is caching (principle 3) or vectorizing (principle 4), not
parallelism.

When you do need parallelism, run it at the coarsest level — one substantial task
per session/subject, not per trial:

```python
from joblib import Parallel, delayed

# ❌ fine-grained: per-trial overhead (spawning, pickling) dwarfs the work
results = Parallel(n_jobs=-1)(delayed(process_trial)(t) for t in all_trials)

# ✅ coarse-grained: one independent, substantial task per session
results = Parallel(n_jobs=-1)(delayed(analyze_session)(s) for s in sessions)
```

`analyze_session` is a pure per-session function (principle 8), so each worker
loads its own data once and there's no shared state.

**Threads or processes?** For CPU-bound numeric work use *processes* — CPython's
GIL stops threads from running Python bytecode in parallel, so `ThreadPoolExecutor`
only helps I/O-bound tasks. joblib's default (`loky`) and
`concurrent.futures.ProcessPoolExecutor` both use processes: real parallelism, but
each task's arguments are pickled and shipped to the worker, so keep tasks coarse.
And vectorized NumPy already uses multi-threaded BLAS under the hood — don't wrap
it in more parallelism.

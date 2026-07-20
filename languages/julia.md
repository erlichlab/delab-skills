# delab practices — Julia

Idioms and tooling for the ten core principles in `../SKILL.md`. Defaults below
are lab recommendations; where a tool is named, it's a strong default you may
swap if a project already standardized on something else.

**Default stack:** `Pkg` (env + packaging), `Runic` (formatting),
`ExplicitImports.jl` + `Aqua.jl` (package hygiene), the `Test` stdlib (tests),
`Revise.jl` (dev loop), `BenchmarkTools.jl` (timing), `CairoMakie` (headless
plots) / `GLMakie` (interactive), `JLD2.jl` + `Scratch.jl` (caching).

Julia note: unlike Python, a hand-written `for` loop is already fast, so several
principles here are about *clarity and genericity* rather than speed — the speed
usually comes for free.

---

## 1. Package & environment management

Every project has its own `Project.toml` + `Manifest.toml`; activate it, add
`[compat]` bounds, and commit both files.

```julia
pkg> activate .          # this project's environment, not the global one
pkg> add DataFrames GLM
pkg> resolve             # after editing Project.toml
```

❌ **Before** — packages added to the global environment, no bounds

```julia
pkg> add DataFrames      # lands in @v1.x, shared by everything; unpinned
```

✅ **After** — a local, pinned, reproducible environment

```toml
# Project.toml
name = "SpikeAnalysis"

[deps]
DataFrames = "a93c6f00-e57d-5684-b7b6-d8193f3e46c0"
GLM = "38e38edf-8417-5370-ba26-9b57d4a4fda"

[compat]
DataFrames = "1"
GLM = "1"
julia = "1.10"           # target the LTS
```

A collaborator runs `pkg> instantiate` and gets the exact same versions. For
work spanning Julia versions, keep version-specific manifests (e.g.
`Manifest-v1.10.toml`) so each stays resolvable.

## 2. Functional code

Prefer pure functions; keep computation out of globals. In Julia this is also a
*performance* rule: reading a non-`const` global is type-unstable and slow.

❌ **Before** — reads and mutates a global, does I/O, all at once

```julia
const RESULTS = Dict{Symbol,Any}()

function analyze()
    df = CSV.read("session.csv", DataFrame)   # hidden I/O
    RESULTS[:mean_rt] = mean(df.rt)           # mutates global
end
```

✅ **After** — a pure core you can test, I/O at the call site

```julia
mean_rt(trials) = mean(@view trials.rt[trials.valid])

trials = CSV.read(path, DataFrame)   # edge: caller does the I/O
rt = mean_rt(trials)                 # pure, deterministic, testable
```

## 3. Cache expensive local results

Cache to disk keyed on the inputs, and only compute on a miss. `Scratch.jl`
gives you a git-ignored cache directory; `JLD2.jl` stores Julia values.

❌ **Before** — recomputes a slow step every run

```julia
load_features(session_id) = extract_features(read_raw(session_id))  # slow every time
```

✅ **After** — cache-or-compute

```julia
using JLD2, Scratch

cachedir() = @get_scratch!("features")     # git-ignored, per-package

function load_features(session_id::AbstractString)
    path = joinpath(cachedir(), "$(session_id).jld2")
    isfile(path) && return load(path, "features")
    features = extract_features(read_raw(session_id))
    jldsave(path; features)                # save once
    return features
end
```

Change the inputs and you write a new file; otherwise you reload in milliseconds.
(For pure in-session memoization, see `Memoization.jl`.)

## 4. Map / broadcast instead of hand-rolled loops

Prefer `map`, a comprehension, or broadcasting (`f.(xs)`) over an index loop that
pre-allocates and fills.

- **Here it's about clarity, not speed** — a Julia `for` loop is already fast.
  The win is no index bookkeeping, no `1:length` off-by-one, and a named
  function you can test on its own. It also pushes you toward small functions
  (principle 5).
- Broadcasting *also* fuses: `@. z = (x - μ) / σ` allocates no temporaries.

❌ **Before** — manual pre-allocate-and-fill

```julia
zscored = similar(rates)
for i in 1:length(rates)
    zscored[i] = (rates[i] - mean(rates)) / std(rates)   # mean/std recomputed each iter!
end
```

✅ **After** — broadcast, correct and allocation-light

```julia
μ, σ = mean(rates), std(rates)
zscored = (rates .- μ) ./ σ
```

The same for per-group work — fitting a GLM per subject won't get faster, but
factoring the body out and mapping still wins:

```julia
# ❌ body inlined in a loop
D = Dict()
for i in 1:length(subjids)
    d = filter(:subjid => ==(subjids[i]), big_df)
    m = fit(GeneralizedLinearModel, @formula(correct ~ coherence), d, Binomial())
    D[subjids[i]] = (; b = coef(m), se = stderror(m))
end

# ✅ a small, testable function mapped over the groups (no global reach-in)
function fit_subject(trials)
    m = fit(GeneralizedLinearModel, @formula(correct ~ coherence), trials, Binomial())
    return (; b = coef(m), se = stderror(m))
end

D = Dict(s => fit_subject(sdf) for (s, sdf) in pairs(groupby(big_df, :subjid)))
```

Now `fit_subject` can be unit-tested on one subject and reused elsewhere.

## 5. Small, single-purpose functions

Multiple dispatch rewards small methods with clear names — lean into it.

❌ **Before** — one function loads, cleans, models, and plots

```julia
function do_everything(path)
    df = CSV.read(path, DataFrame)
    df = filter(:rt => >(0), df)
    df.log_rt = log.(df.rt)
    m = lm(@formula(log_rt ~ coherence), df)
    scatter(df.coherence, df.log_rt); ...
    return m
end
```

✅ **After** — small, named, composable steps

```julia
load_trials(path) = CSV.read(path, DataFrame)
clean(trials)     = filter(:rt => >(0), trials)
fit_rt(trials)    = lm(@formula(log_rt ~ coherence), trials)

trials = clean(load_trials(path))
model  = fit_rt(trials)
```

## 6. Test-driven development

Write the test first with the `Test` stdlib, watch it fail, then implement.

```julia
using Test

@testset "mean_rt ignores invalid" begin           # write this BEFORE mean_rt exists
    trials = DataFrame(rt = [1.0, 3.0, 99.0], valid = [true, true, false])
    @test mean_rt(trials) == 2.0
end
```

Run with `pkg> test` (or `Pkg.test()`) — reserve full test runs for before you
submit; use `Revise` + a running session while iterating.

**Use synthetic fixtures, not real data.** The test builds its own tiny
`DataFrame`, so it passes on a fresh clone and in CI with no lab data present.
Never point a test at `/data/...`.

## 7. Never store secrets or hard-coded paths

❌ **Before** — credentials and an absolute path baked into source

```julia
const DB   = connect("postg:https://admin:hunter2@10.0.0.5/spikes")   # secret in git forever
const DATA = "/Users/jane/Dropbox/lab/data/session.csv"       # one machine only
```

✅ **After** — read from the environment / configurable roots

```julia
Base.@kwdef struct Config
    db_url::String    = ENV["LAB_DB_URL"]                         # required: errors if unset
    data_root::String = get(ENV, "LAB_DATA", expanduser("~/data"))
end

cfg = Config()
session = joinpath(cfg.data_root, "session.csv")
```

`ENV["LAB_DB_URL"]` throws a clear `KeyError` if the variable is missing (fail
loudly — principle 9). Load a `.env` in dev with `DotEnv.jl`; for persistent
per-package settings use `Preferences.jl`. Commit a `.env.example` with the
variable *names* only, and git-ignore `.env` and the cache directory.

## 8. Separate I/O, analysis, and plotting

Three layers, three functions: load the data, compute on it, draw it. A plotting
function takes an optional `ax` and makes its own only if none is given, so any
single panel drops into a multi-panel figure unchanged.

❌ **Before** — one function loads, computes, and plots

```julia
function behavior_figure(subjid)
    df   = CSV.read("/data/$(subjid).csv", DataFrame)       # I/O + hard-coded path
    perf = combine(groupby(df, :session), :correct => mean) # analysis
    fig  = Figure(); ax = Axis(fig[1, 1])
    scatterlines!(ax, perf.session, perf.correct_mean)      # plotting, own figure only
    save("$(subjid).png", fig)
end
```

✅ **After** — I/O (with cache-or-compute), pure analysis, an `ax`-aware plot

```julia
# --- I/O layer: load, with cache-or-compute (principle 3) ---
function get_behavior(subjid)
    data = load_from_behavior_cache(subjid)
    if isnothing(data)                       # cache miss: do the work once, save it
        data = compute_behavior(subjid)
        save_to_behavior_cache(subjid, data)
    end
    return data
end

# --- analysis layer: pure, testable, no I/O or plotting ---
session_performance(trials) =
    combine(groupby(trials, :session), :correct => mean => :perf)

# --- plotting layer: takes an ax, makes its own only if none is given ---
function plot_behavior(subjid; ax = nothing)
    perf = session_performance(get_behavior(subjid))
    if isnothing(ax)
        fig = Figure()
        ax = Axis(fig[1, 1]; xlabel = "session", ylabel = "P(correct)")
    end
    scatterlines!(ax, perf.session, perf.perf)
    return ax
end
```

Because `plot_behavior` accepts an `ax`, single-subject panels compose into a
grid with no changes:

```julia
fig = Figure()
for (i, subj) in enumerate(subjects)
    plot_behavior(subj; ax = Axis(fig[1, i]))
end
fig
```

(Prefer `nothing`/`isnothing` for an absent optional argument; reserve `missing`
for genuinely missing *data*.)

## 9. Fail loudly

❌ **Before** — a silent fallback hides a real problem

```julia
function load_weight(subjid)
    try
        return get_weight(db, subjid)
    catch
        return 0.0            # a missing weight now looks like a 0 g animal
    end
end
```

✅ **After** — let it fail where the problem actually is

```julia
function load_weight(subjid)
    weight = get_weight(db, subjid)               # throws if the subject is missing
    weight > 0 || throw(ArgumentError("implausible weight $(weight) g for $(subjid)"))
    return weight
end
```

A bare `catch` that returns a stand-in `0.0`/`NaN` turns a five-minute bug into a
wrong figure you trust for a month. This "surface it immediately" stance is the
default for the whole session — only swallow an error when it's a deliberate,
documented choice.

## 10. Comments explain the present, not the history

❌ **Before** — changelog and planning noise

```julia
# changed from mean to median on 2026-05 (see analysis_plan.md, chunk 3)
# used to crash on empty input, fixed now
rate = median(counts) / window
```

✅ **After** — the invariant and the non-obvious why

```julia
# median, not mean: a few giant ISIs from bursting would skew the mean
rate = median(counts) / window
```

The reader may not have your commit log, tickets, or session notes — comment the
code that's in front of them. The same goes for commit messages.

---

## Julia-specific: write generic code

These aren't among the ten core principles, but they're where lab Julia code
most often goes wrong. They also reinforce principle 2 (reuse) and principle 9
(fail loudly, not silently wrong).

- **Signatures: accept the widest type that works.** `f(A::AbstractMatrix)`, not
  `f(A::Matrix{Float64})`. An over-narrow signature silently fails to match a
  `view`, an `Adjoint`, a unit-bearing array, or a GPU array — and blocks reuse
  for no benefit. Constrain only when the algorithm genuinely requires it.
- **Don't assume 1-based indexing.** Use `eachindex(x)`, `axes(x, d)`,
  `firstindex`/`lastindex`, and `begin`/`end` instead of `1:length(x)`. Code that
  hardcodes `1` breaks on `OffsetArrays` and array views.
- **`@inbounds` is a loaded gun.** Add it only after you've proven the indices are
  valid *and* profiling shows the bounds check matters. A wrong `@inbounds` is
  silent memory corruption — the exact opposite of failing loudly.
- **Watch type stability in hot code.** A function whose return type is fixed by
  its argument types stays fast; check with `@code_warntype` or `JET.jl`.
- **Format and check.** Run `Runic` for formatting, `ExplicitImports.jl` to keep
  imports explicit, and `Aqua.jl` to catch common package problems in CI.

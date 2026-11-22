# delab practices — Julia

Idioms and tooling for the core principles in `../SKILL.md`. Defaults below
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

## 3. Separate I/O, analysis, and plotting

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
# --- I/O layer: load, with cache-or-compute (principle 7) ---
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

**Inject pre-fetched data.** Give the I/O function an optional `data` keyword: if
the caller passes already-loaded data, use it and skip I/O; otherwise fall back to
cache-or-fetch. Now one bulk query replaces N per-subject calls, and the same code
runs offline or in a test with no network.

```julia
function get_behavior(subjid; data = nothing)
    if !isnothing(data)                          # caller pre-fetched: no I/O, just select
        return filter(:subjid => ==(subjid), data)
    end
    cached = load_from_behavior_cache(subjid)
    if isnothing(cached)
        cached = compute_behavior(subjid)
        save_to_behavior_cache(subjid, cached)
    end
    return cached
end

all_trials = fetch_all_behavior(sessids)         # one bulk query, not length(sessids)
perf = map(s -> session_performance(get_behavior(s; data = all_trials)), sessids)
```

## 4. The point of a visualisation comes first

State the point of the panel before plotting (principle 4 in `../SKILL.md`;
details in [`visualisation.md`](../visualisation.md)). Use `CairoMakie` for
publication figures. `AlgebraOfGraphics.jl` is an allowed dependency if you
prefer a declarative style.

❌ **Before** — defaults: small text, crowded ticks, no units, opaque points

```julia
scatter(dose, effect)
save("fig.png", current_figure())
```

✅ **After** — one function draws, a separate one saves PNG and PDF

```julia
using CairoMakie

const FONT_SIZE = 14  # large enough to read at the size the panel is shown

"""
We plot each subject's effect against dose to show that the effect grows
with dose. Draws only; the caller passes computed values.
"""
function plot_dose_response!(ax::Axis, dose, effect)
    scatter!(ax, dose, effect; markersize = 10, color = (:black, 0.5))  # alpha
    return ax
end

function plot_dose_response(dose, effect)
    fig = Figure()
    ax = Axis(fig[1, 1];
        xlabel = "Dose (mg/kg)",
        ylabel = "Effect (% change in P(correct))",
        xlabelsize = FONT_SIZE, ylabelsize = FONT_SIZE,
        xticklabelsize = FONT_SIZE, yticklabelsize = FONT_SIZE,
        xticks = LinearTicks(4), yticks = LinearTicks(4),  # a modest number
    )
    plot_dose_response!(ax, dose, effect)
    return fig
end

"Write `<stem>.png` and `<stem>.pdf`."
function save_figure(fig, stem)
    for ext in ("png", "pdf")
        save("$stem.$ext", fig)
    end
end
```

The `!` method draws into an existing `Axis`, so the panel drops into a larger
`Figure`.

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

## 6. Map / broadcast instead of hand-rolled loops

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

## 7. Cache expensive local results

Cache to disk, and only compute on a miss. The key covers the inputs, the
parameters, and the code of the cached function; the file has a readable name,
and the key is stored in the file itself (see SKILL.md principle 7).
`Scratch.jl` gives you a cache directory and `JLD2.jl` stores Julia values.

❌ **Before** — recomputes a slow step every run

```julia
load_features(session_id) = extract_features(read_raw(session_id))  # slow every time
```

✅ **After** — readable filename, key stored in the file, code version in the key

```julia
using JLD2, Scratch, SHA

cachedir() = @get_scratch!("features")     # outside the repo; see note below

# Hash of the file that defines the method (so closures, comprehensions and
# keyword bodies inside it count); helpers in other files are not included.
# `argtypes` picks the method, e.g. (Vector{Float64},). Errors if no single
# method matches or the file cannot be read (a REPL definition has no file).
function code_version(f, argtypes)
    file = String(only(methods(f, argtypes)).file)
    first(bytes2hex(open(sha256, file)), 12)
end

# raw_path: your project's session id -> raw file lookup
function cache_key(session_id, bin_ms)
    Dict("input_sha256" => bytes2hex(open(sha256, raw_path(session_id))),
         "code" => code_version(extract_features, (Vector{Float64},)),
         "params" => string((; bin_ms)))
end

# A corrupt file (crash mid-save) errors on load: delete it by hand.
function cached_jld2(path::AbstractString, key, compute)
    if isfile(path)
        hit = jldopen(path) do f
            haskey(f, "key") && f["key"] == key ? f["value"] : nothing
        end
        isnothing(hit) || return hit
    end
    value = compute()
    mkpath(dirname(path))
    jldsave(path; value, key)              # data and key saved together
    return value
end

function load_features(session_id::AbstractString; bin_ms = 50)
    path = joinpath(cachedir(), "features_$(session_id)_bin$(bin_ms)ms.jld2")
    cached_jld2(path, cache_key(session_id, bin_ms),
                () -> extract_features(read_raw(session_id); bin_ms))
end
```

Change the input file, the parameters, or anything in the file that defines
`extract_features` and the stored key no longer matches, so it recomputes and
overwrites; otherwise it reads the cached file. (Any edit to that file counts,
even to another function in it: one file, not the whole repo.) Every call still
hashes the raw file. The file is `features_subj12_bin50ms.jld2`, and
`load(path, "key")` shows how it was made.

Limits. Only the file defining `extract_features` is hashed, so a change in a
helper defined in another file is not noticed: clear the cache by hand when you
change a helper. Config and anything read at run time must be in the
parameters. The hash is of the function you pass, so with several methods pass
the argument types of the one that actually runs. It reads the file on disk, so
reload it (`Revise`, or restart) after editing before trusting a hit; a session
still running the old code would store its result under the new key. Inside a
package, `@get_scratch!` is a per-package directory outside the repo (so there
is nothing to git-ignore); in a plain script it is a shared scratchspace where
same-named files from different projects can collide: use a project-specific
name, or a git-ignored `.cache/` in the repo instead. (For pure in-session
memoization, see `Memoization.jl`.)

## 8. Test-driven development

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

## 9. Never store secrets or hard-coded paths

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
loudly — principle 10). Load a `.env` in dev with `DotEnv.jl`; for persistent
per-package settings use `Preferences.jl`. Commit a `.env.example` with the
variable *names* only, and git-ignore `.env` and the cache directory.

## 10. Fail loudly

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

## 11. Comments explain the present, not the history

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

## 12. Optimize only when needed — and parallelize at the coarsest level

Correctness and clarity first. When something really is too slow, **measure
before you optimize** — `@btime` (BenchmarkTools) for a function, `@profile` +
`Profile` for a whole run. In Julia the first fix is almost never parallelism:
it's **type stability** (check `@code_warntype` or `JET.jl`), which often buys a
10× on its own, then caching (principle 7) and broadcasting (principle 6).

When you do need parallelism, run it at the coarsest level — one substantial task
per session/subject, not per trial:

```julia
# ❌ fine-grained: per-trial overhead dwarfs the work
Threads.@threads for t in all_trials ... end

# ✅ coarse-grained: spawn one task per session, then fetch the results
tasks   = [Threads.@spawn analyze_session(s) for s in sessions]
results = fetch.(tasks)
```

For a handful of heavy, independent, uneven per-session tasks, `Threads.@spawn` +
`fetch` is the idiomatic choice: the scheduler load-balances across threads and
spawn overhead is nothing next to a whole-session analysis. (`@threads` — ideally
`@threads :dynamic` — is for simple uniform loops over *many cheap* items, the
fine-grained case you're avoiding here; `OhMyThreads.jl` offers an ergonomic
`tmap`.) `analyze_session` is pure (principle 3), so tasks share no mutable state.

**Threads or processes?** `Threads.@spawn` shares memory — workers see the same
arrays with no copying — at low overhead, but stays on one machine and needs
`julia -t auto`; use it when sessions share large read-only data. `pmap`/
`Distributed` run separate worker *processes*: data is copied to them and startup
costs more, but they isolate state and scale across machines — the path to a SLURM
cluster (a later version). Stick with threads until you outgrow one node.

---

## Julia-specific: write generic code

These aren't among the core principles, but they're where lab Julia code
most often goes wrong. They also reinforce principle 2 (reuse) and principle 10
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

# delab practices — MATLAB

Idioms and tooling for the core principles in `../SKILL.md`, matched to the
lab's [elutils](https://github.com/erlichlab/elutils) conventions. Where elutils
already establishes a pattern (`+packages`, `utils.inputordefault`, axis-handle
plotting), follow it so lab code stays consistent.

**MATLAB has no package manager and one function per file** — two facts that
shape several principles below. Organize with `+package` folders, manage the
path with a MATLAB Project (`.prj`) or a `setup.m`, test with `matlab.unittest`
(`runtests`), and pull shared helpers from elutils (`utils.`, `stats.`, `draw.`).

MATLAB note: it's array-oriented, so vectorized code is both idiomatic and fast;
reserve explicit loops for genuine sequential state.

---

## 1. Package & environment management

There's no dependency resolver, so do the reproducible things you *can*:

- **Organize into `+package` folders** and call with dot notation
  (`stats.bootmean`). The parent folder goes on the path; the packages namespace
  everything under it.
- **Put the repo on the path deterministically** — a MATLAB Project (`.prj`) or a
  committed `setup.m`, not each user's ad-hoc `addpath`. Avoid
  `addpath(genpath(...))` of everything; add the specific roots.
- **Declare what you depend on**: the required MATLAB release and toolboxes (in
  the README or a `Contents.m`), and pin external lab code like elutils as a git
  submodule, not copied-in files.

❌ **Before** — a flat pile of `.m` files, path assumed, toolboxes assumed

```matlab
addpath(genpath('~/matlab/mystuff'))    % everything, in some order, per machine
m = fitglm(...)                          % assumes Statistics Toolbox is present
```

✅ **After** — namespaced, set up once, dependencies stated

```matlab
% setup.m (committed): add just what this project needs
here = fileparts(mfilename('fullpath'));
addpath(here, fullfile(here, 'extern', 'elutils'));

% README: "Requires R2021b+, Statistics and Machine Learning Toolbox."
perf = stats.bootmean(x);                % from elutils, namespaced
```

## 2. Functional code

Prefer pure functions; pass data in and return results. Never reach into the
base workspace (`evalin`/`assignin`) or lean on `global` — both are invisible
state that breaks reuse and testing.

❌ **Before** — `global` state and I/O tangled together

```matlab
function analyze()
    global RESULTS
    T = readtable('session.csv');        % hidden I/O
    RESULTS.mean_rt = mean(T.rt);        % mutates a global
end
```

✅ **After** — a pure core, I/O at the call site

```matlab
function rt = mean_rt(trials)
    rt = mean(trials.rt(trials.valid));
end

trials = readtable(path);                % edge: caller does the I/O
rt = mean_rt(trials);                    % pure, deterministic, testable
```

## 3. Cache expensive local results

Cache to a `.mat` file keyed on the inputs, and only compute on a miss.

❌ **Before** — recomputes a slow step every run

```matlab
function f = load_features(session_id)
    f = extract_features(read_raw(session_id));   % slow every time
end
```

✅ **After** — cache-or-compute

```matlab
function features = load_features(session_id)
    cachefile = fullfile(cachedir(), sprintf('features_%s.mat', session_id));
    if isfile(cachefile)
        features = load(cachefile).features;      % reload in ms
        return
    end
    features = extract_features(read_raw(session_id));
    save(cachefile, 'features');                  % save once
end
```

`cachedir()` returns a git-ignored folder. (For in-session reuse of a pure
function, MATLAB's built-in `memoize` wraps a function handle.)

## 4. Map / vectorize instead of hand-rolled loops

Prefer a vectorized operation, or `arrayfun`/`cellfun` as `map`, over an index
loop that pre-allocates and fills.

❌ **Before** — manual loop, statistics recomputed each iteration

```matlab
z = zeros(size(rates));
for i = 1:numel(rates)
    z(i) = (rates(i) - mean(rates)) / std(rates);   % mean/std recomputed each iter!
end
```

✅ **After** — vectorized

```matlab
z = (rates - mean(rates)) / std(rates);
```

For per-group work — fitting a GLM per subject won't get faster, but factoring
the body into a small function and mapping still wins (testable, reusable):

```matlab
function s = fit_subject(trials)
    m = fitglm(trials, 'correct ~ coherence', 'Distribution', 'binomial');
    s = struct('b', m.Coefficients.Estimate, 'p', m.Coefficients.pValue);
end

% map fit_subject over per-subject groups
[gid, subj] = findgroups(big_table.subjid);
results = arrayfun(@(g) fit_subject(big_table(gid == g, :)), 1:numel(subj));
```

Now `fit_subject` can be unit-tested on one subject. (`splitapply`/`rowfun` are
the fully vectorized route when the body fits their shape.)

**Use the map-style functions — they're underused.** Many people reach for a
`for` loop because `arrayfun`, `cellfun`, and `structfun` feel unfamiliar, but
they *are* MATLAB's `map` and make the intent obvious (pass `'UniformOutput',
false` when the result isn't a scalar per element). One exception: `bsxfun` is
legacy — since R2016b MATLAB expands sizes implicitly, so write `a - mean(a)`,
not `bsxfun(@minus, a, mean(a))`.

## 5. Small, single-purpose functions

Keep functions small — but MATLAB's *one function per file* rule means a pile of
tiny public files is its own kind of mess. Two tools resolve the tension:

- **Local functions** for helpers used only within one file: define them after
  the main function in the same `.m` file. No file explosion, and they stay
  private to that file.
- **`+package` folders** to organize the functions that *are* shared, so related
  helpers group under one namespace (`utils.`, `draw.`).

**Don't** create a `classdef` full of `static` methods just to group functions —
a `+package` folder does exactly that, without the ceremony.

```matlab
% fit_rt_model.m — one public function, private helpers as local functions
function model = fit_rt_model(path)
    trials = clean(load_trials(path));
    model  = fit_rt(trials);
end

function trials = load_trials(path)     % local: visible only in this file
    trials = readtable(path);
end
function trials = clean(trials)
    trials = trials(trials.rt > 0, :);
end
function model = fit_rt(trials)
    model = fitlm(trials, 'log_rt ~ coherence');
end
```

## 6. Test-driven development

Write a test first with `matlab.unittest`, watch it fail, then implement. Run the
folder with `runtests`.

```matlab
% tests/test_mean_rt.m — write this BEFORE mean_rt exists
function tests = test_mean_rt
    tests = functiontests(localfunctions);
end

function test_ignores_invalid(testCase)
    trials = table([1;3;99], logical([1;1;0]), 'VariableNames', {'rt','valid'});
    verifyEqual(testCase, mean_rt(trials), 2)
end
```

```matlab
>> runtests('tests')      % red -> implement mean_rt -> green
```

**Use synthetic fixtures, not real data.** The test builds its own tiny `table`,
so it passes on a fresh clone with no lab data present. Never point a test at a
`/data/...` file.

## 7. Never store secrets or hard-coded paths

❌ **Before** — credentials and an absolute path baked into source

```matlab
conn = database('spikes', 'admin', 'hunter2');          % secret in git forever
data = '/Users/jane/Dropbox/lab/data/session.csv';      % one machine only
```

✅ **After** — read from the environment / configurable roots

```matlab
db_url    = getenv('LAB_DB_URL');                        % set outside the repo
assert(~isempty(db_url), 'delab:config', 'set LAB_DB_URL');   % fail loudly (principle 9)

data_root = getenv('LAB_DATA');
if isempty(data_root), data_root = fullfile(getenv('HOME'), 'data'); end
session = fullfile(data_root, 'session.csv');
```

Use `fullfile` (never string-concatenate paths), keep credentials in environment
variables or a git-ignored config file, and git-ignore the cache directory.

## 8. Separate I/O, analysis, and plotting

Three layers: load the data, compute on it, draw it. A plotting function takes an
optional axes handle and creates one only if none is given — the elutils
`draw.shadeplot` convention — so any panel drops into a multi-panel figure.

❌ **Before** — one function loads, computes, and plots

```matlab
function behavior_figure(subjid)
    T    = readtable(sprintf('/data/%s.csv', subjid));         % I/O + hard-coded path
    perf = groupsummary(T, 'session', 'mean', 'correct');      % analysis
    figure; plot(perf.session, perf.mean_correct, '-o');       % plotting, own figure only
    saveas(gcf, sprintf('%s.png', subjid));
end
```

✅ **After** — I/O (cache-or-compute), pure analysis, an `ax`-aware plot

```matlab
% --- I/O layer: load, with cache-or-compute (principle 3) ---
function data = get_behavior(subjid)
    data = load_from_behavior_cache(subjid);
    if isempty(data)                          % cache miss: do the work once, save it
        data = compute_behavior(subjid);
        save_to_behavior_cache(subjid, data);
    end
end

% --- analysis layer: pure, testable, no I/O or plotting ---
function perf = session_performance(trials)
    perf = groupsummary(trials, 'session', 'mean', 'correct');
end

% --- plotting layer: takes an ax, makes its own only if none is given ---
function ax = plot_behavior(subjid, varargin)
    ax = utils.inputordefault('ax', [], varargin);
    perf = session_performance(get_behavior(subjid));
    if isempty(ax), ax = axes(); end
    plot(ax, perf.session, perf.mean_correct, '-o');
    xlabel(ax, 'session'); ylabel(ax, 'P(correct)');
end
```

Because `plot_behavior` accepts an `'ax'`, single-subject panels compose into a
grid with no changes:

```matlab
t = tiledlayout(1, numel(subjects));
for i = 1:numel(subjects)
    plot_behavior(subjects(i), 'ax', nexttile(t));
end
```

## 9. Fail loudly

❌ **Before** — a silent fallback hides a real problem

```matlab
function w = load_weight(subjid)
    try
        w = get_weight(subjid);
    catch
        w = 0;              % a missing weight now looks like a 0 g animal
    end
end
```

✅ **After** — let it fail where the problem actually is

```matlab
function w = load_weight(subjid)
    w = get_weight(subjid);                 % errors if the subject is missing
    assert(w > 0, 'delab:implausibleWeight', ...
        'implausible weight %g g for %s', w, subjid);
end
```

A bare `catch` that returns a stand-in `0`/`NaN` turns a five-minute bug into a
wrong figure you trust for a month. Use `error`/`assert` with an identifier and a
clear message, or `validateattributes`/an `arguments` block to reject bad input
at the door. Only swallow an error when it's a deliberate, documented choice.

## 10. Comments explain the present, not the history

❌ **Before** — changelog and planning noise

```matlab
% changed from mean to median on 2026-05 (see analysis_plan.md, chunk 3)
% used to crash on empty input, fixed now
rate = median(counts) / window;
```

✅ **After** — the invariant and the non-obvious why

```matlab
% median, not mean: a few giant ISIs from bursting would skew the mean
rate = median(counts) / window;
```

The reader may not have your commit log, tickets, or session notes — comment the
code that's in front of them. (Keep the separate *help block* below the signature
— see the MATLAB-specific note — that's documentation, not a comment about a
line.)

## 11. Optimize only when needed — and parallelize at the coarsest level

Correctness and clarity first. When something really is too slow, **profile
before you optimize** — `profile on` / `profile viewer`, or `timeit` and
`tic`/`toc` for a single call. Usually the fix is preallocation, vectorization
(principle 4), or caching (principle 3), not parallelism.

When you do need parallelism, run it at the coarsest level — one substantial task
per session/subject, not per trial (requires the Parallel Computing Toolbox):

```matlab
% ❌ fine-grained: per-trial overhead dwarfs the work
parfor t = 1:numel(all_trials)
    r(t) = process_trial(all_trials(t));
end

% ✅ coarse-grained: one independent, substantial task per session
results = cell(1, numel(sessions));
parfor s = 1:numel(sessions)
    results{s} = analyze_session(sessions(s));   % pure, loads its own data
end
```

`analyze_session` is a pure per-session function (principle 8), so each worker
loads its own data with no shared state. Start the pool once with `parpool`;
`parfeval`/`batch` help when tasks are long-running.

**Pool type — and implicit multithreading.** Since R2020a a pool is either
`parpool("Processes")` (the default: separate process workers, ~one per core, full
function support, data copied to each) or `parpool("threads")` (thread workers
with shared memory, faster startup and no copy, but only a subset of functions
supported). Default to Processes; switch to threads when workers share large data
and the functions you call are supported. Separately, MATLAB already multithreads
many built-in array and BLAS operations across cores on its own — so vectorized
math (principle 4) uses your cores with no pool at all.

---

## MATLAB-specific notes

- **Keep the H1 line and help block.** The first comment line after the signature
  is the "H1 line" that `lookfor` and `help` display; the block under it is the
  function's documentation. elutils functions all carry a short usage block —
  match that.
- **`arguments` blocks (R2019b+)** are a modern alternative to
  `utils.inputordefault` for defaults and input validation, and they fail loudly
  on bad input. Either is fine; be consistent within a project.
- **Preallocate** loop outputs (`x = zeros(n,1)`) instead of growing arrays in a
  loop.
- **Avoid `global`, `eval`, `evalin`, and `assignin`** — they hide state and
  defeat both testing and the Code Analyzer.
- **Heed the Code Analyzer** (`checkcode`, or the editor squiggles) — it catches
  most of the above automatically.

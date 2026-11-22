# delab practices — R

Idioms and tooling for the core principles in `../SKILL.md`. Defaults
below are lab recommendations; where a tool is named, it's a strong default you
may swap if a project already standardized on something else.

**Default stack:** `renv` (environments) with `pak` for fast binary installs, the
`tidyverse` (`dplyr`, `tidyr`, `purrr`, `ggplot2`), `testthat` (tests),
`memoise` (in-session memoization), `targets` (pipeline caching), `digest`
(hashing for cache keys), `here` (paths), `styler` + `lintr` (format/lint),
`furrr`/`future` (parallelism).

R note: it's vectorized and functional, so vectorized and `purrr` code is
idiomatic. User-level R code is single-threaded, so parallelism means separate
processes (see principle 12).

---

## 1. Package & environment management

Unlike MATLAB, R has real dependency management — use it. `renv` gives each
project an isolated library and a committed lockfile.

```r
renv::init()        # once: create a project library
renv::snapshot()    # write renv.lock (commit it)
renv::restore()     # collaborator: reproduce the exact versions
```

❌ **Before** — ad hoc installs, no record

```r
install.packages("dplyr")
library(dplyr)        # whatever version happens to be installed globally
```

✅ **After** — declared and locked in `renv.lock`

```r
# renv.lock records dplyr 1.1.4, its dependencies, and the R version.
# A fresh clone + renv::restore() reproduces the environment exactly.
library(dplyr)
```

For a shared analysis packaged as a package, declare dependencies in
`DESCRIPTION` (`Imports:`) as well.

### Get prebuilt binaries on Linux — don't compile from source

Plain CRAN ships precompiled binaries only for Windows and macOS, so on Linux
`renv`/`install.packages` often **compiles heavy packages from source**
(`brms`, `RcppParallel`, `StanHeaders`, …) — slow, and it fails without the right
system toolchain. Fix it in the project `.Rprofile` with two changes: use `pak`
as the installer, and pull binaries from [Posit Public Package Manager
(P3M)](https://p3m.dev) for the detected distro. It's best-effort — on an
unsupported distro (or Windows/macOS, which already get CRAN binaries) it falls
back to plain CRAN and still works, with no env vars or manual setup.

```r
# .Rprofile — after source("renv/activate.R")
local({
  # 1. Use pak as renv's installer backend (parallel downloads/installs).
  options(renv.config.pak.enabled = TRUE)

  # 2. On supported Linux distros, fetch precompiled binaries from P3M.
  if (Sys.info()[["sysname"]] != "Linux") return(invisible())

  codename <- tryCatch({
    os <- readLines("/etc/os-release", warn = FALSE)
    ln <- grep("^VERSION_CODENAME=", os, value = TRUE)
    if (length(ln)) gsub('^VERSION_CODENAME=|"', "", ln[1]) else ""
  }, error = function(e) "")

  supported <- c("focal", "jammy", "noble",   # Ubuntu 20.04 / 22.04 / 24.04
                 "bullseye", "bookworm")       # Debian 11 / 12
  if (!codename %in% supported) return(invisible())   # fall back to CRAN

  options(
    repos = c(P3M = sprintf(
      "https://packagemanager.posit.co/cran/__linux__/%s/latest", codename)),
    # P3M only returns binaries when the client advertises its platform.
    HTTPUserAgent = sprintf("R/%s R (%s)", getRversion(),
      paste(getRversion(), R.version$platform, R.version$arch, R.version$os)))
})
```

Committed to `.Rprofile`, a labmate just runs `renv::restore()` and gets binaries.
(Working example: the `alm-riskychoice-2026` paper repo, `src/R/.Rprofile`.)

## 2. Functional code

R is a functional language — lean into it. Keep functions pure; never mutate the
global environment with `<<-` or reach for globals.

❌ **Before** — superassignment mutates a global, I/O tangled in

```r
RESULTS <- list()
analyze <- function() {
  df <- readr::read_csv("session.csv")     # hidden I/O
  RESULTS$mean_rt <<- mean(df$rt)          # mutates the global env
}
```

✅ **After** — a pure core you can test, I/O at the call site

```r
mean_rt <- function(trials) mean(trials$rt[trials$valid])

trials <- readr::read_csv(path)            # edge: caller does the I/O
rt <- mean_rt(trials)                      # pure, deterministic, testable
```

## 3. Separate I/O, analysis, and plotting

Three layers: load the data, compute on it, draw it. In R the composable-plot
idiom is to **return a `ggplot` object** (don't print or `ggsave` inside), then
combine panels with `patchwork` — the analog of passing in an axis.

❌ **Before** — one function loads, computes, and plots

```r
behavior_figure <- function(subjid) {
  df   <- readr::read_csv(sprintf("/data/%s.csv", subjid))          # I/O + hard-coded path
  perf <- dplyr::summarise(dplyr::group_by(df, session), perf = mean(correct))  # analysis
  ggplot2::ggsave(sprintf("%s.png", subjid),                         # plotting + side effect
    ggplot2::ggplot(perf, ggplot2::aes(session, perf)) + ggplot2::geom_line())
}
```

✅ **After** — I/O (cache-or-compute), pure analysis, a plot that returns an object

```r
# --- I/O layer: load, with cache-or-compute (principle 7) ---
get_behavior <- function(subjid) {
  data <- load_from_behavior_cache(subjid)
  if (is.null(data)) {                       # cache miss: do the work once, save it
    data <- compute_behavior(subjid)
    save_to_behavior_cache(subjid, data)
  }
  data
}

# --- analysis layer: pure, testable, no I/O or plotting ---
session_performance <- function(trials) {
  trials |>
    dplyr::group_by(session) |>
    dplyr::summarise(perf = mean(correct), .groups = "drop")
}

# --- plotting layer: build and RETURN a ggplot; caller composes/saves it ---
plot_behavior <- function(subjid) {
  perf <- session_performance(get_behavior(subjid))
  ggplot2::ggplot(perf, ggplot2::aes(session, perf)) +
    ggplot2::geom_line() + ggplot2::geom_point() +
    ggplot2::labs(x = "session", y = "P(correct)")
}
```

Because each call returns a plot object, panels compose into a figure with no
changes:

```r
library(patchwork)
plots <- purrr::map(subjects, plot_behavior)
wrap_plots(plots, nrow = 1)
```

**Inject pre-fetched data.** Give the I/O function an optional `data` argument: if
the caller passes already-loaded data, use it and skip I/O; otherwise fall back to
cache-or-fetch. Now one bulk query replaces N per-subject calls, and the same code
runs offline or in a test with no network.

```r
get_behavior <- function(subjid, data = NULL) {
  if (!is.null(data)) {                      # caller pre-fetched: no I/O, just select
    return(dplyr::filter(data, subjid == !!subjid))
  }
  cached <- load_from_behavior_cache(subjid)
  if (is.null(cached)) {
    cached <- compute_behavior(subjid)
    save_to_behavior_cache(subjid, cached)
  }
  cached
}

all_trials <- fetch_all_behavior(subjids)    # one bulk query, not length(subjids)
perf <- purrr::map(subjids, ~ session_performance(get_behavior(.x, data = all_trials)))
```

## 4. The point of a visualisation comes first

State the point of the panel before plotting (principle 4 in `../SKILL.md`;
details in [`visualisation.md`](../visualisation.md)). Use `ggplot2`: it
returns a plot object, so a panel composes into a larger figure.

❌ **Before** — defaults: small text, opaque points, no units on the labels

```r
plot(df$dose, df$effect)
```

✅ **After** — one function builds the plot, a separate one saves PNG and PDF

```r
library(ggplot2)

FONT_SIZE <- 14  # large enough to read at the size the panel is shown

plot_dose_response <- function(dose, effect) {
  # We plot each subject's effect against dose to show that the effect grows
  # with dose. Builds the plot only; the caller passes computed values. (This
  # function makes one manuscript panel, so its comment states that panel's
  # point; a general-purpose plotting function would say when to use it.)
  ggplot(data.frame(dose, effect), aes(dose, effect)) +
    geom_point(size = 3, alpha = 0.5) +  # alpha: overlap stays visible
    # n.breaks is a hint: ggplot picks round values, which may omit the top
    # dose; pass `breaks =` with the dose levels if they must all show.
    scale_x_continuous(n.breaks = 4) +
    scale_y_continuous(n.breaks = 4) +
    labs(x = "Dose (mg/kg)", y = "Effect (% change in P(correct))") +
    theme_classic(base_size = FONT_SIZE)
}

save_figure <- function(plot, stem) {
  # Writes `<stem>.png` and `<stem>.pdf`.
  for (ext in c("png", "pdf")) {
    ggsave(paste0(stem, ".", ext), plot, width = 4, height = 3.5, dpi = 300)
  }
}
```

## 5. Small, single-purpose functions

Small functions compose cleanly through the pipe. R lets you keep several in one
file, so group them by theme (and use the package `R/` layout for shared code).

❌ **Before** — one function loads, cleans, and models

```r
do_everything <- function(path) {
  df <- readr::read_csv(path)
  df <- dplyr::filter(df, rt > 0)
  df$log_rt <- log(df$rt)
  lm(log_rt ~ coherence, df)
}
```

✅ **After** — small, named steps composed with the pipe

```r
load_trials <- function(path) readr::read_csv(path)
clean       <- function(trials) dplyr::filter(trials, rt > 0)
add_log_rt  <- function(trials) dplyr::mutate(trials, log_rt = log(rt))
fit_rt      <- function(trials) lm(log_rt ~ coherence, trials)

model <- load_trials(path) |> clean() |> add_log_rt() |> fit_rt()
```

## 6. Map / vectorize instead of hand-rolled loops

Prefer a vectorized operation or `purrr::map` over a `for` loop that grows a list
by index.

❌ **Before** — manual loop, statistics recomputed each iteration

```r
z <- numeric(length(rates))
for (i in seq_along(rates)) {
  z[i] <- (rates[i] - mean(rates)) / sd(rates)    # mean/sd recomputed each iter!
}
```

✅ **After** — vectorized

```r
z <- (rates - mean(rates)) / sd(rates)
```

For per-group work — fitting a GLM per subject won't get faster, but factoring the
body into a small function and mapping still wins:

```r
# ❌ body inlined in a loop
results <- list()
for (i in seq_along(subjids)) {
  d <- dplyr::filter(big_df, subjid == subjids[i])
  m <- glm(correct ~ coherence, binomial(), d)
  results[[i]] <- coef(m)
}

# ✅ a small, testable function mapped over per-subject groups
fit_subject <- function(trials) {
  m <- glm(correct ~ coherence, binomial(), trials)
  tibble::tibble(term = names(coef(m)), b = coef(m))
}

results <- big_df |>
  dplyr::group_by(subjid) |>
  dplyr::group_modify(~ fit_subject(.x))
```

Now `fit_subject` can be unit-tested on one subject. (`split(big_df, ~subjid) |>
purrr::map_dfr(fit_subject, .id = "subjid")` is the base-`purrr` equivalent.)

## 7. Cache expensive local results

Cache to disk so unchanged work isn't repeated. The key covers the inputs, the
parameters, and the code of the cached function; the file has a readable name,
and the key is stored in the file's metadata (see SKILL.md principle 7).

❌ **Before** — recomputes a slow step every run

```r
load_features <- function(session_id) extract_features(read_raw(session_id))  # slow every time
```

✅ **After** — readable filename, key on the object, code version in the key

```r
CACHE_DIR <- ".cache"                      # git-ignored

# The function's own arguments and body (live, so it matches what runs);
# helpers it calls are not included.
code_version <- function(f) {
  code <- c(deparse(formals(f)), deparse(body(f)))
  substr(digest::digest(paste(code, collapse = "\n"), "sha256",
                        serialize = FALSE), 1, 12)
}

# raw_path: your project's session id -> raw file lookup
cache_key <- function(session_id, params) {
  list(input_sha256 = digest::digest(raw_path(session_id), "sha256",
                                     file = TRUE),
       code = code_version(extract_features),
       params = params)
}

cached_rds <- function(path, key, compute) {
  if (file.exists(path)) {
    cached <- readRDS(path)     # a corrupt file errors here: delete it by hand
    if (identical(attr(cached, "cache_key"), key)) return(cached)
  }
  result <- compute()
  stopifnot(!is.null(result))   # attributes cannot be set on NULL
  attr(result, "cache_key") <- key           # key travels with the data
  dir.create(dirname(path), showWarnings = FALSE, recursive = TRUE)
  saveRDS(result, path)
  result
}

load_features <- function(session_id, bin_ms = 50) {
  path <- file.path(CACHE_DIR,
                    sprintf("features_%s_bin%dms.rds", session_id, bin_ms))
  cached_rds(path, cache_key(session_id, list(bin_ms = bin_ms)), function() {
    extract_features(read_raw(session_id), bin_ms = bin_ms)
  })
}
```

Change the input file, the parameters, or the body of `extract_features` and the
stored key no longer matches, so it recomputes; otherwise it reads the cached
file. Every call still hashes the raw file. The file is
`features_subj12_bin50ms.rds`, and `attr(readRDS(path), "cache_key")` shows how
it was made.

Limits. Only `extract_features` itself is hashed, so a change in a helper it
calls is not noticed: clear `.cache/` by hand when you change a helper. Config
and anything read at run time must be in the parameters. The hash is of the
function you pass, so for an S3 generic pass the method that actually runs. It
is the function as defined in the running session, so it matches what runs;
re-`source` an edited file before trusting a hit. `digest` belongs in your
`renv` lockfile.
(For in-session memoization of a pure function, see `memoise`; for a whole
multi-step pipeline, `targets` caches each step and reruns only what changed.)

## 8. Test-driven development

Write the test first with `testthat`, watch it fail, then implement.

```r
# tests/testthat/test-mean_rt.R — write this BEFORE mean_rt exists
test_that("mean_rt ignores invalid trials", {
  trials <- tibble::tibble(rt = c(1, 3, 99), valid = c(TRUE, TRUE, FALSE))
  expect_equal(mean_rt(trials), 2)
})
```

```r
devtools::test()      # red -> implement mean_rt -> green
```

**Use synthetic fixtures, not real data.** The test builds its own tiny `tibble`,
so it passes on a fresh clone with no lab data present. Never point a test at a
`/data/...` file.

## 9. Never store secrets or hard-coded paths

❌ **Before** — credentials and an absolute path baked into source

```r
con  <- DBI::dbConnect(RMariaDB::MariaDB(), user = "admin", password = "hunter2")  # secret in git
data <- "/Users/jane/Dropbox/lab/data/session.csv"                        # one machine only
```

✅ **After** — read from the environment / configurable roots

```r
db_url <- Sys.getenv("LAB_DB_URL")
stopifnot(nzchar(db_url))                    # fail loudly if unset (principle 10)

data_root <- Sys.getenv("LAB_DATA", unset = path.expand("~/data"))
session   <- file.path(data_root, "session.csv")
```

Keep secrets in a git-ignored `.Renviron` (read via `Sys.getenv`) or the `keyring`
package. Use `here::here()` for paths *inside* the project — never `setwd()` or
absolute paths — and git-ignore `.Renviron` and the cache directory. Also git-
ignore R's session cruft — `.Rhistory`, `.RData`, `.Rproj.user/` — and never
commit `renv/library/`; the lockfile (principle 1) is enough to rebuild it.

## 10. Fail loudly

❌ **Before** — a silent fallback hides a real problem

```r
load_weight <- function(subjid) {
  tryCatch(get_weight(subjid), error = function(e) 0)   # a missing weight looks like 0 g
}
```

✅ **After** — let it fail where the problem actually is

```r
load_weight <- function(subjid) {
  weight <- get_weight(subjid)               # errors if the subject is missing
  if (weight <= 0) {
    stop(sprintf("implausible weight %g g for %s", weight, subjid))
  }
  weight
}
```

A `tryCatch` that returns a stand-in `0`/`NA` turns a five-minute bug into a wrong
figure you trust for a month. Use `stop`/`stopifnot`/`rlang::abort` with a clear
message, and be wary of R silently returning `NA` or partial-matching argument
names. Only swallow an error when it's a deliberate, documented choice.

## 11. Comments explain the present, not the history

❌ **Before** — changelog and planning noise

```r
# changed from mean to median on 2026-05 (see analysis_plan.md, chunk 3)
# used to crash on empty input, fixed now
rate <- median(counts) / window
```

✅ **After** — the invariant and the non-obvious why

```r
# median, not mean: a few giant ISIs from bursting would skew the mean
rate <- median(counts) / window
```

The reader may not have your commit log, tickets, or session notes — comment the
code that's in front of them. The same goes for commit messages.

## 12. Optimize only when needed — and parallelize at the coarsest level

Correctness and clarity first. When something really is too slow, **profile before
you optimize** — `profvis::profvis()` for a run, `bench::mark()` to compare
alternatives. Usually the fix is vectorizing (principle 6) or caching (principle
7), not parallelism.

When you do need parallelism, run it at the coarsest level — one substantial task
per session/subject, not per trial:

```r
library(furrr)
plan(multisession)                     # separate R processes

# ❌ fine-grained: per-trial overhead dwarfs the work
results <- future_map(all_trials, process_trial)

# ✅ coarse-grained: one independent, substantial task per session
results <- future_map(sessions, analyze_session)
```

`analyze_session` is a pure per-session function (principle 3), so each worker
loads its own data with no shared state.

**Threads or processes?** R runs your code single-threaded, so parallelism means
separate *processes*: `plan(multisession)` (fresh R sessions, all platforms) or
`plan(multicore)` (forks; faster, but not on Windows or inside RStudio). Data is
copied to each worker, so keep tasks coarse. (Some packages — `data.table`, the
BLAS behind matrix math — use threads internally in C, independent of this.)
Scaling to a cluster uses `future.batchtools` + SLURM — a later version.

---

## R-specific notes

- **Use the native pipe `|>`** (R 4.1+); tidyverse-heavy code may still use
  `%>%`. Pick one per project.
- **Format with `styler`, lint with `lintr`** — ideally in CI.
- **In packages, reference functions as `pkg::fn()`** and declare dependencies in
  `DESCRIPTION`; don't call `library()` from package code.
- **Avoid `attach()`, `setwd()`, and `<<-`** — they create hidden state. Use
  `here::here()` for paths and pass data explicitly.
- **Prefer type-stable maps** — `vapply()` or `purrr::map_*()` over `sapply()`,
  which can silently change the result type (a quiet cousin of principle 10).

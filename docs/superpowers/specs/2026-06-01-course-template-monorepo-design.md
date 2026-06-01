# Design: move the course template into the monorepo + fix checker's eager-pytest-import bug

- **Date:** 2026-06-01
- **Issue:** [manytask#637](https://github.com/manytask/manytask/issues/637) — "Создать общий шаблон курса"
- **Branch (in progress):** `docs/issue-637-course-template`
- **Status:** approved in brainstorming; pending spec review

## 1. Context and problem

manytask is a monorepo (web app + `checker` CLI + docs). Issue #637 asks for a **reference course template**: one course, pre-configured for **C++, Python, Bash, Go, Rust**, with the checker wired to grade all five, deployed and gradeable, plus documentation. The Definition of Done is: *"Курс настроен, задеплоен, задачки проверяются. Документация написана."*

Today the work-in-progress template is a standalone local git repo at `~/Documents/yandex/manytask-sandbox` containing only a Python task (`python/add`). It is already pushed to `gitlab.manytask2.org/sandbox/private`, exports to `…/sandbox/public`, and its CI (`.releaser-ci.yml` + `.gitlab-ci.yml`) has been validated end-to-end on the dev GitLab runner.

Two problems motivate this work:

1. **The template lives outside the monorepo.** `docs/course_template.md` documents a layout that exists only in a separate GitLab repo, so it can silently drift from reality. There is no CI in the monorepo that validates the template, which is exactly the kind of gap that let a private-file leak (`test_private.py`, `.releaser-ci.yml` exported to the public repo) ship unnoticed.
2. **A genuine checker bug surfaced while building the template.** `checker`'s plugin loader eagerly imports a pytest plugin, so `checker` crashes at startup if `pytest` is not installed — even for non-Python courses.

This design covers both: relocating the template into the monorepo as the canonical source of truth, and fixing the checker bug.

## 2. Goals / non-goals

### Goals

- Make the monorepo the **single source of truth** for the course template; the deployed GitLab `sandbox/private` repo becomes a downstream push target.
- House the template at a discoverable, self-describing top-level location.
- Structure it as **one course with five language groups** (`python`, `cpp`, `bash`, `go`, `rust`), each with at least one trivial task that grades correctly.
- Wire the checker to grade every language via per-task pipelines.
- Add monorepo CI that runs `checker validate` against the template (cheap structural guard that would have caught the private-file leak).
- Fix the checker eager-pytest-import bug with a regression test.
- Update `docs/course_template.md` to point at the in-repo location.

### Non-goals (left to the operator / later iterations)

- Real `git push` to GitLab, CI/CD variable setup, registering the course on the web app, and running grading on live GitLab runners (the user does these manually).
- Building a fully production-grade multi-toolchain Docker image is in scope to *specify*, but per-language grading is *verified* in the deployed GitLab CI, not necessarily on the developer's laptop.
- Touching `checker/demo-sample-course/` — it stays a minimal smoke fixture for checker's own tests and serves a different purpose.

## 3. Deliverable A — fix checker's eager-pytest-import bug

### Root cause (verified)

- `checker/checker/plugins/__init__.py:load_plugins()` iterates every module in `checker/plugins/` and calls `spec.loader.exec_module(module)` to discover `PluginABC` subclasses.
- One of those modules, `checker/plugins/checker_reporter.py`, does an unguarded top-level `import pytest` and defines `@pytest.hookimpl`-decorated hooks at class-definition time.
- `checker_reporter` is **not** a `PluginABC` — it is a *pytest* plugin, loaded into the pytest subprocess via `-p checker.plugins.checker_reporter` (see `plugins/python.py:_setup_percentage_reporting`). It has no reason to be executed during checker's own plugin discovery.
- Reproduced: with `pytest` unavailable, `load_plugins()` raises `ModuleNotFoundError: No module named 'pytest'` at the "Loading plugins..." step — crashing `checker validate`/`grade`/`export` for **any** course, including non-pytest (C++/Go/Rust/Bash) courses.

### Fix

Stop the plugin discovery loop from forcing `import pytest`. Preferred approach: **relocate `checker_reporter.py` out of the auto-scanned `checker/plugins/` package** (e.g. to `checker/checker_reporter.py`, which is already in the packaged `checker` namespace) and update the single `-p checker.plugins.checker_reporter` reference in `plugins/python.py` to the new module path. The reporter is then loaded only inside the pytest subprocess, where pytest is guaranteed present.

A lighter alternative (if relocation proves to ripple): guard the pytest-dependent definitions in `checker_reporter.py` behind an availability check so the module imports cleanly without pytest. The implementation plan will pick whichever is least invasive once the tests below are in place.

### Verification

- **Regression test (TDD, write first):** a test in `checker/tests/plugins/` that runs `load_plugins()` in an environment where `pytest` is not importable and asserts it succeeds (no `ModuleNotFoundError`). Drive the fix from this failing test.
- **End-to-end guard:** if the fix relocates the reporter, also keep coverage for the percentage-reporting path (`run_pytest` with `report_percentage: true`, which loads the reporter via `-p`) so the relocation doesn't silently break score reporting.
- Existing checker test suite stays green.
- `checker validate` / `checker check` against the template still pass.

This keeps `pip install pytest` in the template CI **correct and intentional** (a Python course provides its own test runner) rather than papering over a checker crash.

## 4. Deliverable B — relocate the template into the monorepo

### 4.1 Placement and naming

New top-level directory **`course-template/`** holding the course directly:

```
manytask/
├── checker/
├── manytask/
├── docs/
├── packages/
└── course-template/          # NEW — the reference course (== gitlab sandbox/private contents)
    ├── .checker.yml  .manytask.yml  .gitlab-ci.yml  .releaser-ci.yml  .gitignore
    ├── README.md  testenv.docker  pyproject.toml
    ├── python/  cpp/  bash/  go/  rust/
    └── tools/
```

Rationale: top-level is discoverable ("here is the template, copy it"); the name describes purpose to a monorepo reader; it does not scope a course-as-code artifact under `checker/`; and its contents map 1:1 to the GitLab `sandbox/private` repo. The deployed instance keeps the name **`sandbox`** everywhere it already appears (GitLab namespace, course slug, `.manytask.yml`, docs). *(Open naming question for spec review: `course-template/` vs `sandbox/` as the directory name — §11.)*

### 4.2 Source-of-truth / sync model

The monorepo is the single source of truth. Deployment to `gitlab.manytask2.org/sandbox/private` happens by pushing the `course-template/` subtree (via `git subtree split`/push or a small sync script — exact mechanism decided in the plan). The standalone `~/manytask-sandbox` repo is absorbed; its git history is **not** imported (early commits contain the private-file leak — a clean start is preferable).

### 4.3 Multi-language structure

One course, one set of root configs, five language groups. Layout per group:

```
<lang>/
├── .group.yml                      # shared parameters AND the per-language test pipeline
└── <task>/
    ├── .task.yml                   # usually empty; per-task pipeline override only when a task differs
    ├── README.md                   # task statement
    ├── <solution files>            # reference solution (NOT exported)
    ├── <template files> (*.template)  # what students get
    ├── <public tests>              # exported
    └── <private tests>             # NOT exported
```

Trivial tasks (anyone can solve), one per language to start, e.g. an `add`/`hello`-style task per language.

**Per-language grading mechanism (verified against checker):** both `.group.yml` and `.task.yml` parse into `CheckerSubConfig`, which supports a `task_pipeline` override. `tester.py` resolves the pipeline per task as task `.task.yml` → group `.group.yml` → global `testing.tasks_pipeline` (three-level fallback). Parameters cascade `default_parameters` → `.group.yml` → `.task.yml`. To stay DRY, the per-language pipeline lives in the group's `.group.yml` (shared by all its tasks); an individual `.task.yml` overrides it only when a task genuinely differs. Therefore:

- **Python** uses the existing `run_pytest`-based pipeline (set in `python/.group.yml`, or left to the global default).
- **C++ / Go / Rust / Bash** each define a `task_pipeline` in their `<lang>/.group.yml` that uses `run_script` to compile and run that language's tests (`go test`, `cargo test`, a `g++`-compiled test driver, shell assertions / `bats` for Bash).

This is a real, supported mechanism — no checker changes needed for multi-language.

### 4.4 Test environment

`testenv.docker` must carry all five toolchains (python+pytest, g++, bash, go, rust). Carrying four extra toolchains means the base almost certainly moves off `python:3.12-slim` (e.g. a fuller Debian base or a multi-stage build) and toolchain versions should be pinned. The image is specified here; building/grading per language is verified in the deployed GitLab CI (the dev runner has Docker), not necessarily on the developer laptop.

### 4.5 CI files

`.releaser-ci.yml` (private repo: validate + export to public) and `.gitlab-ci.yml` (public repo: grade) move with the template unchanged in intent. Both keep the documented `CHECKER_PIP_SPEC=@main` and `pip install … pytest` decisions (already commented in those files). These run on GitLab, not in the monorepo.

### 4.6 Monorepo CI integration

Add a job in the monorepo's CI (GitHub Actions under `.github/`) that installs the in-tree checker and, on PRs touching `course-template/` or `checker/`, runs two cheap checks (neither needs the multi-toolchain Docker image):

1. `checker validate course-template` — pipeline/placeholder structural validity.
2. A **dry-run export** to a temp dir (`checker export-private`/`export` into a throwaway directory) followed by an assertion that the exported public tree contains **no** private files (`test_private*`, `.releaser-ci.yml`, reference solutions). `checker validate` does **not** exercise the `public_patterns`/`private_patterns` export filtering — only export does — so this dry-export assertion is the actual guard that would have caught the private-file leak.

### 4.7 Docs

Rewrite `docs/course_template.md` so "Where to find it" points at `course-template/` in the monorepo (canonical source) and explains that it is deployed to `gitlab.manytask2.org/sandbox/private`. Keep the "Using the template" steps. Update the file tree to show the five language groups.

## 5. Components and boundaries

| Unit | Purpose | Depends on |
|---|---|---|
| `course-template/` content | The course (configs, tasks, CI, docker) | checker config schema |
| Per-language `.task.yml` pipelines | Compile+run each language's tests | checker `run_script` / `run_pytest` plugins |
| `checker_reporter` relocation | Stop eager pytest import at checker startup | checker plugin loader, `plugins/python.py` |
| Monorepo CI validate job | Guard template validity on every PR | in-tree checker |
| `docs/course_template.md` | User-facing documentation | — |

Each is independently testable: the checker fix has a unit regression test; the template validates via `checker validate`; the CI job is exercised by a PR; the docs are prose.

## 6. Verification strategy

- **checker fix:** failing-first regression test → fix → full checker suite green.
- **Template structure:** `checker validate course-template` exit 0; `checker check` runs the per-language pipelines locally where the toolchain exists (at minimum Python).
- **No private-file leak:** confirm `.checker.yml` `public_patterns`/`private_patterns` keep `test_private*`, `.releaser-ci.yml`, and reference solutions out of the exported public tree (the bug already fixed in the standalone repo is carried over correctly).
- **Per-language grading on live infra:** verified by the operator in the deployed GitLab CI after push (out of scope for local automation).

## 7. Implementation phasing (for writing-plans)

The work is one spec implemented incrementally:

1. checker bug fix + regression test.
2. Create `course-template/` and port the existing Python task + root configs from `~/manytask-sandbox` (carrying the leak fix).
3. Add the four remaining language groups (cpp, bash, go, rust), each with a trivial task and `.task.yml` pipeline.
4. Expand `testenv.docker` to all five toolchains.
5. Add the monorepo CI validate job.
6. Rewrite `docs/course_template.md`.
7. (Operator) push subtree to GitLab, verify grading on live runners.

## 8. Risks

- **Per-language pipelines** depend on toolchains present in `testenv.docker`; a missing/misversioned toolchain fails grading. Mitigated by pinning toolchain versions in the Dockerfile and verifying in GitLab CI.
- **`CHECKER_PIP_SPEC=@main`** is unpinned by deliberate decision (PyPI 0.9.2 lacks `validate`); a breaking checker change could break the template CI. Documented in the CI files; revisit when checker ships a release with the needed commands.
- **Subtree sync** can drift if someone edits the GitLab repo directly. Mitigated by treating the monorepo as the only write path.

## 9. Out of scope / explicitly not done

- No history import from `~/manytask-sandbox`.
- No changes to `checker/demo-sample-course/`.
- No live deploy, secrets, or course registration.

## 10. Open questions for spec review

1. Directory name: `course-template/` (purpose-named, recommended) vs `sandbox/` (matches the deployed instance name everywhere else)?
2. Phase-1 breadth: author all five languages now (matches DoD), accepting that cpp/go/rust grading is verified only in GitLab CI — confirmed direction, flag if the user wants to stage languages instead.
3. Sync mechanism: `git subtree push` vs a committed sync script — defer to the implementation plan, or decide now?

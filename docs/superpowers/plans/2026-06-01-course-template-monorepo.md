# Course Template in Monorepo — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the manytask course template into the monorepo at `course-template/` as the canonical source of truth (one course, five language groups), add a CI guard that catches private-file leaks, and fix checker's eager-pytest-import crash.

**Architecture:** A self-contained `course-template/` directory whose contents map 1:1 to the deployed GitLab `sandbox/private` repo, deployed via a committed sync script. Per-language grading uses checker's per-group `task_pipeline` override (`run_pytest` for Python, `run_script` for the rest). A monorepo GitHub Actions job runs `checker validate` + a dry-run export with a no-private-file assertion. A separate small checker fix relocates a pytest-only plugin out of the eager plugin-discovery path.

**Tech Stack:** Python 3.12 + checker CLI, GitLab CI (template's own pipelines), GitHub Actions (monorepo guard), pytest, g++, bash, Go, Rust.

**Spec:** `docs/superpowers/specs/2026-06-01-course-template-monorepo-design.md`

---

## File Structure

**New / modified in `checker/` (Chunk 1):**
- Modify (move): `checker/checker/plugins/checker_reporter.py` → `checker/checker/checker_reporter.py`
- Modify: `checker/checker/plugins/python.py` (the `-p` reference, ~line 106)
- Modify (replace stub): `checker/tests/plugins/test_load_plugins.py`

**New `course-template/` (Chunks 2–3)** — contents map 1:1 to GitLab `sandbox/private`:
- Root: `.checker.yml`, `.manytask.yml`, `.gitlab-ci.yml`, `.releaser-ci.yml`, `.gitignore`, `README.md`, `testenv.docker`, `pyproject.toml`, `tools/.gitkeep`
- Per language `<lang>/`: `.group.yml` (shared params + `task_pipeline`) and one trivial task `<lang>/<task>/` (statement, solution, `.template`, public + private tests)
- `deploy.sh` — sync script to push the subtree to GitLab

**Monorepo CI + docs (Chunk 3):**
- Create: `.github/workflows/course-template.yml`
- Rewrite: `docs/course_template.md`

**Source to port from:** `~/Documents/yandex/manytask-sandbox/` (the already-validated standalone template — Python task + root configs are correct and carried over verbatim except where noted).

---

## Chunk 1: Fix checker's eager-pytest-import bug

**Why:** `load_plugins()` (`checker/checker/plugins/__init__.py:42-56`) `exec_module`s every file in `checker/plugins/`. One of them, `checker_reporter.py`, does an unguarded top-level `import pytest` and runs `@pytest.hookimpl` at class-definition time. It is a *pytest* plugin (loaded via `-p` inside the pytest subprocess), not a checker `PluginABC`, so it must not sit in the auto-discovered package. Result today: `checker` crashes at "Loading plugins..." with `ModuleNotFoundError: No module named 'pytest'` for any course when pytest is absent (e.g. a C++-only course). Fix = relocate it out of `checker/plugins/`.

### Task 1.1: Failing regression test for plugin discovery without pytest

**Files:**
- Test: `checker/tests/plugins/test_load_plugins.py` (currently a `# TODO` stub — replace it)

- [ ] **Step 1: Write the failing test**

Replace the stub contents of `checker/tests/plugins/test_load_plugins.py` with:

```python
import builtins

from checker.plugins import load_plugins


def test_load_plugins_without_pytest(monkeypatch):
    """Plugin discovery must not require pytest to be importable.

    Regression: checker_reporter.py used to live in checker/plugins/ with a
    top-level `import pytest`, so load_plugins() (which exec_module's every
    plugin file) crashed at startup when pytest was absent — breaking checker
    for non-pytest (e.g. C++) courses.
    """
    real_import = builtins.__import__

    def blocked_import(name, *args, **kwargs):
        if name == "pytest" or name.startswith("pytest."):
            raise ModuleNotFoundError("No module named 'pytest'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", blocked_import)

    plugins = load_plugins()

    assert "run_pytest" in plugins  # pytest *runner* plugin still discovered
```

- [ ] **Step 2: Run it and confirm it fails for the right reason**

Run: `cd checker && uv run pytest tests/plugins/test_load_plugins.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pytest'` raised from inside `load_plugins()` (proving the eager import).

- [ ] **Step 3: Commit the failing test**

```bash
cd "/Users/seliverstow/Documents/yandex/manytask copy"
git add checker/tests/plugins/test_load_plugins.py
git commit -m "test(checker): load_plugins must not require pytest (failing)"
```

### Task 1.2: Relocate the pytest reporter out of the plugin-discovery path

**Files:**
- Move: `checker/checker/plugins/checker_reporter.py` → `checker/checker/checker_reporter.py`
- Modify: `checker/checker/plugins/python.py` (the `-p checker.plugins.checker_reporter` string)

- [ ] **Step 1: Find every reference to the old module path**

Run: `cd checker && grep -rn "plugins.checker_reporter\|plugins/checker_reporter\|checker_reporter" checker/ tests/ ../docs/`
Expected: the `-p checker.plugins.checker_reporter` string in `checker/plugins/python.py` (around line 106) and the file itself. Note any doc mention to update.

- [ ] **Step 2: Move the file**

Run: `cd checker && git mv checker/plugins/checker_reporter.py checker/checker_reporter.py`

- [ ] **Step 3: Update the `-p` reference in `python.py`**

In `checker/checker/plugins/python.py`, change the plugin path passed to pytest:

```python
        # before
        tests_cmd += [
            "-p",
            "checker.plugins.checker_reporter",
        # after
        tests_cmd += [
            "-p",
            "checker.checker_reporter",
```

(Keep the `--checker-report` / `--checker-use-pipe` args unchanged.)

- [ ] **Step 4: Update any internal imports in the moved file**

Open `checker/checker/checker_reporter.py`. If it imports siblings via `from checker.plugins...` that no longer make sense, leave functional imports as-is (it only depends on `pytest` and stdlib). No package-relative imports are expected. Update any doc reference found in Step 1.

- [ ] **Step 5: Run the regression test — now passes**

Run: `cd checker && uv run pytest tests/plugins/test_load_plugins.py -v`
Expected: PASS.

- [ ] **Step 6: Run the full checker suite — still green**

Run: `cd checker && uv run pytest -q`
Expected: PASS (no test referenced the old module path; if one did, Step 1 caught it).

- [ ] **Step 7: Verify percentage-reporting path still loads the reporter**

Run: `cd checker && uv run pytest tests/ -q -k "pytest or report or percentage" -v` (and/or run `checker check` against `course-template` once Chunk 2 exists).
Expected: PASS — confirms `-p checker.checker_reporter` resolves inside the pytest subprocess.

- [ ] **Step 8: Commit the fix**

```bash
cd "/Users/seliverstow/Documents/yandex/manytask copy"
git add -A checker/
git commit -m "fix(checker): relocate pytest reporter out of plugin discovery so checker runs without pytest"
```

---

## Chunk 2: Relocate the Python template into `course-template/` + CI guard + docs

**Why:** This is the fully-verifiable half — it makes the monorepo the source of truth for the (currently Python-only) template, adds the dry-export leak guard, rewrites the docs, and adds the deploy script. After this chunk the template still has one language; Chunk 3 adds the other four.

All commands assume CWD `/Users/seliverstow/Documents/yandex/manytask copy` unless noted.

### Task 2.1: Port the existing template into `course-template/`

The 17 files in `~/Documents/yandex/manytask-sandbox/` are already validated; copy them verbatim (history is intentionally **not** imported).

**Files:** Create `course-template/` with the full sandbox tree.

- [ ] **Step 1: Copy the sandbox tree (excluding its .git)**

```bash
mkdir -p course-template
rsync -a --exclude '.git' --exclude '__pycache__' --exclude '.pytest_cache' \
  ~/Documents/yandex/manytask-sandbox/ course-template/
```

- [ ] **Step 2: Verify the inventory matches the spec layout**

Run: `find course-template -type f -not -path '*/.git/*' | sort`
Expected: `.checker.yml .gitignore .gitlab-ci.yml .manytask.yml .releaser-ci.yml README.md pyproject.toml testenv.docker tools/.gitkeep python/.group.yml python/add/{.task.yml,README.md,add.py,add.py.template,conftest.py,test_private.py,test_public.py}`.

- [ ] **Step 3: Confirm the leak fix is present (no `"*"` in public_patterns)**

Run: `grep -nA12 "public_patterns" course-template/.checker.yml`
Expected: the explicit dotfile allow-list (`.gitignore`, `.gitlab-ci.yml`, `.checker.yml`, `.manytask.yml`, `.task.yml`, `.group.yml`) — **no** bare `"*"`. (If a `"*"` is present, stop — the wrong source was copied.)

- [ ] **Step 4: Commit the relocated template**

```bash
git add course-template
git commit -m "feat(course-template): relocate sandbox course template into the monorepo"
```

### Task 2.2: Validate + dry-export the relocated template locally

**Files:** none (verification only).

- [ ] **Step 1: `checker validate` passes**

Run: `cd checker && uv run checker validate ../course-template`
Expected: ends with `Ok` / exit 0.

- [ ] **Step 2: Dry-export to a temp dir and assert no private files leak**

```bash
cd "/Users/seliverstow/Documents/yandex/manytask copy"
rm -rf /tmp/ct-export && mkdir -p /tmp/ct-export
cd checker && uv run checker export ../course-template /tmp/ct-export
echo "--- exported tree ---"; find /tmp/ct-export -type f -not -path '*/.git/*' | sort
```
Expected: the exported tree contains `python/add/add.py` (the *stub* from `add.py.template`), `test_public.py`, and the public dotfiles — but **NOT** `test_private.py` and **NOT** `.releaser-ci.yml`.

- [ ] **Step 3: Turn the assertion into a one-liner (used by CI in Task 2.4)**

```bash
if find /tmp/ct-export -type f \( -name '*private*' -o -name '.releaser-ci.yml' \) | grep -q .; then
  echo "LEAK: private files in export"; exit 1; else echo "clean export"; fi
```
Expected: `clean export`. (`*private*` covers every language's hidden test, including Go's `private_test.go` added in Chunk 3 — use it from the start so the guard stays valid.)

### Task 2.3: Add the GitLab deploy/sync script

**Files:** Create `course-template/deploy.sh`

- [ ] **Step 1: Write the script**

```bash
#!/usr/bin/env bash
# Deploy course-template/ (the monorepo source of truth) to the GitLab
# private repo. Usage: course-template/deploy.sh git@gitlab.manytask2.org:sandbox/private.git
set -euo pipefail

REMOTE="${1:?usage: deploy.sh <gitlab-private-remote-url>}"
SRC="$(cd "$(dirname "$0")" && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

git clone "$REMOTE" "$WORK" 2>/dev/null || { git init "$WORK"; git -C "$WORK" remote add origin "$REMOTE"; }
# Mirror source over the clone (delete removed files; never touch .git or the script itself)
rsync -a --delete --exclude '.git' --exclude 'deploy.sh' "$SRC"/ "$WORK"/
git -C "$WORK" add -A
git -C "$WORK" commit -m "chore: sync course template from monorepo" || { echo "nothing to deploy"; exit 0; }
git -C "$WORK" push origin HEAD:main
echo "deployed to $REMOTE"
```

- [ ] **Step 2: Make it executable and commit**

```bash
chmod +x course-template/deploy.sh
git add course-template/deploy.sh
git commit -m "feat(course-template): add GitLab deploy/sync script"
```

(The script is not run here — the operator runs it manually with the GitLab remote and an authenticated SSH key.)

### Task 2.4: Monorepo CI guard (GitHub Actions)

**Files:** Create `.github/workflows/course-template.yml`

- [ ] **Step 1: Inspect an existing workflow for house style**

Run: `sed -n '1,40p' ".github/workflows/test.yml"`
Expected: note how the repo installs the checker / uv and the trigger style; match it.

- [ ] **Step 2: Write the workflow**

```yaml
name: course-template

on:
  pull_request:
    paths:
      - "course-template/**"
      - "checker/**"
      - ".github/workflows/course-template.yml"
  push:
    branches: [main]

jobs:
  validate-and-no-leak:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Install in-tree checker
        run: pip install ./checker pytest
      - name: checker validate
        run: checker validate course-template
      - name: Dry-export and assert no private files leak
        run: |
          rm -rf /tmp/ct-export && mkdir -p /tmp/ct-export
          checker export course-template /tmp/ct-export
          if find /tmp/ct-export -type f \( -name '*private*' -o -name '.releaser-ci.yml' \) | grep -q .; then
            echo "::error::private files leaked into export"; exit 1
          fi
          echo "clean export"
```

- [ ] **Step 3: Lint the YAML locally**

Run: `python -c "import yaml,sys; yaml.safe_load(open('.github/workflows/course-template.yml'))" && echo OK`
Expected: `OK`.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/course-template.yml
git commit -m "ci: validate course-template and guard against private-file leaks"
```

### Task 2.5: Rewrite `docs/course_template.md`

**Files:** Modify `docs/course_template.md`

- [ ] **Step 1: Read the current doc** (`docs/course_template.md`) to preserve the "Using the template" steps and `toc.yaml` linkage.

- [ ] **Step 2: Update "Where to find it" and the file tree**

Change the "Where to find it" section so it states the canonical source is `course-template/` in the monorepo, deployed to `gitlab.manytask2.org/sandbox/private` via `course-template/deploy.sh`. Update the `## What is inside` tree to show the five language groups (`python/ cpp/ bash/ go/ rust/`) — Chunk 3 fills these in; the doc may describe the intended final layout. Keep the "Using the template for your own course" steps, adjusting clone instructions to mention the monorepo source.

- [ ] **Step 3: Commit**

```bash
git add docs/course_template.md
git commit -m "docs: point course template at the in-monorepo source"
```

---

## Chunk 3: Add the four remaining languages (cpp, bash, go, rust)

**Why:** Satisfy the #637 DoD (one course, five languages). Each language adds a group with a `task_pipeline` and one trivial `add`-style task. Per-language grading on live runners is **verified in GitLab CI**, not on the laptop — except where the toolchain happens to be installed.

**Naming convention (all languages):** solution file `add.<ext>` (excluded from export), `add.<ext>.template` (becomes the student's stub), `test_public.<ext>` (exported), and a hidden test whose filename contains `private` (Go must use `private_test.go` for the `_test.go` suffix). One glob (`*private*`) keeps every hidden test private.

### Task 3.0: SPIKE — how do hidden tests reach the student grade job? (BLOCKING)

**Why this is a spike:** the student/public repo's `.gitlab-ci.yml` runs `checker grade` with `reference_root="."`, but `test_private.*` were excluded from the public repo by export. The previous sessions verified `checker check <root> <reference_root>` (with the full private repo as `reference_root`) and `checker validate`, but **never verified live student grading with hidden tests**. The per-language pipelines must match whatever the real mechanism is. Resolve this before writing four pipelines against an assumption.

**Files:** none (investigation; record findings in the plan / a scratch note).

- [ ] **Step 1: Read how `grade` sources reference/private files**

Run: `cd checker && sed -n '255,360p' checker/__main__.py` and `grep -rn "reference_root\|TESTER_TOKEN\|tester\|clone\|private" checker/__main__.py docs/private_repo.md docs/checker_pipelines_and_plugins.md`
Determine: does the student grade job (a) clone the private/reference repo via `TESTER_TOKEN` and point `reference_root` at it, (b) run only public tests while private grading happens server-side, or (c) something else.

- [ ] **Step 2: Decide the per-language pipeline shape from the finding**
  - If hidden tests are present at grade time (reference repo available): each `task_pipeline` runs public **and** private tests.
  - If only public tests are available in the student job: the `private` pipeline step is gated (`run_if`) on a parameter that is only true in the instructor/reference context, mirroring how the Python `.checker.yml` already separates the two steps.

- [ ] **Step 3: Write the decision as a comment block** at the top of each new `.group.yml` you create below, so the pipeline shape is justified. If the mechanism cannot be determined from the repo, STOP and surface to the human — do not guess.

> **SPIKE FINDING (2026-06-01, high confidence) — answer = (C), with a gap.**
> Hidden tests are NOT cloned at grade time. `checker grade` has no clone logic; `reference_root` defaults to `.`; `TESTER_TOKEN` is score-reporting auth only (`docs/checker_config.md:174`), not a git token. The intended mechanism is the **Testenv Docker image**: per `docs/concepts.md:27`, the testenv "should contain a copy of the private repository with private tests; it is used to run `checker grade` in students' repositories", produced via `checker export_private` (`concepts.md:24`). `docs/concepts.md:38` confirms the student grade job runs both public and private tests — i.e. private tests come from the image, not a fetch.
> **Consequence for pipeline shape:** keep the SAME two-step public+private shape as the existing Python `.checker.yml` for every language. The pipelines are correct as-is.
> **Consequence for Task 3.6 (load-bearing gap):** the shipped template does NOT yet implement this — `testenv.docker` bakes in no private tests and `.gitlab-ci.yml` runs on `python:3.12-slim` with bare `checker grade`, so private tests would be absent at grade time and the private step would fail. Task 3.6 MUST therefore (a) bake the private tests into the testenv image (`checker export_private` into it, or COPY the private tree) **in addition to** the five toolchains, and (b) point `.gitlab-ci.yml`'s grade job `image:` at that image. Live grading remains operator-verified (needs GitLab + registry).
> **Local verification still works:** `checker check <root> <reference_root>` with `reference_root` = the full template runs public+private locally (the reference context has the private files), so each language's pipeline is verifiable on the laptop, toolchain permitting.

### Task 3.1: Generalize private-file patterns + per-language test split

**Files:** Modify `course-template/.checker.yml`

- [ ] **Step 1: Generalize `private_patterns`**

In `course-template/.checker.yml`, change the hidden-test pattern from Python-specific to a cross-language glob:

```yaml
  private_patterns:
    - ".*"
    - "*private*"   # test_private.{py,cpp,sh,rs} and Go's private_test.go
```

- [ ] **Step 2: Re-run the dry-export leak check (Task 2.2 Step 2–3)**

Expected: still `clean export` (the new glob is a superset of `test_private.py`).

- [ ] **Step 3: Commit**

```bash
git add course-template/.checker.yml
git commit -m "feat(course-template): generalize private-test glob for all languages"
```

### Task 3.2: C++ group + `cpp/add`

**Files (create):** `course-template/cpp/.group.yml`, and under `course-template/cpp/add/`: `.task.yml`, `README.md`, `add.h`, `add.cpp`, `add.cpp.template`, `test_public.cpp`, `test_private.cpp`

- [ ] **Step 1: Create the files**

`cpp/.group.yml` (pipeline shape per Task 3.0 decision; example assumes hidden tests present at grade time):
```yaml
version: 1
parameters:
  timeout: 30
task_pipeline:
  - name: "Build and run public tests"
    run: run_script
    args:
      origin: "${{ global.temp_dir }}"
      script: "cd ${{ task.task_sub_path }} && g++ -std=c++17 -Wall add.cpp test_public.cpp -o /tmp/cpp_pub && /tmp/cpp_pub"
      timeout: ${{ parameters.timeout }}
  - name: "Build and run private tests"
    run: run_script
    args:
      origin: "${{ global.temp_dir }}"
      script: "cd ${{ task.task_sub_path }} && g++ -std=c++17 -Wall add.cpp test_private.cpp -o /tmp/cpp_priv && /tmp/cpp_priv"
      timeout: ${{ parameters.timeout }}
```
`cpp/add/.task.yml`: `version: 1`
`cpp/add/add.h`:
```cpp
#pragma once
int add(int a, int b);
```
`cpp/add/add.cpp`:
```cpp
#include "add.h"
int add(int a, int b) { return a + b; }
```
`cpp/add/add.cpp.template`:
```cpp
#include "add.h"
int add(int a, int b) { (void)a; (void)b; return 0; /* TODO: implement */ }
```
`cpp/add/test_public.cpp`:
```cpp
#include <cassert>
#include "add.h"
int main() { assert(add(2, 3) == 5); assert(add(0, 0) == 0); return 0; }
```
`cpp/add/test_private.cpp`:
```cpp
#include <cassert>
#include "add.h"
int main() { assert(add(-1, 1) == 0); assert(add(-7, -8) == -15); return 0; }
```
`cpp/add/README.md`: one-paragraph statement ("Implement `int add(int, int)` in `add.cpp`.").

- [ ] **Step 2: Verify the stub fails and the solution passes (toolchain permitting)**

Run (if `g++` available locally):
```bash
cd course-template/cpp/add
g++ -std=c++17 add.cpp test_public.cpp -o /tmp/p && /tmp/p && echo "solution OK"
g++ -std=c++17 add.cpp.template test_public.cpp -o /tmp/s && (/tmp/s; echo "stub exit=$?")
```
Expected: solution prints `solution OK` (exit 0); stub aborts (non-zero) on the assert. If `g++` is absent locally, defer to GitLab CI and note it.

- [ ] **Step 3: `checker validate` still passes**

Run: `cd checker && uv run checker validate ../course-template`
Expected: exit 0.

- [ ] **Step 4: Commit**

```bash
git add course-template/cpp
git commit -m "feat(course-template): add C++ language group with add task"
```

### Task 3.3: Bash group + `bash/add`

**Files (create):** `course-template/bash/.group.yml`, under `bash/add/`: `.task.yml`, `README.md`, `add.sh`, `add.sh.template`, `test_public.sh`, `test_private.sh`

- [ ] **Step 1: Create the files**

`bash/.group.yml`:
```yaml
version: 1
parameters:
  timeout: 30
task_pipeline:
  - name: "Run public tests"
    run: run_script
    args:
      origin: "${{ global.temp_dir }}"
      script: "cd ${{ task.task_sub_path }} && bash test_public.sh"
      timeout: ${{ parameters.timeout }}
  - name: "Run private tests"
    run: run_script
    args:
      origin: "${{ global.temp_dir }}"
      script: "cd ${{ task.task_sub_path }} && bash test_private.sh"
      timeout: ${{ parameters.timeout }}
```
`bash/add/add.sh`:
```bash
add() { echo $(( $1 + $2 )); }
```
`bash/add/add.sh.template` (the `# TODO` comment and the closing `}` MUST be on separate lines, or `}` gets commented out):
```bash
add() {
  echo 0  # TODO: implement
}
```
`bash/add/test_public.sh`:
```bash
#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/add.sh"
[ "$(add 2 3)" = "5" ] || { echo "FAIL add 2 3"; exit 1; }
[ "$(add 0 0)" = "0" ] || { echo "FAIL add 0 0"; exit 1; }
echo OK
```
`bash/add/test_private.sh`: same skeleton, asserts `add -1 1 == 0` and `add -7 -8 == -15`.
`bash/add/.task.yml`: `version: 1`; `README.md`: statement.

- [ ] **Step 2: Verify locally** (`bash` is always available)
```bash
cd course-template/bash/add && bash test_public.sh && bash test_private.sh && echo "solution OK"
```
Expected: `OK`/`OK`/`solution OK`. Then temporarily swap in the template and confirm it fails.

- [ ] **Step 3: `checker validate` passes; commit**
```bash
cd checker && uv run checker validate ../course-template
cd .. && git add course-template/bash && git commit -m "feat(course-template): add Bash language group with add task"
```

### Task 3.4: Go group + `go/add`

**Files (create):** `course-template/go/.group.yml`, under `go/add/`: `.task.yml`, `README.md`, `go.mod`, `add.go`, `add.go.template`, `public_test.go`, `private_test.go`

- [ ] **Step 1: Create the files**

`go/.group.yml`: same two-step shape; the run script is `cd ${{ task.task_sub_path }} && go test ./...` for public and (per Task 3.0) a private run if hidden tests are present. Because `go test` runs all `_test.go` in the package at once, a single step `go test ./...` covers both when present; document this in the group comment and use one step:
```yaml
version: 1
parameters:
  timeout: 60
task_pipeline:
  - name: "Run go tests"
    run: run_script
    args:
      origin: "${{ global.temp_dir }}"
      script: "cd ${{ task.task_sub_path }} && go test ./..."
      timeout: ${{ parameters.timeout }}
```
`go/add/go.mod`:
```
module add

go 1.21
```
`go/add/add.go`:
```go
package main

func Add(a, b int) int { return a + b }
```
`go/add/add.go.template` (the `//` comment and closing `}` MUST be on separate lines):
```go
package main

func Add(a, b int) int {
	return 0 // TODO: implement
}
```
`go/add/public_test.go`:
```go
package main
import "testing"
func TestPublic(t *testing.T) {
    if Add(2, 3) != 5 || Add(0, 0) != 0 { t.Fatal("public") }
}
```
`go/add/private_test.go`: `TestPrivate` asserting `Add(-1,1)==0 && Add(-7,-8)==-15`.
`go/add/.task.yml`: `version: 1`; `README.md`: statement.

- [ ] **Step 2: Verify (toolchain permitting)**
```bash
cd course-template/go/add && go test ./... && echo "solution OK"
```
If `go` absent locally, defer to GitLab CI and note it.

- [ ] **Step 3: `checker validate` passes; commit**
```bash
cd checker && uv run checker validate ../course-template
cd .. && git add course-template/go && git commit -m "feat(course-template): add Go language group with add task"
```

### Task 3.5: Rust group + `rust/add`

**Files (create):** `course-template/rust/.group.yml`, under `rust/add/`: `.task.yml`, `README.md`, `add.rs`, `add.rs.template`, `test_public.rs`, `test_private.rs`, `tests.rs`

**Note:** to avoid Cargo while keeping the public/private split, a small harness `tests.rs` `include!`s the solution and the public tests; the private harness is added by the grading context. Because the public repo lacks `test_private.rs`, the harness must not unconditionally `include!` it — keep two harness entry points or have the grade step compile public and private separately. Finalize the exact harness against the Task 3.0 finding.

- [ ] **Step 1: Create the files**

`rust/add/add.rs`: `pub fn add(a: i32, b: i32) -> i32 { a + b }`
`rust/add/add.rs.template`: `pub fn add(_a: i32, _b: i32) -> i32 { 0 /* TODO */ }`
`rust/add/test_public.rs`:
```rust
#[test] fn public() { assert_eq!(add(2, 3), 5); assert_eq!(add(0, 0), 0); }
```
`rust/add/test_private.rs`: `#[test] fn private() { assert_eq!(add(-1, 1), 0); assert_eq!(add(-7, -8), -15); }`
`rust/add/tests.rs` (public harness): `include!("add.rs"); include!("test_public.rs");`
`rust/.group.yml`:
```yaml
version: 1
parameters:
  timeout: 60
task_pipeline:
  - name: "Compile and run public tests"
    run: run_script
    args:
      origin: "${{ global.temp_dir }}"
      script: "cd ${{ task.task_sub_path }} && rustc --test tests.rs -o /tmp/rust_pub && /tmp/rust_pub"
      timeout: ${{ parameters.timeout }}
  - name: "Compile and run private tests"
    run: run_script
    args:
      origin: "${{ global.temp_dir }}"
      script: "cd ${{ task.task_sub_path }} && printf 'include!(\"add.rs\");\\ninclude!(\"test_private.rs\");\\n' > priv_harness.rs && rustc --test priv_harness.rs -o /tmp/rust_priv && /tmp/rust_priv; rm -f priv_harness.rs"
      timeout: ${{ parameters.timeout }}
```
(The private step builds its harness **inside the task dir** — `include!` resolves paths relative to the harness file, so `add.rs`/`test_private.rs` must sit beside it; writing it to `/tmp` would fail to find them. The harness lives only in the grading temp copy, never in the exported public repo, so `tests.rs` in the student repo never references the missing private file.)
`rust/add/.task.yml`: `version: 1`; `README.md`: statement.

- [ ] **Step 2: Verify (toolchain permitting)**
```bash
cd course-template/rust/add && rustc --test tests.rs -o /tmp/r && /tmp/r && echo "solution OK"
```
If `rustc` absent locally, defer to GitLab CI and note it.

- [ ] **Step 3: `checker validate` passes; commit**
```bash
cd checker && uv run checker validate ../course-template
cd .. && git add course-template/rust && git commit -m "feat(course-template): add Rust language group with add task"
```

### Task 3.6: Multi-toolchain `testenv.docker` + wire the grade job

**Files:** Modify `course-template/testenv.docker`; modify `course-template/.gitlab-ci.yml` (and `.releaser-ci.yml` if it builds the image)

- [ ] **Step 1: Rewrite `testenv.docker` to carry all five toolchains**

Move off `python:3.12-slim` to a base that can host every toolchain (e.g. `debian:bookworm-slim` + apt installs for `python3 python3-pip g++ golang bash`, plus `rustup`/`rustc` via the `rust` apt package or rustup). Pin versions. Install the checker (`$CHECKER_PIP_SPEC` or `manytask-checker`) + `pytest`. Keep `WORKDIR /workspace`.

- [ ] **Step 1b: Bake the private tests into the image (REQUIRED — per the Task 3.0 spike).**

The grade job runs `checker grade` with no clone; private tests must already be on disk in the image. So the testenv image must carry a copy of the private repo's tests. Do this in the image build (e.g. `COPY` the course tree in and run `checker export_private` to materialise the reference/private tree at the task paths, or `COPY` the private test files directly). Without this, the "Run private tests" step fails at grade time and the DoD's "tasks are graded" is not met.

- [ ] **Step 2: Decide image delivery for the grade job**

Per the spec + spike, the grade job needs the toolchains AND the private tests. Build+push `testenv.docker` to the GitLab project registry in `.releaser-ci.yml` and set `image:` in `.gitlab-ci.yml`'s grade job to `$CI_REGISTRY_IMAGE/...` (replacing the current `python:3.12-slim`). Document the `CI_REGISTRY_IMAGE` usage in a comment. (Inline toolchain install in `before_script` is a fallback but does NOT solve the private-tests-present problem — the image is the right place.)

- [ ] **Step 3: Build the image locally to confirm it's valid (if Docker available)**

Run: `cd course-template && docker build -f testenv.docker -t ct-testenv . && docker run --rm ct-testenv bash -lc 'python3 --version; g++ --version | head -1; go version; rustc --version; bash --version | head -1'`
Expected: every toolchain prints a version. If Docker is unavailable locally, defer to GitLab CI and note it.

- [ ] **Step 4: Commit**
```bash
git add course-template/testenv.docker course-template/.gitlab-ci.yml course-template/.releaser-ci.yml
git commit -m "feat(course-template): multi-toolchain test image for all five languages"
```

### Task 3.7: Add all five groups to `.manytask.yml` deadlines schedule

**Files:** Modify `course-template/.manytask.yml`

- [ ] **Step 1: Add `cpp`, `bash`, `go`, `rust` groups** to `deadlines.schedule`, mirroring the existing `python` group block (same `start`/`end`/`enabled`, one `add` task at `score: 100`). Group names must match the directory names.

- [ ] **Step 2: `checker validate` passes** (validate cross-checks `.manytask.yml` groups against the filesystem groups)

Run: `cd checker && uv run checker validate ../course-template`
Expected: exit 0, all five groups recognized.

- [ ] **Step 3: Commit**
```bash
git add course-template/.manytask.yml
git commit -m "feat(course-template): schedule all five language groups"
```

### Task 3.8: Full-course verification

**Files:** none.

- [ ] **Step 1: `checker validate` + dry-export leak check** on the complete five-language course (Task 2.2 commands). Expected: exit 0; `clean export`; exported tree contains no `*private*` files for any language.
- [ ] **Step 2: `checker check` per language where the toolchain is installed locally** (at minimum Python; cpp/go/rust/bash as available):
  Run: `cd checker && uv run checker check ../course-template ../course-template`
  Expected: each available language's task pipeline runs and passes. Languages whose toolchain is absent locally are verified in GitLab CI by the operator.
- [ ] **Step 3: Note in the PR description** which languages were verified locally vs deferred to GitLab CI (no silent gaps).

---

## Operator hand-off (manual, after the plan is implemented)

These are the spec's non-goals — done by the user, not the plan:
1. Run `course-template/deploy.sh git@gitlab.manytask2.org:sandbox/private.git` to push the source of truth to GitLab.
2. Ensure CI/CD variables (`GITLAB_API_TOKEN`, `MANYTASK_TOKEN`, `TESTER_TOKEN`) and registry access are set.
3. Confirm the GitLab pipeline grades all five languages on live runners (the real test of Task 3.0's assumption).
4. Open the PR for #637 from branch `docs/issue-637-course-template`.


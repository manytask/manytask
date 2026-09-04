# Checker configuration (`.checker.yml`)

The `.checker.yml` file lives in the root of your **private** repository and answers three
questions:

1. **What do students see?** — which files are exported to the public repository.
2. **What are students allowed to change?** — which of their files survive into the grading tree,
   and which ones are silently replaced by your originals.
3. **How is a solution graded?** — the pipelines and plugins that run for each task.

This page is a step-by-step guide for writing that file. For the exhaustive field-by-field
description see the [`.checker.yml` reference](./checker_yml_reference.md).

The examples below use a small Python course. The same rules apply to any language — the
[course template](./course_template.md) ships equivalent C++, Go, Rust and Bash groups.

---

## The file classification model

Everything in `.checker.yml` starts with `structure`. Every file in the private repository falls
into exactly one of **four** classes, and the class decides both what is exported and what happens
to the student's copy at grading time.

```yaml
structure:
  ignore_patterns: [".git", "__pycache__", ".venv", "*.pyc"]
  public_patterns: [".gitignore", ".gitlab-ci.yml", ".task.yml", ".group.yml"]
  private_patterns: [".*", "*private*"]
```

| Class | Matched by | Exported to public repo? | At grading time the file comes from |
|---|---|---|---|
| **ignored** | `ignore_patterns` | no | nowhere — never copied |
| **public** | `public_patterns` | yes | the **private** repo (student edits discarded) |
| **private** | `private_patterns` | no | the **private** repo (student never had it) |
| **other** | nothing above | yes | the **student's** repo |

> **The "other" class is the student-editable set.** This is the single most important consequence
> of the model and it is the inverse of how most people first read it: you do not list the files a
> student may change — you list the files they may *not* change, and everything left over is
> theirs.

Precedence when a file matches several lists is `ignore_patterns` > `public_patterns` >
`private_patterns`. A public match wins over a private one, which is why an over-broad
`public_patterns` entry is dangerous — see [Rules for writing patterns](#rules-for-writing-patterns).

## Where student edits actually go

`checker check` and `checker grade` never run tests in the student's checkout. They build a fresh
**merged tree** in a temporary directory, in two passes:

```text
pass 1 — from the STUDENT repository:   "other" files only      → the solution
pass 2 — from the PRIVATE repository:   public + private files  → overwrites pass 1
```

```mermaid
flowchart LR
    S["student repo<br/>add.py, test_public.py*"] -->|other files only| M["merged tree<br/>used for grading"]
    P["private repo<br/>test_public.py, test_private.py, .task.yml"] -->|public + private, overwrite| M
```

So if a student "fixes" a test to make it pass, pass 2 puts your version back on top and the edit
has no effect — **but only if that test is classified as public or private.** A visible test that
matches no pattern list is an "other" file, so pass 1 takes the student's edited copy and pass 2
never overwrites it.

> **Visible does not mean protected.** `test_public.py` is exported to students whether or not you
> list it, because ordinary files are exported by default. Being exported is *not* what protects
> it. If you want the student's edits to it discarded at grading time, you must put it in
> `public_patterns` explicitly.

Gold solutions never enter the merged tree, because on export they were replaced by their
`.template` counterparts (see [Templates](#templates)) and at grading time `add.py` is an "other"
file, taken from the student.

## Procedure: designing `structure` for a course

**Step 1 — decide what students must never touch.** Tests, task metadata and CI definitions. Make
them public (visible, still tamper-proof) or private (invisible). Listing them is what makes them
tamper-proof — leaving a visible test unlisted means the student's version is the one that runs.

**Step 2 — leave the solution files unmatched.** They must be "other" so the student's version is
the one that gets graded. If you accidentally list `add.py` in `public_patterns`, every student is
graded against *your* reference solution and everyone passes.

**Step 3 — hide every secret behind `".*"`.** Dotfiles are private by default with the `".*"` rule,
so a stray `.env` cannot leak. Then allow-list only the dotfiles students genuinely need.

**Step 4 — check the result** with a dry export before pointing it at a real repository:

```bash
checker validate
checker export . ./export-preview
```

Then inspect `./export-preview` and confirm no private test or secret is present.

A configuration following these steps:

```yaml
version: 1

structure:
  ignore_patterns:
    - ".git"
    - "__pycache__"
    - ".venv"
    - "*.pyc"

  # Two jobs here: (1) allow-list the dotfiles students need, since ".*" below makes
  # every dotfile private; (2) pin the visible files students must not change.
  public_patterns:
    - ".gitignore"
    - ".gitlab-ci.yml"    # CI that runs in the student repository
    - ".checker.yml"      # `checker grade` reads it in the student checkout
    - ".manytask.yml"     # deadlines and scores
    - ".task.yml"         # marks a task folder
    - ".group.yml"        # marks a group folder
    - "test_public.py"    # visible to students, but restored from here at grading time

  private_patterns:
    - ".*"                # every dotfile not allow-listed above
    - "*private*"         # test_private.py, test_private.cpp, ... in one rule
```

`test_public.py` is listed even though it would be exported anyway: the entry is there to make it
**tamper-proof**, not to publish it. `README.md` is absent because a student rewriting their own
copy of the task statement harms nobody. And `add.py` is deliberately absent from every list — that
is what makes it the student's to edit.

> The [course template](./course_template.md) omits `test_public.py` from `public_patterns`. It
> gets away with it because its private tests are the ones that produce the score, so a tampered
> public test cannot inflate a grade. If any part of your score comes from public tests, list them.

## Rules for writing patterns

Patterns are matched with `Path.match` **at each directory level individually**.

- **`**` is not supported.** Write `"*.py"`, not `"**/*.py"`.
- **Never put a bare `"*"` in `public_patterns`.** `Path.match("*")` matches *every* file including
  dotfiles. Because public wins over private, this marks `test_private.py` as public and leaks it
  into the student repository. You never need it: ordinary files are exported regardless.
- **A directory that matches is copied whole.** If a directory matches `public_patterns` or
  `private_patterns`, everything inside it is copied — `private_patterns` is *not* re-evaluated for
  its contents. So `public_patterns: ["tools"]` publishes every file under `tools/`, including a
  `tools/test_private.py`. Prefer matching files over matching directories when a folder holds a
  mix.
- **Match by convention, not by enumeration.** `"*private*"` covers every language's hidden tests,
  so adding a new language needs no change here.

## Per-group and per-task overrides

A folder becomes a **group** when it contains `.group.yml` and a **task** when it contains
`.task.yml`. Both files may be as short as `version: 1`, and both can override the root
configuration for their own folder and everything below it.

```yaml
# python/add/.task.yml
version: 1

structure:            # optional
  private_patterns: [".*", "*private*", "reference_data"]

parameters:           # optional — merged on top of default_parameters
  timeout: 60

task_pipeline:        # optional — replaces testing.tasks_pipeline for this task
  - name: "Run tests"
    run: "run_pytest"
    args:
      origin: ${{ global.temp_dir }}
      target: ${{ task.task_sub_path }}
```

Two different merge behaviors, easy to mix up:

- **`structure` fields replace, they do not merge.** Setting `private_patterns` in a `.task.yml`
  discards the root list for that folder — repeat the entries you still need, including `".*"`.
- **`parameters` merge**, with the narrower scope winning: `default_parameters` < `.group.yml` <
  `.task.yml`.

Pipelines resolve by the same narrowest-wins rule: `.task.yml` → `.group.yml` → root
`testing.tasks_pipeline`. Note the singular key `task_pipeline` in sub-configs versus the plural
`tasks_pipeline` in the root file.

> Sub-configs are only read for **enabled** groups and tasks, i.e. those listed in `.manytask.yml`
> with `enabled: true`.

## Optional: an explicit allow-list with `allow_change`

The structure model above is implicit — the editable set is whatever is left over. If you prefer to
name the editable files per task, use the `allow_change` convention.

`allow_change` is **not** a built-in field. It is an ordinary user-defined parameter that becomes
meaningful only because a pipeline stage reads it. Declare a default and override it per task:

```yaml
# .checker.yml
default_parameters:
  allow_change: ["*.py"]
```

```yaml
# python/add/.task.yml
version: 1
parameters:
  allow_change: ["add.py"]      # only this file may come from the student
```

Then copy exactly those files from the student checkout on top of the reference tree, as the first
stage of the task pipeline:

```yaml
testing:
  tasks_pipeline:
    - name: "Take the student's allowed files"
      run: "copy_files"
      args:
        source_dir: ${{ global.repo_dir }}/${{ task.task_sub_path }}
        target_dir: ${{ global.temp_dir }}/${{ task.task_sub_path }}
        patterns: ${{ parameters.allow_change }}
        ignore_patterns: ["*.pyc"]
```

The same parameter can drive other stages, which is the real benefit — one list, several uses:

```yaml
    - name: "Check forbidden constructs"
      run: "check_regexps"
      args:
        origin: ${{ global.temp_dir }}/${{ task.task_sub_path }}
        patterns: ${{ parameters.allow_change }}
        regexps: ["exit\\(0\\)", "import solution"]
```

Use this when a task has an unusual shape — several solution files, generated artefacts, a data
folder — and you want the reviewable list to sit next to the task instead of in the root config.
For a uniform course the structure patterns alone are simpler and harder to get wrong.

## Templates

Students must receive a stub instead of your solution. Two strategies, selected by
`export.templates`:

**`search`** (default) — put the stub in a `.template` file next to the solution:

```python
# python/add/add.py  — reference solution, tested in your CI
def add(a: int, b: int) -> int:
    return a + b
```

```python
# python/add/add.py.template  — exported as add.py
def add(a: int, b: int) -> int:
    raise NotImplementedError("Implement me")
```

An empty `.template` file deletes the original on export. Every task needs at least one
`.template`.

**`create`** — keep one file and mark the part to strip:

```python
def add(a: int, b: int) -> int:
    # SOLUTION BEGIN
    return a + b
    # SOLUTION END
```

is exported as:

```python
def add(a: int, b: int) -> int:
    # TODO: Your solution
```

`search_or_create` allows either strategy per task, but a single task may not use both.

Because your repository holds the *working* solution, `checker check` grades it exactly as a
student submission would be graded — a task whose reference solution fails its own tests is caught
before export.

## Export

```yaml
export:
  destination: https://gitlab.manytask.org/sandbox/public
  default_branch: main
  commit_message: "chore(auto): export new tasks"
  templates: search
  push_options: ["ci.skip"]
```

`push_options` are passed to `git push` as `-o` flags; the default skips CI for the export commit.
Set it to `[]` on servers that do not support push options, such as SourceCraft.

Tasks and groups marked `enabled: false`, or whose `start` date has not arrived, are skipped —
scheduling in `.manytask.yml` doubles as the release mechanism for task text.

Run it from the private repository root:

```bash
checker export . ./export --commit
```

## Testing pipelines

```yaml
default_parameters:
  run_testing: true
  timeout: 30

testing:
  changes_detection: last_commit_changes

  tasks_pipeline:
    - name: "Run public tests"
      run_if: ${{ parameters.run_testing }}
      fail: fast
      run: "run_pytest"
      register_output: public_tests
      args:
        origin: "${{ global.temp_dir }}"
        target: "${{ task.task_sub_path }}/test_public.py"
        timeout: ${{ parameters.timeout }}

    - name: "Run private tests"
      run_if: ${{ parameters.run_testing }}
      fail: fast
      run: "run_pytest"
      register_output: private_tests
      args:
        origin: "${{ global.temp_dir }}"
        target: "${{ task.task_sub_path }}/test_private.py"
        timeout: ${{ parameters.timeout }}
        report_percentage: true

  report_pipeline:
    - name: "Report score to manytask"
      run: "report_score_manytask"
      args:
        origin: "${{ global.temp_dir }}"
        username: ${{ env.GITLAB_USER_LOGIN }}
        task_name: ${{ task.task_name }}
        score: ${{ outputs.private_tests.percentage }}
        report_url: https://app.manytask.org
        report_token: ${{ env.MANYTASK_TOKEN }}
        check_deadline: true
```

`report_pipeline` runs only when `tasks_pipeline` succeeded, and only under `checker grade` — this
is what pushes the score to Manytask, so it needs a `MANYTASK_TOKEN` CI variable. `checker check`
runs the report pipeline in dry-run mode, so local runs never report a score.

`changes_detection: last_commit_changes` means `checker grade` tests only the tasks touched by the
last commit. `checker check` always tests everything.

See [Checker pipelines and plugins](./checker_pipelines_and_plugins.md) and the
[built-in plugin list](./checker_plugins.md) for the available stages.

## CI wiring

Two pipelines, one per repository.

**`.releaser-ci.yml`** runs in the *private* repository: it grades your own reference solution and,
if that passes, exports to the public repository.

```yaml
deploy-public:
  stage: deploy
  rules:
    - if: $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH
  script:
    - git clone https://oauth2:$GITLAB_API_TOKEN@gitlab.manytask.org/sandbox/public ./export
    - cd ./export && git config user.email "ci@manytask.org" && git config user.name "CI Bot" && cd ..
    - checker export . ./export --commit
```

**`.gitlab-ci.yml`** is exported to the students and runs in their repositories. The private
reference is not available there, so it is baked into the test image and passed as the second
argument:

```yaml
grade:
  image: "$TESTENV_IMAGE"
  script:
    - checker grade . /opt/course
```

`checker grade STUDENT_ROOT REFERENCE_ROOT` builds the merged tree from those two roots — the same
two passes described [above](#where-student-edits-actually-go).

### Required CI/CD variables

| Variable | Where | Description |
|---|---|---|
| `GITLAB_API_TOKEN` | private repo | Push access to the public repo (`write_repository`, Maintainer) |
| `MANYTASK_TOKEN` | group | Course token used by `report_score_manytask` |
| `DOCKER_AUTH_CONFIG` | group | Registry credentials so student repos can pull the test image |

## Adding a new task

1. Create `python/new_task/` with `.task.yml` containing `version: 1`.
2. Add the solution `new_task.py`, the stub `new_task.py.template`, `test_public.py` and
   `test_private.py`.
3. Add the task to the schedule in `.manytask.yml` — a task absent from it is never exported or
   graded.
4. Verify locally, then push:

```bash
checker validate
checker check --task new_task
```

## Pre-flight checklist

- [ ] `add.py` (and every other solution file) matches **no** pattern list.
- [ ] Every file that contributes to the score — including visible tests — is in
      `public_patterns` or `private_patterns`. Being exported is not protection.
- [ ] Every task has a `.template` file or a `SOLUTION BEGIN`/`SOLUTION END` pair.
- [ ] `public_patterns` contains no bare `"*"` and no directory holding private files.
- [ ] `private_patterns` starts with `".*"`.
- [ ] `checker validate` passes and `checker check` grades your reference solution green.
- [ ] A trial `checker export . ./export-preview` contains no `*private*` file and no secret.
- [ ] Tamper test: edit a test in a copy of the exported repo, run
      `checker grade <that copy> .`, and confirm the edit had no effect on the result.

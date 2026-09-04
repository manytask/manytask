# Course template (sandbox)

To make spinning up a new course painless, Manytask ships a **reference course template** — a pre-configured repository that already has a working `.checker.yml`, `.manytask.yml`, CI pipelines, a Docker test environment, and one solved sample task per supported language.

Use it to:

- bootstrap a new course in minutes instead of writing configs from scratch,
- learn the *Course as Code* layout by reading a real working example,
- copy patterns for adding new tasks and languages.

## Where to find it

The canonical source lives **in this monorepo** under [`course-template/`](../course-template/).

It is deployed to the GitLab private template repository at:

> **`gitlab.manytask2.org/sandbox/private`**

A maintainer runs `course-template/deploy.sh` to push changes from the monorepo to GitLab:

```bash
# From the repository root
course-template/deploy.sh git@gitlab.manytask2.org:sandbox/private.git
```

The script clones (or initialises) the GitLab repo, mirrors the `course-template/` tree over it (excluding `.git` and `deploy.sh` itself), commits the result, and pushes to `main`.

> **`deploy.sh` is a one-shot bootstrap, not a sync tool.** It runs `rsync -a --delete`, so a second run deletes everything you added to the private repo and pushes the deletion. After the first deploy, work with the private repo as an ordinary git clone.

Once the template stabilises it will be promoted to the production instance
(`gitlab.manytask.org/sandbox`) and bound to a `sandbox` course on
<https://app.manytask.org>.

## What is inside

The template ships five language groups — **Python**, **C++**, **Bash**, **Go**,
**Rust** — each with one solved `add` sample task. Python tasks test
with `run_pytest`; the compiled/script languages override the pipeline in their
`.group.yml` to compile-and-run the solution with the test driver via `run_script`.
A single multi-toolchain `testenv.docker` (Alpine + every toolchain) grades them all,
because `checker grade` has no per-language scoping — one commit may touch several
groups and the same image runs all of them.

```
course-template/
├── .checker.yml          # structure, export rules, default run_pytest tasks_pipeline
├── .manytask.yml         # settings + deadlines schedule (one group per language)
├── .gitlab-ci.yml        # CI for grading student submissions (uses the testenv image)
├── .releaser-ci.yml      # CI: build+push testenv image, check, export private → public (not exported)
├── .gitignore
├── testenv.docker        # ONE Alpine image with python/g++/go/rust/bash; bakes the reference at /opt/course
├── pyproject.toml        # pytest configuration (NOT an installable package)
├── deploy.sh             # one-shot bootstrap: monorepo → GitLab private repo
├── python/
│   └── add/              # sum of two integers — run_pytest
│       ├── .task.yml · README.md
│       ├── add.py · add.py.template      # reference (private) · student stub (exported as add.py)
│       ├── test_public.py · test_private.py   # visible · hidden (NOT exported)
│       └── conftest.py                   # adds the task folder to sys.path
├── cpp/                  # .group.yml overrides pipeline: g++ compile+run (run_script)
│   └── add_cpp/          # add.cpp(.template) · test_public.cpp · test_private.cpp
├── bash/                 # .group.yml: bash test driver sources the solution
│   └── add_bash/         # add.sh(.template) · test_public.sh · test_private.sh
├── go/                   # .group.yml: `go run add.go test_*.go` (GOPATH mode)
│   └── add_go/           # add.go(.template) · test_public.go · test_private.go
└── rust/                 # .group.yml: `rustc --test` (single-file, no cargo)
    └── add_rust/         # add.rs(.template) · test_public.rs · test_private.rs
```

Task folder names are globally unique (`add`, `add_cpp`, `add_bash`, `add_go`,
`add_rust`). `.manytask.yml` rejects duplicate task names, but the checker's
on-disk scan collapses same-named folders into one entry silently
(`checker/checker/course.py`), so a duplicate is not an error — it just makes one
of the two tasks unreachable. Keep folder names unique yourself.

This is the smallest end-to-end example that:

- passes `checker validate` and `checker check`,
- demonstrates the `.template` strategy for hiding reference solutions,
- separates public and private tests,
- reports its score back to the Manytask web app once the report pipeline is enabled (see [Enabling score reporting](#enabling-score-reporting)).

## How grading works (testenv image)

Student submissions must be graded against the **hidden** (`test_private.*`) tests,
but those tests are never exported to the public/student repository. Manytask solves
this with a **testenv docker image** (see [Concepts](./concepts.md)): an image that
carries a copy of the private repository — including the private tests — and the
checker. The same image runs `checker check` in the private repo and `checker grade`
in student repos.

The template wires this in two pipelines:

1. **Private repo (`.releaser-ci.yml`)** — on every push:
   - **`build-testenv`** builds [`testenv.docker`](../course-template/testenv.docker)
     with [kaniko](https://github.com/GoogleContainerTools/kaniko) (no privileged
     runner needed) and pushes it to the project's GitLab Container Registry. The
     Dockerfile bakes the reference tree at **`/opt/course`** via
     `checker export-private`: student-facing stubs produced from the `.template`
     files, plus public **and** private tests. Reference solutions are *replaced* by
     their templates — `/opt/course/python/add/add.py` contains the stub, not your
     solution. Both `:$CI_COMMIT_SHORT_SHA` and `:latest` tags are pushed.
   - **`check`** runs *inside that image*: `checker check . /opt/course` overlays the
     baked private tests onto the reference solution taken from the repo checkout
     (`.`, not from the image) and runs the full pipeline on a live runner.
   - **`deploy-public`** exports public files to the public repo and POSTs
     `.manytask.yml` to the web app.

2. **Student repo (`.gitlab-ci.yml`)** — on every push, the **`grade`** job uses the
   testenv image (`image: "$TESTENV_IMAGE"`) and runs `checker grade . /opt/course`:
   the student's solution comes from the checkout (`.`), the hidden tests come from the
   baked `/opt/course`.

   `checker grade` reads **both** `.checker.yml` and `.manytask.yml` from the second
   argument — i.e. from `/opt/course` inside the image, not from the student's
   checkout. Any change to the report pipeline therefore only takes effect after
   `build-testenv` rebuilds the image.

Because the image lives in the **private** project's registry but student repos are
forks of the **public** project, students pull it across projects via a
`DOCKER_AUTH_CONFIG` group CI/CD variable (a deploy/group token with `read_registry`
scope on the private project). `TESTENV_IMAGE` must be the **absolute** registry path
whose host matches the private project's `CI_REGISTRY` — on this instance
`gitlab.manytask2.org:5050/sandbox/private/testenv:latest` (a `:5050` port, not a
`registry.` subdomain) — since `.gitlab-ci.yml` is exported verbatim and
`$CI_REGISTRY_IMAGE` would resolve to the student project's own empty registry. The
`auths` key in `DOCKER_AUTH_CONFIG` must use that same host.

> **Caveat (inherent to this design):** a student who controls their own CI can read
> files from the image, including the baked private tests. This is a property of the
> documented manytask testenv approach; the template demonstrates the flow rather than
> hardening against it.

## Using the template for your own course

The steps below are ordered. Several of them are load-bearing — the notes say which.

### 1. Create the course in Manytask (this creates the GitLab objects)

Course creation lives at **`/instance_admin/courses/new`** and requires an
**instance admin** or a **namespace admin**. If you are neither, ask an instance
admin to create the course for you.

Submitting that form creates three things in the RMS for you:

| Object | Created by | Note |
|---|---|---|
| course group `<course>` | Manytask | derived from the public repo path minus its last segment |
| public repo `<course>/public` | Manytask | visibility **public**, initialised with a README |
| students group `<course>/students` | Manytask | created as a **subgroup** of the course group |
| private repo `<course>/private` | **you, by hand** | Manytask never creates it |

Because Manytask derives the course group from the public repo path and creates the
students group beneath it, the public repo and the students group must be siblings
under one group. Create the private repo under that same group too, so that
group-level CI/CD variables reach both pipelines.

Form fields you must decide on:

- **Unique course name** — the course *slug*. This is the DB key and the URL segment
  (`/<course>/…`, `/api/<course>/…`). It must match the `MANYTASK_COURSE` CI variable,
  the `<course>` segment of `report_url`, and what students type to join.
  It is **not** `.manytask.yml → settings.course_name`, which the server ignores.
- **Namespace** — required. On a brand-new instance there are no namespaces, so only
  an instance admin can create the first course, choosing the "no namespace" option.
- **Registration secret** — free text you invent. Students need it to join; distribute
  it out of band along with the slug.
- **Course token** — pre-filled with a generated value. It authenticates
  `update_config` and score reports. Afterwards it is readable at
  `/instance_admin/courses/<course>/edit`; there is no rotation UI, so treat it as
  permanent.

> On a fresh instance, the only bootstrap is the `INITIAL_INSTANCE_ADMIN` env var.
> That user must complete OAuth login **and** signup before they can create anything —
> the row inserted at boot carries a placeholder RMS id until then.

### 2. Put the template into your private repo

```bash
git clone https://github.com/manytask/manytask.git
cd manytask
course-template/deploy.sh git@<your-gitlab-host>:<your-course>/private.git
```

Or clone the deployed GitLab template directly (available only after a maintainer has
published it to `gitlab.manytask2.org/sandbox/private`):

```bash
git clone https://gitlab.manytask2.org/sandbox/private private
cd private
git remote set-url origin git@<your-gitlab-host>:<your-course>/private.git
git push -u origin main
```

Remember that `deploy.sh` mirrors with `--delete`; use it once, then work in a normal
clone.

### 3. Point the private project at the right CI file

**In `<course>/private` → Settings → CI/CD → General pipelines → CI/CD configuration
file, set `.releaser-ci.yml`.**

This is mandatory and easy to miss. Both CI files ship in the same directory, and
GitLab defaults to `.gitlab-ci.yml` — which is the *student* grade job. An
unconfigured private project runs `checker grade . /opt/course` against your own
checkout on every push and fails on an image that does not exist yet.

### 4. Enable the registry and create the deploy token

- Enable the **Container Registry** on the private project, otherwise `CI_REGISTRY`
  and `CI_REGISTRY_IMAGE` are empty and `build-testenv` cannot push.
- Create a deploy token on the private project (**Settings → Repository → Deploy
  tokens**) named **exactly** `gitlab-deploy-token`, scopes `read_registry` +
  `write_registry`. GitLab then exposes it to CI as `CI_DEPLOY_USER` /
  `CI_DEPLOY_PASSWORD`, which kaniko uses. The CI **job token** is deliberately not
  used: self-managed GitLab often denies it registry-push access
  (`UNAUTHORIZED: HTTP Basic: Access denied`).
- Make sure a runner is available that accepts **untagged** jobs (neither CI file sets
  `tags:`) and uses a **docker or kubernetes** executor — kaniko runs with
  `entrypoint: [""]`, which a shell executor cannot honour.

### 5. Edit the configs

| File | What to change |
|---|---|
| `.manytask.yml` | `settings.course_name`, `settings.gitlab_base_url`, `settings.public_repo`, `settings.students_group`; `ui.task_url_template`, `ui.links`; every `deadlines.schedule` date; keep `status: in_progress` |
| `.checker.yml` | `export.destination` (schema-required, but **documentation only** — no code reads it); the `report_pipeline` block, see [below](#enabling-score-reporting) |
| `.releaser-ci.yml` | `PUBLIC_REPO_URL` (the authenticated clone URL of *your* public repo — this is the real push target), `CHECKER_PIP_SPEC` |
| `.gitlab-ci.yml` | `TESTENV_IMAGE` — absolute registry path, host must match the private project's `CI_REGISTRY` including the `:5050` port |

There is no `REGISTRY` variable to edit: registry paths come from GitLab's predefined
`$CI_REGISTRY_IMAGE`.

### 6. Add CI/CD variables — mind the scope

Scope matters for both correctness and security. Group variables propagate into every
student fork under `<course>/students/…`, where students can run pipelines and print
them.

| Variable | Scope | Purpose |
|---|---|---|
| `GITLAB_API_TOKEN` | **private project only** | Lets `checker export --commit` push to the public repo. Group/project access token, role `Maintainer`, scope `write_repository`. Never set this at group scope — that hands every student a Maintainer write token. |
| `MANYTASK_URL` | private project | Base URL of your Manytask instance. **Required**: unset, it defaults to the sandbox instance. |
| `MANYTASK_COURSE` | private project | Your course slug. **Required**: unset, it defaults to `sandbox` and your deadlines are pushed into the shared sandbox course. |
| `MANYTASK_TOKEN` | private project (and `<course>` group only if reporting is enabled) | Course token: pushes `.manytask.yml` to `/api/<course>/update_config`, and the grader reports scores with it. |
| `DOCKER_AUTH_CONFIG` | `<course>` **group**, **unprotected** | Lets student repos pull the testenv image from the private project's registry. Must be unprotected: Manytask deletes protected branches on each fork, so protected variables are never injected into student pipelines. |
| `TESTENV_IMAGE` | `<course>` group (or edit `.gitlab-ci.yml`) | Absolute registry path to the testenv image used by the student `grade` job. |
| `BOT_URL` | `<course>` group | Optional. Base URL of the mr-reviewer bot; the `deploy-mr-review` job is a no-op when unset. |

> **Known limitation.** Enabling score reporting requires `MANYTASK_TOKEN` to be
> visible inside student pipelines, and masking is trivially bypassed. A leaked course
> token lets its holder become a course admin via `/create_project` and write arbitrary
> scores through the database API, and it cannot be rotated from any UI. Until
> per-student tokens land there is no configuration that closes this.

### 7. Push to `main`

The releaser pipeline runs `validate → build-testenv → check → deploy-public`, in that
order. `deploy-public` exports public files **and** POSTs `.manytask.yml` to
`/api/<course>/update_config`, which is why step 1 has to come first: for an unknown
slug that endpoint answers `404 Course not found` and the job fails.

Two things to check after the first green pipeline:

- The course status. The very first `update_config` only promotes a course from
  `created` to `hidden`, and hidden courses are invisible to non-admins. The template
  ships `status: in_progress`, which is what actually makes the course usable — keep
  it, or flip the status on the Edit Course page.
- The public repo's default branch must be `main`, since the exporter pushes `main` and
  students' pipelines resolve `.gitlab-ci.yml` on the public repo's default branch.

### 8. Let students in

Give each student the **course slug** and the **registration secret**. The flow is:

1. The student logs into Manytask (OAuth) and completes signup. Their Manytask login
   and their GitLab username must be the same string — Manytask still looks the RMS
   user up by the auth username.
2. On the courses page they type the slug into the "Register on new course" box.
   There is no course browser: without the exact slug they cannot find the course.
3. They are redirected to `/<course>/create_project`, enter the registration secret,
   and Manytask forks the public repo into `<course>/students/<username>` and grants
   them Reporter on the public project.
4. They push a solution; the `grade` job runs and reports the score.

Two consequences worth telling students about:

- The fork's CI config path points at `.gitlab-ci.yml` **in the public repo**, so a
  student's own `.gitlab-ci.yml` is ignored. You change the grade job by exporting a
  new one, not by asking students to edit anything.
- **The fork is a point-in-time snapshot and is never refreshed.** Students who joined
  before you added a task will not see it until they sync manually:

  ```bash
  git remote add upstream https://<your-gitlab-host>/<course>/public.git
  git fetch upstream
  git merge upstream/main
  ```

## Enabling score reporting

`.checker.yml` ships with `report_pipeline` **commented out**, so a green student
pipeline reports nothing. To turn scoring on:

1. Uncomment the `report_pipeline` block in the **private** repo's `.checker.yml`.
2. Set `report_url` to the **full endpoint**, `https://<your-manytask-host>/api/<course>/report`.
   The plugin POSTs this URL verbatim — it appends no path. The value the template
   ships (a bare host) is not a working endpoint.
3. Make sure `CHECKER_PIP_SPEC` is new enough to resolve `${{ env.… }}` expressions.
   The commit pinned in the shipped `.releaser-ci.yml` and `testenv.docker` predates
   that fix, so `${{ env.GITLAB_USER_LOGIN }}` and `${{ env.MANYTASK_TOKEN }}` come out
   undefined. Bump the pin in **both** files.
4. Provide `MANYTASK_TOKEN` where student pipelines can see it (see the scope warning
   above).
5. Push, and wait for `build-testenv` to finish: `checker grade` reads `.checker.yml`
   from `/opt/course`, so the change only takes effect in the rebuilt image.

How the score is interpreted by `/api/<course>/report`:

- a value that looks like an integer (`"5"`) is an **absolute** score,
- anything else parseable as a float (`0.67`, `1.0`) is a **fraction** of the task's
  configured score.

The template's `${{ outputs.private_tests.percentage }}` is a fraction, which is
correct — but wiring an absolute integer there silently changes the meaning.

Failure modes to expect:

- **A student whose public tests fail gets no report at all — not a zero.** The public
  stage is `fail: fast`, and the report pipeline only runs when the task pipeline
  passed. An empty cell is indistinguishable from "never submitted".
- `404 There is no registered user with rms_id=…` — the pusher exists in GitLab but has
  never completed Manytask signup. Also fires when a *teacher* pushes into a student's
  fork, since the report uses the pusher's login.
- `404 Task 'X' not found in course 'Y' (or it is closed for submission)` — the task or
  its group is not enabled in the config the server currently holds. Every
  `update_config` disables everything and re-enables only what the pushed file lists,
  so never push a partial `.manytask.yml`.

## Adding a task

1. Create `<group>/<task_name>/` inside an existing group.
2. Add:
   - `.task.yml` — may be empty, or `version: 1`. **A folder without it is not a task.**
   - `<task_name>.py` — the reference solution.
   - `<task_name>.py.template` — what students get. Every task needs at least one
     `.template` file or the export fails.
   - `test_public.py` and `test_private.py` — the root `tasks_pipeline` targets these
     two filenames literally, so a Python task must use exactly them.
   - `README.md` — the task statement.
   - `conftest.py` — copy from `python/add/` if your tests import from the task folder.
3. Register the task in `.manytask.yml` under its group's `tasks:`.
4. Commit and push to `main`.

Rules the checker enforces (or silently does not):

- A task listed in `.manytask.yml` but **missing on disk** is a hard `validate` error.
  A missing *group* is only a warning.
- A task on disk but **not listed** in `.manytask.yml` is still exported to students —
  it is simply never graded. Keep drafts outside the course tree, or list them with
  `enabled: false`.
- A group whose `start` is in the future is excluded from **both** the public export
  and `/opt/course`. Since both jobs only run on push, a task does not appear when its
  start time arrives — it appears at the next push. Use a scheduled pipeline if your
  schedule releases tasks over time.

## Adding a language group

Three edits, all required:

1. `<lang>/.group.yml` containing `version: 1` and a `task_pipeline:` block that
   overrides the default `run_pytest` stages.

   > The field is `task_pipeline` — **singular, at the top level**, not
   > `testing.tasks_pipeline` as in `.checker.yml`. Sub-configs ignore unknown keys, so
   > a misspelled override is silently dropped and the root pipeline runs instead.

2. A `- group:` entry in `.manytask.yml`. Without it the group's tasks are exported but
   never graded (a missing group is only a warning).
3. The toolchain added to the single `apk add` block in `testenv.docker`. Forgetting
   this surfaces only as `command not found` inside a student's job.

See `cpp/.group.yml`, `go/.group.yml`, `rust/.group.yml` and `bash/.group.yml` for
working `run_script` examples.

## Local development

`pyproject.toml` is pytest configuration, not an installable package — `pip install -e .`
fails on the multi-language layout. Install the tools directly:

```bash
python -m venv .venv
source .venv/bin/activate
pip install pytest

pytest                            # all Python tasks (testpaths = ["python"])
pytest python/add/test_public.py  # one task's visible tests
```

To run the checker itself, install the same spec the CI uses — the PyPI release
predates the monorepo commands and has no `validate` or `export`:

```bash
pip install "git+https://github.com/manytask/manytask.git@<pin>#subdirectory=checker" pytest
checker validate
checker export . /tmp/export-preview   # inspect what students would receive
```

`checker export` always writes, and wipes its target first — `--dry-run` does not
suppress that. Always give it a throwaway directory, never your working tree.

Note also that `checker check` re-validates the tree it is pointed at, and exported
trees have no `.template` files. Running `checker check` inside a student checkout
therefore fails on validation rather than on the tests.

## Related references

- [Course as Code](./course_as_code.md) — the underlying concept
- [The basic example](./basic_example.md) — the same course without the checker
- [Private repository](./private_repo.md) — how the private repo is structured
- [.checker.yml reference](./checker_yml_reference.md) — every field explained
- [.manytask.yml reference](./manytask_yml_reference.md) — schedule and grades schema
- [Checker pipelines and plugins](./checker_pipelines_and_plugins.md) — building custom pipelines

# manytask sandbox — course template

This repository is the **reference course template** for [Manytask](https://manytask.org).
Fork or copy it to bootstrap a new course in minutes.

The template demonstrates the standard *Course as Code* layout:

- One **private** repository (this one) containing reference solutions, hidden tests, configs.
- One **public** repository that is auto-generated from the private one by `checker export`.
- One **students group** where Manytask creates a fork of the public repo for each student.

See the upstream docs:

- Concept: [Course as Code](https://manytask.org/course_as_code.html)
- **Full deployment guide: [Course template](https://manytask.org/course_template.html)**
- Checker configuration: <https://manytask.org/checker_config.html>
- `.checker.yml` reference: <https://manytask.org/checker_yml_reference.html>
- Checker pipelines and plugins: <https://manytask.org/checker_pipelines_and_plugins.html>

---

## What is in here

```
.
├── .checker.yml          # checker structure, export rules, default run_pytest pipeline
├── .manytask.yml         # course settings + deadlines schedule (one group per language)
├── .gitlab-ci.yml        # CI for grading student submissions (exported into public)
├── .releaser-ci.yml      # CI for building the testenv image and exporting private -> public
├── testenv.docker        # ONE Alpine image with every toolchain; bakes the reference at /opt/course
├── pyproject.toml        # pytest configuration (NOT an installable package)
├── deploy.sh             # one-shot bootstrap: monorepo -> GitLab private repo
├── python/add/           # sum of two integers — run_pytest
├── cpp/add_cpp/          # g++ compile + run       (.group.yml overrides the pipeline)
├── bash/add_bash/        # bash test driver        (.group.yml overrides the pipeline)
├── go/add_go/            # go run add.go test_*.go (.group.yml overrides the pipeline)
└── rust/add_rust/        # rustc --test            (.group.yml overrides the pipeline)
```

Every task folder holds the same six things:

```
python/add/
├── .task.yml         # marks the folder as a task (may be empty)
├── README.md         # task statement
├── add.py            # reference solution (NOT exported)
├── add.py.template   # becomes add.py in the public repo
├── test_public.py    # visible to students
├── test_private.py   # hidden, used for grading
└── conftest.py       # makes `from add import add` work in pytest
```

Five language groups with one `add` task each: the smallest end-to-end example you can
run, copy, and extend. Python uses `run_pytest`; the other four override
`task_pipeline` in their `.group.yml` to compile-and-run via `run_script`. One
multi-toolchain `testenv.docker` grades all of them, because `checker grade` has no
per-language scoping.

Task folder names are globally unique on purpose — the checker's on-disk scan collapses
same-named folders into one entry without complaining.

---

## Use this template for your own course

Below is the short version. The [full guide](https://manytask.org/course_template.html)
explains each step, its ordering constraints, and its failure modes.

### 1. Create the course in Manytask first

Course creation (`/instance_admin/courses/new`, instance or namespace admin) creates
the GitLab **course group**, the **public repo** and the **students group** for you.
It does **not** create the private repo — that one is yours to create by hand, under
the same course group so that group CI/CD variables reach both pipelines.

Write down three things from the form: the **course slug** (`unique_course_name`), the
**registration secret** (students need it), and the **course token**.

This has to happen before the first pipeline run: `deploy-public` POSTs your config to
`/api/<course>/update_config`, which 404s for a course that does not exist.

### 2. Copy this template into your private project

The template lives in the `course-template/` folder of the Manytask repo, so
clone that repo and copy the folder out — a plain `git clone` can't fetch a
single subdirectory:

```bash
git clone https://github.com/manytask/manytask.git
cp -r manytask/course-template private
rm -rf manytask
cd private
rm deploy.sh
git init -b main
git add .
git commit -m "chore: init course from template"
git remote add origin git@<your-gitlab-host>:<your-course>/private.git
git push -u origin main
```

(`deploy.sh` is a maintainer tool for syncing the monorepo to the sandbox repo. It
mirrors with `rsync --delete`, so keeping it around in your own course is a footgun.)

### 3. Point the private project at `.releaser-ci.yml`

**`<course>/private` → Settings → CI/CD → General pipelines → CI/CD configuration file
→ `.releaser-ci.yml`.**

Mandatory. Both CI files live in this directory and GitLab defaults to
`.gitlab-ci.yml`, which is the *student* grade job — an unconfigured private project
runs it against your own checkout and fails.

### 4. Enable the registry and create the deploy token

- Enable the **Container Registry** on the private project.
- Create a deploy token named **exactly** `gitlab-deploy-token`, scopes
  `read_registry` + `write_registry`. GitLab exposes it as
  `CI_DEPLOY_USER` / `CI_DEPLOY_PASSWORD`, which kaniko uses; the CI job token is
  deliberately not used because self-managed GitLab often denies it registry pushes.
- Provide a runner that accepts **untagged** jobs and uses a **docker or kubernetes**
  executor (kaniko needs `entrypoint: [""]`).

### 5. Edit the configs

| File | Change |
|---|---|
| `.manytask.yml` | `settings.course_name`, `settings.gitlab_base_url`, `settings.public_repo`, `settings.students_group`; `ui.task_url_template`, `ui.links`; every `deadlines.schedule` date; keep `status: in_progress` |
| `.checker.yml` | `export.destination` (schema-required, documentation only — no code reads it); the `report_pipeline` block, see below |
| `.releaser-ci.yml` | `PUBLIC_REPO_URL` — the authenticated clone URL of *your* public repo, and the actual push target |
| `.gitlab-ci.yml` | `TESTENV_IMAGE` — absolute registry path; the host must match the private project's `CI_REGISTRY`, including the `:5050` port |

There is no `REGISTRY` variable: registry paths come from the predefined
`$CI_REGISTRY_IMAGE`.

### 6. Set the CI/CD variables — scope matters

Group variables reach every student fork, where students can print them.

| Variable | Scope | Used for |
|---|---|---|
| `GITLAB_API_TOKEN` | **private project only** | `checker export --commit` push to public. Access token, role `Maintainer`, scope `write_repository`. Never at group scope. |
| `MANYTASK_URL` | private project | Your Manytask host. Unset → defaults to the sandbox instance. |
| `MANYTASK_COURSE` | private project | Your course slug. Unset → defaults to `sandbox`, and your deadlines land in the shared sandbox course. |
| `MANYTASK_TOKEN` | private project (+ group only if reporting is on) | `update_config`, and score reporting. |
| `DOCKER_AUTH_CONFIG` | `<course>` group, **unprotected** | Lets student forks pull the testenv image. Must be unprotected — Manytask deletes protected branches on forks, so protected variables never reach student pipelines. |
| `TESTENV_IMAGE` | `<course>` group (or edit `.gitlab-ci.yml`) | Image the student grade job pulls. |
| `BOT_URL` | `<course>` group | Optional; mr-reviewer bot. The job self-skips when unset. |

### 7. Push to `main`

`.releaser-ci.yml` runs, in order:

1. `validate` — `checker validate` sanity-checks the configs.
2. `build-testenv` — kaniko builds `testenv.docker` and pushes it to the registry.
3. `check` — runs the reference solution through the full pipeline inside that image.
4. `deploy-public` — `checker export --commit` copies public files into the public
   repo, then POSTs `.manytask.yml` to `${MANYTASK_URL}/api/${MANYTASK_COURSE}/update_config`
   with `Authorization: Bearer $MANYTASK_TOKEN`. (There is no `checker` subcommand for
   this; checker only exports files.)

### 8. Enable score reporting

`.checker.yml` ships with `report_pipeline` commented out, so a green student pipeline
reports nothing. To turn it on:

- Uncomment the block.
- Set `report_url` to the **full endpoint** — `https://<host>/api/<course>/report`.
  The plugin POSTs the URL verbatim and appends no path.
- Bump `CHECKER_PIP_SPEC` in **both** `.releaser-ci.yml` and `testenv.docker`: the
  pinned commit predates `${{ env.… }}` resolution, so `GITLAB_USER_LOGIN` and
  `MANYTASK_TOKEN` come out undefined.
- Push and wait for `build-testenv`: `checker grade . /opt/course` reads `.checker.yml`
  from the image, not from the student checkout.

---

## Local development

`pyproject.toml` is pytest configuration, not an installable package — `pip install -e .`
fails on the multi-language layout. Install the tools directly:

```bash
python -m venv .venv
source .venv/bin/activate
pip install pytest

# run all Python tasks (testpaths = ["python"])
pytest

# run a single task's public tests
pytest python/add/test_public.py
```

To run the checker, install the same spec the CI uses — the PyPI release predates the
monorepo commands and has no `validate` or `export`:

```bash
pip install "git+https://github.com/manytask/manytask.git@<pin>#subdirectory=checker" pytest
checker validate
checker export . /tmp/export-preview   # inspect what students would receive
```

`checker export` always writes and wipes its target first; `--dry-run` does not
suppress that. Point it at a throwaway directory, never at your working tree.

For the full list of commands and config options, see the
[checker configuration docs](https://manytask.org/checker_config.html) and the
[`.checker.yml` reference](https://manytask.org/checker_yml_reference.html).

---

## Adding a new task

1. Create a folder: `python/<task_name>/`
2. Add:
   - `.task.yml` — may be empty. A folder without it is not a task.
   - `<task_name>.py` — reference solution
   - `<task_name>.py.template` — what students see. Each task needs at least one
     `.template`, or the export fails.
   - `test_public.py` and `test_private.py` — the root pipeline targets these two
     filenames literally, so a Python task must use exactly them.
   - `README.md` — task description
   - `conftest.py` — copy from `python/add/` if you use top-level imports
3. Register the task in `.manytask.yml` under `deadlines.schedule[python].tasks`.
4. Commit and push to `main`. The pipeline does the rest.

Worth knowing:

- A task in `.manytask.yml` but missing on disk is a hard `validate` error; a missing
  *group* is only a warning.
- A task on disk but not in `.manytask.yml` is still exported to students — it is just
  never graded. Keep drafts out of the tree, or list them with `enabled: false`.
- A group whose `start` is in the future is excluded from the export *and* from
  `/opt/course`. Tasks appear at the next push after the start time, not at the start
  time itself.
- Students who already forked do **not** receive new tasks automatically. Tell them to
  `git remote add upstream <public repo>` and merge.

## Adding a new language group

1. `<lang>/.group.yml` with `version: 1` and a `task_pipeline:` block.
   The field is `task_pipeline` — singular, top level — not `testing.tasks_pipeline` as
   in `.checker.yml`. Sub-configs ignore unknown keys, so a misspelling is dropped
   silently and the default pipeline runs instead.
2. A `- group:` entry in `.manytask.yml`, or the group's tasks are never graded.
3. The toolchain added to the `apk add` block in `testenv.docker`, or student jobs fail
   with `command not found`.

`cpp/`, `go/`, `rust/` and `bash/` are working `run_script` examples.

---

## License

See the upstream [manytask](https://github.com/manytask/manytask) repository.

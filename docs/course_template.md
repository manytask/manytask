# Course template (sandbox)

To make spinning up a new course painless, Manytask ships a **reference course template** — a pre-configured repository that already has a working `.checker.yml`, `.manytask.yml`, CI pipelines, a Docker test environment, and one solved sample task per supported language.

Use it to:

- bootstrap a new course in minutes instead of writing configs from scratch,
- learn the *Course as Code* layout by reading a real working example,
- copy patterns for adding new tasks and languages.

## Where to find it

The canonical source lives **in this monorepo** under [`course-template/`](../course-template/).

It is deployed to the GitLab private template repository at:

> **`gitlab.manytask.org/sandbox/private`**

A maintainer runs `course-template/deploy.sh` to push changes from the monorepo to GitLab:

```bash
# From the repository root
course-template/deploy.sh git@gitlab.manytask.org:sandbox/private.git
```

The script clones (or initialises) the GitLab repo, mirrors the `course-template/` tree over it (excluding `.git` and `deploy.sh` itself), commits the result, and pushes to `main`.

Once the template stabilises it will be promoted to the production instance
(`gitlab.manytask.org/sandbox`) and bound to a `sandbox` course on
<https://app.manytask.org>.

## What is inside

The template ships five language groups — **Python**, **C++**, **Bash**, **Go**,
**Rust** — each with one solved `add` sample task, demonstrating
[manytask#637](https://github.com/manytask/manytask/issues/637). Python tasks test
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
├── base.docker           # checker + Python/C++/Go/Rust/Bash toolchains
├── testenv.docker        # two-stage build; final image has export-private output at /opt/course
├── pyproject.toml        # Python toolchain
├── tools/                # shared tooling (empty placeholder)
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
`add_rust`) because the checker requires unique task names across all groups.

This is the smallest end-to-end example that:

- passes `checker validate` and `checker check`,
- demonstrates the `.template` strategy for hiding reference solutions,
- separates public and private tests,
- reports its score back to the Manytask web app once the report pipeline is enabled in CI.

## How grading works (testenv image)

Student submissions must be graded against the **hidden** (`test_private.*`) tests,
but those tests are never exported to the public/student repository. Manytask solves
this with a **testenv docker image** (see [Concepts](./concepts.md)): an image that
carries a copy of the private repository — including the private tests — and the
checker. The same image runs `checker check` in the private repo and `checker grade`
in student repos.

The template wires this in two pipelines:

1. **Private repo (`.releaser-ci.yml`)** — on every push:
   - **`verify`** validates the course configuration. **`build-base`** then publishes
     a checker/toolchain image, and **`check`** runs `checker check . .` in it.
   - **`build-testenv`** uses that base image and builds
     [`testenv.docker`](../course-template/testenv.docker). Its first Docker stage
     runs `checker export-private`; the final, published stage copies only that
     exported reference into **`/opt/course`**, not the raw private checkout.
   - On the default branch, manual deploy jobs publish the `:latest` testenv image,
     `.manytask.yml`, and the public repository.

2. **Student repo (`.gitlab-ci.yml`)** — on every push, the **`grade`** job uses the
   testenv image (`image: "$TESTENV_IMAGE"`) and runs `checker grade . /opt/course`:
   the student's solution comes from the checkout (`.`), the hidden tests come from the
   baked `/opt/course`. To report the score to the web app, enable the
   `report_pipeline` (`report_score_manytask`) in `.checker.yml` — `checker grade`
   always runs it — and provide a `MANYTASK_TOKEN` CI variable. (The grade
   `--submit-score` flag is currently a no-op in checker, so it does not report.)

Because the image lives in the **private** project's registry but student repos are
forks of the **public** project, students pull it across projects via a
`DOCKER_AUTH_CONFIG` group CI/CD variable (a deploy/group token with `read_registry`
scope on the private project). `TESTENV_IMAGE` must be the **absolute** registry path
whose host matches the private project's `CI_REGISTRY` — on this instance
`gitlab.manytask.org:5050/sandbox/private/testenv-image:latest` (a `:5050` port, not a
`registry.` subdomain) — since `.gitlab-ci.yml` is exported verbatim and
`$CI_REGISTRY_IMAGE` would resolve to the student project's own empty registry. The
`auths` key in `DOCKER_AUTH_CONFIG` must use that same host.

> **Caveat (inherent to this design):** a student who controls their own CI can read
> files from the image, including the baked private tests. This is a property of the
> documented manytask testenv approach; the template demonstrates the flow rather than
> hardening against it.

## Using the template for your own course

1. Create two empty GitLab projects — `<your-course>/private` (template clone) and `<your-course>/public` (auto-generated for students) — plus an empty `<your-course>/students` group.
2. Clone the monorepo, then deploy the template to your private GitLab project:

    ```bash
    git clone https://github.com/manytask/manytask.git
    cd manytask
    course-template/deploy.sh git@gitlab.manytask.org:<your-course>/private.git
    ```

   Alternatively, clone the deployed GitLab template directly (available only after a maintainer has run `deploy.sh` to publish it to `gitlab.manytask.org/sandbox/private`):

    ```bash
    git clone https://gitlab.manytask.org/sandbox/private private
    cd private
    git remote set-url origin git@gitlab.manytask.org:<your-course>/private.git
    git push -u origin main
    ```

3. Edit `.checker.yml` (`export.destination`), `.manytask.yml` (`settings`, `ui`, `deadlines.schedule`), and `.releaser-ci.yml` (`REGISTRY`, `MANYTASK_URL`, `COURSE_NAME`, and `PUBLIC_REPO_URL`).
4. Add CI/CD variables in **Group → Settings → CI/CD → Variables**:

    | Variable | Purpose |
    |---|---|
    | `GITLAB_API_TOKEN` | Lets `checker export --commit` push to the public repo. Group access token, role `Maintainer`, scope `write_repository`. |
    | `DOCKER_AUTH_CONFIG` | Lets the private pipeline push course images and student repos pull them. Set it to deploy/group-token credentials with `read_registry` + `write_registry` on the private project. |
    | `TESTENV_IMAGE` | Absolute registry path to the testenv image used by the student `grade` job; host must match the private project's `CI_REGISTRY` (e.g. `gitlab.manytask.org:5050/<course>/private/testenv-image:latest`). Defaults to the sandbox path in `.gitlab-ci.yml`; override for your course. |
    | `MANYTASK_TOKEN` | Course token used by the optional `report_score_manytask` pipeline in `.checker.yml` and by `.releaser-ci.yml` to send `.manytask.yml` to Manytask. |

5. Create a **deploy token** with `read_registry` + `write_registry` on the private
   project and store its Docker auth JSON in `DOCKER_AUTH_CONFIG`. The release jobs
   use Docker CLI with that config to publish `ci-base` and `testenv-image`; the same
   token's read scope supports the student-side image pull.

6. Ask a Manytask admin to register your course (slug, public repo URL, students group URL).
7. Push to `main`, then run the three manual deploy jobs to publish the image, export the public repo, and update Manytask.

Full step-by-step instructions live in the template's own
[`README.md`](https://github.com/manytask/manytask/blob/main/course-template/README.md).

## Related references

- [Course as Code](./course_as_code.md) — the underlying concept
- [Private repository](./private_repo.md) — how the private repo is structured
- [.checker.yml reference](./checker_yml_reference.md) — every field explained
- [.manytask.yml reference](./manytask_yml_reference.md) — schedule and grades schema
- [Checker pipelines and plugins](./checker_pipelines_and_plugins.md) — building custom pipelines

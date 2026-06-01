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

Once the template stabilises it will be promoted to the production instance
(`gitlab.manytask.org/sandbox`) and bound to a `sandbox` course on
<https://app.manytask.org>.

## What is inside

The template is designed for five language groups. Only `python/` is present in the
initial iteration; the remaining groups — **C++**, **Bash**, **Go**, **Rust** — are
placeholders planned as follow-up iterations of
[manytask#637](https://github.com/manytask/manytask/issues/637).

```
course-template/
├── .checker.yml          # structure, export rules, testing pipeline
├── .manytask.yml         # settings + deadlines schedule
├── .gitlab-ci.yml        # CI for grading student submissions (uses the testenv image)
├── .releaser-ci.yml      # CI: build+push testenv image, check, export private → public (not exported)
├── .gitignore
├── testenv.docker        # testenv image: bakes the private reference at /opt/course
├── pyproject.toml        # Python toolchain
├── tools/                # shared tooling (empty placeholder)
├── python/
│   └── add/              # sample task: sum of two integers
│       ├── .task.yml
│       ├── README.md
│       ├── add.py            # reference solution (NOT exported)
│       ├── add.py.template   # what students see (becomes add.py on export)
│       ├── test_public.py    # visible tests
│       ├── test_private.py   # hidden grading tests (NOT exported)
│       └── conftest.py       # adds the task folder to sys.path
├── cpp/                  # (planned)
├── bash/                 # (planned)
├── go/                   # (planned)
└── rust/                 # (planned)
```

This is the smallest end-to-end example that:

- passes `checker validate` and `checker check`,
- demonstrates the `.template` strategy for hiding reference solutions,
- separates public and private tests,
- reports its score back to the Manytask web app once the report pipeline is enabled in CI.

## How grading works (testenv image)

Student submissions must be graded against the **hidden** (`test_private.py`) tests,
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
     Dockerfile bakes the full private reference at **`/opt/course`** via
     `checker export-private` (gold solutions, filled templates, public **and**
     private tests). Both `:$CI_COMMIT_SHORT_SHA` and `:latest` tags are pushed.
   - **`check`** runs *inside that image*: `checker check . /opt/course` overlays the
     baked private tests onto the reference solution and runs the full pipeline on a
     live runner. This is the dress rehearsal for student grading.
   - **`deploy-public`** exports public files to `sandbox/public`.

2. **Student repo (`.gitlab-ci.yml`)** — on every push, the **`grade`** job uses the
   testenv image (`image: "$TESTENV_IMAGE"`) and runs `checker grade . /opt/course`:
   the student's solution comes from the checkout (`.`), the hidden tests come from the
   baked `/opt/course`. Add `--submit-score` (plus a `MANYTASK_TOKEN`) to report the
   score to the web app.

Because the image lives in the **private** project's registry but student repos are
forks of the **public** project, students pull it across projects via a
`DOCKER_AUTH_CONFIG` group CI/CD variable (a deploy/group token with `read_registry`
scope on the private project). `TESTENV_IMAGE` must be the **absolute** registry path
(e.g. `registry.gitlab.manytask2.org/sandbox/private/testenv:latest`), since
`.gitlab-ci.yml` is exported verbatim and `$CI_REGISTRY_IMAGE` would resolve to the
student project's own empty registry.

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
    course-template/deploy.sh git@gitlab.manytask2.org:<your-course>/private.git
    ```

   Alternatively, clone the deployed GitLab template directly (available only after a maintainer has run `deploy.sh` to publish it to `gitlab.manytask2.org/sandbox/private`):

    ```bash
    git clone https://gitlab.manytask2.org/sandbox/private private
    cd private
    git remote set-url origin git@gitlab.manytask2.org:<your-course>/private.git
    git push -u origin main
    ```

3. Edit `.checker.yml` (`export.destination`), `.manytask.yml` (`settings`, `ui`, `deadlines.schedule`), and `.releaser-ci.yml` (`REGISTRY`).
4. Add CI/CD variables in **Group → Settings → CI/CD → Variables**:

    | Variable | Purpose |
    |---|---|
    | `GITLAB_API_TOKEN` | Lets `checker export --commit` push to the public repo. Group access token, role `Maintainer`, scope `write_repository`. |
    | `DOCKER_AUTH_CONFIG` | Lets student repos pull the testenv image from the private project's registry. Set as a **group** variable holding creds for a deploy/group token with `read_registry` scope on the private project. |
    | `TESTENV_IMAGE` | Absolute registry path to the testenv image used by the student `grade` job (e.g. `registry.gitlab.manytask2.org/<course>/private/testenv:latest`). Defaults to the sandbox path in `.gitlab-ci.yml`; override for your course. |
    | `MANYTASK_TOKEN` | Lets the grader report scores back to the Manytask web app. |
    | `TESTER_TOKEN` | Authentication for the grading job. |

5. Create a **deploy token** so `build-testenv` can push the image. On the **private**
   project: **Settings → Repository → Deploy tokens**, name it exactly
   `gitlab-deploy-token`, scopes `read_registry` + `write_registry`. GitLab then
   auto-exposes it to CI as `CI_DEPLOY_USER` / `CI_DEPLOY_PASSWORD`, which the kaniko
   `build-testenv` job uses to authenticate — the CI **job token** is not used, because
   self-managed GitLab often denies it registry-push access (`UNAUTHORIZED: HTTP Basic:
   Access denied`). The same token's `read_registry` scope can back the
   `DOCKER_AUTH_CONFIG` group variable above for the student pull side.

6. Ask a Manytask admin to register your course (slug, public repo URL, students group URL).
6. Push to `main` — the pipeline validates configs, exports public files, and updates deadlines on the web app.

Full step-by-step instructions live in the template's own
[`README.md`](../course-template/README.md).

## Related references

- [Course as Code](./course_as_code.md) — the underlying concept
- [Private repository](./private_repo.md) — how the private repo is structured
- [.checker.yml reference](./checker_yml_reference.md) — every field explained
- [.manytask.yml reference](./manytask_yml_reference.md) — schedule and grades schema
- [Checker pipelines and plugins](./checker_pipelines_and_plugins.md) — building custom pipelines

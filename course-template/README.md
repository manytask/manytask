# manytask sandbox — course template

This repository is the **reference course template** for [Manytask](https://manytask.org).
Fork or copy it to bootstrap a new course in minutes.

The template demonstrates the standard *Course as Code* layout:

- One **private** repository (this one) containing reference solutions, hidden tests, configs.
- One **public** repository that is auto-generated from the private one by `checker export`.
- One **students group** in GitLab where Manytask creates a fork of the public repo for each student.

See the upstream docs:

- Concept: [Course as Code](https://manytask.org/course_as_code.html)
- Checker configuration: <https://manytask.org/checker_config.html>
- `.checker.yml` reference: <https://manytask.org/checker_yml_reference.html>
- Checker pipelines and plugins: <https://manytask.org/checker_pipelines_and_plugins.html>

---

## What is in here

```
.
├── .checker.yml          # checker structure, export rules, testing pipeline
├── .manytask.yml         # course settings + deadlines schedule
├── .gitlab-ci.yml        # CI for grading student submissions (lives in public)
├── .releaser-ci.yml      # CI for exporting private -> public (lives in private)
├── .sourcecraft/ci.yaml  # SourceCraft CI for the private repository
├── .sourcecraft.public/ci.yaml # SourceCraft CI installed in public/student repos
├── base.docker           # checker + language toolchains, built before checks
├── testenv.docker        # exports private reference in a two-stage Docker build
├── pyproject.toml        # python toolchain dependencies
├── tools/                # placeholder for shared plugins / testlib
├── python/
│   └── add/              # sample task — sum of two integers
│       ├── .task.yml
│       ├── README.md
│       ├── add.py            # reference solution (NOT exported)
│       ├── add.py.template   # becomes add.py in the public repo
│       ├── test_public.py    # visible to students
│       ├── test_private.py   # hidden, used for grading
│       └── conftest.py       # makes `from add import add` work in pytest
├── cpp/add_cpp/          # C++ sample task
├── bash/add_bash/        # Bash sample task
├── go/add_go/            # Go sample task
└── rust/add_rust/        # Rust sample task
```

Each language has one sample task with a reference solution, a student template,
public tests, and hidden tests.

---

## Use this template for your own course on GitLab

### 1. Create two empty GitLab projects

| Project | Visibility | Purpose |
|---|---|---|
| `<your-course>/private` | private | This template. Holds solutions and hidden tests. |
| `<your-course>/public`  | internal | Auto-generated. Students fork from here. |

Also create an empty group `<your-course>/students` — Manytask will create
per-student forks of `public` inside it.

### 2. Copy this template into your private project

The template lives in the `course-template/` folder of the Manytask repo, so
clone that repo and copy the folder out — a plain `git clone` can't fetch a
single subdirectory:

```bash
git clone https://github.com/manytask/manytask.git
cp -r manytask/course-template private
rm -rf manytask
cd private
git init -b main
git add .
git commit -m "chore: init course from template"
git remote add origin git@gitlab.com:<your-course>/private.git
git push -u origin main
```

### 3. Edit the configs

Change at least these fields:

- `.checker.yml` -> `export.destination` -> URL of your `public` repo
- `.manytask.yml` -> `ui.task_url_template`, `ui.links`, `deadlines.schedule` (set real dates)
- `.releaser-ci.yml` -> `REGISTRY`, `MANYTASK_URL`, `COURSE_NAME`, and `PUBLIC_REPO_URL`

### 4. Set required GitLab CI/CD variables

In **Group -> Settings -> CI/CD -> Variables**:

| Variable | Where to get it | Used for |
|---|---|---|
| `GITLAB_API_TOKEN` | Group access token, role `Maintainer`, scope `write_repository` | `checker export --commit` push to public |
| `DOCKER_AUTH_CONFIG` | Docker auth JSON for a deploy/group token with `read_registry` + `write_registry` | push base/testenv images and let student repos pull testenv |
| `MANYTASK_TOKEN` | course token from your Manytask admin panel | report scores and deploy `.manytask.yml` |

### 5. Register the course on manytask.org

Ask a Manytask admin to register your course, providing:
- course slug (e.g. `your-course`)
- public repo URL
- students group URL

### 6. Push to `main` and watch the pipeline

`.releaser-ci.yml` will:
1. Verify configuration with `checker validate`.
2. Build a checker/toolchain base image, then run `checker check . .`.
3. Build and publish a testenv whose final image contains only the
   `checker export-private` result.
4. On `main`, manually deploy the image, `.manytask.yml`, and public repo.

---

## Use this template on SourceCraft

Create private and public SourceCraft repositories plus the student repository
namespace. Copy this template into the private repository. The private
`.sourcecraft/ci.yaml` runs `verify-and-build` on pushes; it validates the course,
checks reference solutions, and builds the same two-stage testenv image used by
the GitLab pipeline. The `grade` workflow is shared with student repositories.

Before pushing, replace the example values in both SourceCraft CI files:

| File | Value to configure |
|---|---|
| `.sourcecraft/ci.yaml` | `SERVICE_CONNECTION`, every `pkg.sourcecraft.tech` image/registry path, `PUBLIC_REPO_URL`, and `MANYTASK_API` |
| `.sourcecraft.public/ci.yaml` | `ORG_SLUG`, `REPO_SLUG`, and `STUDENT_REPO_PREFIX` (the part before the student's Manytask username in each repository name) |
| `.checker.yml` | `export.destination` and the optional `report_pipeline` URL |
| `.manytask.yml` | Course settings, repository URLs, and real deadlines |

The SourceCraft service connection must allow the private workflow to clone and
push the public repository. Configure `MANYTASK_TOKEN` as a SourceCraft secret
for updating the course and, if score reporting is enabled, for grading.
SourceCraft's `SOURCECRAFT_TOKEN` authenticates registry access and image pulls.
The registry path in the `grade` workflow must point to the private course's
`testenv-image:latest`.

After `verify-and-build` succeeds on the default branch, run `deploy-docker`,
`deploy-public`, and `deploy-manytask` from that branch. `deploy-public` runs
`checker export`, then installs `.sourcecraft.public/ci.yaml` as
`.sourcecraft/ci.yaml` in the public repository before committing and pushing.
Student repositories call the private shared `grade` workflow on pushes. Their
repository name supplies `STUDENT_USERNAME`; set the prefix above to match your
course's naming scheme. To report scores, uncomment the `report_pipeline` in
`.checker.yml` after setting its `report_url` and `MANYTASK_TOKEN`.

---

## Local development

You don't need GitLab to iterate on tasks. Install deps and run pytest directly:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .

# run all tests
pytest

# run a single task's public tests
pytest python/add/test_public.py
```

To verify that the public export would generate a valid student repo:

```bash
pip install manytask-checker
checker validate
checker export --dry-run
```

For the full list of commands and config options, see the
[checker configuration docs](https://manytask.org/checker_config.html) and the
[`.checker.yml` reference](https://manytask.org/checker_yml_reference.html).

---

## Adding a new task

1. Create a folder: `python/<task_name>/`
2. Add files:
   - `.task.yml` with `version: 1`
   - `<task_name>.py` — reference solution
   - `<task_name>.py.template` — what students will see (use `raise NotImplementedError` or stubs)
   - `test_public.py` — visible tests
   - `test_private.py` — hidden grading tests
   - `README.md` — task description
   - `conftest.py` — copy from `python/add/` if you use top-level imports
3. Register the task in `.manytask.yml` under `deadlines.schedule[python].tasks`.
4. Commit and push to `main`. The pipeline does the rest.

---

## License

See the upstream [manytask](https://github.com/manytask/manytask) repository.

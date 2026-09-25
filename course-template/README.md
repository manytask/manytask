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
├── testenv.docker        # image used by .gitlab-ci.yml to run tests
├── pyproject.toml        # python toolchain dependencies
├── tools/                # placeholder for shared plugins / testlib
└── python/
    └── add/              # the only task so far — sum of two integers
        ├── .task.yml
        ├── README.md
        ├── add.py            # reference solution (NOT exported)
        ├── add.py.template   # becomes add.py in the public repo
        ├── test_public.py    # visible to students
        ├── test_private.py   # hidden, used for grading
        └── conftest.py       # makes `from add import add` work in pytest
```

Only **one language** (Python) and **one task** (`add`) are included on purpose:
this is the smallest end-to-end example you can run, copy, and extend.
Additional languages (C++, Bash, Go, Rust) will be added in follow-up iterations
of [manytask#637](https://github.com/manytask/manytask/issues/637).

---

## Use this template for your own course

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
- `.releaser-ci.yml` -> `REGISTRY` variable if you build images

### 4. Set required GitLab CI/CD variables

In **Group -> Settings -> CI/CD -> Variables**:

| Variable | Where to get it | Used for |
|---|---|---|
| `GITLAB_API_TOKEN` | Group access token, role `Maintainer`, scope `write_repository` | `checker export --commit` push to public |
| `MANYTASK_TOKEN` | from your Manytask admin panel | reporting scores |
| `TESTER_TOKEN` | same as `MANYTASK_TOKEN` | grading job auth |

### 5. Register the course on manytask2.org

Ask a Manytask admin to register your course, providing:
- course slug (e.g. `your-course`)
- public repo URL
- students group URL

### 6. Push to `main` and watch the pipeline

`.releaser-ci.yml` will:
1. Run `checker validate` to sanity-check configs.
2. Run `checker export --commit` to copy public files into the public repo.
3. Run `checker manytask update` to push deadlines to the Manytask web app.

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

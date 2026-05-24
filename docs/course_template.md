# Course template (sandbox)

To make spinning up a new course painless, Manytask ships a **reference course template** — a private repository that already has a working `.checker.yml`, `.manytask.yml`, CI pipelines, a Docker test environment, and one tiny task you can solve locally.

Use it to:

- bootstrap a new course in minutes instead of writing configs from scratch,
- learn the *Course as Code* layout by reading a real working example,
- copy patterns for adding new tasks and languages.

## Where to find it

The template lives in a separate GitLab repository on the **dev** GitLab instance:

> **`gitlab.manytask2.org/sandbox/private`** *(work in progress — see [manytask#637](https://github.com/manytask/manytask/issues/637) for status)*

Once the template stabilises it will be promoted to the production instance
(`gitlab.manytask.org/sandbox`) and bound to a `sandbox` course on
<https://app.manytask.org>.

## What is inside

```
sandbox/
├── .checker.yml          # structure, export rules, testing pipeline
├── .manytask.yml         # settings + deadlines schedule
├── .gitlab-ci.yml        # CI for grading student submissions
├── .releaser-ci.yml      # CI for exporting private → public
├── testenv.docker        # image used by the grading job
├── pyproject.toml        # Python toolchain
└── python/
    └── add/              # the only task so far — sum of two integers
        ├── .task.yml
        ├── README.md
        ├── add.py            # reference solution (NOT exported)
        ├── add.py.template   # what students see (becomes add.py)
        ├── test_public.py    # visible tests
        ├── test_private.py   # hidden grading tests
        └── conftest.py       # adds the task folder to sys.path
```

This is the smallest end-to-end example that:

- passes `checker validate` and `checker check`,
- demonstrates the `.template` strategy for hiding reference solutions,
- separates public and private tests,
- reports its score back to the Manytask web app once the report pipeline is enabled in CI.

Additional languages — **C++**, **Bash**, **Go**, **Rust** — are planned as
follow-up iterations of [manytask#637](https://github.com/manytask/manytask/issues/637).

## Using the template for your own course

1. Create two empty GitLab projects — `<your-course>/private` (template clone) and `<your-course>/public` (auto-generated for students) — plus an empty `<your-course>/students` group.
2. Clone the sandbox repo and re-point `origin` at your private project:

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
    | `MANYTASK_TOKEN` | Lets the grader report scores back to the Manytask web app. |
    | `TESTER_TOKEN` | Authentication for the grading job. |

5. Ask a Manytask admin to register your course (slug, public repo URL, students group URL).
6. Push to `main` — the pipeline validates configs, exports public files, and updates deadlines on the web app.

Full step-by-step instructions live in the sandbox repository's own
[`README.md`](https://gitlab.manytask2.org/sandbox/private/-/blob/main/README.md).

## Related references

- [Course as Code](./course_as_code.md) — the underlying concept
- [Private repository](./private_repo.md) — how the private repo is structured
- [.checker.yml reference](./checker_yml_reference.md) — every field explained
- [.manytask.yml reference](./manytask_yml_reference.md) — schedule and grades schema
- [Checker pipelines and plugins](./checker_pipelines_and_plugins.md) — building custom pipelines

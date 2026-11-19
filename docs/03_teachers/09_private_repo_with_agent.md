# Prepare a private course repository with an agent

The `manytask-private-repo` skill prepares tasks, checker configuration, Docker
and CI in a local clone of an existing private repository, for example on
gitlab.com. Use [course-template](03_course_template.md) as the structure and
configuration example.

## 1. Clone the repository

```bash
git clone "<PRIVATE_REPOSITORY_URL>" course-private
cd course-private
```

Fill in `<PRIVATE_REPOSITORY_URL>` with the SSH or HTTPS URL of your existing
private repository. Use the existing clone if you already have one. Set up SSH
or a Git credential manager beforehand.

## 2. Give the agent the task

Copy `skills/manytask-private-repo` from the Manytask checkout into your agent's
skills directory (`~/.codex/skills/` for Codex). Supply the course clone path,
the `course-template/` path, the language and task requirements:

> Use $manytask-private-repo. Populate `/path/to/course-private`.
> Private repository: `<PRIVATE_REPOSITORY_URL>`.
> Example: `/path/to/manytask/course-template`. Prepare a Python course with tasks: …
> Prepare the files and manual setup checklist; do not commit or push yet.

For integration, also supply the Manytask URL, course name, student GitLab
address, public repository path and students group path. Teacher GitLab may
differ from student GitLab.

## 3. Configure CI before running it

Set `.releaser-ci.yml` as the teacher project's CI/CD configuration file.
Manually add `GITLAB_API_TOKEN`, `MANYTASK_TOKEN` and registry credentials as CI/CD
variables; do not put secret values in chat or course files. These tokens are
not required for local course preparation.

See the skill's [detailed guide](https://github.com/manytask/manytask/blob/main/skills/manytask-private-repo/references/usage.md)
for token permissions, runner and registry setup, course checks and Manytask
integration. The [agent instructions, SKILL.md](https://github.com/manytask/manytask/blob/main/skills/manytask-private-repo/SKILL.md)
are alongside it; both files are available locally under `skills/manytask-private-repo/`.

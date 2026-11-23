# Prepare a private course repository with an agent

The `manytask-private-repo` skill prepares tasks, checker configuration, Docker
and CI in a local clone of an existing private repository, for example on
gitlab.com. Use [course-template](03_course_template.md) as the structure and
configuration example.

## 1. Clone the repository

```bash
git clone "<PRIVATE_REPOSITORY_URL>" private
cd private
```

Fill in `<PRIVATE_REPOSITORY_URL>` with the SSH or HTTPS URL of your existing
private repository. Use the existing clone if you already have one. Set up SSH
or a Git credential manager beforehand.

## 2. Give the agent the task

Copy `skills/manytask-private-repo` from the Manytask checkout into your agent's
skills directory (`~/.codex/skills/` for Codex). Supply the course clone path,
the `course-template/` path, the language and task requirements:

For example, ask in plain language:

> Populate the XXX folder with the Manytask private repo with a Python hello world task.

Replace `XXX` with your local clone path. You can also invoke the skill explicitly:

> Use $manytask-private-repo. Populate `/path/to/private`.
> Private repository: `<PRIVATE_REPOSITORY_URL>`.
> Example: `/path/to/manytask/course-template`. Prepare a Python course with tasks: …
> Prepare the files and manual setup checklist; do not commit or push yet.

For integration, also supply the Manytask URL, course name, student GitLab
address, public repository path and students group path. The GitLab hosting the private repository may
differ from student GitLab.

For example, keep the private repository on `gitlab.com`, while
student repositories live on our self-hosted GitLab at `gitlab.manytask.org`.
Images can be stored in any container registry supported by Docker and the runner.
We normally use the GitLab Container Registry attached to the **public assignment
repository**. Supply the actual registry host and image namespace/path; the agent
will suggest that usual setup and let you choose another registry.

You can leave these settings out of the initial request: the agent will ask
for missing values with suggestions, including the public repository URL,
course API base URL (`<MANYTASK_BASE_URL>/api/<COURSE_NAME>`), students group,
registry and runner. It reuses answers already given and can continue local
preparation while you decide. See [the setup questions](https://github.com/manytask/manytask/blob/main/skills/manytask-private-repo/references/usage.md#questions-and-suggested-answers).

## 3. Configure CI before running it

Set `.releaser-ci.yml` as the private project's CI/CD configuration file.
In the private project, open **Settings → CI/CD → Variables → Add
variable**. Use type **Variable**, disable expansion, and select Masked/Hidden
where supported. Supply these values manually:

| Variable | How to obtain its value |
| --- | --- |
| `DOCKER_AUTH_CONFIG` | Obtain credentials from the chosen registry provider, usually deploy tokens for the public assignment project's GitLab Container Registry. Run `docker login "<REGISTRY_HOST>"` locally, then copy only that registry's `auths` entry from local `~/.docker/config.json` (or `$DOCKER_CONFIG/config.json`) into single-line JSON. See [registry credentials](https://github.com/manytask/manytask/blob/main/skills/manytask-private-repo/references/usage.md#registry-credentials-docker_auth_config) for permissions, credential helpers and the exact format |
| `GITLAB_API_TOKEN` | In the **public assignment repository's Settings → Access tokens**, create a project token with Maintainer role, `write_repository` scope and permission to push to its export branch. It needs no access to student projects. Save it in the private project's variable. See [export credentials](https://github.com/manytask/manytask/blob/main/skills/manytask-private-repo/references/usage.md#export-credentials-gitlab_api_token) for alternatives |
| `MANYTASK_TOKEN` | In Manytask, open **Edit course → Course Token** as a course administrator and reveal/copy the existing token, or ask the administrator. See [the course setup guide](02_basic_example.md#create-the-course-in-the-manytask-interface) |

Student jobs need an additional `DOCKER_AUTH_CONFIG` **only if their runner
cannot already pull the image**. On the same GitLab instance, integrated
`CI_JOB_TOKEN` access can work when the user starting the job has at least
Reporter access to the image project and that project allows the student
project/group to authenticate. Sharing a GitLab group alone does not guarantee
this. Existing inherited or runner credentials may also suffice; verify with
an actual student's pipeline. Otherwise, configure read-only credentials for
the image namespace/repository in the students group, separate from release write
credentials. See [student registry access](https://github.com/manytask/manytask/blob/main/skills/manytask-private-repo/references/usage.md#registry-credentials-docker_auth_config).

Also verify `MANYTASK_TOKEN` in the students group if score reporting is enabled.
Never give students registry write or export credentials, and do not put secret
values in chat or course files.
These tokens are not required for local course preparation.

For an external registry, edit the existing top-level **`variables:` block in
the private repository's `.releaser-ci.yml`**: set `REGISTRY`, `BASE_IMAGE` and
`TESTENV_IMAGE` to that registry's image paths. Then edit **`TESTENV_IMAGE` in
the top-level `variables:` block of `.gitlab-ci.yml`**, also in the private
repository, to the published `testenv-image:latest` URL. That file is exported
to public/student repositories. See [the image path examples](https://github.com/manytask/manytask/blob/main/skills/manytask-private-repo/references/usage.md#runner-and-registry).
These paths are non-secret configuration and can be committed; credentials go
in GitLab CI/CD variables. Leave predefined `CI_REGISTRY_*` values unchanged.

See the skill's [detailed guide](https://github.com/manytask/manytask/blob/main/skills/manytask-private-repo/references/usage.md)
for token permissions, runner and registry setup, course checks and Manytask
integration. The [agent instructions, SKILL.md](https://github.com/manytask/manytask/blob/main/skills/manytask-private-repo/SKILL.md)
are alongside it; both files are available locally under `skills/manytask-private-repo/`.

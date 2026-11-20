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

> Use $manytask-private-repo. Populate `/path/to/private`.
> Private repository: `<PRIVATE_REPOSITORY_URL>`.
> Example: `/path/to/manytask/course-template`. Prepare a Python course with tasks: …
> Prepare the files and manual setup checklist; do not commit or push yet.

For integration, also supply the Manytask URL, course name, student GitLab
address, public repository path and students group path. Teacher GitLab may
differ from student GitLab.

For example, keep the teacher's private repository on `gitlab.com`, while
student repositories live on our self-hosted GitLab at `gitlab.manytask.org`.
The image registry can also be on a different GitLab from the source repository;
supply its actual host and image project path separately.

## 3. Configure CI before running it

Set `.releaser-ci.yml` as the teacher project's CI/CD configuration file.
In the teacher private project, open **Settings → CI/CD → Variables → Add
variable**. Use type **Variable**, disable expansion, and select Masked/Hidden
where supported. Supply these values manually:

| Variable | How to obtain its value |
| --- | --- |
| `DOCKER_AUTH_CONFIG` | Obtain access to the project **hosting the images**, which may be on another GitLab. Run `docker login "<REGISTRY_HOST>"` locally, then copy only that registry's `auths` entry from local `~/.docker/config.json` (or `$DOCKER_CONFIG/config.json`) into single-line JSON. See [registry credentials](https://github.com/manytask/manytask/blob/main/skills/manytask-private-repo/references/usage.md#registry-credentials-docker_auth_config) for scopes, credential helpers and the exact format |
| `GITLAB_API_TOKEN` | In the **public assignment repository's Settings → Access tokens**, create a project token with Maintainer role, `write_repository` scope and permission to push to its export branch. It needs no access to student projects. Save it in the teacher private project's variable. See [export credentials](https://github.com/manytask/manytask/blob/main/skills/manytask-private-repo/references/usage.md#export-credentials-gitlab_api_token) for alternatives |
| `MANYTASK_TOKEN` | In Manytask, open **Edit course → Course Token** as a course administrator and reveal/copy the existing token, or ask the administrator. See [the course setup guide](02_basic_example.md#create-the-course-in-the-manytask-interface) |

Student jobs need a **separate** `DOCKER_AUTH_CONFIG` in their GitLab group,
using credentials for the image-hosting project with **`read_registry` only**. Also verify
`MANYTASK_TOKEN` there if score reporting is enabled. Variables do not inherit
between gitlab.com and gitlab.manytask.org. Never give students registry write
or export credentials, and do not put secret values in chat or course files.
These tokens are not required for local course preparation.

For an external registry, set the release pipeline's `REGISTRY`, `BASE_IMAGE`
and `TESTENV_IMAGE` to that registry's image paths, and use its published testenv
URL in student CI. The source GitLab's predefined `CI_REGISTRY_*` values describe
its own registry and do not grant access to another GitLab.

See the skill's [detailed guide](https://github.com/manytask/manytask/blob/main/skills/manytask-private-repo/references/usage.md)
for token permissions, runner and registry setup, course checks and Manytask
integration. The [agent instructions, SKILL.md](https://github.com/manytask/manytask/blob/main/skills/manytask-private-repo/SKILL.md)
are alongside it; both files are available locally under `skills/manytask-private-repo/`.

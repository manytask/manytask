# Prepare a private Manytask course repository

Assume the private GitLab project already exists, for example on gitlab.com.
This skill works in its local clone: it prepares tasks, configuration, Docker
and CI using Manytask's `course-template/` as an example. No project creation
through the API is required.

## 1. Clone the existing private repository

```bash
git clone "<PRIVATE_REPOSITORY_URL>" course-private
cd course-private
```

Replace `<PRIVATE_REPOSITORY_URL>` with the SSH or HTTPS URL of your existing
private repository. You supply this address; the skill does not assume a project
or group. Fill in the other `<...>` placeholders below with your course settings.

Set up SSH access to your GitLab host first. For HTTPS, authenticate Git through a
credential manager rather than embedding a token in the URL. If the clone
already exists, enter it and give the agent its path. An empty repository
without commits is valid; do not run `git init` again.

## 2. Point the agent to course-template

**`course-template/` in the Manytask repository is a working course example:**
checker and Manytask configuration, Dockerfiles, two separate CI pipelines,
and tasks in several languages. The agent must read the relevant files and
adapt the example. Do not copy every language or leave the `sandbox` settings
unchanged.

If you already have a Manytask checkout, provide its path. Otherwise clone it
separately:

```bash
git clone https://github.com/manytask/manytask.git manytask-reference
```

The example is in `manytask-reference/course-template/`. Use it as a reference;
do not transfer the entire Manytask history into the course repository. Inspect
the actual files: the template README may lag behind the available profiles.

## 3. Ask the agent to populate the local clone

> Use $manytask-private-repo. Populate the existing private repository clone
> at `/path/to/course-private`. Private repository: `<PRIVATE_REPOSITORY_URL>`.
> Course example:
> `/path/to/manytask/course-template`. Prepare a Python course with these tasks: …
> Manytask: `<MANYTASK_URL>`, course name: `<COURSE_NAME>`.
> Student GitLab: `<STUDENT_GITLAB_URL>`, assignment repository:
> `<PUBLIC_REPOSITORY_PATH>`, students group: `<STUDENTS_GROUP_PATH>`.
> Prepare the files and manual setup instructions; do not commit or push yet.

You can also supply existing tasks from another local directory. The agent must
preserve existing files and uncommitted changes, prepare the required
configuration and verify the course. A project-creation API token and namespace
ID are unnecessary. CI tokens are not needed for local editing either.

The result follows the `course-template` structure:

```text
course-private/
├── .git/                   # preserved from the original clone
├── .checker.yml            # testing and export
├── .manytask.yml           # course settings, tasks, deadlines and scores
├── .releaser-ci.yml        # teacher pipeline
├── .gitlab-ci.yml          # student pipeline, exported to public
├── base.docker
├── testenv.docker
├── pyproject.toml
└── python/
    ├── .group.yml
    └── task_name/
        ├── .task.yml
        ├── README.md
        ├── solution.py
        ├── solution.py.template
        ├── test_public.py
        └── test_private.py
```

File names and additional dependencies depend on the language and course content.
Use `.tasks.yml` instead of `.task.yml` for several tasks sharing one folder.
For an existing course, the template is a reference, not a reason to overwrite
working configuration.

## 4. Manually prepare CI access and settings

Before the first push, open the teacher project's Settings → CI/CD → General
pipelines → CI/CD configuration file and select **`.releaser-ci.yml`**. GitLab
reads `.gitlab-ci.yml` by default, but that file is for students in this course.
Until variables and the runner are ready, keep changes local or use `[skip ci]`
if committing and pushing have already been authorized.

| Access / variable | Where to obtain it | Where to supply it | Purpose |
| --- | --- | --- | --- |
| Git access over SSH or HTTPS | Teacher GitLab | Local SSH agent or credential manager | Clone/push to the existing private project; a separate PAT with `api` scope is not required |
| `GITLAB_API_TOKEN` | **Assignment/student GitLab** | CI/CD variable in the teacher private project | For `deploy-public`: a token with `write_repository` and permission to push to the assignment branch. Add `api` only for additional API calls |
| `MANYTASK_TOKEN` | Administrator of the registered Manytask course | CI/CD variable in private; separately on the student side if score reporting is enabled | Apply `.manytask.yml` and report scores; this is not a GitLab PAT |
| `DOCKER_AUTH_CONFIG` | Teacher project's registry | Separately in private and the destination student projects/group | Docker auth JSON. Students get a deploy token with only `read_registry`; use separate credentials for pushes |

Project/group access token availability depends on the host and subscription;
a personal GitLab token with the necessary destination repository permissions
is another option. Enter secrets manually in Settings → CI/CD → Variables or
provide them through the agent environment. Do not put values in chat, course
files, Git remotes or Dockerfiles. Mark CI variables Masked and Hidden where
available, and disable expansion. Use Protected only when the jobs run on
protected refs; otherwise variables will be absent on ordinary student pushes.
Do not expose secrets to untrusted merge request pipelines.

## 5. Connect the course to Manytask if needed

The Manytask form creates resources only on the instance's configured GitLab.
For an external private repository, register the course without selecting
"create private repository". Public and students stay on Manytask's RMS. Add a
link to the external private repository in the course links. Moving **all**
repositories to gitlab.com requires separate instance RMS/OAuth configuration,
not a change to the private repository path.

Before the first pipeline, adapt these files in the course clone:

- `.manytask.yml`: `settings.course_name`, `gitlab_base_url`, `public_repo`,
  `students_group`; task URLs point to student GitLab, while the source link
  points to teacher GitLab.
- `.checker.yml`: `export.destination` points to the assignment repository on
  the RMS. Check the testing language and report pipeline; score reporting is
  commented out in the template. If enabling it, set the Manytask `report_url`
  and supply `report_token` through the environment.
- `.releaser-ci.yml`: course name, Manytask address and `PUBLIC_REPO_URL`.
  Prefer a credential-free URL with a temporary `GIT_ASKPASS` reading the token
  from the environment and tracing disabled. The current template embeds a
  token in the URL: do not print it or preserve that remote in artifacts;
  adapt it before running CI. The template's `deploy-manytask` job adds
  `https://` itself; local HTTP requires changing the job, not simply supplying
  a URL with a scheme.
- `.gitlab-ci.yml`: the full `TESTENV_IMAGE` URL:
  `<REGISTRY_HOST>/<PRIVATE_PROJECT_PATH>/testenv-image:latest`, with your
  teacher registry host and private project path filled in.
  In a student project, `$CI_REGISTRY_IMAGE` points to that project's own registry.

`checker validate` checks course structure; `checker check . .` tests reference
solutions. Run in the course environment with the required compilers and score
reporting disabled. Read the installed version's `--help` for `checker export`
and `checker export-private`. Use a disposable export directory: export clears
the destination except `.git`. Verify that student stubs replace solutions and
hidden tests stay out of assignments. Never widen `public_patterns` to `"*"`:
public rules override private rules.

### Runner and registry

The current template uses `/var/run/docker.sock` and explicitly sets
`DOCKER_HOST=unix:///var/run/docker.sock`. It needs a runner with that socket
mounted; gitlab.com shared runners do not guarantee this setup. Choose a suitable
self-managed runner and tags, or adapt `.docker` for Docker-in-Docker, including
the service, TLS and DOCKER_HOST. Do not mix the two modes.

On gitlab.com, use the actual `CI_REGISTRY`, usually `registry.gitlab.com`, rather
than `gitlab.com:5050`. For pushes inside the private pipeline,
`CI_REGISTRY_USER` / `CI_REGISTRY_PASSWORD` are available for the job's lifetime.
If retaining the current `DOCKER_AUTH_CONFIG` step, configure it explicitly or
replace authentication with `docker login --password-stdin`. Do not put registry
write credentials in the students group.

To let students pull the image, supply a separate `DOCKER_AUTH_CONFIG` in their
GitLab projects/group:

```json
{"auths":{"registry.gitlab.com":{"auth":"BASE64_OF_READ_ONLY_DEPLOY_USERNAME_COLON_TOKEN"}}}
```

`auth` is the base64 encoding of `username:token`: it is a **secret**, not
encryption. Generate it locally and enter it directly into the Variables UI
without printing it in chat. Create the token with only `read_registry` on the
teacher project. A student GitLab's `CI_JOB_TOKEN` does not authorize access to
another GitLab instance.

The testenv image contains hidden tests in `/opt/course`. A user who can pull the
image or control their CI can read those files. This matches the current template
but does not isolate hidden tests from students. Strict secrecy requires a
separate trusted grading system. A shared `MANYTASK_TOKEN` in student-controlled
CI can also be extracted; masked logs are not a trust boundary.

### Local Manytask and cloud CI

`localhost:8081` in a gitlab.com job refers to the runner, not your computer.
The same applies to local GitLab and registry addresses. A hybrid setup needs a
runner that can reach both GitLab instances, the registry and Manytask. Use
routable addresses; inside Docker, `localhost` usually does not refer to the host.
A cloud runner needs an address it can reach, such as an approved HTTPS endpoint.
The skill does not expose local services to the internet automatically.

## Enable and verify CI

After configuring variables and the runner, enable CI/CD under Settings →
General → Visibility, project features, permissions. Verify `.releaser-ci.yml`
under Settings → CI/CD → General pipelines. Start with the verification stages:
`verify → build-base → check → build-testenv`. The template's deployment jobs
are manual.

When deployment is separately authorized, run `deploy-docker`, `deploy-public`
and `deploy-manytask`; verify registry digests, assignment contents, the
`update_config` response and course page, then a student submission and score.
Public names the destination, not a requirement to make its visibility public.
Do not change assignment project visibility without authorization.

After the first push, compare the remote branch SHA through API/Git, default
branch, private visibility, CI configuration and executable bits. State explicitly
if a pipeline was not run or failed. A prepared repository is not a deployed course.

## API and further documentation

- [GitLab: project CI/CD variables](https://docs.gitlab.com/api/project_level_variables/)
- [GitLab: registry authentication](https://docs.gitlab.com/user/packages/container_registry/authenticate_with_container_registry/)
- [GitLab: Docker-in-Docker](https://docs.gitlab.com/ci/docker/using_docker_build/)

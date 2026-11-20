# Prepare a private Manytask course repository

Assume the private GitLab project already exists, for example on gitlab.com.
This skill works in its local clone: it prepares tasks, configuration, Docker
and CI using Manytask's `course-template/` as an example. No project creation
through the API is required.

## 1. Clone the existing private repository

```bash
git clone "<PRIVATE_REPOSITORY_URL>" private
cd private
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
> at `/path/to/private`. Private repository: `<PRIVATE_REPOSITORY_URL>`.
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
private/
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
| `DOCKER_AUTH_CONFIG` | GitLab/project hosting the images, which may differ from the teacher source repository | Separately in private and the destination student projects/group | Docker auth JSON. Students get a deploy token with only `read_registry`; use separate credentials for pushes |

Project/group access token availability depends on the host and subscription;
a personal GitLab token with the necessary destination repository permissions
is another option. Enter secrets manually in Settings → CI/CD → Variables or
provide them through the agent environment. Do not put values in chat, course
files, Git remotes or Dockerfiles. Mark CI variables Masked and Hidden where
available, and disable expansion. Use Protected only when the jobs run on
protected refs; otherwise variables will be absent on ordinary student pushes.
Do not expose secrets to untrusted merge request pipelines.

### Add the variables in GitLab

In the **teacher private project**, open Settings → CI/CD → Variables → Add
variable. Use the exact key from the table, type **Variable** (not File), and
environment scope `*` unless you deliberately restrict the jobs. Paste the value,
disable variable expansion, select Masked and Hidden where supported, and save.
Use single-line JSON without whitespace for masked `DOCKER_AUTH_CONFIG` values.
The current pipeline reads the JSON value itself, not a path to a file.

Repeat the relevant setup in the **students group** on student GitLab; variables
from the teacher's gitlab.com project do not propagate to gitlab.manytask.org.
Use a separate registry credential there with read access only. Keep export and
registry write tokens in the teacher private project.

### Registry credentials: DOCKER_AUTH_CONFIG

The registry is an independent endpoint. The teacher repository can be on
`gitlab.com` while images are stored on another GitLab, for example a registry
on our self-hosted `gitlab.manytask.org`. Obtain the exact registry `host[:port]`
and image project path from the image-hosting project's Deploy → Container
Registry page or its administrator. Do not assume `registry.gitlab.com` or use
the teacher source project's `CI_REGISTRY` when the images live elsewhere.
The registry host has no `https://` prefix or project path.

**Log in to the remote registry, then use the local Docker config:**

1. Obtain credentials with access to the project **hosting the images**. You
   can use an existing authorized registry login. For dedicated CI credentials,
   create deploy tokens under that project's Settings → Repository → Deploy
   tokens **on the registry's GitLab instance**, or ask its administrator for
   them. Use `read_registry` + `write_registry` for release jobs and separate
   `read_registry`-only credentials for student jobs. Save the generated username
   and token when shown; the username need not match your account login.
2. From your own terminal, log in to that remote registry:

   ```bash
   docker login "<REGISTRY_HOST>"
   ```

   Enter the registry username and token/password at the prompts, without
   putting the secret in the command. With 2FA, use an appropriate access token.
   `docker login` contacts the remote registry but stores credentials on the
   **machine running the Docker client**. If you run it over SSH on another
   machine, the config is on that machine, not automatically on your laptop.
3. Open the resulting config yourself: normally `~/.docker/config.json`, or
   `$DOCKER_CONFIG/config.json` if `DOCKER_CONFIG` was set. Copy **only the entry
   for the intended registry** under `auths`, preserving its exact `host[:port]`.
   Do not copy credentials for unrelated registries or ask the agent to read
   or print the file.
4. In the teacher private project's Settings → CI/CD → Variables, save
   `DOCKER_AUTH_CONFIG` as type **Variable**, not File. Use a single-line value
   with no whitespace for masking:

   ```json
   {"auths":{"<REGISTRY_HOST>":{"auth":"<BASE64_USERNAME_COLON_TOKEN>"}}}
   ```

   The `auth` value is the one from the local config: base64 of `username:token`,
   not the raw password alone. Keep the release read/write version in the teacher
   private project's variables. Repeat with separate read-only credentials for
   the `DOCKER_AUTH_CONFIG` variable in the students group on student GitLab.
   The credentials come from the registry's GitLab even though the variable
   is saved on the GitLab running the pipeline. Base64 is not encryption;
   do not commit this JSON or paste it into chat.

**If Docker uses a credential helper:** a config containing `credsStore` or
`credHelpers` may have no inline `auth` value. Copying that config to CI will not
copy credentials from your local keychain. Generate standalone auth JSON from
the registry username and token instead. This manual command writes a private
temporary file (mode `0600`) and prints only its path:

```bash
python3 -c '
import base64, getpass, json, os, tempfile
registry = input("Registry host (host[:port]): ").strip()
username = input("Registry username: ")
token = getpass.getpass("Registry token/password: ")
auth = base64.b64encode((username + ":" + token).encode()).decode()
fd, path = tempfile.mkstemp(prefix="registry-auth-", suffix=".json")
with os.fdopen(fd, "w") as output:
    json.dump({"auths": {registry: {"auth": auth}}}, output, separators=(",", ":"))
print("Copy this file into DOCKER_AUTH_CONFIG, then delete it:", path)
'
```

Open that file yourself, copy its contents into the variable, and delete it
afterwards. Do not have the agent read it. An isolated `DOCKER_CONFIG` directory
can keep a new login separate from your normal config, but it does not guarantee
inline `auth`: Docker may still select an installed credential helper.

The current release jobs write `DOCKER_AUTH_CONFIG` into Docker's config file
before pushing images. The student runner also needs registry authentication to
pull the testenv image **before** the job starts. A login command in the student's
job script is too late for that image pull.

GitLab's predefined `CI_REGISTRY_USER` and `CI_REGISTRY_PASSWORD` apply to its own
job registry. They do **not** authorize a registry on another GitLab instance.
Use the external registry credentials described above for that case. Only when
using the job's own registry can you replace the release auth step with
`docker login --password-stdin` using those predefined credentials.

See [GitLab deploy tokens](https://docs.gitlab.com/user/project/deploy_tokens/),
[Docker login and credential stores](https://docs.docker.com/reference/cli/docker/login/),
and [runner registry authentication](https://docs.gitlab.com/ci/docker/using_docker_images/#access-an-image-from-a-private-container-registry).

### Export credentials: GITLAB_API_TOKEN

Create this token on the **destination assignment/student GitLab**, for example
`gitlab.manytask.org`, even when the teacher private project is on gitlab.com.
Open the assignment project's Settings → Access tokens, or the owning group's
Settings → Access tokens. Create a token with a name, expiry date, **Maintainer**
role and **`write_repository`** scope. It must be allowed to push to the assignment
repository's default branch, including any protected-branch restrictions.
Copy the token value when shown and add it as `GITLAB_API_TOKEN` in the teacher
private project's CI/CD variables. It is not a registry deploy token.

If project/group tokens are unavailable on your subscription, create a personal
access token under your account's access-token settings with `write_repository`;
the user must have the required access to the assignment repository. Add `api`
only if your customized pipeline also calls the GitLab API. Keep this token out
of student projects. See [project access tokens](https://docs.gitlab.com/user/project/settings/project_access_tokens/)
and [personal access tokens](https://docs.gitlab.com/user/profile/personal_access_tokens/).

### Course credentials: MANYTASK_TOKEN

Sign in to Manytask as a course administrator, open **Edit course**, and copy
the **Course Token** value (use the visibility toggle to reveal it). The token
is also shown when creating a course. If you cannot access these controls, ask
the course or instance administrator to provide it securely. Use the existing
course token, not a newly generated GitLab token or the student registration
secret.

Add it as `MANYTASK_TOKEN` in the teacher private project's CI/CD variables for
`deploy-manytask`. Score reporting also needs `MANYTASK_TOKEN` in the students
group. Manytask normally adds it to the public repository and students group
when creating the course on its configured GitLab; verify that setup and copy
it manually to the external teacher project. Masking does not prevent students
who control their CI from extracting a token made available to those jobs.

See the [Manytask basic example](https://github.com/manytask/manytask/blob/main/docs/03_teachers/02_basic_example.md#create-the-course-in-the-manytask-interface)
for the course creation and token fields.

### Other pipeline values

These are configuration values, not secrets:

| Value | Where it comes from |
| --- | --- |
| `MANYTASK_URL` | The address of your Manytask instance. The current template prepends `https://`, so set its hostname (and any required path), without the scheme |
| `COURSE_NAME` | The unique course name/slug used when registering the course in Manytask; it appears in the course URL |
| `MANYTASK_API` | Derived by the template from `MANYTASK_URL` and `COURSE_NAME`; normally no manual variable is needed |
| `REGISTRY`, `BASE_IMAGE`, branch `TESTENV_IMAGE` | The template defaults to the source project's `CI_REGISTRY_IMAGE`. For an external registry, override all three with the actual image project paths as shown below |
| Student `TESTENV_IMAGE` | Copy the full image path from the image-hosting project's Container Registry and select the published `testenv-image:latest` tag. Set it in the exported `.gitlab-ci.yml` or a students-group CI variable, because student `CI_REGISTRY_IMAGE` points elsewhere |

## 5. Connect the course to Manytask if needed

Teacher and student repositories can use different GitLab instances. For example,
keep the teacher's private repository on `gitlab.com`, while assignment and
student repositories live on our self-hosted GitLab at `gitlab.manytask.org`.

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
  `<REGISTRY_HOST>/<REGISTRY_PROJECT_PATH>/testenv-image:latest`, with the
  actual registry host and image-hosting project path filled in. That path need
  not match the teacher source repository.
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

When images live on another GitLab, the template's defaults still point to the
source GitLab registry. Override **all three** release image variables, not just
`REGISTRY`:

```yaml
variables:
  REGISTRY: "<REGISTRY_HOST>/<REGISTRY_PROJECT_PATH>"
  BASE_IMAGE: "$REGISTRY/ci-base:$CI_COMMIT_REF_SLUG"
  TESTENV_IMAGE: "$REGISTRY/testenv-image:$CI_COMMIT_REF_SLUG"
```

Use `<REGISTRY_HOST>/<REGISTRY_PROJECT_PATH>/testenv-image:latest` for the student
pipeline after `deploy-docker` publishes that tag. The registry path is the
image-hosting project, not necessarily the source repository. Release jobs need
push access and student runners need pull access to this exact registry. Follow
[the registry credential setup](#registry-credentials-docker_auth_config) above
for `DOCKER_AUTH_CONFIG`. A student GitLab's `CI_JOB_TOKEN` does not authorize
access to another GitLab instance.

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

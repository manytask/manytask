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

You can use the usual Manytask terminology without naming the skill:

> Populate the XXX folder with the Manytask private repo with a Python hello world task.

Replace `XXX` with the path to your local clone. "Private repo" means the course
repository with its reference solutions, hidden tests and configuration. For
an explicit invocation with integration settings:

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

### Questions and suggested answers

You do not have to supply every integration setting in the initial request.
The agent should ask about missing settings, offer suggestions, and reuse
anything you have already specified. For example:

| Question | Suggested answers |
| --- | --- |
| Where is the public assignment repository? | `https://gitlab.manytask.org/<COURSE_GROUP>/public` after filling in your group; a repository on another GitLab; decide later |
| What is the course name and API base URL? | `https://app.manytask.org/api/<COURSE_NAME>` after confirming the course slug; your own Manytask deployment; decide later |
| Where should student repositories be created? | The sibling `<COURSE_GROUP>/students` group on the public repository's GitLab; a different group |
| Where are the course images stored? | An existing confirmed image path; otherwise the GitLab Container Registry attached to the public assignment repository (our usual setup); another Docker-compatible registry; decide later. Confirm the registry host and image namespace/path |
| Which runner and registry access are available? | An existing Docker-socket runner; a Docker-in-Docker runner; not configured yet. Use existing student pull access if available |
| How far should setup go? | Prepare local files and tasks only; also configure integration. Confirm any missing task behavior, grading or deadline requirements using proposed defaults |

The agent asks a small batch of related questions at a time. It should show a
concrete candidate where your existing configuration provides one, allow custom
answers, and never treat a suggested value as your decision. No secret values
belong in these answers. Local preparation can proceed while an integration
setting is pending; configuration that depends on it must wait.

The **course API base URL** includes the course slug:
`<MANYTASK_BASE_URL>/api/<COURSE_NAME>`. Configuration is sent to
`<COURSE_API_BASE_URL>/update_config`; scores go to
`<COURSE_API_BASE_URL>/report`. If you provide a complete endpoint instead, the
agent should distinguish it from the base rather than append these paths twice.
These values map to the release pipeline's `MANYTASK_URL`, `COURSE_NAME` and
derived `MANYTASK_API`, and the checker's full `report_url`. The current template
prepends `https://` itself in the release job, so it must not be duplicated.

The result follows the `course-template` structure:

```text
private/
├── .git/                   # preserved from the original clone
├── .checker.yml            # testing and export
├── .manytask.yml           # course settings, tasks, deadlines and scores
├── .releaser-ci.yml        # private release pipeline
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

Before the first push, open the private project's Settings → CI/CD → General
pipelines → CI/CD configuration file and select **`.releaser-ci.yml`**. GitLab
reads `.gitlab-ci.yml` by default, but that file is for students in this course.
Until variables and the runner are ready, keep changes local or use `[skip ci]`
if committing and pushing have already been authorized.

| Access / variable | Where to obtain it | Where to supply it | Purpose |
| --- | --- | --- | --- |
| Git access over SSH or HTTPS | GitLab hosting the private repository | Local SSH agent or credential manager | Clone/push to the existing private project; a separate PAT with `api` scope is not required |
| `GITLAB_API_TOKEN` | **Public assignment repository** on its GitLab instance | CI/CD variable in the private project | For `deploy-public`: a token with `write_repository` and permission to push to the public repository's export branch. No access to student projects is required. Add `api` only for additional API calls |
| `MANYTASK_TOKEN` | Administrator of the registered Manytask course | CI/CD variable in private; separately on the student side if score reporting is enabled | Apply `.manytask.yml` and report scores; this is not a GitLab PAT |
| `DOCKER_AUTH_CONFIG` | Chosen registry provider, usually the public assignment project's GitLab Container Registry | Private release pipeline with the current template; student projects/group only if existing pull access is insufficient | Docker auth JSON. When students need additional credentials, use pull-only access (`read_registry` for GitLab), separate from release push credentials |

Project access token availability depends on the host and subscription;
a personal token for a dedicated account restricted to the public repository
is another option. Enter secrets manually in Settings → CI/CD → Variables or
provide them through the agent environment. Do not put values in chat, course
files, Git remotes or Dockerfiles. Mark CI variables Masked and Hidden where
available, and disable expansion. Use Protected only when the jobs run on
protected refs; otherwise variables will be absent on ordinary student pushes.
Do not expose secrets to untrusted merge request pipelines.

### Add the variables in GitLab

In the **private project**, open Settings → CI/CD → Variables → Add
variable. Use the exact key from the table, type **Variable** (not File), and
environment scope `*` unless you deliberately restrict the jobs. Paste the value,
disable variable expansion, select Masked and Hidden where supported, and save.
Use single-line JSON without whitespace for masked `DOCKER_AUTH_CONFIG` values.
The current pipeline reads the JSON value itself, not a path to a file.

Repeat only the necessary setup in the **students group** on student GitLab.
Check existing student image-pull access before adding a
registry variable. If additional credentials are required, use read-only access.
Keep export and registry write tokens in the private project.

### Registry credentials: DOCKER_AUTH_CONFIG

The registry is an independent endpoint and can be **any container registry
supported by Docker and the runner**, not only GitLab. We normally store images
in the **GitLab Container Registry attached to the public assignment repository**.
For example, the private source can be on `gitlab.com`, with public/student
repositories and the public project's registry on our self-hosted
`gitlab.manytask.org`.

For that usual setup, obtain the exact registry `host[:port]` and public project
path from the public repository's Deploy → Container Registry page. For another
provider, obtain its registry endpoint and image namespace/repository path from
that provider's console or administrator. Confirm the user's choice; do not
assume `registry.gitlab.com` or use the private source project's `CI_REGISTRY`
when images live elsewhere. The registry host has no `https://` prefix or path.

**Check student image-pull access first.** A student `DOCKER_AUTH_CONFIG` variable
is conditional, not a universal requirement:

- On the **same GitLab instance**, GitLab can supply integrated registry
  credentials based on `CI_JOB_TOKEN`. The user starting the job must have at
  least **Reporter** access to the image-hosting project, and that project must
  allow the student project or group in its job-token allowlist (Settings →
  CI/CD → Job token permissions). Sharing a group can provide inherited user
  membership, but does not by itself establish job-token access.
- Existing inherited CI variables, runner-level registry credentials, or public
  access may already permit the pull. Do not add a duplicate variable when the
  runner already has suitable access.
- A job token from another GitLab instance does not authenticate to the registry.
  If the registry is private and the runner has no existing access, add a
  read-only `DOCKER_AUTH_CONFIG` to student CI as described below.

Verify with a job that uses the published testenv image and is triggered by an
actual student account. An administrator's successful pipeline does not prove
student access. Authentication must work before the job image is pulled, so a
`docker login` in that job's script cannot fix the initial image pull. See
[GitLab registry access](https://docs.gitlab.com/ci/docker/using_docker_images/#access-an-image-from-a-private-container-registry)
and [job-token access controls](https://docs.gitlab.com/ci/jobs/ci_job_token/#control-job-token-access-to-your-project).

**Log in to the remote registry, then use the local Docker config:**

1. Obtain credentials with access to the chosen image namespace/repository. You
   can use an existing authorized registry login. For our usual **GitLab** setup,
   create deploy tokens in the **public assignment project's** Settings →
   Repository → Deploy tokens, or ask its administrator. Use `read_registry` +
   `write_registry` for release jobs; if student jobs need extra credentials,
   create a separate `read_registry`-only token. For **other registries**, use
   the provider's service account or token with equivalent pull/push permissions
   for releases and pull-only permissions for students. GitLab deploy-token
   scopes are not universal registry scope names.
   Save the generated username and token when shown; the username need not
   match your account login.
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
4. In the private project's Settings → CI/CD → Variables, save
   `DOCKER_AUTH_CONFIG` as type **Variable**, not File. Use a single-line value
   with no whitespace for masking:

   ```json
   {"auths":{"<REGISTRY_HOST>":{"auth":"<BASE64_USERNAME_COLON_TOKEN>"}}}
   ```

   The `auth` value is the one from the local config: base64 of `username:token`,
   not the raw password alone. Keep the release read/write version in the
   private project's variables. Only if student pull access is insufficient,
   repeat with separate read-only credentials for the `DOCKER_AUTH_CONFIG`
   variable in the students group on student GitLab.
   The credentials come from the registry provider even though the variable
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
before pushing images; keep it configured for that template unless adapting its
authentication step. This release requirement does not imply that students need
another variable: their runner may already have integrated or configured pull
access.

GitLab's predefined `CI_REGISTRY_USER` and `CI_REGISTRY_PASSWORD` apply to its own
job registry. Do not assume they authorize another GitLab or an external provider.
Use the external registry credentials described above for that case. Only when
using the job's own registry can you replace the release auth step with
`docker login --password-stdin` using those predefined credentials.

For provider-specific login flows, follow the provider's Docker authentication
instructions. Short-lived credentials may require refresh or runner integration
before the job image is pulled; a copied static JSON value may expire.

See [GitLab deploy tokens](https://docs.gitlab.com/user/project/deploy_tokens/),
[Docker login and credential stores](https://docs.docker.com/reference/cli/docker/login/),
and [runner registry authentication](https://docs.gitlab.com/ci/docker/using_docker_images/#access-an-image-from-a-private-container-registry).

### Export credentials: GITLAB_API_TOKEN

This token is for pushing exported tasks to the **public assignment repository**,
not accessing student projects or the students group. Create it on the GitLab
hosting that public repository, for example `gitlab.manytask.org`, even when
the private project is on gitlab.com.

Open the **public repository's Settings → Access tokens**. Create a project
access token with a name, expiry date, **Maintainer** role and
**`write_repository`** scope. It must be allowed to push to the public
repository's export branch, including any protected-branch restrictions.
Copy the token value when shown and add it as `GITLAB_API_TOKEN` in the
private project's CI/CD variables. It is not a registry deploy token.

If project tokens are unavailable on your subscription, use a dedicated account
with write access only to the public repository and create a personal access
token with `write_repository` under that account. Personal tokens inherit the
account's access; this scope alone does not restrict a broadly privileged account
to one project. A group token covering student projects grants unnecessary access
for this export job. Add `api` only if your customized pipeline also calls the
GitLab API. Keep this token out of student projects.
See [project access tokens](https://docs.gitlab.com/user/project/settings/project_access_tokens/)
and [personal access tokens](https://docs.gitlab.com/user/profile/personal_access_tokens/).

### Course credentials: MANYTASK_TOKEN

Sign in to Manytask as a course administrator, open **Edit course**, and copy
the **Course Token** value (use the visibility toggle to reveal it). The token
is also shown when creating a course. If you cannot access these controls, ask
the course or instance administrator to provide it securely. Use the existing
course token, not a newly generated GitLab token or the student registration
secret.

Add it as `MANYTASK_TOKEN` in the private project's CI/CD variables for
`deploy-manytask`. Score reporting also needs `MANYTASK_TOKEN` in the students
group. Manytask normally adds it to the public repository and students group
when creating the course on its configured GitLab; verify that setup and copy
it manually to the external private project. Masking does not prevent students
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
| `REGISTRY`, `BASE_IMAGE`, branch `TESTENV_IMAGE` | The template defaults to the source project's `CI_REGISTRY_IMAGE`. For an external registry, override all three with the actual image namespace paths as shown below |
| Student `TESTENV_IMAGE` | Copy the full image path from the chosen registry and select the published `testenv-image:latest` tag. Set it in the exported `.gitlab-ci.yml` or a students-group CI variable, because student `CI_REGISTRY_IMAGE` points elsewhere |

## 5. Connect the course to Manytask if needed

Private and student repositories can use different GitLab instances. For example,
keep the private repository on `gitlab.com`, while assignment and
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
  points to the GitLab hosting the private repository.
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
  `<REGISTRY_HOST>/<IMAGE_NAMESPACE>/testenv-image:latest`, with the
  actual registry host and image namespace/path filled in. That path need
  not match the private source repository.
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

When images live outside the source project's default registry, the template still points to the
source GitLab registry. In your **private repository's `.releaser-ci.yml`**,
edit the existing **top-level `variables:` block**, alongside `COURSE_NAME` and
`MANYTASK_URL`. Set **all three** release image variables, not just `REGISTRY`:

```yaml
variables:
  REGISTRY: "<REGISTRY_HOST>/<IMAGE_NAMESPACE>"
  BASE_IMAGE: "$REGISTRY/ci-base:$CI_COMMIT_REF_SLUG"
  TESTENV_IMAGE: "$REGISTRY/testenv-image:$CI_COMMIT_REF_SLUG"
```

Merge these entries into the existing block; keep its other variables and do
not add a second top-level `variables:` key.

Next, in **`.gitlab-ci.yml` in the same private repository**, update
`TESTENV_IMAGE` in its existing top-level `variables:` block:

```yaml
variables:
  TESTENV_IMAGE: "<REGISTRY_HOST>/<IMAGE_NAMESPACE>/testenv-image:latest"
```

Keep other student CI settings such as `GIT_DEPTH`. The checker exports this
`.gitlab-ci.yml` to the public repository for use by student projects, so set
the path in the private source before exporting rather than editing each
student fork. The `:latest` image is available after `deploy-docker` publishes
that tag. These YAML values are non-secret configuration and can be committed;
store credentials such as `DOCKER_AUTH_CONFIG` in GitLab's CI/CD variables UI.
Do not change GitLab's predefined `CI_REGISTRY_*` variables.

The image namespace/path belongs to the chosen registry; in our usual GitLab
setup it is the public assignment project path, not the private source path.
Release jobs need
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

---
name: manytask-private-repo
description: Populate a Manytask private repository (private repo) in a local folder using course-template as a reference. Use for requests such as "populate the XXX folder with the Manytask private repo with a Python hello world task"; prepare tasks, checker configuration, Docker and CI, including manual credential setup.
---

# Populate a Manytask private repository

Work in an existing local clone of the private repository. The GitLab project
already exists; creating projects, namespaces or API tokens for project creation
is outside this workflow. The user guide starts with cloning:
[usage and credential setup](references/usage.md).

## Recognize the request

"Private repository" or "private repo" is the standard Manytask name for the
course repository containing configuration, reference solutions and hidden tests.
A request such as "populate the XXX folder with the Manytask private repo with
a Python hello world task" belongs to this skill, without requiring the user
to say "teacher repository" or name the skill explicitly.

Given a local clone path, language and task requirements, prepare the local
course content using `course-template`. Missing integration URLs or credentials
can remain pending while local preparation proceeds.

## Inputs

Obtain the private repository URL supplied by the user, the local clone path,
course content or chosen language, and the path to a Manytask checkout containing
`course-template/`. Never infer the target repository from the template or a
previous example; the user fills in `<PRIVATE_REPOSITORY_URL>` in the guide.
Full integration also needs
the Manytask URL, course name, assignment/student GitLab, public repository,
students group, and the container registry host and image namespace/path.
Missing service addresses need not block task preparation;
record them as unresolved parameters and do not call an incomplete configuration
ready to run.

## Ask for missing settings with suggestions

Before configuring integration, **ask the user about missing or conflicting
settings**. Do not merely leave placeholders without asking. Reuse information
already supplied in the conversation or existing course files; do not ask again
for known values. Treat values copied from `course-template` as examples, not
confirmed settings for this course.

Use the available question/input tool with suggested options and custom input;
otherwise ask a concise numbered set in chat. Ask up to three related questions
per round. Give concrete proposed values from the known context and an option
to decide later. Suggestions are not answers: do not select them silently.

Cover these settings when they are unresolved:

| Ask about | Suggested answers to offer |
| --- | --- |
| Public assignment repository URL | A public-repo URL already present in course configuration; `https://gitlab.manytask.org/<COURSE_GROUP>/public` with the user's group filled in when known; a custom URL; decide later. Ask for the repository URL, not access to student projects |
| Course identity and API base URL | The known deployment plus confirmed course slug, such as `https://app.manytask.org/api/<COURSE_NAME>`; an existing custom Manytask deployment; decide later. Ask for the course slug if unknown; do not derive it from the generic folder name `private` |
| Students group and default branch | A sibling `<COURSE_GROUP>/students` on the public repository's GitLab; a custom group. Suggest the existing configured branch or `main` for an empty repository |
| Registry host and image namespace/path | Reuse an existing confirmed image path. Otherwise suggest the GitLab Container Registry attached to the public assignment repository (the usual setup), with its project path as the image namespace; any other Docker-compatible registry; decide later. Confirm the actual host and path rather than assuming them from the private repository |
| Runner and image-pull access | An existing runner with a Docker socket; a Docker-in-Docker runner; not configured yet. Ask whether student jobs already have registry pull access before proposing another credential |
| Scope and course-specific requirements | Local preparation only; also configure integration. For unspecified task behavior, scores or deadlines that matter, offer explicit defaults rather than inventing requirements |

Record the chosen URLs and paths, their corresponding configuration fields,
and anything the user deferred. A **course API base URL** is
`<MANYTASK_BASE_URL>/api/<COURSE_NAME>`; derive `/update_config` and `/report`
from it. Distinguish that base from the site URL and a complete endpoint, and
avoid duplicating the scheme or `/api/<COURSE_NAME>` in the current template's
`MANYTASK_URL`/`MANYTASK_API` settings. See the
[questionnaire examples](references/usage.md#questions-and-suggested-answers).

Ask early while continuing independent local task preparation. Await an answer
before applying dependent integration settings. If the user defers a setting,
keep it visibly unresolved and report the limited readiness. Ask how credentials
will be supplied, never for secret values in the questionnaire.

Distinguish the GitLab hosting the private repository (for example gitlab.com), the assignment/student
GitLab (RMS), the container registry, and Manytask. Any Docker-compatible registry
can be used; normally suggest the GitLab Container Registry attached to the
public assignment repository. Never infer its host or credentials from the source
repository. Do not switch the entire
Manytask instance's RMS to accommodate a private repository on another host.

## Populate the local clone

1. Read applicable AGENTS.md files. Check `git status`, the current branch and
   remotes without exposing credentials. An empty clone may have no HEAD yet;
   this is normal. Preserve `.git`, origin, existing files and the user's changes.
   Do not reinitialize the clone, replace origin or force-push.
2. **Read the actual `course-template/` example in Manytask:** `.checker.yml`,
   `.manytask.yml`, `.gitlab-ci.yml`, `.releaser-ci.yml`, `base.docker`,
   `testenv.docker`, `pyproject.toml`, and a sample task in the selected language.
   The README provides context; actual files establish current settings. If the
   path is unknown, locate the template in the current Manytask checkout or ask
   where it is available.
3. For a new course, copy the required shared files and selected language profiles
   from the example, then adapt them. Do not copy another repository's `.git`,
   `deploy.sh`, local settings, caches or unnecessary language profiles. For an
   existing course, use the template as a reference rather than replacing working
   files wholesale.
4. Prepare task statements, reference solutions, student `.template` stubs, and
   public/private tests; register tasks in the `.manytask.yml` schedule. Use
   `.task.yml` for one task or `.tasks.yml` for several tasks sharing a folder,
   never both. Align the language/compiler, test pipeline, dependencies, deadlines
   and scores.
5. Adapt `.checker.yml` (export, tests and score reporting), `.manytask.yml`
   (RMS, paths, schedule and UI), both CI configurations and Dockerfiles. Link
   to the external private repository while pointing task URLs to student GitLab.

The example is a reference, not a requirement to copy every limitation. In
particular, do not apply course-specific Lean fixes from another session to
unrelated courses. Never use `public_patterns: ["*"]`: public rules override
private rules and would expose hidden tests.

## Prepare manual CI settings

Read the guide's [variable setup](references/usage.md#add-the-variables-in-gitlab)
before preparing the user's CI handoff. Explain both where each value comes from
and where to save it; listing variable names alone is insufficient:

- **`DOCKER_AUTH_CONFIG`**: follow the [registry credential procedure](references/usage.md#registry-credentials-docker_auth_config).
  Obtain credentials from the chosen registry provider, usually the public
  assignment project's GitLab Container Registry. The user runs `docker login` against
  that remote registry and retrieves the matching `auths` entry from the Docker
  client's local `config.json`. See the guide for config paths and credential
  helper handling. Save single-line JSON as type **Variable**, not File. Release
  jobs need pull/push access to the chosen image namespace. Before adding a student
  variable, check whether its runner can already pull through GitLab-integrated
  `CI_JOB_TOKEN` access, inherited/runner credentials, or public registry access.
  For same-instance job-token access, the triggering user needs at least Reporter
  access to the image project, which must allow the student project/group;
  being in the same group alone is insufficient. Only if existing pull access
  is unavailable, supply separate pull-only credentials to student CI
  (`read_registry` for GitLab; the provider's equivalent elsewhere).
  The `auths` key must match the actual registry's exact `host[:port]`. Do not
  copy unrelated registry credentials into CI.
- **`GITLAB_API_TOKEN`**: follow the [export credential procedure](references/usage.md#export-credentials-gitlab_api_token).
  Create a project access token for the **public assignment repository** with
  `write_repository`, Maintainer access and permission to push to its export
  branch, then save it in the private project's variables. It needs no
  access to student projects or the students group. If a personal token is
  necessary, use a dedicated account restricted to the public repository;
  personal tokens inherit the account's repository access. Do not give the
  export token to students.
- **`MANYTASK_TOKEN`**: follow the [course credential procedure](references/usage.md#course-credentials-manytask_token).
  Use the existing **Edit course → Course Token** value from Manytask, obtained
  by a course administrator. It is neither a GitLab token nor the registration
  secret. Save it in the private project for deployment; verify its
  presence in the students group if score reporting is enabled.

These secrets are not required to populate the local clone. Do not demand a PAT
with `api` scope or a namespace ID merely to edit files. Accept secrets through
environment variables or leave entry in the GitLab UI to the user; do not read
secret files, print values or write them into course files. Check variable names,
type, environment scope and Protected settings without exposing values. Explain
Masked/Hidden and disabled expansion; Protected variables are unavailable on
unprotected refs. Distinguish manually supplied secrets from GitLab's predefined
variables and the [other pipeline values](references/usage.md#other-pipeline-values).

The private project's CI configuration path must be **`.releaser-ci.yml`**.
The `.gitlab-ci.yml` file grades student submissions and is exported to public.
Explain the manual path setting: otherwise the first push may run the wrong
pipeline. Before an authorized push, check CI settings; use `[skip ci]` in the
authorized commit if pipeline execution is not yet intended.

Check the runner: the current template expects a Docker socket, while gitlab.com
shared runners may need Docker-in-Docker. For a registry outside the source project's default,
override `REGISTRY`, `BASE_IMAGE` and the release `TESTENV_IMAGE` in the existing
top-level `variables:` block of the private repository's `.releaser-ci.yml`;
changing `REGISTRY` alone leaves the template's build paths pointing at
`CI_REGISTRY_IMAGE`. Set the full published testenv image URL in the top-level
`variables:` block of `.gitlab-ci.yml` in the same private clone before it is
exported for students. These paths are non-secret YAML configuration;
credentials belong in CI/CD variables. Do not modify predefined `CI_REGISTRY_*`.
GitLab's predefined `CI_REGISTRY_USER`/`CI_REGISTRY_PASSWORD` do not authenticate
to an unrelated GitLab registry. Test image pull under an actual student's job
permissions; add read-only student registry credentials only when needed.

Account for network access: a cloud runner's `localhost` does not reach a local
Manytask instance. Do not expose local services automatically. Anyone able to
pull an image containing `/opt/course` can read it; a private project alone does
not isolate hidden tests. See the guide for details.

## Verify and report

Inspect the diff and executable bits, run `checker validate`, and test reference
solutions in the course environment with score reporting disabled. Export into
a disposable directory and check that student stubs replace reference solutions
and no hidden tests or secrets reach the assignment repository. Export can clear
the destination except `.git`. Read `--help` for the installed checker version
before choosing commands.

The result is prepared files in the local clone plus a list of manual settings.
Commit, push, GitLab settings changes and deployment require authorization within
the user's request; populating a clone alone does not include them. After an
authorized push, verify the remote branch SHA. Distinguish local preparation,
checker success and pipeline startup from a course actually delivered to Manytask.
Report the prepared files/tasks, example source, completed checks and remaining
settings or tokens the user must provide manually.

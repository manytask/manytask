# Course lifecycle test

Run from `manytask/` with the component's development environment installed.
This is an opt-in, real-service integration test, separate from the regular pytest suite.
It requires an **empty, dedicated Docker daemon with at least 8 GB RAM**, Docker Compose v2,
and `uv`. Internet access is needed for toolchain/dependency images.

On macOS, create a separate Colima profile:

```sh
colima start manytask-e2e --activate=false --ssh-config=false --cpu 4 --memory 8 --disk 35 --edit
```

In that profile's editor, set the existing `docker` section to:

```yaml
docker:
  insecure-registries:
    - "172.28.0.0/16"
```

This permits the registry on the test's private Docker bridge subnet. Configure it only
in the dedicated profile. Do not stop, resize, reconfigure, or reset the development
profile. No host ports are published, and the active Docker context is unchanged.

```sh
make test-e2e E2E_DOCKER_HOST="unix://${HOME}/.colima/manytask-e2e/docker.sock"
```

An optional `E2E_TOOLCHAIN_IMAGE=<preloaded-image>` reuses a compiler/toolchain image
already present on the dedicated daemon. It must match the template's `base.docker`
environment, including the checker dependencies and pytest. The fixture uses it for
verification and as the base image's parent, installs the current checkout's checker wheel
with `--force-reinstall --no-deps`, and runs `pip check`. This avoids external package
downloads during CI. It still builds the course images, pushes
them to the fresh registry, and runs the actual release and grading jobs. Without this
option, the original verification image and uncached base build are used.

Each invocation creates a unique Compose project, a labeled network, and fresh volumes for
GitLab, PostgreSQL, registry storage, application cache, and runner configuration. It never
loads development `.env` files or mounts development databases/configuration. The launcher
refuses a daemon that already has containers, including stopped containers. It does not
switch Docker contexts, run Docker prune commands, or alter existing images.

The test migrates the empty Manytask database and bootstraps a GitLab OAuth application,
root PAT, and runner. Teacher and student authentication then use real GitLab login/OAuth
and Manytask registration forms. Course creation and student enrollment use real Manytask
HTTP forms with CSRF enabled. There are no mocked RMS adapters or signed-session shortcuts.
JavaScript and visual browser rendering are not covered.

The teacher fixture explicitly selects `.releaser-ci.yml`, enables score reporting, configures
the isolated HTTP endpoints and current deadlines, and supplies a wheel built from the
checked-out checker. These are fixture setup steps, not assertions that course creation
automatically configures them. The actual release jobs build and push images, deploy the
course configuration, and export the public repository. The test checks the export for
private-file leaks and matches the published `latest` and release image digests.
The initial template push can asynchronously queue a pipeline using the unconfigured CI
file. The fixture cancels those setup pipelines in its own private project so they cannot
occupy the runner; the explicitly triggered release pipeline is preserved and checked.

A separate student enrolls, receives a fork, and makes real Git pushes as that student.
A solution passing public tests but failing one of three hidden tests must earn 67/100;
the correct solution must earn 100/100. The test waits for the pipelines for the exact pushed
commits, reads persisted scores through the Manytask API, and checks the student's course HTML.

The launcher prints its private artifact directory under `manytask/.tmp/e2e/`. It retains stage evidence and
redacted job/service logs, deletes generated credentials, and destroys its Compose project
and volumes on success or failure by default. `e2e/run.py --keep-on-failure` is an explicit
debugging option: it retains that test stack and its private generated credentials until
you tear it down. It leaves the dedicated VM and image cache available for
reuse; stop that profile afterward to release RAM. Do not run the development cleanup targets.

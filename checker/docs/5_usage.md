# Usage

This section describes advanced usage of the checker.


## CLI

The main checker functionality is available via CLI.

::: mkdocs-click
    :module: checker.__main__
    :command: cli
    :prog_name: checker
    :list_subcommands: True
    :style: table
    :depth: 2


## Docker

Also, we provide a docker image with checker installed.  
We have tried to optimize it, but you may want to create your own image from scratch.

The docker entrypoint is `checker` script, so you can use it as a CLI application.

```shell
docker run --rm -it manytask/checker:0.0.1-python3.8 --help
```

or you can build it from your Dockerfile

```dockerfile
FROM manytask/checker:0.0.1-python3.8
# ...
```

Check available versions on [dockerhub](https://hub.docker.com/r/manytask/checker/tags?page=1&ordering=last_updated).

* `manytask/checker:main-pythonX.X` is main branch version of checker. It is DEVELOPMENT version and may be unstable.
* `manytask/checker:X.X.X-pythonX.X` is stable version, generated from release tag.

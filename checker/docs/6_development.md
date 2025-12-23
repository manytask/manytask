# Developing 

This section describes how to contribute and develop the project itself.  
For plugins development please refer to [plugins usage and development guide](./3_plugins.md).

First of all, please refer to organization contribution guide [CONTRIBUTING.md](https://github.com/manytask/.github/CONTRIBUTING.md).


## Installation

After cloning the repo, you can install it in development mode with all dev dependencies.

Recommended way is you use virtualenv
```shell
python -m venv .venv
source .venv/bin/activate
```

Install lib in dev mode
```shell
(.venv)$ pip install -U --editable .[test,docs]  # .\[test\] in zsh 
```

Also, you need to install pre-commit hooks

[//]: # (TODO: make pre-commit hooks)
```shell
TBA
```

## Testing and linting

This project uses makefile to manage testing and linting.  
The formatting, linting and testing is mandatory for each PR.


To apply formatting use
```shell
(.venv)$ make format
```

To run linting use
```shell
(.venv)$ make lint
```

To running all test or integration/unit/doctests separately use
```shell
(.venv)$ make test
(.venv)$ make test-integration
(.venv)$ make test-unit
(.venv)$ make test-doctest
```
Note: integration tests require docker to be installed and running. TBA

[//]: # (TODO: describe how to run manytask for testing and connect gitlab)

## Documentation

This project uses `mkdocs` to generate documentation.   
All documentation locating in the *.md root files and in the docs folder.  

To run docs locally use
```shell
(.venv)$ make docs-serve
```
This will start local server with hot reload. 

To build docs use
```shell
(.venv)$ make docs-build
```
This will build docs in the `site` folder.


## Contributing

Really appreciate any contributions!

Feel free to open issues and PRs. Please check on existing issues and PRs before opening new ones.



## Git hooks

This project uses [pre-commit](https://pre-commit.com/) hooks to check:

* `commit-msg` - check commit message format to follow [conventional commits](https://www.conventionalcommits.org/en/v1.0.0/)

Please install it with (included in `test` extra)
```shell
(.venv)$ pre-commit install --hook-type commit-msg
```

## CI

This project uses GitHub actions to run tests and build docs on each push and pull request.

Your PR will not be merged if tests or docs build will fail. The following checks are mandatory:

1. Testing
2. Linting/typechecks/formatting
3. Docs build and Docs Tests
4. PR title should follow [conventional commits](https://www.conventionalcommits.org/en/v1.0.0/)

# Development Guide

## Setup

1. Install Poetry (if not already installed):
```shell
curl -sSL https://install.python-poetry.org | python3 -
```

2. Install dependencies and setup pre-commit hooks:
```shell
poetry install --with dev
poetry run pre-commit install --hook-type commit-msg
```

## Git hooks

This project uses [pre-commit](https://pre-commit.com/) hooks to check:

* `commit-msg` - check commit message format to follow [conventional commits](https://www.conventionalcommits.org/en/v1.0.0/)

The hooks are automatically installed when running `poetry install`.
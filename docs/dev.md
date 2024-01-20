


## Git hooks

This project uses [pre-commit](https://pre-commit.com/) hooks to check:

* `commit-msg` - check commit message format to follow [conventional commits](https://www.conventionalcommits.org/en/v1.0.0/)

Please install it with (included in `test` extra)
```shell
(.venv)$ pre-commit install --hook-type commit-msg
```


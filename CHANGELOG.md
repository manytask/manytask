# Changelog

## [0.8.1](https://github.com/manytask/manytask/releases/tag/0.8.1) - 2023-12-28

Accept `username` and `submit_time` and deprecate `user_id` and `commit_time` as api inputs

**Full Changelog**: [0.8.0...0.8.1](https://github.com/manytask/manytask/compare/0.8.0...0.8.1)

## [0.8.0](https://github.com/manytask/manytask/releases/tag/0.8.0) - 2023-12-27

BREAKING ci_config_path for fork repositories will point to the `.gitlab-ci.yml@path/to/public/repo`

### Features

- feat: add ci_config_path from public repo (.gitlab-ci.yml@path/to/repo) by @k4black in [#94](https://github.com/$OWNER/$REPOSITORY/pull/94)

### Tests and CI/CD

- feat: add ci_config_path from public repo (.gitlab-ci.yml@path/to/repo) by @k4black in [#94](https://github.com/$OWNER/$REPOSITORY/pull/94)

### Dependency Updates

- chore(deps): bump python-gitlab from 3.15.0 to 4.2.0 by @dependabot in [#84](https://github.com/$OWNER/$REPOSITORY/pull/84)
- chore(deps): bump mypy from 1.7.0 to 1.8.0 by @dependabot in [#92](https://github.com/$OWNER/$REPOSITORY/pull/92)
- chore(deps): bump authlib from 1.2.1 to 1.3.0 by @dependabot in [#91](https://github.com/$OWNER/$REPOSITORY/pull/91)
- chore(deps): bump black from 23.11.0 to 23.12.1 by @dependabot in [#93](https://github.com/$OWNER/$REPOSITORY/pull/93)
- chore(deps): bump isort from 5.12.0 to 5.13.2 by @dependabot in [#90](https://github.com/$OWNER/$REPOSITORY/pull/90)
- chore(deps): bump actions/setup-python from 4 to 5 by @dependabot in [#86](https://github.com/$OWNER/$REPOSITORY/pull/86)
- chore(deps): bump mypy from 1.6.1 to 1.7.0 by @dependabot in [#81](https://github.com/$OWNER/$REPOSITORY/pull/81)
- chore(deps): bump ruff from 0.1.3 to 0.1.5 by @dependabot in [#80](https://github.com/$OWNER/$REPOSITORY/pull/80)
- chore(deps): bump flask from 2.3.3 to 3.0.0 by @dependabot in [#73](https://github.com/$OWNER/$REPOSITORY/pull/73)
- chore(deps): bump python from 3.11-slim to 3.12-slim by @dependabot in [#61](https://github.com/$OWNER/$REPOSITORY/pull/61)
- chore(deps): bump black from 23.10.1 to 23.11.0 by @dependabot in [#79](https://github.com/$OWNER/$REPOSITORY/pull/79)

**Full Changelog**: [0.7.0...0.8.0](https://github.com/manytask/manytask/compare/0.7.0...0.8.0)

## [0.7.0](https://github.com/manytask/manytask/releases/tag/0.7.0) - 2023-11-08

### Fixes

- fix: set CONFIDENCE_INTERVAL = timedelta(hours=2)

### Other changes

- ci: update ci with reusable workflows and new release flow by @k4black in [#76](https://github.com/$OWNER/$REPOSITORY/pull/76)
- ci: add dependabot updates configuration by @k4black in [#59](https://github.com/$OWNER/$REPOSITORY/pull/59)
- chore(docker): Add curl to docker image by @kalabukdima in [#49](https://github.com/$OWNER/$REPOSITORY/pull/49)
- ci: check PR title by @k4black in [#57](https://github.com/$OWNER/$REPOSITORY/pull/57)

### Dependency Updates

- chore(deps): bump ruff from 0.0.286 to 0.1.3 by @dependabot in [#72](https://github.com/$OWNER/$REPOSITORY/pull/72)
- chore(deps): bump types-pyyaml from 6.0.11 to 6.0.12.12 by @dependabot in [#71](https://github.com/$OWNER/$REPOSITORY/pull/71)
- chore(deps): bump codecov/codecov-action from 2 to 3 by @dependabot in [#74](https://github.com/$OWNER/$REPOSITORY/pull/74)
- chore(deps): bump types-requests from 2.28.9 to 2.31.0.10 by @dependabot in [#62](https://github.com/$OWNER/$REPOSITORY/pull/62)
- chore(deps): bump gspread from 5.10.0 to 5.12.0 by @dependabot in [#64](https://github.com/$OWNER/$REPOSITORY/pull/64)
- chore(deps): bump pytest from 7.4.0 to 7.4.3 by @dependabot in [#66](https://github.com/$OWNER/$REPOSITORY/pull/66)
- chore(deps): bump docker/build-push-action from 4 to 5 by @dependabot in [#60](https://github.com/$OWNER/$REPOSITORY/pull/60)
- chore(deps): bump docker/login-action from 2 to 3 by @dependabot in [#63](https://github.com/$OWNER/$REPOSITORY/pull/63)
- chore(deps): bump docker/setup-qemu-action from 2 to 3 by @dependabot in [#67](https://github.com/$OWNER/$REPOSITORY/pull/67)
- chore(deps): bump docker/setup-buildx-action from 2 to 3 by @dependabot in [#69](https://github.com/$OWNER/$REPOSITORY/pull/69)
- chore(deps): bump actions/checkout from 3 to 4 by @dependabot in [#65](https://github.com/$OWNER/$REPOSITORY/pull/65)
- chore(deps): bump black from 23.7.0 to 23.10.1 by @dependabot in [#68](https://github.com/$OWNER/$REPOSITORY/pull/68)
- chore(deps): bump mypy from 1.5.1 to 1.6.1 by @dependabot in [#70](https://github.com/$OWNER/$REPOSITORY/pull/70)
- chore(deps): bump werkzeug from 2.3.7 to 3.0.1 by @dependabot in [#53](https://github.com/$OWNER/$REPOSITORY/pull/53)

**Full Changelog**: [0.6.2...0.6.3](https://github.com/manytask/manytask/compare/0.6.2...0.6.3)

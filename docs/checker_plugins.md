
# Built-in plugins

## `copy_files`

Copy files matching glob patterns from one directory to another. Used to collect students solutions and private tests in one place in preparation for testing. In the example below only those files in the `allow_change` parameter will be copied, thus if the student changes tests these changes will not affect testing in the CI (`allow_change` can be set in the `.task.yml` file on a task basis).

```yaml
- name: "Copy reference tests"
  run: "copy_files"
  args:
    source_dir: ${{ global.ref_dir }}/${{ task.task_sub_path }}
    target_dir: ${{ global.temp_dir }}/${{ task.task_sub_path }}
    patterns: ${{ parameters.allow_change }}
    ignore_patterns: ["*.pyc"]
```

| Arg | Type | Required | Description |
|---|---|---|---|
| `source_dir` | `Path` | yes | Source directory. |
| `target_dir` | `Path` | yes | Destination directory (created if it does not exist). |
| `patterns` | `list[str]` | yes | Glob patterns selecting files/dirs to copy. |
| `ignore_patterns` | `list[str]` | yes | Glob patterns for entries to skip. |

## `check_regexps`

Fail if any of the given regular expressions are found in the matched files. Useful for forbidding certain patterns (e.g. `exit(0)`, hardcoded answers).

```yaml
- name: "Check forbidden patterns"
  run: "check_regexps"
  args:
    origin: ${{ global.temp_dir }}/${{ task.task_sub_path }}
    patterns: ${{ parameters.allow_change }}
    regexps: ["exit\\(0\\)", "import solution"]
```

| Arg | Type | Required | Description |
|---|---|---|---|
| `origin` | `str` | yes | Root directory to search in. |
| `patterns` | `list[str]` | yes | Glob patterns selecting which files to scan. |
| `regexps` | `list[str]` | yes | Python `re` regular expressions. The stage fails if **any** regexp matches **any** file. |


## `run_script`

Execute an arbitrary shell command or script list. By far the most flexible plugin: cat be used to compile students code, run linter and typechecker, etc. In an example below, a bash script is executed from the tests folder.

```yaml
- name: "Install dependencies"
  run: "run_script"
  args:
    origin: ${{ global.temp_dir }}
    script: "cd ${{ task.task_sub_path }} && bash check.sh"
    timeout: 60
```

| Arg | Type | Required | Default | Description |
|---|---|---|---|---|
| `origin` | `str` | yes | — | Working directory for the script. |
| `script` | `str \| list[str]` | yes | — | Shell command string or argv list. |
| `timeout` | `float \| null` | no | `null` | Kill the process after this many seconds. |
| `env_additional` | `dict[str, str]` | no | `{}` | Extra environment variables to inject. |
| `env_whitelist` | `list[str] \| null` | no | `null` | If set, only these env vars are kept (all others are cleared). |
| `input` | `Path \| null` | no | `null` | Path to a file to use as stdin. |


## `safe_run_script`

Like `run_script` but wraps the command in [Firejail](https://firejail.wordpress.com/) for sandboxing. Requires Firejail to be installed on the host.

```yaml
- name: "Run student code safely"
  run: "safe_run_script"
  args:
    origin: ${{ global.temp_dir }}/${{ task.task_sub_path }}
    script: "python solution.py"
    timeout: 10
    lock_network: true
    allow_fallback: false
```

| Arg | Type | Required | Default | Description |
|---|---|---|---|---|
| `origin` | `str` | yes | — | Working directory for the script. |
| `script` | `str \| list[str]` | yes | — | Shell command string or argv list. |
| `timeout` | `float \| null` | no | `null` | Kill the process after this many seconds. |
| `input` | `Path \| null` | no | `null` | Path to a file to use as stdin. |
| `env_additional` | `dict[str, str]` | no | `{}` | Extra environment variables to inject. |
| `env_whitelist` | `list[str]` | no | `[]` | Environment variables to pass through into the sandbox. |
| `paths_whitelist` | `list[str]` | no | `[]` | Filesystem paths the sandboxed process may access (in addition to `origin`). |
| `paths_blacklist` | `list[str]` | no | `[]` | Filesystem paths explicitly denied inside the sandbox. |
| `lock_network` | `bool` | no | `true` | Disable network access inside the sandbox. |
| `allow_fallback` | `bool` | no | `false` | If `true` and Firejail is not installed, fall back to `run_script` instead of failing. |

## `aggregate`

Combine multiple score percentages into a single value using a weighted strategy. Typically used in `report_pipeline` to merge scores from several `register_output` stages.

```yaml
- name: "Aggregate scores"
  run: "aggregate"
  register_output: final_score
  args:
    scores:
      - ${{ outputs.unit_tests.percentage }}
      - ${{ outputs.integration_tests.percentage }}
    weights: [0.6, 0.4]
    strategy: mean
```

| Arg | Type | Required | Default | Description |
|---|---|---|---|---|
| `scores` | `list[float]` | yes | — | List of score values (typically from `outputs.<key>.percentage`). |
| `weights` | `list[float] \| null` | no | `null` (equal weights) | Per-score multipliers. Must have the same length as `scores`. |
| `strategy` | `str` | no | `"mean"` | Aggregation strategy: `mean`, `sum`, `min`, `max`, or `product`. |

---

## `report_score_manytask`

Send the final score to the Manytask platform via its [REST API](./api.md). Used in `report_pipeline` to send the resulting score to the Manytask. The plugin will retry 3 times on HTTP errors `408`, `500`, `502`, `503`, `504` with exponentially increasing waiting times (1, 2 and 4 seconds).

```yaml
- name: "Report score"
  run: "report_score_manytask"
  args:
    username: ${{ global.username }}
    task_name: ${{ task.task_name }}
    score: ${{ outputs.test_result.percentage }}
    report_url: https://manytask.example.com/api/course-name
    report_token: ${{ env.MANYTASK_TOKEN }}
    check_deadline: true
```

| Arg | Type | Required | Default | Description |
|---|---|---|---|---|
| `username` | `str` | yes | — | Student's username in RMS. |
| `task_name` | `str` | yes | — | Task identifier as registered in `.manytask.yml`. |
| `score` | `float \| int \| null` | yes | — | Score to report, in `[0.0, 1.0]` (bonus scores may exceed `1.0` but float larger than `2.0` will not be accepted). |
| `report_url` | `AnyUrl` | yes | — | Base URL of the Manytask instance. |
| `report_token` | `str` | yes | — | Authentication token for the Manytask API. |
| `check_deadline` | `bool` | yes | — | Whether Manytask should apply deadline penalties server-side. |
| `origin` | `str \| null` | no | `null` | If set, collect files matching `patterns` from this directory and attach them to the report. |
| `patterns` | `list[str]` | no | `["*"]` | Glob patterns for files to attach (only used when `origin` is set). |
| `send_time` | `datetime` | no | now | Submission timestamp. Defaults to the current time with local timezone. |

### `score`

| Value | Description |
|---|---|
| `float` | A percentage of the score in `[0.0, 1.0]`, with an ability to give bonus up to `2.0`. Number below `0.0` will be clamped to `0.0`, number over `2.0` will return HTTP Bad Request. The number will be multiplied by the max number of points set to the task. |
| `int` | If the reported number is integer, it is taken as a final score. Can be any integer number, even if larger than max score for the task. |
| `null` | Task is considered fully solved, max points are issued. |


## `run_pytest`

Run [pytest](https://pytest.org/) against a task directory, with optional coverage and weighted scoring.

```yaml
- name: "Run tests"
  run: "run_pytest"
  register_output: test_result
  args:
    origin: ${{ global.temp_dir }}
    target: ${{ task.task_sub_path }}
    timeout: 30
    report_percentage: true
```

| Arg | Type | Required | Default | Description |
|---|---|---|---|---|
| `origin` | `str` | yes | — | Working directory (usually `${{ global.temp_dir }}`). |
| `target` | `str` | yes | — | Path to the test file or directory, relative to `origin`. |
| `timeout` | `int \| null` | no | `null` | Kill pytest after this many seconds. |
| `isolate` | `bool` | no | `false` | Run pytest with `-I` (isolated mode) to block sitecustomize monkey-patching. |
| `env_whitelist` | `list[str]` | no | `["PATH"]` | Environment variables passed into the pytest process. |
| `coverage` | `bool \| int \| null` | no | `null` | Enable coverage reporting. Pass an integer to also enforce a minimum coverage percentage. |
| `allow_failures` | `bool` | no | `false` | Do not fail the stage even if tests fail (useful when combined with `report_percentage`). |
| `report_percentage` | `bool` | no | `true` | Compute `percentage` as `passed / total` tests and store it in the stage result. |

> **Note:** When `report_percentage: true` the plugin uses a secure FIFO pipe to receive test results from a custom pytest plugin (`checker_reporter`). The `percentage` field of the registered output will be the fraction `passed_tests / total_tests`.


## `check_gitlab_merge_request` *(WIP)*

Check that a GitLab merge request is valid (no conflicts, required labels, etc.).

| Arg | Type | Required | Default | Description |
|---|---|---|---|---|
| `token` | `str` | yes | — | GitLab personal access token. |
| `task_dir` | `str` | yes | — | Task directory path. |
| `repo_url` | `AnyUrl` | yes | — | GitLab repository URL. |
| `requre_approval` | `bool` | no | `false` | Require at least one approval on the MR. |
| `search_for_score` | `bool` | no | `false` | Search for a score comment in the MR. |


### `collect_score_gitlab_merge_request` *(WIP)*

Collect a score left by a tutor in a GitLab MR comment.

| Arg | Type | Required | Default | Description |
|---|---|---|---|---|
| `token` | `str` | yes | — | GitLab personal access token. |
| `task_dir` | `str` | yes | — | Task directory path. |
| `repo_url` | `AnyUrl` | yes | — | GitLab repository URL. |
| `requre_approval` | `bool` | no | `false` | Require at least one approval on the MR. |
| `search_for_score` | `bool` | no | `false` | Search for a score comment in the MR. |

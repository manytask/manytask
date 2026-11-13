
# Built-in plugins

## `copy_files`

Copy files matching glob patterns from one directory to another. Used to collect the student's solution and the private tests in one place in preparation for testing.

The example below copies files listed in the `allow_change` parameter **from the student
repository** (`global.repo_dir`) into the testing tree. It leaves other files already in the tree
untouched, so this stage alone does not restrict which student edits can affect grading.

The example reads its patterns from the optional `parameters.allow_change` list, supported in
both task formats. See [Explicit editable files](checker_config.md#explicit-editable-files) for
inheritance and the difference between plugin use and automatic shared-folder preparation.

```yaml
- name: "Take the student's allowed files"
  run: "copy_files"
  args:
    source_dir: ${{ global.repo_dir }}/${{ task.task_sub_path }}
    target_dir: ${{ global.temp_dir }}/${{ task.task_sub_path }}
    patterns: ${{ parameters.allow_change }}
    ignore_patterns: ["*.pyc"]
```

> This stage is **optional**: the checker already builds the grading tree before running plugins.
> Use it when a pipeline needs to copy additional files or arrange them differently.

| Arg | Type | Required | Description |
|---|---|---|---|
| `source_dir` | `Path` | yes | Source directory. |
| `target_dir` | `Path` | yes | Destination directory (created if it does not exist). |
| `patterns` | `list[str]` | yes | Glob patterns selecting files/dirs to copy. |
| `ignore_patterns` | `list[str]` | yes | Glob patterns for entries to skip. |

## `check_regexps`

Fail if any of the given regular expressions are found in the matched files. Useful for forbidding certain patterns (e.g. `exit(0)`, hardcoded answers).

Reusing the same `allow_change` parameter here is a common idiom: the files a student may edit are exactly the files worth scanning for forbidden constructs.

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

Execute an arbitrary shell command or script list. By far the most flexible plugin: can be used to compile students code, run linter and typechecker, etc. In an example below, a bash script is executed from the tests folder.

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

Send the final score to the Manytask platform via its [REST API](./api.md). Used in `report_pipeline`
after a successful task pipeline. HTTP error responses fail the stage; the current retry
configuration does not retry POST requests on HTTP errors.

```yaml
- name: "Report score"
  run: "report_score_manytask"
  args:
    username: ${{ env.GITLAB_USER_LOGIN }}
    task_name: ${{ task.task_name }}
    score: ${{ outputs.test_result.percentage }}
    report_url: https://manytask.example.com/api/course-name/report
    report_token: ${{ env.MANYTASK_TOKEN }}
    check_deadline: true
```

| Arg | Type | Required | Default | Description |
|---|---|---|---|---|
| `username` | `str` | yes | — | Student's username in RMS. |
| `task_name` | `str` | yes | — | Task identifier as registered in `.manytask.yml`. |
| `score` | `float \| int \| null` | yes | — | Score to report, in `[0.0, 1.0]` (bonus scores may exceed `1.0` but float larger than `2.0` will not be accepted). |
| `report_url` | `AnyUrl` | yes | — | Full score endpoint URL: `https://<host>/api/<course_name>/report`. The plugin uses it as given. |
| `report_token` | `str` | yes | — | Authentication token for the Manytask API. |
| `check_deadline` | `bool` | yes | — | Whether Manytask should apply deadline penalties server-side. |
| `allow_reduction` | `bool` | no | `false` | Allow replacing an existing score with a lower value. Must be enabled when reporting a negative integer. |
| `origin` | `str \| null` | no | `null` | If set, collect files matching `patterns` from this directory and attach them to the report. |
| `patterns` | `list[str]` | no | `["*"]` | Glob patterns for files to attach (only used when `origin` is set). |
| `send_time` | `datetime` | no | now | Submission timestamp. Defaults to the current time with local timezone. |

### `score`

| Value | Description |
|---|---|
| `float` | A percentage of the score in `[0.0, 1.0]`, with an ability to give bonus up to `2.0`. Number below `0.0` will be clamped to `0.0`, number over `2.0` will return HTTP Bad Request. The number will be multiplied by the max number of points set to the task. |
| `int` | If the reported number is an integer, including a negative integer, it is taken as a final score. It can be larger than the task maximum. Persisting a negative value requires `allow_reduction: true`. |
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

## `cpp_run_tests`

Run already-built Catch2 test executables through `safe_run_script`. Build each target before
this stage; the plugin looks for it under `<root>/build-<build_type in lowercase>/`.

```yaml
- name: "Run CUDA tests"
  run: "cpp_run_tests"
  args:
    root: ${{ global.temp_dir }}
    tests: ["cuda_tests", "Release"]
    timeout: 60
    no_detect_leaks: false
    args: []
    paths_whitelist: []
    cuda_compute_sanitizer: true
    env_whitelist: ["CUDA_VISIBLE_DEVICES"]
```

| Arg | Type | Required | Default | Description |
|---|---|---|---|---|
| `root` | `Path` | yes | — | Root containing the build directories. |
| `tests` | `list[str]` | yes | — | Alternating executable names and build types, e.g. `["tests", "Debug", "tests", "Release"]`. Must contain at least one pair. |
| `timeout` | `float` | yes | — | Timeout in seconds for each executable. |
| `no_detect_leaks` | `bool` | yes | — | Disable AddressSanitizer leak detection. |
| `args` | `list[str]` | yes | — | Additional arguments passed to each test executable. |
| `paths_whitelist` | `list[str]` | yes | — | Additional sandbox paths, resolved relative to `root`. |
| `lock_network` | `bool` | no | `true` | Disable network access inside Firejail. |
| `cuda_compute_sanitizer` | `bool` | no | `false` | Run each executable through `/usr/local/cuda/bin/compute-sanitizer` with full leak checking and error exit code `1`. |
| `env_whitelist` | `list[str]` | no | `[]` | Environment variables passed into the sandbox. |

Firejail must be installed. CUDA runs also require access to a GPU from the grading environment;
enabling `cuda_compute_sanitizer` requires Compute Sanitizer at the path above. To select a GPU,
set `CUDA_VISIBLE_DEVICES` in the runner environment and include it in `env_whitelist` as shown.
The whitelist passes an existing variable through; it does not set its value.

## `cpp_run_benchmarks`

Run an already-built Catch2 benchmark executable through `safe_run_script` from
`<root>/build-relwithdebinfo/` and check its reported mean times against configured thresholds.
Firejail must be installed.

```yaml
default_parameters:
  benchmark_values: ["vector_add", "0.01"]

testing:
  tasks_pipeline:
    - name: "Run CUDA benchmarks"
      run: "cpp_run_benchmarks"
      args:
        root: ${{ global.temp_dir }}
        benchmark: "cuda_benchmarks"
        timeout: 60
        args: []
        benchmark_values: ${{ parameters.benchmark_values }}
        env_whitelist: ["CUDA_VISIBLE_DEVICES"]
```

| Arg | Type | Required | Default | Description |
|---|---|---|---|---|
| `root` | `Path` | yes | — | Root containing `build-relwithdebinfo`. |
| `benchmark` | `str` | yes | — | Benchmark executable name. Must not be `null`. |
| `timeout` | `float` | yes | — | Timeout in seconds for the executable. |
| `args` | `list[str]` | yes | — | Additional executable arguments. |
| `benchmark_values` | `list[str]` | yes | — | Alternating benchmark names and thresholds in seconds. Names must exactly match the reported benchmarks. Nonnegative thresholds are upper bounds; negative thresholds specify a lower bound by their absolute value. |
| `env_whitelist` | `list[str]` | no | `[]` | Environment variables passed into the sandbox; include `CUDA_VISIBLE_DEVICES` to pass the runner's GPU selection through. |

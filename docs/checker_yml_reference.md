# `.checker.yml` Reference Guide

This document is a complete reference for the `.checker.yml` configuration file used by the [checker](https://github.com/manytask/checker) tool.

The `.checker.yml` file lives at the root of your **private** (reference) course repository and controls:
- How the repository structure is validated and exported to the public student repo
- Default parameters shared across all tasks
- How the testing pipelines are assembled and executed

For sub-folder overrides see [`.task.yml` / `.group.yml`](#taskymltaskgroupyml-sub-configs) at the bottom of this page.

---

## Top-level structure

```yaml
version: 1                  # required

default_parameters: ...     # optional

structure: ...              # required
export: ...                 # required
testing: ...                # required
```

| Field | Type | Required | Description |
|---|---|---|---|
| [`version`](#version) | `int` | yes | Config schema version. Must be `1`. |
| [`default_parameters`](#default_parameters) | object | no | Key/value pairs available as `${{ parameters.<key> }}` in all pipeline templates. |
| [`structure`](#structure) | object | yes | Glob patterns describing which files are public, private, or ignored. |
| [`export`](#export) | object | yes | Settings for the `checker export` command. |
| [`testing`](#testing) | object | yes | Settings for the `checker grade` command — pipelines, plugins, change detection. |


## `version`

```yaml
version: 1
```

The only currently supported value is `1`. The checker will raise a validation error for any other value.


## `default_parameters`

A flat key/value map of parameters available in all pipeline stage templates as `${{ parameters.<key> }}`.  
Values can be `bool`, `int`, `float`, `str`, a list of scalars, or `null`. Example:

```yaml
default_parameters:
  run_testing: true
  timeout: 10
  run_linting: false
  allowed_imports: ["os", "sys"]
```

These defaults can be overridden per-task or per-group in `.task.yml` / `.group.yml` files, more parameters can be added for task group or individual tasks (see [sub-configs](#taskymltaskgroupyml-sub-configs)).


## `structure`

This section controls which files are copied, hidden, or ignored when exporting to the public student repository and when preparing the testing workspace.

```yaml
structure:
  ignore_patterns: [".git", ".idea", "__pycache__", "*.pyc"]
  public_patterns: ["*", ".gitignore", ".gitlab-ci-students.yml"]
  private_patterns: [".*", "test_private.py", "data_private"]
```

| Field | Type | Required | Description |
|---|---|---|---|
| `ignore_patterns` | `list[str]` | no | Glob patterns for files/dirs to **exclude entirely** — not exported, not copied during testing. |
| `public_patterns` | `list[str]` | no | Glob patterns for files/dirs to **include in the public export** and overwrite during testing. |
| `private_patterns` | `list[str]` | no | Glob patterns for files/dirs to **keep private** (excluded from export, overwritten from reference during testing). |

> **Warning:** `**` (double-star recursive glob) is **not allowed** in any pattern. Patterns are applied at each directory level individually.  

Pattern precedence: `ignore_patterns` > `private_patterns` > `public_patterns`


## `export` section

Settings used by the `checker export` command to publish tasks to the public student repository. Example%

```yaml
export:
  destination: https://git.example.com/course/public-repo
  default_branch: main
  commit_message: "chore(auto): export new tasks"
  templates: search
```

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `destination` | `AnyUrl` | yes | — | URL of the public (student) Git repository to push exported tasks to. |
| `default_branch` | `str` | no  | `"main"` | Branch name to push to in the destination repository. |
| `commit_message` | `str` | no  | `"chore(auto): export new tasks"` | Commit message used when pushing exported tasks. |
| `templates` | `str` | no  | `"search"` | Template strategy for generating student-facing task files. One of `search`, `create`, `search_or_create`. |

### `templates` strategies

| Value | Description |
|---|---|
| `search` | Look for files named `some_file.template` and replace `some_file` with their content. An empty `.template` file deletes the original. Every task **must** have at least one `.template` file. |
| `create` | Scan all files for `# SOLUTION BEGIN` / `# SOLUTION END` comment pairs and strip the code between them, replacing it with `# TODO: Your solution`. Files that become empty are deleted. Every task **must** have at least one such pair. |
| `search_or_create` | Try `search` first; fall back to `create` if no `.template` files are found. |

`create` template example:

```python
# private repo (reference solution)
def add(a, b):
    # SOLUTION BEGIN
    return a + b
    # SOLUTION END
```

becomes in the public repo:

```python
def add(a, b):
    # TODO: Your solution
```


## `testing` section

This section controlls how the checker runs tests, the general structure is:

```yaml
testing:
  changes_detection: last_commit_changes
  search_plugins: ["tools/plugins"]

  global_pipeline:
    - ...

  tasks_pipeline:
    - ...

  report_pipeline:
    - ...
```

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `changes_detection` | `str` | ➖ | `last_commit_changes` | Strategy for detecting which tasks changed. The full list of options are `branch_name`, `commit_message`, `last_commit_changes`, `files_changed`. See details [below](#changes_detection). |
| `search_plugins` | `list[str]` | ➖ | `[]` | Paths (relative to repo root) to search for custom plugin Python files. |
| `global_pipeline` | `list[stage]` | ➖ | `[]` | Pipeline executed **once** per checker run, before any task pipeline. |
| `tasks_pipeline` | `list[stage]` | ➖ | `[]` | Pipeline executed **once per task**. Can be overridden in `.task.yml`. |
| `report_pipeline` | `list[stage]` | ➖ | `[]` | Pipeline executed **once per task** only if `tasks_pipeline` succeeded. Can be overridden in `.task.yml`. |

### `changes_detection`

Determines which tasks are selected for grading when running `checker grade`.

| Value | Description |
|---|---|
| `branch_name` | Selects the single task/group whose name matches the current Git branch name. |
| `commit_message` | Selects all tasks/groups whose name appears in the last commit message. |
| `last_commit_changes` | Selects all tasks that have files changed in the last commit. *(default)* |
| `files_changed` | *(Not yet implemented)* Compares current state against the previous commit. |

### `search_plugins`

List of directory paths (relative to the repository root) where the checker will look for custom plugin Python files.

```yaml
testing:
  search_plugins:
    - "tools/plugins"
    - "scripts/checker_plugins"
```

Each `.py` file in those directories is imported and any class inheriting from `PluginABC` with a `name` attribute is registered automatically.

### Pipeline stages

Each entry in `global_pipeline`, `tasks_pipeline`, or `report_pipeline` is a **pipeline stage** — a single plugin invocation.

```yaml
- name: "Run pytest"
  run: "run_pytest"
  fail: fast
  run_if: ${{ parameters.run_testing }}
  register_output: test_result
  args:
    origin: "${{ global.temp_dir }}/${{ task.task_sub_path }}"
    target: "${{ task.task_sub_path }}"
    timeout: ${{ parameters.timeout }}
```

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `name` | `str` | yes | — | Human-readable label shown in logs. |
| `run` | `str` | yes | — | Plugin key name to execute (built-in or custom). |
| `args` | `dict` | no | `{}` | Arguments passed to the plugin. Validated by the plugin's `Args` model. Supports [templating](#templating). |
| `fail` | `str` | no | `fast` | Failure handling strategy. One of `fast`, `after_all`, `never`. See below. |
| `run_if` | `bool` or template | no | `null` (always run) | Condition evaluated before running. Stage is skipped when false. Supports [templating](#templating). |
| `register_output` | `str` | no | `null` | If set, stores the stage result in `outputs.<key>` for use by later stages. Here `<key>` is the value this field is set to. |

#### `fail` values

| Value | Behaviour |
|---|---|
| `fast` | *(default)* Stop the pipeline immediately and mark the task as failed. |
| `after_all` | Continue running remaining stages, but mark the task as failed at the end. |
| `never` | Ignore the failure; the pipeline continues and the task is not marked as failed. |

---

## Templating

Pipeline `args` values and `run_if` conditions support [Jinja2](https://jinja.palletsprojects.com/en/3.0.x/) templating using `${{ ... }}` syntax. Expressions are evaluated just before the plugin is executed.

```yaml
args:
  origin: "${{ global.temp_dir }}/${{ task.task_sub_path }}"
  username: ${{ global.username }}
  score: ${{ outputs.test_result.percentage }}
  run_linting: ${{ parameters.run_linting }}
```

### Available template variables

#### `global` — [`GlobalPipelineVariables`](../checker/checker/pipeline.py)

Available in all three pipeline types.

| Variable | Type | Description |
|---|---|---|
| `global.ref_dir` | `str` | Absolute path to the reference (private) repository root. |
| `global.repo_dir` | `str` | Absolute path to the student repository root. |
| `global.temp_dir` | `str` | Absolute path to the temporary working directory prepared for testing. |
| `global.task_names` | `list[str]` | Names of all tasks being tested in this run. |
| `global.task_sub_paths` | `list[str]` | Relative paths of all tasks being tested in this run. |

#### `task` — [`TaskPipelineVariables`](../checker/checker/pipeline.py)

Available only in `tasks_pipeline` and `report_pipeline` (not in `global_pipeline`).

| Variable | Type | Description |
|---|---|---|
| `task.task_name` | `str` | Name of the current task (e.g. `"hello_world"`). |
| `task.task_sub_path` | `str` | Relative path to the current task folder (e.g. `"1.FirstGroup/hello_world"`). |
| `task.task_score_percent` | `float` | Deadline-adjusted score multiplier in `[0.0, 1.0]`. |

#### `parameters`

Key/value pairs from [`default_parameters`](#default_parameters) merged with any overrides from `parameters` section of `.group.yml` / `.task.yml`.

```yaml
run_if: ${{ parameters.run_linting }}
args:
  timeout: ${{ parameters.timeout }}
```

#### `env`

Dictionary of all environment variables present when the checker process started.

```yaml
args:
  report_token: ${{ env.MANYTASK_TOKEN }}
```

#### `outputs`

Results of previous pipeline stages that used `register_output` to save their outputs under `<key>`. Each entry is a [`PipelineStageResult`](../checker/pipeline.py) object.

| Field | Type | Description |
|---|---|---|
| `outputs.<key>.name` | `str` | Stage name. |
| `outputs.<key>.failed` | `bool` | Whether the stage failed. |
| `outputs.<key>.skipped` | `bool` | Whether the stage was skipped. |
| `outputs.<key>.percentage` | `float \| None` | Score percentage returned by the plugin (default `1.0` on success). |
| `outputs.<key>.elapsed_time` | `float \| None` | Wall-clock time in seconds. |
| `outputs.<key>.output` | `str` | Text output from the plugin. |

Example:

```yaml
- name: "Run tests"
  run: "run_pytest"
  register_output: test_result
  args: ...

- name: "Report score"
  run: "report_score_manytask"
  args:
    score: ${{ outputs.test_result.percentage }}
    ...
```


## `.task.yml` / `.group.yml` sub-configs

You need to place a `.task.yml` (or `.group.yml`) file inside any task or group folder to indicate that this folder contains task (or group of tasks). These files can also be used to override parts of the root `.checker.yml` for this scope, or to add or redefine parameters.

Example:

```yaml
# .task.yml
version: 1

structure:           # optional — overrides root structure for this task
  ignore_patterns: ["*.pyc"]
  public_patterns: ["solution.py", "README.md"]
  private_patterns: ["tests/", ".*"]

parameters:          # optional — merged on top of default_parameters
  timeout: 60
  run_linting: false

task_pipeline:       # optional — replaces testing.tasks_pipeline for this task
  - name: "Run tests"
    run: "run_pytest"
    args:
      origin: ${{ global.temp_dir }}
      target: ${{ task.task_sub_path }}

report_pipeline:     # optional — replaces testing.report_pipeline for this task
  - name: "Report score"
    run: "report_score_manytask"
    args: ...
```

| Field | Type | Description |
|---|---|---|
| `version` | `int` | Must be `1`. |
| `structure` | object | Same fields as root [`structure`](#structure). Replaces the root value entirely for this folder. |
| `parameters` | object | Merged on top of `default_parameters`. Task-level values take precedence. |
| `task_pipeline` | `list[stage]` | Replaces `testing.tasks_pipeline` for this task. Note "task", not "tasks".|
| `report_pipeline` | `list[stage]` | Replaces `testing.report_pipeline` for this task. |

If the pipeline is defined for the smaller scope, this definition overrides larger scope. The priority is then:

1. `.task.yml` in the task folder
2. `.group.yml` in the parent group folder
3. Root `testing.tasks_pipeline` / `testing.report_pipeline`

## Complete example of the file

```yaml
# .checker.yml
version: 1

structure:
  ignore_patterns:
    - ".git"
    - ".idea"
    - ".vscode"
    - "__pycache__"
    - ".venv"
    - ".*_cache"
    - "*.pyc"
  public_patterns:
    - "*"
    - ".gitignore"
    - ".gitlab-ci-students.yml"
  private_patterns:
    - ".*"

default_parameters:
  run_testing: true
  run_linting: true
  timeout: 10

export:
  destination: https://gitlab.example.com/course/public-repo
  default_branch: main
  commit_message: "chore(auto): export new tasks"
  templates: search

testing:
  changes_detection: last_commit_changes
  search_plugins: ["tools/plugins"]

  global_pipeline:
    - name: "Install requirements"
      run: "run_script"
      args:
        origin: ${{ global.temp_dir }}
        script: "pip install -r requirements.txt"
        timeout: 120

  tasks_pipeline:
    - name: "Check forbidden patterns"
      fail: fast
      run: "check_regexps"
      args:
        origin: "${{ global.temp_dir }}/${{ task.task_sub_path }}"
        patterns: ["**/*.py"]
        regexps: ["exit\\(0\\)"]

    - name: "Run linter"
      run_if: ${{ parameters.run_linting }}
      fail: after_all
      run: "run_script"
      args:
        origin: ${{ global.temp_dir }}
        script: "python -m ruff check ${{ task.task_sub_path }}"

    - name: "Run tests"
      run_if: ${{ parameters.run_testing }}
      fail: fast
      run: "run_pytest"
      register_output: test_result
      args:
        origin: ${{ global.temp_dir }}
        target: ${{ task.task_sub_path }}
        timeout: ${{ parameters.timeout }}
        report_percentage: true

  report_pipeline:
    - name: "Report score"
      run: "report_score_manytask"
      args:
        username: ${{ global.username }}
        task_name: ${{ task.task_name }}
        score: ${{ outputs.test_result.percentage }}
        report_url: https://manytask.example.com
        report_token: ${{ env.MANYTASK_TOKEN }}
        check_deadline: true
```

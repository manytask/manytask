# Configuration

This page describes how to configure checker with `.checker.yml`, `.manytask.yml` and `.group.yml`/`.task.yml` files.

You can refer to the [course-template](https://github.com/manytask/course-template) repository for examples of configuration files.


## `.checker.yml`

This file describes how the checker will operate - how to export files, how to run pipelines and so on.

[//]: # (TODO: Add json schema)
TBA

No json schema available yet, but you can refer to the checker.configs.checker.CheckerConfig in [checker](https://github.com/manytask/checker) repository.  
Or [course-template](https://github.com/manytask/course-template) repository.


!!! warning  
    The structure section requires glob patterns to be valid and will apply the same patterns recursively to all subdirectories.  
    The moment it faces `.task.yml` file, it will stop and use the parameters from this file recursively.  
    No `**` patterns are allowed.

Please refer to the [plugins](./3_plugins.md) and [pipelines](./4_pipelines.md) sections for more information on how to configure pipelines.

### Example

The simple `.checker.yml` file is:

[//]: # (TODO: include file directly from course-template)
[//]: # (TODO: add pydantic validation for include files)
```yaml
# .checker.yml
version: 1

# can be overwritten in .task.yml for individual tasks
structure:
  # ignore patterns: exclude from export, overwrite during testing
  ignore_patterns: [".git", ".idea", ".vscode", "__pycache__", ".venv", ".*_cache", "*.pyc"]
  # public patterns: include in export, overwrite during testing
  public_patterns: ["*", ".gitlab-ci-students.yml", ".gitignore"]
  # private patterns: exclude from export, overwrite during testing
  private_patterns: [".*"]

# default values for all tasks, can be overwritten in .task.yml params:
default_parameters:
  run_testing: true
  timeout: 10  # in seconds

# settings for export command, uses .manytask.yml and `params` and each task params (in .task.yml)
export:
  destination: https://gitlab.manytask.org/test/public-test-repo

# settings for Tester, uses .checker.yml and `params` and each task params (in .task.yml)
testing:
  changes_detection: branch_name  # branch_name, commit_message, last_commit_changes
  search_plugins: ["tools/plugins"]

  # run once per repo
  global_pipeline:
    - ...
  # run once per task
  tasks_pipeline:
    - ...
    - ...
  # will run once per task only if task_pipeline NOT failed
  report_pipeline:
    - ...
```

!!! note  
    `changes_detection` parameter select how to detect changes in the repo during testing (`checker grade` command).  
    It can be one of the following:
    * `branch_name` - check if the branch name == task/group name (select only one task/group)
    * `commit_message` - check if the commit message contains task/group name (can select multiple tasks/groups)
    * `last_commit_changes` - check if the last commit contains changes in the task folder (can select multiple tasks)
    * `files` - (NOT IMPLEMENTED) check actual file difference between current state and the previous commit (can select multiple tasks)


## `.manytask.yml`

This file describes deadlines for tasks. It is used by `checker export` command to export only tasks that are started.  
Additionally, it is used by `checker validate` to ensure integrity of the deadlines and local files.

[//]: # (TODO: Add json schema)

No json schema available yet, but you can refer to the checker.configs.deadlines.DeadlinesConfig in [checker](https://github.com/manytask/checker) repository.  
Or [course-template](https://github.com/manytask/course-template) repository.

### Example

[//]: # (TODO: include file directly from course-template)
[//]: # (TODO: add pydantic validation for include files)
The simple `.manytask.yml` file is:
```yaml
# .manytask.yml
version: 1

settings:
  timezone: Europe/Moscow

  deadlines: hard  # hard/interpolate
  max_submissions: 10  # optional
  submission_penalty: 0.1  # optional

  task_url: https://example.com/$GROUP_NAME/$TASK_NAME  # optional

schedule:
  - group: 1.FirstGroup
    enabled: true
    start: 2020-01-01 18:00:00
    steps:
      0.5: 7d
    end: 13d 03:00:00
    tasks:
      - task: hello_world
        score: 10
        bonus: 0
        special: 1
      - task: sum_a_b
        score: 5
        bonus: 5
        special: 0
      - task: disabled_task
        enabled: false
        score: 5

  - group: 2.SecondGroup
    start: 2020-02-01 18:00:00
    steps:
      0.9: 2020-02-08 18:00:00
      0.1: 14d
    tasks:
      - task: factorial
        score: 20

  - group: 3.ThirdGroup
    start: 2020-03-01 18:00:00
    tasks:
      - task: palindrome
        score: 0
        special: 2
        url: https://example.com

  - group: 4.FourthGroup
    enabled: false
    start: 2020-04-01 18:00:00
    tasks: []
```


## `.group.yml`/`.task.yml`

This config files override parameters for the current folder and all subfolders.  
When some field is not defined (e.g. only version present) the default parameter from the main config or from the folder above applied.

[//]: # (TODO: Add json schema)

No json schema available yet, but you can refer to the checker.configs.task.TaskConfig in [checker](https://github.com/manytask/checker) repository.  
Or [course-template](https://github.com/manytask/course-template) repository.

### Example

[//]: # (TODO: include file directly from course-template)
[//]: # (TODO: add pydantic validation for include files)

```yaml
# .task.yml
version: 1

structure:  # optional
  ignore_patterns: ["*.pyc"]
  public_patterns: ["custom_public_file.txt"]
  private_patterns: [".*", "custom_private_tests.py"]
  
parameters:  # optional
  run_testing: true
  timeout: 10  # in seconds
  
task_pipeline:  # optional
  ...

report_pipeline:  # optional
  ...
```
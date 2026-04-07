# Configuration

This page describes how to configure checker with `.checker.yml`, `.manytask.yml` and `.group.yml`/`.task.yml` files.

You can refer to the [course-template](https://github.com/manytask/course-template) repository for examples of configuration files.



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

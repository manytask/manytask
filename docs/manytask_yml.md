# `.manytask.yml` Reference

The `.manytask.yml` file is the primary course configuration file. It is stored in the course's private repository and pushed to the Manytask server to update course settings, deadlines, and grading rules. It is also used by `checker export` command to export only tasks that are started.  Additionally, it is used by `checker validate` to ensure integrity of the deadlines and local files

## Top-level structure

```yaml
version: 1
status: in_progress   # optional

ui:
  ...

deadlines:
  ...

grades:               # optional
  ...
```

| Field | Type | Required | Description |
|---|---|---|---|
| `version` | integer | yes | Config format version. Currently only `1` is supported. |
| `status` | string | no | Course lifecycle status. See [Course Statuses](#status). |
| `ui` | object | yes | UI display settings. See [`ui`](#ui). |
| `deadlines` | object | yes | Deadline schedule and submission rules. See [`deadlines`](#deadlines). |
| `grades` | object | no | Final grade computation rules. See [`grades`](#grades). |


## `status`

Controls the course lifecycle stage. When omitted, the status is not changed on update.

| Value | Description |
|---|---|
| `created` | Course was just created; no tasks yet; students cannot access it. |
| `hidden` | Course has tasks but is hidden from students; teachers have full access. |
| `in_progress` | Course is active and running. |
| `all_tasks_issued` | No more tasks will be added; maximum possible grade is finalized. |
| `doreshka` | Post-course upsolving period allowing students to earn additional points, which only satisfactory (3 out of 5) grade is possible. |
| `finished` | Course is fully completed; no longer shown on the student main page. |

Status can also be changed through the admin panel without modifying the config file.


## `ui`

Controls how the course is displayed in the Manytask web interface.

```yaml
ui:
  task_url_template: https://rms.example.com/course/students/$USER_NAME/$GROUP_NAME/$TASK_NAME
  links:
    "TG Channel": https://t.me/joinchat/example
    "LMS": https://lms.example.com/
```

| Field | Type | Required | Description |
|---|---|---|---|
| `task_url_template` | string | yes | URL template for linking to individual tasks in Repository Management System (RMS, e.g. GitLab). Must start with `http://` or `https://`. |
| `links` | dict[string, string] | no | Named links shown in the course UI (e.g. Telegram, LMS). Any number of entries. |

### `task_url_template` macros

The following placeholders are substituted at render time:

| Macro | Replaced with |
|---|---|
| `$GROUP_NAME` | The task group name (e.g. `week_1`) |
| `$TASK_NAME` | The task name (e.g. `task_1_1`) |
| `$USER_NAME` | The student's username in the RMS |


## `deadlines`

Defines the timezone, submission policy, and the full schedule of task groups.

```yaml
deadlines:
  timezone: Europe/Moscow
  deadlines: hard
  max_submissions: 10       # optional
  submission_penalty: 0.1   # optional

  schedule:
    - group: week_1
      ...
```

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `timezone` | string | yes | — | Timezone name applied to all naive datetimes in the schedule (e.g. `Europe/Moscow`, `Europe/Berlin`, `UTC`). Should be in [IANA Time Zone Database](https://www.iana.org/time-zones) format. |
| `deadlines` | string | no | `hard` | Deadline scoring mode. `hard` or `interpolate`. See [Deadline modes](#deadline-modes). |
| `max_submissions` | integer | no | unlimited | Maximum number of submissions allowed per task. Must be a positive integer. |
| `submission_penalty` | float | no | `0` | Score penalty applied per extra submission beyond the limit. Must be non-negative. |
| `schedule` | list | yes | — | Ordered list of task groups. See [`schedule` group](#schedule-group). |

### Deadline modes

| Mode | Behaviour |
|---|---|
| `hard` | Full score is awarded before the deadline; zero after. Each `step` defines an intermediate hard cutoff at a reduced multiplier. |
| `interpolate` | Score is linearly interpolated between steps. Students receive a continuously decreasing score as time passes. |


## `schedule` group

Each entry in `schedule` represents a logical group of tasks (e.g. a week, a topic, a homework set).

```yaml
schedule:
  - group: week_1
    start: 2025-01-01 10:00
    steps:
      0.5: 2025-01-08 23:59
    end: 2025-01-15 23:59
    enabled: true
    tasks:
      - task: task_1_1
        score: 10
      - task: task_1_2
        score: 10
        is_bonus: true
```

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `group` | string | yes | — | Unique group identifier. Must be unique across all groups in the schedule. |
| `start` | datetime | yes | — | When the group opens. Format: `YYYY-MM-DD HH:MM`. Timezone from `deadlines.timezone` is applied. |
| `end` | datetime or timedelta | **yes** | — | Deadline after which score drops to zero. See [Date and timedelta formats](#date-and-timedelta-formats). Must be after `start`. |
| `steps` | dict[float, datetime or timedelta] | no | `{}` | Intermediate score multiplier cutoffs. Keys are multipliers (0–1); values are dates or timedeltas. See [Steps](#steps). |
| `enabled` | boolean | no | `true` | Whether the group is visible and active. Set to `false` to hide the group from students. |
| `tasks` | list | no | `[]` | Tasks belonging to this group. See [`task`](#task). |

### Steps

`steps` is a mapping from a **score multiplier** (float between 0 and 1, exclusive) to a **deadline** (datetime or timedelta from `start`).

```yaml
steps:
  0.5: 2025-01-08 23:59   # after this date, max score is 50%
  0.3: 13d 05:00:00       # 13 days and 5 hours after start, max score drops to 30%
```

- Steps must be in **chronological order** (each step deadline must be after the previous one).
- All step deadlines must be after `start` and before `end`.
- In `hard` mode: each step is a hard cutoff — the multiplier drops instantly at the step deadline.
- In `interpolate` mode: score is linearly interpolated between consecutive step boundaries.

### Date and timedelta formats

| Format | Example | Description |
|---|---|---|
| Absolute datetime | `2025-01-15 23:59` | Parsed as `YYYY-MM-DD HH:MM`; timezone from `deadlines.timezone` is applied. |
| Timedelta | `13d 05:00:00` | Duration relative to the group's `start`. Format: `Dd HH:MM:SS`. |


## `task`

Each task entry inside a group's `tasks` list.

```yaml
tasks:
  - task: task_1_1
    score: 10
    enabled: true
    is_bonus: false
    is_large: false
    is_special: false
    min_score: 0
    url: https://example.com/task-description
```

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `task` | string | yes | — | Unique task identifier. Must be unique across **all** tasks in the entire schedule. |
| `score` | integer | yes | — | Maximum score awarded for this task. |
| `enabled` | boolean | no | `true` | Whether the task is active. Disabled tasks are hidden from students and checker export. |
| `is_bonus` | boolean | no | `false` | Marks the task as a bonus task. Bonus scores are counted separately and do not affect the base percentage. |
| `is_large` | boolean | no | `false` | Marks the task as a large (major) task. Used in grade computation via `large_count`. |
| `is_special` | boolean | no | `false` | Marks the task as special. Special tasks are displayed differently in the UI. |
| `min_score` | integer | no | `0` | Minimum score required to count this task as completed (relevant for `is_large` tasks and `large_count` in grading). |
| `url` | string | no | `null` | Optional direct URL to the task description. Overrides the `task_url_template` for this task. Must be a valid HTTP/HTTPS URL. |


## `grades`

Optional section that defines how a final grade is computed from a student's accumulated scores.

```yaml
grades:
  grades:
    5:
      - { "percent": 90, "large_count": 1 }
      - { "percent": 80, "large_count": 2 }
    4:
      - { "percent": 80, "large_count": 1 }
      - { "percent": 70, "large_count": 2 }
    3:
      - { "percent": 60 }
    2:
      - { "": 0 }
```

| Field | Type | Required | Description |
|---|---|---|---|
| `grades` | dict[integer, list[dict]] | **yes** (if section present) | Mapping from grade value to a list of condition sets. |

### Grade evaluation logic

Grades are evaluated from **highest to lowest**. The first grade whose conditions are satisfied is assigned to the student.

Each grade value maps to a **list of condition sets** (disjunctive normal form):

- A student satisfies a grade if they satisfy **at least one** condition set in the list (logical OR).
- A condition set is satisfied if **all** key-value pairs in the dict are met (logical AND).
- Each key is a **path** into the student's score data; each value is the **minimum** required value.

### Built-in score paths

| Path | Type | Description |
|---|---|---|
| `percent` | float | Percentage of total non-bonus score earned (0–100). |
| `total_score` | integer | Raw total score earned. |
| `large_count` | integer | Number of large tasks (`is_large: true`) completed above their `min_score`. |
| `scores/<task_name>` | integer | Score for a specific task, e.g. `scores/task_1_1`. |

### Catch-all (lowest grade)

Use an empty key `""` with value `0` to create a condition that always matches — useful for the lowest grade:

```yaml
2:
  - { "": 0 }
```

## Validation rules

- `version` must be `1`.
- `task_url_template` must start with `http://` or `https://`.
- `timezone` must be a valid IANA timezone name.
- `max_submissions` must be a positive integer if specified.
- `submission_penalty` must be non-negative.
- All `group` names must be unique within the schedule.
- All `task` names must be unique across the entire schedule (not just within a group).
- `end` must be after `start`.
- Each `step` deadline must be strictly after the previous step (or `start`) and before `end`.
- Step timedeltas must be positive.
- `score` and `min_score` are integers; `min_score` defaults to `0`.
- `url` on a task must be a valid HTTP/HTTPS URL if specified.


## Complete example

```yaml
version: 1
status: in_progress

ui:
  task_url_template: https://rms.example.com/course/students/$USER_NAME/$GROUP_NAME/$TASK_NAME
  links:
    "TG Channel": https://t.me/joinchat/example
    "TG Chat": https://t.me/joinchat/example2
    "LMS": https://lms.example.com/

deadlines:
  timezone: Europe/Moscow
  deadlines: hard
  max_submissions: 10
  submission_penalty: 0.1

  schedule:
    - group: week_1
      start: 2025-01-01 10:00
      steps:
        0.5: 2025-01-08 23:59
      end: 2025-01-15 23:59
      enabled: true
      tasks:
        - task: task_1_1
          score: 10
        - task: task_1_2
          score: 10
        - task: task_1_3
          score: 20
          is_large: true
          min_score: 10

    - group: week_2
      start: 2025-01-08 10:00
      steps:
        0.5: 2025-01-15 23:59
        0.3: 13d 05:00:00
      end: 13d 05:59:59
      enabled: true
      tasks:
        - task: task_2_1
          score: 15
        - task: task_2_2
          score: 15
          is_bonus: true
          url: https://example.com/task-2-2-description

grades:
  grades:
    5:
      - { "percent": 90, "large_count": 1 }
      - { "percent": 80, "large_count": 2 }
    4:
      - { "percent": 75, "large_count": 1 }
      - { "percent": 65, "large_count": 2 }
    3:
      - { "percent": 60 }
    2:
      - { "": 0 }
```

# API and Testing Script Interface 

## Checker script 

Please refer to Manytask plugin if you are using Checker (look for `plugins/manytask.py` in Checker folder).

## Custom script 

However, you can implement your own checker just use the Manytask api. Note that all the endpoints require `Authorization: Bearer <token>` or `Authorization: <token>` (deprecated) header contain `MANYTASK_COURSE_TOKEN`, to validate it's authorized checker. The `<course_name>` is the unique name of the course.
  
| method | api endpoint                | description                                       | required in body                                                          | optional in body                                                                                                      | return                                                               |
|--------|-----------------------------|---------------------------------------------------|---------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------|----------------------------------------------------------------------|
| POST   | `/api/<course_name>/report`               | set student's score (optionally save source code) | `task`, `username`, `user_id` (deprecated), `score` (if None - max score) | `check_deadline`, `allow_reduction`, `submit_time` (`%Y-%m-%d %H:%M:%S%z`), `commit_time` (deprecated), multipart/form-data source files | `user_id`, `username`, `task`, `score`, `commit_time`, `submit_time` |
| GET    | `/api/<course_name>/score`                | get student's score                               | `task`, `username`, `user_id` (deprecated)                                | -                                                                                                                     | `user_id`, `username`, `task`, `score`                               |
| POST   | `/api/<course_name>/update_config`        | update course to sent `config`                    | \*config yaml file\* (see examples)                                       | -                                                                                                                     | -                                                                    |
| GET    | `/api/<course_name>/ping`                 | validate course-token without side effects        | -                                                                         | -                                                                                                                     | `course`, `ok`                                                       |
| GET    | `/api/<course_name>/is_admin`             | check whether RMS user is a course admin          | `rms_username` (query string, RMS/GitLab login)                           | -                                                                                                                     | `rms_username`, `is_admin`                                           |
| GET    | `/api/<course_name>/deadlines`            | machine-readable list of tasks with deadlines     | -                                                                         | -                                                                                                                     | `course`, `tasks` (list of `{task_name, group, deadline, score, is_bonus, is_large}`) |

## Errors

Every endpoint under `/api/` reports failures as plain text, so a failing CI job says
what actually went wrong instead of returning an HTML error page. The body is the
message itself, optionally followed by a `Hint:` line:

```
Invalid course token
Hint: The course token was not accepted. Check that it belongs to this exact course (in the checker it is the `report_token` argument, usually the MANYTASK_TOKEN CI secret).
```

The first line is the specific reason; the `Hint:` line is added for the statuses
below and suggests the likely misconfiguration.

| status | typical cause for `/report` |
|---|---|
| `400 Bad Request` | `score` is not a number in `[0.0, 2.0]`, or a required field (`task`, `username`/`user_id`) is missing. |
| `403 Forbidden` | Token missing, empty or not matching the course token. |
| `404 Not Found` | Wrong URL, or unknown course, task or user. The task must exist and be enabled in `.manytask.yml`, and the student must be signed up for the course. |
| `405 Method Not Allowed` | `/report` was called with something other than `POST`. |
| `409 Conflict` | The course is finished, so scores can no longer be changed. |

Use `GET /api/<course_name>/ping` to check the URL and the token without side effects.

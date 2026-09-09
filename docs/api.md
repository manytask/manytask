# API and Testing Script Interface 

## Checker script 

Please refer to Manytask plugin if you are using Checker (look for `plugins/manytask.py` in Checker folder).

## Custom script 

However, you can implement your own checker just use the Manytask api. Note that all the endpoints require `Authorization: Bearer <token>` or `Authorization: <token>` (deprecated) header contain `MANYTASK_COURSE_TOKEN`, to validate it's authorized checker. The `<course_name>` is the unique name of the course.
  
| method | api endpoint                | description                                       | required in body                                                          | optional in body                                                                                                      | return                                                               |
|--------|-----------------------------|---------------------------------------------------|---------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------|----------------------------------------------------------------------|
| POST   | `/api/<course_name>/report`               | set student's score (optionally save source code); signed integers are accepted as final scores | `task`, `username`, `user_id` (deprecated), `score` (if None - max score) | `check_deadline`, `allow_reduction` (required to persist a negative score), `submit_time` (`%Y-%m-%d %H:%M:%S%z`), `commit_time` (deprecated), multipart/form-data source files | `user_id`, `username`, `task`, `score`, `commit_time`, `submit_time` |
| GET    | `/api/<course_name>/score`                | get student's score                               | `task`, `username`, `user_id` (deprecated)                                | -                                                                                                                     | `user_id`, `username`, `task`, `score`                               |
| POST   | `/api/<course_name>/update_config`        | update course to sent `config`                    | \*config yaml file\* (see examples)                                       | -                                                                                                                     | -                                                                    |
| GET    | `/api/<course_name>/ping`                 | validate course-token without side effects        | -                                                                         | -                                                                                                                     | `course`, `ok`                                                       |
| GET    | `/api/<course_name>/is_admin`             | check whether RMS user is a course admin          | `rms_username` (query string, RMS/GitLab login)                           | -                                                                                                                     | `rms_username`, `is_admin`                                           |
| GET    | `/api/<course_name>/deadlines`            | machine-readable list of tasks with deadlines     | -                                                                         | -                                                                                                                     | `course`, `tasks` (list of `{task_name, group, deadline, score, is_bonus, is_large}`) |
| POST   | `/api/<course_name>/enroll`               | enroll a manytask user on the course (create their `users_on_courses` row and RMS project); user must already exist, see `POST /api/users` below | `username` | `course_admin` (bool, default `false`) | `username`, `course`, `is_course_admin`, `project` (`<students_group>/<username>`) |

## Instance-scoped API (external registration)

`POST /api/users` is instance-scoped (not tied to a course), so it lives directly under `/api` and is
authorized differently: it requires an `Authorization: Bearer <token>` header containing
`MANYTASK_API_TOKEN` (set as an environment variable for the whole manytask instance). If
`MANYTASK_API_TOKEN` is not set, the endpoint always returns 403.

`POST /api/<course_name>/enroll` (see the table above) also accepts `MANYTASK_API_TOKEN` in addition to
the course token, so an external registration flow (e.g. a bot) can enroll a user on a course using only
the instance token, without knowing any individual course's token.

| method | api endpoint  | description                                                                 | required in body                                          | optional in body                                                                     | return                                              |
|--------|---------------|------------------------------------------------------------------------------|-------------------------------------------------------------|-----------------------------------------------------------------------------------|------------------------------------------------------|
| POST   | `/api/users`  | create or update a manytask user from an already-existing RMS (GitLab) user | exactly one of `rms_id`, `username` (to look up the RMS user) | `first_name`, `last_name` (derived from the RMS user's name if omitted), `auth_id` (defaults to `rms_id` when `rms == gitlab`) | `user_id`, `username`, `rms_id`, `created` |

Calling `POST /api/users` before a student's first login makes `/signup_finish` skip the "enter your
name" form on that first OAuth login, since the user row (matched by `auth_id`) already exists.

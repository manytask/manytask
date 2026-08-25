# API and Testing Script Interface 

## Checker script 

Please refer to Manytask plugin if you are using Checker (look for `plugins/manytask.py` in Checker folder).

## Tokens

Every endpoint below requires `Authorization: Bearer <token>` or `Authorization: <token>` (deprecated).
There are two kinds of token, and they are not interchangeable.

**Course token** (`MANYTASK_COURSE_TOKEN`) is the course-wide credential. It may report scores for any
student, read any score, and change the course config. Keep it in the private repository only — never in
a group or project CI/CD variable that student pipelines can read.

**Personal student token** is issued per student per course. It only acts on behalf of its owner:
reporting a score for anybody else returns `403`, and the course-wide endpoints refuse it outright. A
student who extracts their own token from their pipeline can at worst inflate their own results, which
is why student pipelines get a personal token instead of the course token.

Manytask writes each student's personal token into the `MANYTASK_TOKEN` CI/CD variable of their
repository when the repository is created. A student can copy, re-publish or regenerate the token from
the "My API token" panel on the course page. Regenerating invalidates the previous token immediately.

Personal tokens are deliberately weaker than the course token on `/report`:

- `check_deadline` is always on, `allow_reduction` is always off, and a submitted `submit_time` is
  ignored in favour of the server time, so the deadline multiplier cannot be side-stepped;
- the reported score is capped at twice the task's max score, the same ceiling the fractional `score`
  form already imposes.

## Custom script 

You can implement your own checker and just use the Manytask api. The `<course_name>` is the unique name
of the course.
  
| method | api endpoint                | description                                       | token                | required in body                                                          | optional in body                                                                                                      | return                                                               |
|--------|-----------------------------|---------------------------------------------------|----------------------|---------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------|----------------------------------------------------------------------|
| POST   | `/api/<course_name>/report`               | set student's score (optionally save source code); signed integers are accepted as final scores | course or personal | `task`, `username`, `user_id` (deprecated, both default to the personal token's owner), `score` (if None - max score) | `check_deadline`, `allow_reduction` (required to persist a negative score), `submit_time` (`%Y-%m-%d %H:%M:%S%z`), `commit_time` (deprecated), multipart/form-data source files | `user_id`, `username`, `task`, `score`, `commit_time`, `submit_time` |
| GET    | `/api/<course_name>/score`                | get student's score                               | course or personal | `task`, `username`, `user_id` (deprecated, both default to the personal token's owner) | -                                                                                                                     | `user_id`, `username`, `task`, `score`                               |
| POST   | `/api/<course_name>/update_config`        | update course to sent `config`                    | course only          | \*config yaml file\* (see examples)                                       | -                                                                                                                     | -                                                                    |
| GET    | `/api/<course_name>/ping`                 | validate a token without side effects             | course or personal | -                                                                         | -                                                                                                                     | `course`, `ok`, `scope` (`course`/`student`), `username`             |
| GET    | `/api/<course_name>/is_admin`             | check whether RMS user is a course admin          | course only          | `rms_username` (query string, RMS/GitLab login)                           | -                                                                                                                     | `rms_username`, `is_admin`                                           |
| GET    | `/api/<course_name>/deadlines`            | machine-readable list of tasks with deadlines     | course or personal | -                                                                         | -                                                                                                                     | `course`, `tasks` (list of `{task_name, group, deadline, score, is_bonus, is_large}`) |

### Personal token management

These endpoints are for the signed-in student in the browser, they use the session and not a token.

| method | api endpoint                                    | description                                                        | return                                                            |
|--------|-------------------------------------------------|--------------------------------------------------------------------|-------------------------------------------------------------------|
| GET    | `/api/<course_name>/student_token`              | read own personal token, issuing one on first call                 | `course`, `username`, `token`, `ci_variable`, `published_to_repo` |
| POST   | `/api/<course_name>/student_token/publish`      | write own token into the CI/CD variables of own repository         | same as above                                                      |
| POST   | `/api/<course_name>/student_token/rotate`       | issue a new token, invalidate the old one, re-publish it           | same as above                                                      |

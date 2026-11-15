# API and Testing Script Interface 

## Checker script 

Please refer to Manytask plugin if you are using Checker (look for `plugins/manytask.py` in Checker folder).

## Custom script 

However, you can implement your own checker just use the Manytask api. Note that all the endpoints require `Authorization: Bearer <token>` or `Authorization: <token>` (deprecated) header contain `MANYTASK_COURSE_TOKEN`, to validate it's authorized checker. The `<course_name>` is the unique name of the course.
  
| method | api endpoint                | description                                       | required in body                                                          | optional in body                                                                                                      | return                                                               |
|--------|-----------------------------|---------------------------------------------------|---------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------|----------------------------------------------------------------------|
| POST   | `/api/<course_name>/report`               | report a submission; only `OK` updates the score; signed integers are accepted as final scores | `task`, `username`, `user_id` (deprecated), `score` (if None - max score) | `verdict` (defaults to `OK`; all submissions are stored; non-`OK` submissions do not update scores or grades), `check_deadline`, `allow_reduction` (required to persist a negative score), `submit_time` (`%Y-%m-%d %H:%M:%S%z`), `commit_time` (deprecated), multipart/form-data source files | `user_id`, `username`, `task`, `score` (unchanged for non-`OK`), `verdict`, `commit_time`, `submit_time` |
| GET    | `/api/<course_name>/score`                | get student's score                               | `task`, `username`, `user_id` (deprecated)                                | -                                                                                                                     | `user_id`, `username`, `task`, `score`                               |
| POST   | `/api/<course_name>/update_config`        | update course to sent `config`                    | \*config yaml file\* (see examples)                                       | -                                                                                                                     | -                                                                    |
| GET    | `/api/<course_name>/ping`                 | validate course-token without side effects        | -                                                                         | -                                                                                                                     | `course`, `ok`                                                       |
| GET    | `/api/<course_name>/is_admin`             | check whether RMS user is a course admin          | `rms_username` (query string, RMS/GitLab login)                           | -                                                                                                                     | `rms_username`, `is_admin`                                           |
| GET    | `/api/<course_name>/deadlines`            | machine-readable list of tasks with deadlines     | -                                                                         | -                                                                                                                     | `course`, `tasks` (list of `{task_name, group, deadline, score, is_bonus, is_large}`) |

Every accepted `/report` request appends a row to `submissions`, linked to the existing
`UserOnCourse` enrollment and the task. The enrollment supplies the user and course;
reports do not enroll users automatically. Each row stores the verdict, reported points
before deadline penalties (`score`, unavailable for non-`OK` verdicts), the supplied
submission timestamp (`submit_time`), and the database receipt timestamp (`received_at`).
The response's `score` remains the current aggregate score. Submission insertion and any
`OK` score update commit together. Repeated reports remain separate attempts, even if
their timestamps match or their score is lower than the best score. History starts with
this migration; existing grades cannot reconstruct earlier attempts. Source files,
a history browsing endpoint, and a history UI are outside this stage.

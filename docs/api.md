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
| GET    | `/api/<course_name>/is_admin`             | check whether user is a course admin              | `username` (query string)                                                 | -                                                                                                                     | `username`, `is_admin`                                               |
| GET    | `/api/<course_name>/deadlines`            | machine-readable list of tasks with deadlines     | -                                                                         | -                                                                                                                     | `course`, `tasks` (list of `{task_name, group, deadline, score}`)    |

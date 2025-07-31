## API and Testing Script Interface 

### Checker script 

There is already implemented python lib [manytask/checker](https://github.com/manytask/checker) for testing students' solutions with manytask integration. The basic idea: `checker` is a script running in a gitlab-ci that performs students' solutions testing and call `manytask` api to set scores achieved;
More info in the [manytask/checker repo](https://github.com/manytask/checker);

### Custom script 

However, you can implement your own checker just use the Manytask api. Note that all the endpoints require `Authorization: Bearer <token>` or `Authorization: <token>` (deprecated) header contain `MANYTASK_COURSE_TOKEN`, to validate it's authorized checker. The `<course_name>` is the unique name of the course.
  
| method | api endpoint                | description                                       | required in body                                                          | optional in body                                                                                                      | return                                                               |
|--------|-----------------------------|---------------------------------------------------|---------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------|----------------------------------------------------------------------|
| POST   | `/api/<course_name>/report`               | set student's score (optionally save source code) | `task`, `username`, `user_id` (deprecated), `score` (if None - max score) | `check_deadline`, `submit_time` (`%Y-%m-%d %H:%M:%S%z`), `commit_time` (deprecated), multipart/form-data source files | `user_id`, `username`, `task`, `score`, `commit_time`, `submit_time` |
| GET    | `/api/<course_name>/score`                | get student's score                               | `task`, `username`, `user_id` (deprecated)                                | -                                                                                                                     | `user_id`, `username`, `task`, `score`                               |
| POST   | `/api/<course_name>/update_config`        | update course to sent `config`                    | \*config yaml file\* (see examples)                                       | -                                                                                                                     | -                                                                    |
| POST   | `/api/<course_name>/update_cache`         | update cached scores for all users                | -                                                                         | -                                                                                                                     | -                                                                    |

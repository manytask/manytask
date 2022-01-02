# manytask

Small application for manage course: set students' scores and so on


## Run application

### Local (debug) 
```shell
FLASK_ENV=development FLASK_APP=manytask.main:create_app python -m flask run --host=0.0.0.0 --port=8000 --reload --without-threads
```

### Docker (production manytask only)
```shell
docker build -t manytask .
docker run -p "8000:8000" --name manytask manytask
```

### Docker-compose (production with certs)
```shell
docker-compose up --build
```



## Testing script api

### Standard script 

There is already implemented lib [yandexdataschool/checker](https://github.com/yandexdataschool/checker) for testing.  
The basic idea: `checker` is a script running in a gitlab-ci that performs students' solutions testing and call `manytask` api to set scores achieved;
More info in the `checker` repo;

### Custom script 
However, you can implement your own checker just following `manytask` api:

* All the endpoints require `Authorization: Bearer <token>` header contain `TESTER_TOKEN`, to validate it's authorized checker. 

[//]: # (* POST `/api/report` to set score  )

[//]: # (  required in body: `task`, `user_id` &#40;gitlab&#41;, `score`  )

[//]: # (  optional in body: `check_deadline`, `commit_time` &#40;`%Y-%m-%d %H:%M:%S%z`&#41;  )

[//]: # (  return json dict: `user_id`, `username`, `task`, `score`, `commit_time`, `submit_time`  )

[//]: # (* GET `/api/score` to get score  )

[//]: # (  required in body: `task`, `user_id` &#40;gitlab&#41;  )

[//]: # (  return json dict: `user_id`, `username`, `task`, `score`  )

[//]: # (* GET `/api/sync_task_columns` to update course to `deadlines`  )

[//]: # (  required json body &#40;??? CHECK IT ???&#41;)

[//]: # (* GET `/api/update_cached_scores` to update cached scores for all users  )

[//]: # (  required in body: `task`, `user_id` &#40;gitlab&#41;  )

[//]: # (  return json dict: `user_id`, `username`, `task`, `score`  )
  
| method | api endpoint | description         | required in body           | optional in body | return |
|--------|--------------|---------------------|----------------------------|------------------|--------|
| POST   | `/api/report` | set student's score | `task`, `user_id` (gitlab), `score` | `check_deadline`, `commit_time` (`%Y-%m-%d %H:%M:%S%z`) | `user_id`, `username`, `task`, `score`, `commit_time`, `submit_time` |
| GET    | `/api/score` | get student's score | `task`, `user_id` (gitlab) |                  | `user_id`, `username`, `task`, `score`|
| GET    | `/api/sync_task_columns` | update course to `deadlines` | \*deadlines\* |                  |        |
| GET    | `/api/update_cached_scores` | update cached scores for all users | `task`, `user_id` (gitlab) |                  |        |
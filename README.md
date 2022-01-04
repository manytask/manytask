# manytask

Small application for manage course: set students' scores and so on


## Setup a new course 

```shell
git clone https://github.com/yandexdataschool/manytask
cp .env.example .env
```


## Run application

### Local (debug) 
```shell
FLASK_ENV=development FLASK_APP=manytask.main:create_app python -m flask run --host=0.0.0.0 --port=5000 --reload --without-threads
```

### Docker (production manytask only)
```shell
docker build -t manytask .
docker run \
    --port "5000:5000" \
    --name manytask \
    --env-file .env \
    --restart "unless-stopped"
#    --volume "$PERSISTENT_VOLUME:$CACHE_MP"
    manytask
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



## About

Originally was developed at gitlab as [shad-ts](https://gitlab.com/slon/shad-ts/) by [@slon](https://github.com/slon) for [Yandex School of Data Analysis](https://yandexdataschool.com/) 

### Acknowledgment 

* [Fedor Korotkiy](https://github.com/slon) aka @slon - development of the very first version, 2017-2018
* Belova Ilariia - updates for python course, 2018
* [Vadim Mazaev](https://github.com/GreenRiverRUS) - updates for python course, 2019-2020
* Nikita Bondartsev - minor updates for python course, 2020-2021
* [Konstantin Chernyshev](https://github.com/k4black) - updates for python course, refactoring and moving to github, 2020-2021
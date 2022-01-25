# manytask

Small application for manage course: set students' scores and so on


## Setup

Clone repo
```shell
git clone https://github.com/yandexdataschool/manytask
```

Create `.env` file with dev/production environment
```shell
cp .env.example .env
```


## Run application

### Debug and development 

First you need to create `.env` file with debug environment

* gitlab oauth credentials can be taken from `test` app here: [gitlab.manytask.org/admin/applications](https://gitlab.manytask.org/admin/applications/)


#### Local

Create new venv and install requirements 
```shell
python -m venv .venv
source .venv/bin/activate
python -m pip install -U -r requirements.txt
```
Run it
```shell
CACHE_DIR=.tmp/cache/ FLASK_ENV=development FLASK_APP=manytask.main:create_app python -m flask run --host=0.0.0.0 --port=5000 --reload --without-threads
```

#### Docker (manytask only)
```shell
docker build -t manytask .
docker run \
    --port "5000:5000" \
    --name manytask \
    --env-file .env \
    --env FLASK_ENV=development \ 
    manytask
```

#### Docker-compose (development)
```shell
docker-compose -f docker-compose.yml -f docker-compose.override.yml up --build
```
or just
```shell
docker-compose up --build
```

### Production 

#### Docker (manytask only)
```shell
docker build -t manytask .
docker run \
    --port "5000:5000" \
    --name manytask \
    --env-file .env \
    --env FLASK_ENV=production \ 
    --restart "unless-stopped" \
    manytask
```


#### Docker-compose (manytask with certs)
```shell
docker-compose -f docker-compose.yml -f docker-compose.production.yml up --build
```



## Testing script api

### Standard script 

There is already implemented lib [yandexdataschool/checker](https://github.com/yandexdataschool/checker) for testing.  
The basic idea: `checker` is a script running in a gitlab-ci that performs students' solutions testing and call `manytask` api to set scores achieved;
More info in the `checker` repo;

### Custom script 
However, you can implement your own checker just following `manytask` api:

* All the endpoints require `Authorization: Bearer <token>` header contain `TESTER_TOKEN`, to validate it's authorized checker. 
* Or, alternatively, being admin (session with admin field) 
  
| method | api endpoint                | description                          | required in body                                              | optional in body                                        | return                                                               |
|--------|-----------------------------|--------------------------------------|---------------------------------------------------------------|---------------------------------------------------------|----------------------------------------------------------------------|
| POST   | `/api/report`               | set student's score                  | `task`, `user_id` (gitlab), `score`                           | `check_deadline`, `commit_time` (`%Y-%m-%d %H:%M:%S%z`) | `user_id`, `username`, `task`, `score`, `commit_time`, `submit_time` |
| GET    | `/api/score`                | get student's score                  | `task`, `user_id` (gitlab)                                    | -                                                       | `user_id`, `username`, `task`, `score`                               |
| GET    | `/api/sync_task_columns`    | update course to `deadlines`         | \*deadlines\*                                                 | -                                                       | -                                                                    |
| GET    | `/api/update_cached_scores` | update cached scores for all users   | `task`, `user_id` (gitlab)                                    | -                                                       | -                                                                    |
| POST   | `/api/report_source`        | save student's solution source files | `task`, `user_id` (gitlab) + multipart/form-data source files | -                                                       | -                                                                    |
| GET    | `/api/solutions`            | get all solutions for the task       | `task`                                                        | -                                                       | zip archive file with solutions                                      |



## About

Originally was developed at gitlab as [shad-ts](https://gitlab.com/slon/shad-ts/) by [@slon](https://github.com/slon) for [Yandex School of Data Analysis](https://yandexdataschool.com/) 

### Acknowledgment 

* [Fedor Korotkiy](https://github.com/slon) - development of the very first version, 2017-2018
* [Belova Ilariia](https://github.com/jhilary) - updates for python course, 2018
* [Vadim Mazaev](https://github.com/GreenRiverRUS) - updates for python course, 2019-2020
* Nikita Bondartsev - minor updates for python course, 2020-2021
* [Konstantin Chernyshev](https://github.com/k4black) - updates for python course, massive refactor and moving to github, 2020-2021

# manytask

[![Test](https://github.com/yandexdataschool/manytask/actions/workflows/test.yml/badge.svg)](https://github.com/yandexdataschool/manytask/actions/workflows/test.yml)
[![Publish](https://github.com/yandexdataschool/manytask/actions/workflows/publish.yml/badge.svg)](https://github.com/yandexdataschool/manytask/actions/workflows/publish.yml)
[![codecov](https://codecov.io/gh/yandexdataschool/manytask/branch/main/graph/badge.svg?token=3F9J850FX2)](https://codecov.io/gh/yandexdataschool/manytask)
[![github](https://img.shields.io/github/v/release/yandexdataschool/manytask?logo=github&display_name=tag&sort=semver)](https://github.com/yandexdataschool/manytask/releases)
[![docker](https://img.shields.io/docker/v/manytask/manytask?label=docker&logo=docker&sort=semver)](https://hub.docker.com/manytask/manytask?sort=semver)


Small web application for managing courses: store students' grades, maintain deadlines, provide scoreboard etc.

---

## How it works

In a nutshell, `manytask` is a wrapper around google sheets (as database, storing students' scores) and some bunch of functions to interact with gitlab.

The full `manytask` setup roughly looks as follows

* `google sheet` - in readable format, store students' scores/grades
* self-hosted `gitlab` instance - storing repos with assignments and students' repo  
  * private repo - a repository with tasks, public and private tests, gold solutions, ect.
  * public repo - a repository available to students with tasks and solution templates
  * students' group - the group where `manytask` will create repositories for students  
    each students' repo - fork from public repo
* `gitlab runners` - place where students' solutions likely to be tested 
* `checker` script - some script to test students' solutions and push scores/grades to the `manytask`  
* `manytask` instance - web application managing students' grades (in google sheet) and deadlines (web page)  

So the main aims of `manytask`:
* Store and manage students' grades (store, provide, show, edit, ect)
* Show web page with grades and deadlines for student
* Manage users and repositories creation

Functions for which `manytask` is NOT intended:
* Test students' solutions
* Be language/course specific


So basically, manytask will store and display grades for you, but not test solutions' correctness in any way. 


---


## Setup

### Debug and development 

1. Clone repo
```shell
git clone https://github.com/yandexdataschool/manytask
```

2. Create `.env` file with dev environment
```shell
cp .env.example .env
```

3. Generate credentials for accessing google spreadsheets API (for [this test table](https://docs.google.com/spreadsheets/d/1cRah9NC5Nl7_NyzttC3Q5BtrnbdO6KyaG7gx5ZGusTM/edit#gid=0))
    1. Follow the steps described in [this article](https://medium.com/@a.marenkov/how-to-get-credentials-for-google-sheets-456b7e88c430)
    2. Base64 encode the created JSON key (using tools online, `base64` lib in python, or `btoa` function in the browser)
    3. Put it in the .env file by GDOC_ACCOUNT_CREDENTIALS_BASE64 key


### Production

Please refer to the [system setup documentation](./docs/system_setup.md).


## Run application

### Debug and development 

First you need to create `.env` file with debug environment

* gitlab oauth credentials can be taken from `test` app here: [gitlab.manytask.org/admin/applications](https://gitlab.manytask.org/admin/applications/)


#### Local (manytask only)

Create new venv and install requirements 
```shell
python -m venv .venv
source .venv/bin/activate
python -m pip install -U -r requirements.txt
```
Run it
```shell
CACHE_DIR=.tmp/cache/ FLASK_ENV=development FLASK_APP="manytask:create_app()" python -m flask run --host=0.0.0.0 --port=5050 --reload --without-threads
```

So, now it's available at `localhost:5050`

#### Docker (manytask only)
```shell
docker build --tag manytask .
docker rm manytask || true
docker run \
    --name manytask \
    --restart always \
    --publish "5050:5050" \
    --env-file .env \
    --env FLASK_ENV=development \
    manytask:latest
```

So, now it's available at `localhost:5050` 


#### Docker-compose (manytask only)
```shell
docker-compose -f docker-compose.development.yml up --build
```

So, now it's available at `localhost:5050` 


### Production 

Please, refer to the [production documentation](./docs/production.md).


## API and Testing Script Interface 

### Checker script 

There is already implemented python lib [yandexdataschool/checker](https://github.com/yandexdataschool/checker) for testing students' solutions with manytask integration.  
The basic idea: `checker` is a script running in a gitlab-ci that performs students' solutions testing and call `manytask` api to set scores achieved;
More info in the [yandexdataschool/checker repo](https://github.com/yandexdataschool/checker);

### Custom script 
However, you can implement your own checker just following `manytask` api:

* All the endpoints require `Authorization: Bearer <token>` or `Authorization: <token>` (deprecated) header contain `TESTER_TOKEN`, to validate it's authorized checker. 
* Or, alternatively, being admin (session with admin field) 
  
| method | api endpoint                | description                                       | required in body                                             | optional in body                                                                           | return                                                               |
|--------|-----------------------------|---------------------------------------------------|--------------------------------------------------------------|--------------------------------------------------------------------------------------------|----------------------------------------------------------------------|
| POST   | `/api/report`               | set student's score (optionally save source code) | `task`, `user_id` (gitlab), `score`                          | `check_deadline`, `commit_time` (`%Y-%m-%d %H:%M:%S%z`), multipart/form-data source files  | `user_id`, `username`, `task`, `score`, `commit_time`, `submit_time` |
| GET    | `/api/score`                | get student's score                               | `task`, `user_id` (gitlab)                                   | -                                                                                          | `user_id`, `username`, `task`, `score`                               |
| POST   | `/api/sync_task_columns`    | update course to `deadlines` (deprecated)         | \*deadlines json body\*                                      | -                                                                                          | -                                                                    |
| POST   | `/api/update_task_columns`  | update course to `deadlines`                      | \*deadlines yaml file\*                                      | -                                                                                          | -                                                                    |
| POST   | `/api/update_cached_scores` | update cached scores for all users                | -                                                            | -                                                                                          | -                                                                    |
| GET    | `/api/solutions`            | get all solutions for the task                    | `task`                                                       | -                                                                                          | zip archive file with solutions                                      |

Please refer [yandexdataschool/checker repo](https://github.com/yandexdataschool/checker) for instructions and  tips


## Additional information

Originally was developed at gitlab as [shad-ts](https://gitlab.com/slon/shad-ts/) by [Fedor Korotkiy](https://github.com/slon) for [Yandex School of Data Analysis](https://yandexdataschool.com/) 

### Acknowledgment 

* [Fedor Korotkiy](https://github.com/slon) - development of the very first version, 2017-2018
* [Ilariia_Belova](https://github.com/jhilary) - updates for python course, 2018
* [Vadim Mazaev](https://github.com/GreenRiverRUS) - updates for python course, 2019-2020
* Nikita Bondartsev - minor updates for python course, 2020-2021
* [Konstantin Chernyshev](https://github.com/k4black) - updates for python course, massive refactor and moving to github, 2020-2022

# Production setup

NB: First you need [manytask](https://github.com/yandexdataschool/manytask) up and running as checker is integrated with manytask only. 


Note: The following instructions assume you will use `checker`. If you are going to use custom `checker` with manytask - just read these docs for advices and approaches


---

## Pre-requirements 

Also, please refet to the [manytask setup docs -> new-course/new-semester](https://github.com/yandexdataschool/manytask/blob/main/docs/system_setup.md#new-course) to get and set  up:

* (Self-hosted) gitlab to work with
  * public repo with assignments for students 
  * private group for students' repo 
* Virtual Machine/Server
* Running manytask instance


## Layout

### Pre-required

Assuming you already have base layout for manytask system up' see [manytask setup docs -> new-course/new-semester](https://github.com/yandexdataschool/manytask/blob/main/docs/system_setup.md#new-course)

* course group (gitlab.manytask.org), e.g. [python](https://gitlab.manytask.org/python/)
* this year students group (gitlab.manytask.org), e.g. [python/students-fall-2022](https://gitlab.manytask.org/python/students-fall-2022/)
* this year public repo (gitlab.manytask.org or gitlab.com), e.g. [python/public-fall-2022](https://gitlab.manytask.org/python/public-fall-2022/)


### Setup layout

This script will rely on the following layouts of the course repositories

#### Private-repo (recommended)

The following layout allows you to push assignments automatically and fielder files students will see (for example hide all docker files or configs)

* `private` (gitlab.com or gitlab.manytask.org) - private repository with tasks, tests, ect - (hosted on gitlab.com (recommended) or gitlab.manytask.org) 
* `python/public-2022-fall` - public repository of this year with auto-exported tasks from `private-repo` (hosted on gitlab.manytask.org (recommended) or gitlab.com)
* private students' group e.g. `python/students-fall-2022`

So each student can see only `public-repo` repo and his/her own repo and can not access `private-repo`


#### Submodule (not recommended, but possible)

In this case auto-exporting of the tasks will not work. However, the task checking is still working.  

* `python/public-2022-fall` - public repository with assignments for students   
* `python/tests-2022-fall` - git `tests` submodule in `public-2022-fall`; private repository with tests and all private info 
* private students' group e.g. `python/students-fall-2022`

So each student can see only `tasks` repo and his/her own repo and can not access `tests`


### Final layout

So the recommended layout is the following 

`gitlab.com`
* [manytask/python](https://gitlab.com/manytask/python) - course group + group runner 
* [manytask/python/private](https://gitlab.com/manytask/python/private) - private course repo (all tasks and tests)

`gitlab.manytask.org`
* [python](https://gitlab.manytask.org/python/) - course group
* [python/students-fall-2022](https://gitlab.manytask.org/python/students-fall-2022/) - this year students group
* [python/public-fall-2022](https://gitlab.manytask.org/python/public-fall-2022/) - this year public repo (only public tasks and tests)


### Service account 

Also, you need to create service account with access to the students' repos.  

Go to manytask.gitlab.org -> [course_name] -> Settings -> Access Tokens  
Create named group token with write(!) repo and write(!) api permissions  
Save it and use later as `GITLAB_SERVICE_TOKEN`

It will automatically create user `[token_name]123_bot` with access to the group.  
The token can be used even for http access with `https://any_non_empty:$GITLAB_SERVICE_TOKEN@gitlab.manytask.org/path/to/the/repo.git` 


## Gitlab runners 

You need gitlab runners to run checker script. 

This system we try to utilize shared/group runners as much as possible to decrease the number of services to up and maintain for each separate course.  

### server

You need to obtain a server for your runners.  
The base requirements is `gitlab runner` and `docker`.

If you create runner in separate machine, it's better to use [self-hoster runner for linux](https://docs.gitlab.com/runner/install/linux-repository.html)  
If you create runner in shared machine, it's better to use [self-hoster runner in docker](https://docs.gitlab.com/runner/install/docker.html)  

Sometimes gitlab runner will leave outdated docker images, so you need to add in chrone: 
```shell
0 3 * * * /usr/bin/bash -c 'docker system prune'
```

Note: if you will use shared runners for your course - just check it's available, no need to create new ones.


### gitlab.com

You need 2 runners available for your private repository:  
* `build` - runner for docker building
* `private-tester` - to check reference-solution and test... tests

1. Go to the gitlab.com main group (e.g. [manytask](https://gitlab.com/manytask)) and add runners.  
   If you use private runners, go to your course group (e.g. [manytask/python](https://gitlab.com/manytask/python))  
   Group -> CI/CD settings -> Runners


2. Register runners, following [register gitlab-runner instruction](https://docs.gitlab.com/runner/register/#registering-runners)
   * Register `build` and `private-tester` runners
   * It will register them in gitlab and generate `config.toml` in `/srv/gitlab-runner/config` 
   * Copy generated tokens from `config.toml` (you need to keep only tokens) and update `config.toml` to match [examples/config.gitlab.toml](../examples/config.gitlab.toml)  
   * reload gitlab runner


3. Check group to have active runners (2 in total) 


### gitlab.manytask.org

Also you need runner to check students' solution 

For self-hosted gitlab instance it's even easier - we can use shared runners.  
If you'd like to use private runners - add it as group runners to your course group and disable shared runners.  


1. For shared runners go GitLab Admin Area -> Overview -> Runners


2. Register runners, following [register gitlab-runner instruction](https://docs.gitlab.com/runner/register/#registering-runners)
   * Register `public-tester` runner
   * It will register them in gitlab and generate `config.toml` in `/srv/gitlab-runner/config` 
   * Copy generated tokens from `config.toml` (you need to keep only tokens) and update `config.toml` to match [examples/config.gitlab.toml](../examples/config.gitlab.toml)  
   * reload gitlab runner


3. Check students group to have active runners (1 in total) 


### Security

Note: see [examples/config.gitlab.toml](../examples/config.gitlab.toml)  

Student can change `.gitlab-ci.yml` and get all secrets exposed. So in public runner we need to compare it with original `.gitlab-ci.yml` file


## docker

Gitlab runner operates and run dockers. So you need to create docker where test will be executed 

It's convenient to have 2 dockers: 

* `base` - 'empty' docker with libs and apps you will use for testing (as well as `checker` pkg). Students can use it to run and test course tasks in docker
* `testenv` - based on `base` docker with copied tests 

see [examples/base.docker](../examples/base.docker) and  [examples/testenv.docker](../examples/testenv.docker)

#### Docker registry 

Currently, the main registry is docker yandex cloud registry (credentials: @slon)  
Be ready to set `DOCKER_AUTH_CONFIG` to gitlab-runners config (see [examples/config.gitlab.toml](../examples/config.gitlab.toml))


## gitlab-ci

You need to create gitlab-ci config files for gitlab to run `checker` script commands. 

We offer to create 2 separate files:
* `.gitlab-ci.yml` - file with jobs to run in students repositories:  
    * `grade` job to general solutions testing 
    * `grade-mrs` job to test students' email
    * `check` job to check students contributions in the repo (run updated tests against authors' solutions)
* `.releaser-ci.yml` - file with jobs to run in private repo - test tasks, test tests, test course tools etc.
    * `build` job to build base docker 
    * `check-tools` some jobs to check course tools if any
    * `check-tasks` job with task testing 
    * `deploy` jobs to deploy testenv docker, manytask deadlines, public repo 
    * `manual` some jobs to run manually by tutors  

see [examples/.gitlab-ci.yml](../examples/.gitlab-ci.yml) and  [examples/.releaser-ci.yml](../examples/.releaser-ci.yml)

So you need to select in private repo CI/CD Settings `.releaser-ci.yml` as ci file.


## Repo settings and Variables 


* In gitlab.com -> [course_group]  
  Set variables for checker and gitlab runner to operate   
  * DOCKER_AUTH_CONFIG (none),  
  * TESTER_TOKEN (protected, masked),  
  * GITLAB_SERVICE_TOKEN (protected, masked)  


* In gitlab.com -> [course_group] -> private  
  Set CI/CD settings: 
  * `.releaser-ci.yml` as ci file  
  * strategy - clone   
  * Scheduling for each day time just after the lecture (to auto publish assignments)


* In gitlab.manytask.org -> [course_group]  
  Set variables for checker and gitlab runner to operate   
  * DOCKER_AUTH_CONFIG (none),  
  * TESTER_TOKEN (masked),  
  * GITLAB_SERVICE_TOKEN (masked) 

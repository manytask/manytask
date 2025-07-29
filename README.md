# Manytask

[![Test](https://github.com/manytask/manytask/actions/workflows/test.yml/badge.svg)](https://github.com/manytask/manytask/actions/workflows/test.yml)
[![Publish](https://github.com/manytask/manytask/actions/workflows/publish.yml/badge.svg)](https://github.com/manytask/manytask/actions/workflows/publish.yml)
[![codecov](https://codecov.io/gh/yandexdataschool/manytask/branch/main/graph/badge.svg?token=3F9J850FX2)](https://codecov.io/gh/yandexdataschool/manytask)
[![github](https://img.shields.io/github/v/release/manytask/manytask?logo=github&display_name=tag&sort=semver)](https://github.com/manytask/manytask/releases)
[![docker](https://img.shields.io/docker/v/manytask/manytask?label=docker&logo=docker&sort=semver)](https://hub.docker.com/r/manytask/manytask)


Small web application for managing courses: store students' grades, maintain [deadlines](docs/deadline_schedule.md), provide scoreboard etc.

---

## How it works

For the students, `Manytask` is an app that stores scores and shows progress though courses. For the teacher, `Manytask` provides flexible interfaces to interact with Repository Management System, reveal tasks while the course progresses, set deadlines.

The full `Manytask` setup includes:

* A database to store student scores
* Self-hosted Repository Management System instance (currently only GitLab is supported).
* A set of courses, each of which is represented by:
  * Private repository - one per course - a teacher's repository that contains all the information on the course, including tasks, public and private tests, gold solutions, deadlines and testing environment, information on how to deploy the course. This repository contains all the data on the course, it is not visible by students.
  * Public repository - a repository available to students with tasks and solution templates. This repository is derived from private repository: only public tests, task formulations and templates are exported, while teacher's solutions and private tests are not. Teacher can also control which tasks are exported and which are not.
  * Group for students repositories - the group where Manytask will create repositories for students.  
    Each student will have their own repository, which is forked from public repository.
* CI/CD runners -  where students' solutions will be tested 
* Manytask Checker script - some script to test students' solutions and send scores/grades to the Manytask web application
* Manytask instance - web application managing students' grades and deadlines

So the main aims of Manytask:
* Store and manage students' grades (store, provide, show, edit, ect)
* Show web page with grades and deadlines for student
* Manage users and repositories creation

Functions for which Manytask is NOT intended:
* Test students' solutions
* Be language/course specific
* Substitute for Lerning Management System (LMS)

## Acknowledgment

Originally was developed at gitlab as [shad-ts](https://gitlab.com/slon/shad-ts/) by [Fedor Korotkiy](https://github.com/slon) for [Yandex School of Data Analysis](https://yandexdataschool.com/).

The project would not be possible without an effort of many developers, including:

* [Fedor Korotkiy](https://github.com/slon) - development of the very first version, 2017-2018
* [Ilariia_Belova](https://github.com/jhilary) - updates for python course, 2018
* [Vadim Mazaev](https://github.com/GreenRiverRUS) - updates for python course, 2019-2020
* Nikita Bondartsev - minor updates for python course, 2020-2021
* [Konstantin Chernyshev](https://github.com/k4black) - updates for python course, massive refactor and moving to github, 2020-2024

Current developers:

* [Sofia Anokhovskaya](https://github.com/cin-bun)
* [Ivan Gorobets](https://github.com/KIoppert)
* [Ivan Komarov](https://github.com/gagarinkomar)
* [Alexander Kostrikov](https://github.com/akostrikov)
* [Alexey Seliverstov](https://github.com/prawwtocol)
* [Artem Zhmurov](https://github.com/zhmurov)

And many others! Please, see [the full list of contributors](https://github.com/manytask/manytask/graphs/contributors).
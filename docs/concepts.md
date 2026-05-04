# Concepts

This page describes the main concepts used in the `Manytask` project - public/private repository, students' repositories, etc.

* **RMS** - repository management system where the teachers and students repositories are hosted. Currently GitLab and SourceCraft are supported

* **Manytask Web App** - a web application to manage students', repos, grades and deadlines. Stores information on courses, tasks, deadlines, as well as students progress and grades. Provides web-interface and API to read and manipulate these data. It also automatically creates repositories for students with tasks and solution templates when they register for the course. When used self-hosted gitlab instance, it can also register users.


* **Public Repo** - a public repository with tasks and solution templates. This is used as a starting point for the students, each of whom gets their own copy or fork of this repo (see Students Repositories below). The public repo can evolve as the course progresses and new tasks are added, in which case students need to update their working repo for the course.


* **Students' Repositories** - for each student on each course a copy of a public repo is created. Students see complete their repo by adding their implementations for tasks and commit-push their changes for testing and grading. If all tests are succesifull for a given task, their score is posted to the Manytask Web App via its API.


* **Private Repo** - a private (tutors) repository for the course with tasks, tests, templates and solutions (and anything extra teacher may need). This repository have to be private as it contains solutions and optional private tests. We highly recommend to have testing of gold solution against public and private tests - checker can help organizing your files so that you don't share this solution (or any other private files, e.g. private tests) with students. The private repository is the source of truth for the course: public repository is created from the private repository by keeping only those files ready for students. Manytask realizes a concept "Course as Code": once everything is set up, teacher needs to interact only with the private repository - new tasks will be automatically delivered to the students and Manytask web app, to the code, tasks, deadlines, points, etc. will be automatically updated if changes were made.

* **Manytask checker** is a CLI script providing the following functionality:

    * **grade** - to run in a student's repository to test solution against private and public tests and push scores.
    * **validate** - to run in a private (tutors') repository to validate tasks and deadlines integrity (will run in check automatically).
    * **check** - to run in a private (tutors') repository to test gold solutions against private and public tests.
    * **export** - to run in a private (tutors') repository to export tasks, templates and tests to the public repository.
    * **export_private** - to run in a private (tutors') repository to export tasks and tests when preparing docker environment for testing


* **Docker Env**/**Testenv** - a docker image with your course environment and checker installed.  E.g. cpp compiler, go compiler, python interpreter, additional libraries, etc. Also, it should contain copy of the private repository with private tests. It is used to run `checker grade` in students' repositories and `checker check` in private repository to have consistent environment and dependencies. You may use provided `checker` docker image to base on or create your own from scratch.  

* **Private CI** - a CI workflow that runs checks on private repository and if they completed successfully, updates Manytask web-interface, container registry and public repository. Normally and if Manytask Checker is used, it should contain following steps:
    * Build docker image with your environment and checker installed
    * Run `checker check` on each push/mr in private repository to test gold solution against private and public tests
    * If the stages above complete successfully: 
        * `checker export` on each push/mr/release/regularly to export tasks, templates and tests to the public repository. This stage needs access to the public repo.
        * Push the docker image to the registry. Push access to the registry is needed.
        * Send updated Manytask config file (usually .manytask.yml) to the Manytask web app via /update_config API handle. This requires Manytask course token.


* **Students' CI** - a CI file that runs checks on students code and reports to Manytask web app in case of success. If case Manytask Checker is used, it runs `checker grade` which checks what task(s) need checking, runs public and private tests on them and sends the API request to update score. One can use custom scripts


* **Runner** that will run all the CI tasks above. You may need specific configuration for the runner, e.g. if tests require specific hardware (SSD/GPU). In many cases, regular VM should be sufficient.

## Glossary

* **Layout** - a structure of the private repository (and respectively public repository).   
    It is described in the [Private repository docs](./private_repo.md) page.


* **Config-s** - a yaml files with configuration for checker - `.checker.yml` and `.manytask.yml`.  
    See the minimal example in the [Private Repository docs](./private_repo.md) page. Also, there are detailed reference docs for [.cheker.yml](./checker_yml_reference.md) and [.manytask.yml](./manytask_yml.md)


* **Pipeline** - a yaml-described pipeline in `.checker.yml` file to run during `checker check` and `checker export` commands.   
    It is described in the [Pipelines and Plugins](./checker_pipelines_and_plugins.md) page.


* **Plugin** - a single stage of the pipeline, have arguments, return exclusion result. In a nutshell, it is a Python class with `run` method and `Args` pydantic class.  
    Checker have some [build-in plugins](./checker_plugins.md), but you can write your own.  
    See [Pipelines and Plugins](./checker_pipelines_and_plugins.md) page for more information on plugins.


* **Group** - a group of tasks with the same deadlines, can refer as lecture.


* **Task** - a task ready to be tested within your environment.  


* **Public Tests/Files** - a files to be copied to public repository from private repository, used in testing.


* **Private Tests/Files** - a files to NOT be copied to public repository from private repository, but used in testing.


* **Gold Solution** - a tutors-written task solution to be tested against public and private tests.  
    It is used to check tests integrity. Never exposed to students.


* **Template** - a solution template files, copied to students' repositories instead of gold solution.


* **Verbose True/False** - a flag to set level of verbosity of the checker - private/public.   
  
    1. When `verbose` is `True` - checker will print all logs and results and debug info.  
    2. When `verbose` is `False` - checker will print only public-friendly outputs - less info, hidden private tests results, etc.  
  
    It is set automatically as True for `checker check` and False for `checker grade`/`checker check --contribute` commands.  
    Plugins have to implement `verbose` flag.

## Manytask and Checker

**Manytask** - web application to host, responsible for the following things:

1. Get and show deadlines on the web page
2. Get and store students' grades
3. Get and store students' submissions for anti-cheat purposes
4. Create Students' Repositories as forks from Public Repo or as empty repositories
5. (self-hosted GitLab only) Create gitlab users for students

It is language-agnostic and do not care about your course environment and tests. Just create repositories and store grades.  
Here is the scheme of the manytask workflow:
``` mermaid
flowchart LR
    subgraph RMS
        public(Public Repo) -.->|fork| student
        public -->|updates| student
        student([Student's Repo])
    end
    student -->|push scores| manytask
    manytask[manytask] -.->|creates| student
```


**Checker** - CLI script to run in CI, responsible for the following things:
1. Test students' solutions against public and private tests
2. Test gold solution against public and private tests
3. Export tasks, templates and tests from private to public repository
4. Validate tasks and deadlines integrity

It is language-agnostic, but requires docker with your course environment and pipeline configures in yaml files how to run tests.  
Here is the scheme of the checker workflow:
``` mermaid
flowchart LR
    private(Private Repo) -->|checker check| private
    private -->|checker export| public
    student([Student's Repo]) -->|checker grade| manytask
    subgraph RMS
        public(Public Repo) -.->|fork| student
        public -->|updates| student
    end
    manytask -.->|creates| student
```
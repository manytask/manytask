# Concepts

This page describes the main concepts used in the `manytask` project - public/private repository, students' repositories, etc.


## Manytask

This project extends the [manytask](https://github.com/manytask/manytask) project, so please refer to its documentation first.  

The key `manytask` concepts are:

* **Gitlab** - a gitlab.com or self-hosted gitlab instance where students' repositories will be created.


* **Manytask/Web App** - a web application to manage students', repos, grades and deadlines.  
    It stores grades in google sheet and display deadlines on a web page.  
    It also automatically creates gitlab repositories for students as forks from Public Repo with tasks and solution templates.  
    When used self-hosted gitlab instance, it create gitlab users automatically.


* **Public Repo** - a public (only gitlab at the moment) repository with tasks and solution templates.


* **Students' Group** - a group where `manytask` will create repositories for students.


* **Students' Repositories** - repositories for students as forks from Public Repo.


!!! note  
    Manytask do not restrict repository structure in any way, except
    1. Students' must have access to the public repository.
    2. Students' group should be private, for students not to see each other solutions.
    3. `.gitlab-ci-students.yml` should be present in the public repository root to set up it as `external ci file` for all students' repositories.


## Checker

Checker is much nore strict in terms of repository structure and overall workflow.  
However, you can use all or some functions of the checker, which will influence the strictness. In this docs we assume that you use full recommended workflow. 

First of all, it introduces the following main concepts:

* **Checker** - a CLI script providing the following functionality:

    * **grade** - to run in a student's repository to test solution against private and public tests and push scores.
    * **validate** - to run in a private (tutors') repository to validate tasks and deadlines integrity (will run in check automatically).
    * **check** - to run in a private (tutors') repository to test gold solutions against private and public tests.
    * **export** - to run in a private (tutors') repository to export tasks, templates and tests to the public repository.


* **Docker Env**/**Testenv** - a docker image with your course environment and checker installed.  
    E.g. cpp compiler, go compiler, python interpreter, additional libraries, etc.
    Also, it should contain copy of the private repository with private tests.  
    It is used to run `checker grade` in students' repositories and `checker check` in private repository to have consistent environment and dependencies.  
    You may use provided `checker` docker image to base on or create your own from scratch.  


* **Private Repo** - a private (tutors) repository with tasks, tests, templates and solutions (and any additional you may need).  
    This repository have to be private as it contains solutions and optional private tests.   
    We highly recommend to have testing of gold solution against public and private tests.


* **Private CI** - a gitlab ci or github workflow or whatever you use to run 
    * `checker check` on each push/mr in private repository to test gold solution against private and public tests
    * `checker export` on each push/mr/release/regularly to export tasks, templates and tests to the public repository.
    It should be set up to use the docker image with your environment and checker installed.


* **Students' CI** - a gitlab ci file (only gitlab at the moment) set to run 
    * `checker grade` on each push/mr in students' repositories to test solution against private and public tests and push scores.  
    * `checker contribute` on each mr in public repository to check students' contribution in public tests and test it against gold solution.  
    It should be set up to use the docker image with your environment and checker installed.


* **Runner** - a gitlab-ci (only gitlab at the moment) to run students's tests in it.  
    As you will have a lot of students' solutions, so it is better to have self-hosted gitlab runner.  
    It should be connected to the students' group or gitlab self-hosted instance for students' pipelines to run in.  


Also checker introduces the following inner concepts:

* **Layout** - a structure of the private repository (and respectively public repository).   
    It is described in the [Getting Started docs](./1_getting_started.md) page.


* **Config-s** - a yaml files with configuration for checker - `.checker.yml` and `.manytask.yml`.  
    It is described in the [Configuration docs](./2_configuration.md) page.


* **Pipeline** - a yaml-described pipeline in `.checker.yml` file to run during `checker check` and `checker export` commands.   
    It is described in the [Configuration docs](./2_configuration.md) page.


* **Plugin** - a single stage of the pipeline, have arguments, return exclusion result. In a nutshell, it is a Python class with `run` method and `Args` pydantic class.  
    Checker have some built-in plugins, but you can write your own.  
    It is described in the [Configuration docs](./2_configuration.md) page and [Plugins docs](./3_plugins.md) page.


* **Group** - a group of tasks with the same deadlined, can refer as lecture.


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
  

## Manytask vs Checker

Manytask and checker waaay different things.

**Manytask** - web application to host, responsible for the following things:

1. Get and show deadlines on the web page
2. Get and store students' grades
3. Get and store students' submissions for anti-cheat purposes
4. Create Students' Repositories as forks from Public Repo or as empty repositories
5. (self-hosted gitlab only) Create gitlab users for students

It is language-agnostic and do not care about your course environment and tests. Just create repositories and store grades.  
Here is the scheme of the manytask workflow:
``` mermaid
flowchart LR
    subgraph gitlab
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
    subgraph gitlab
        public(Public Repo) -.->|fork| student
        public -->|updates| student
    end
    manytask -.->|creates| student
```

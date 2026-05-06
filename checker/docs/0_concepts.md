
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

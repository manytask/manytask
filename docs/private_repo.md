# Private repository

Strictly speaking, the private repository is not needed: you can use public tests in public repository and make and API call whenever students solution satisfy them. However, it is very convenient to fully realize the concept of Course as Code, when everything is store in a single private repository. This way the teacher can update the course, add tests, change deadlines all by interacting with this single repository. Manytask Checker is a good helper in realizing this concept and here we will describe how to build a course private repo with checker. Later we will set up the CI/CD so that the course deployment can be fully automated.

## The repository layout

Assume that you already have a task that you want to add, including tests and solution. Let us pack it into the repository, which is structured in a specific way for Manytask Checker to work. Then we configure checker to work locally, and in the CI.


## Layout

The general requirements are to have `.checker.yml` and `.manytask.yml` in the root of the repo, `.task.yml` and `.group.yml` in each tasks and group (can be empty). 

The private repository layout is crucial for the checker to function correctly. 
Each task should be organized into dedicated folders within group directories. 
Also, there are 2 config files `.checker.yml` and `.manytask.yml` that are required for checker to work.

Each task location detected by `.task.yml` file (can be just empty). Each group, if any, detected by `.group.yml` file (can be empty). 

Here's a breakdown:

```
private/
├── .checker.yml          # Checker configuration
├── .manytask.yml         # Course configuration
├── Dockerfile            # Docker file with environment and checker
├── 00_Setup/             # Task group
│   ├── .group.yml        # Group config with parameters overwriting
│   ├── 01_HelloWorld/                  # Task
│   │   ├── .task.yml                   # Task config with parameters overwriting
│   │   ├── [solution files]            # Gold solution (can be folder)
│   │   ├── [solution files].template   # Template that replaces solution files on export
│   │   ├── [public tests]              # Tests that students can see
│   │   └── [private tests]             # Tests that are not shown to students
│   └── 02_SimpleAdd/
│       └── ...
└── 01_FirstSteps/
    └── ...
```

Note that:
- Groups and tasks names have to be unique.

- You have to provide solution templates for each task. Please refer to [Templates](#templates) section for more details.

- By default ".*" files are considered as private (i.e. files that should not be shown to the students). We will see how to override this later.

## Templates

The idea of templates is to make the teachers environment closer to that of the student. This way the teachers solution is tested the same way the students solution will be. This ensures that the tests are properly set up and there is a solution that can pass all the checks in the testing environment. When the CI is properly set up, the teachers solution will be checked every time the private repository changes and the pipeline will be stopped before exporting in case there are errors. If everything is ok, the template will be applied to remove the teachers solution when the private repository is exported for the students.

You have to provide solution templates for each task. There are two ways to define templates:

* Replace the entire file or folder (`templates: "search"` option in configuration file): checker will search for files or folders with `.template` extension in the task directory and use them as templates. Original file/folder will be deleted and replaced with a template (`.template` extension will be removed). For example, if you have `task_1/solution.py.template` file, checker will use it as a template to replace gold solution `task_1/solution.py` file. This is the default option. If you have an empty file/folder with `.template` extension, checker will delete original file/folder.

* Replace specific parts of the solution file with `TODO: Your solution` string (option`templates: "create"` in configuration file): checker will search for the template comments in your gold solution and will delete everything except the template. For example, if you have `task_1/solution.py` file with a pair of comments `SOLUTION BEGIN` and `SOLUTION END`:
    ```python
    a = 1
    # SOLUTION BEGIN
    print(a)
    # SOLUTION END
    b = a + 1
    b += 1
    # SOLUTION BEGIN
    print(b)
    # SOLUTION END
    ```
    When exporting to public checker will replace it with `TODO: Your solution` in NOT-greedy way:
    ```python
    a = 1
    # TODO: Your solution
    b = a + 1
    b += 1
    # TODO: Your solution
    ```
    You can have multiple templates in one file. If you write both `SOLUTION BEGIN` and `SOLUTION END` as comments, resulting `TODO: Your solution` will be a comment as well. If after templating the file is empty, checker will delete it.
  
It may be convenient to use different templating options in different tasks, which is allowed (`templates: "search_or_create"` option in checker configuration file). But you can not have 2 types of templating in the same task. Each task have to have at least one template file or folder, otherwise checker will report an error and exit.

## Checker configuration (`.checker.yml`)

This file specifies the default parameters for the checker script and defines the pipelines for task checking and exporting. There is a detailed [reference guide to the `.checker.yml` file](./checker_yml_reference.md), here we show a minimal example.

```yaml
version: 1

structure:
  ignore_patterns: [".git", ".github", "__pycache__", ".venv"]
  public_patterns: [".task.yml", ".group.yml", "README.md", ".gitignore", "test_public.py", "pyrefly.toml"]
  private_patterns: [".*", "test_private.py"]

export:
  templates: search_or_create
  destination: https://public.repo

testing:
  changes_detection: last_commit_changes

  search_plugins: ["tools/plugins"]

  global_pipeline:
    - name: Report success
      fail: after_all 
      run: "run_script"
      args:
        origin: "${{ global.ref_dir }}"
        script: "echo Start testing"

  tasks_pipeline:
    - name: Run tests
      fail: after_all
      run: "run_pytest"
      register_output: "tests_output"
      args:
        origin: ${{ global.repo_dir }}
        target: ${{ task.task_sub_path }}

  report_pipeline:
    - name: "Report success"
      fail: after_all 
      run: "run_script"
      args:
        origin: "${{ global.ref_dir }}"
        script: "echo Your score percentage is ${{ outputs.tests_output.percentage }}"

```

Briefly, we set up patterns for the files that should be ignored by checker, files that are public (should be available to the students) and those that are private (should not be available to the students). The testing contains three stages: global, tasks and report. The global pipeline runs once per repo, preparing the testing system. Task pipeline runs tests for the task and save the result in `tests_output`. The report pipeline is then uses these data to report score (in this example it prints it). Both task and report pipeline run for each task needs checking. When `checker grade` is executed, the tasks need checking is determined by the changes in the last commit due to `changes_detection: last_commit_changes` setting. With `checker check` all the tasks will be checked.

One can override these settings for a group of tasks or even for single task using `.group.yml` and `.task.yml` files:

* **Group Configuration** (`.group.yml`):  
    Optional file located in group directory, this file allows for task-specific settings. It can override default parameters, private/public files and pipelines set in .checker.yml for individual groups.  
    (apply to any subdirectory)

* **Task Configuration** (`.task.yml`):
    Optional file located in task directory, this file allows for task-specific settings. It can override default parameters, private/public files and pipelines set in .checker.yml for individual tasks.

## Manytask configuration (`.manytask.yml`)

This file outlines the deadlines for each group, task max score and etc. In the checker it is used to validate task and deadlines integrity and it is send to Manytask to update task, their deadlines and scores.

One should consult [the `.manytask.yml` reference guide](./manytask_yml_reference.md) to see the detailed description of the file. Minimal example for a `.manytask.yml` file looks something like this:

```yaml
version: 1


settings:
  course_name: Template

  gitlab_base_url: https://gitlab.manytask.org
  public_repo: examples/template/public
  students_group: examples/template/students


ui:
  task_url_template: https://gitlab.manytask.org/examples/template/students/$USER_NAME/-/tree/main/$GROUP_NAME/$TASK_NAME

  # optional, any number of links
  links:
    "Contribute Manytask": https://github.com/manytask


deadlines:
  timezone: Europe/Moscow

  deadlines: hard  # hard/interpolate

  schedule:
    - group: 00_Setup
      start: 2025-01-01 18:00:00
      end: 2050-01-01 23:59:00
      enabled: true
      tasks:
        - task: 01_HelloWorld
          score: 10
        - task: 02_SimpleAdd
          score: 10
    - group: 01_FirstSteps
      start: 2025-01-01 18:00:00
      end: 2050-01-01 23:59:00
      enabled: false
      tasks:
        - task: 01_CheckAnIf
          score: 20
        - task: 02_LoopALoop
          score: 20
```

This file will be used by the Manytask web app, hence there is some UI information, that is used to enrich the interface for the students (setting and ui sections). The main part of the file is the deadlines section, which lists the tasks in the repo with their respective deadlines. Tasks are combined into groups, which are course topics (usually one group of tasks correspond to a lecture or a week of the course). 

## Docker file with environment and checker

Checking solutions will be happening in CI/CD and we need to set up environment for that. This is done using Docker with a basic example below.

```dockerfile
FROM python:3.13.7-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends curl git && \
    apt-get autoremove -qyy && \
    apt-get clean && rm -rf /var/lib/apt/lists/*


RUN git clone https://github.com/manytask/manytask.git && \
    cd manytask/checker && \
    python3 -m pip install --upgrade uv && \
    uv sync --frozen && \
    uv pip install .
```

Here we use python slim image and expand on it by first installing `curl` and `git`. We are going to use REST API to communicate with Manytask (hence `curl` is installed). We use `git` to get and install checker in the second `RUN` command, this will be used to run tests on the repo.

## Install and run Manytask Checker 

Build you docker image from scratch and install checker there. This way you have full control and can minimize the size of the image as much as you like. The `checker` can be installed directly from the Manytask repository:
    
- Create and activate virtual environment:

  ```shell
  python3 -m venv .venv
  source .venv/bin/activate
  ```

- Clone Manytask repository and install checker:
    
  ```shell
  git clone https://github.com/manytask/manytask.git
  cd manytask/checker
  uv pip install .
  ```

- Verify the installation:
    
    ```shell
    checker --version
    ```

To run tests you need to have a docker testing environment that includes your course's specific environment and the pre-installed checker. It is than useful to create a docker file, where the installation script is executed to have checker available in the docker environment.

## Local testing

For local testing of private repo you have 2 options:

1. Use local checker installation (see above)
2. Build docker image and use it for testing in the interactive mode:
    
    ```shell
    # run docker in interactive mode mounting your repo as /course
    docker build -f DOCKER_FILE -t IMAGE_NAME .
    docker run -it --rm -v $(pwd):/course -w /course IMAGE_NAME bash
    ```

First approach is faster and easier to debug, it is ok for local testing, using docker image ensures that your tests will run in the same environment as in CI.

After you have a working checker executable, you can validate that you repository has valid structure:

  ```shell
  (.venv) checker validate
  ```

And test all tasks, separate task group or a single task:

  ```shell
  (.venv) checker check
  (.venv) checker check --group 00_Setup
  (.venv) checker check --task 01_HelloWorld
  ```
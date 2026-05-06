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

```yaml
00_Setup/
    01_HelloWorld/
      [solution files].template  # file or folder, if set templates="search" in .checker.yml
        [some files]
      [gold solution files]
      [some private tests]
      [some public tests]
      .task.yml  # task config with default parameters overwriting
    02_SimpleAdd/
        ...
    .group.yml  # group config with default parameters overwriting
01_FirstSteps/
    01_CheckAnIf/
        ...
    02_LoopALoop/
        ...
.checker.yml  # checker config with default parameters and pipelines
.manytask.yml  # deadlines config with task scores to send to Manytask
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

This file specifies the default parameters for the checker script and defines the pipelines for task checking and exporting.

* **Group Configuration** (`.group.yml`):  
    Optional file located in group directory, this file allows for task-specific settings. It can override default parameters, private/public files and pipelines set in .checker.yml for individual groups.  
    (apply to any subdirectory)

* **Task Configuration** (`.task.yml`):
    Optional file located in task directory, this file allows for task-specific settings. It can override default parameters, private/public files and pipelines set in .checker.yml for individual tasks.

TODO: Minimal example for a .checker.yml file with link to full reference

## Manytask configuration (`.manytask.yml`)

This file outlines the deadlines for each group, task max score and etc. In the checker it is used to validate task and deadlines integrity and it is send to Manytask to update task, their deadlines and scores.

TODO: Minimal example for a .manytask.yml file with link to full reference

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
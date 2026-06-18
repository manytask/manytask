# Basic example of a public repo

In this section we will see how one can create and set up a public repo for a very basic course. It will have several critical limitations, however it is a very good starting point that helps understanding how Manytask works.

## Create the course in the Manytask interface

To create a course in the Manytask interface you will need to provide the following information:
- **Unique course name** - the course slug, the is unique for the specific iteration of the course: if the course runs each year, it should contain this year. Example: `python-2025-fall`.
- **Namespace** - namespace for your institution. This is used to separate courses from different universities in RMS and also to restrict access rights to a single organization.
- **Registration secret** - a secret token that you will give to the student so that they will gain access to the course.
- **RMS course group**, **public repo** and **students group** - location to create course public repo and students group in the RMS.

The course creation page also contains course token (i.e. TESTER_TOKEN below), which you will need to send data to the Manytask server. Do not worry if you forget these data, you can always get back to it with `Edit course` page. Once the course is created, it will also create the public repository and students group in the RMS. Go to the RMS page and clone the public repository if you want to follow along - the instructions below show what is needed in the public repository in order for the course to work.


## Public repository

Let us illustrate how one can set up a very basic repository that will allow for checking students solutions and report scores back to the Manytask server. We are going to ask students to implement a function that checks if the number is prime, returning `True` if it is and `False` otherwise. First, let us create a layout of the repository and than we will go through the files and describe what they are.

### Repository layout

```
.
├── IsPrime/                # primality-test task
│   ├── README.md           # task statement and required function signature
│   ├── is_prime.py         # place for student implementation
│   ├── test_is_prime.py    # pytest tests
│   └── check.sh            # runs the tests and exits non-zero on failure
│
├── .gitlab-ci.yml          # CI pipeline: parses task name from commit, runs check.sh, reports score
├── .manytask.yml           # Manytask course configuration (groups, tasks, scores, deadlines)
└── README.md               # General repo description

```



### Task statement and tests

Since this is a task for the student to solve, we do not need to provide a solution here (although it is always a good idea to check that your solution can pass the tests). In the `is_prime.py` file we are going to supply students with a function that always returns `False`. This way they know right away, where to put their implementation:

```python
def is_prime(n: int) -> bool:
    return False
```

We also need tests, that will check that solution is correct. It is always good to test all the corner cases, add checks that will fail or time-out on algorithms that do not perform well, etc. Our example is illustrative and we are going to check several numbers up to a 100, so in `test_is_prime.py` we have:

```python
import pytest

from is_prime import is_prime

def test_known_primes() -> None:
    assert is_prime(-1) is False
    assert is_prime(0) is False
    assert is_prime(1) is False
    assert is_prime(2) is True
    assert is_prime(3) is True
    assert is_prime(4) is False
    assert is_prime(5) is True
    assert is_prime(7) is True
    assert is_prime(97) is True
    assert is_prime(100) is False
```

Note that when we introduce private repo, we will be able to add private tests, head-to-head tests with golden solution, etc.

The `check.sh` is used here to unify testing procedures for different tasks. CI will change directory to the task folder and run `check.sh` from there. So each task must have the `check.sh` file, but its content may vary, depending on the task nature. The only requirement is that if the tests fail, this script should return with an error - this will indicate that we should not report score to the Manytask web app. In our case, the script runs pytest:

```bash
#!/bin/bash
python3 -m pytest -v test_is_prime.py
```

Now we need a CI/CD configuration file that will:

- extract `Task` name from the commit message,
- run that task's `check.sh`,
- on success, report the score to the Manytask server via
  `POST /api/<course_name>/report` using the bare task name.

Here is a simple version of such `.gitlab-ci.yml` file:

```yaml
stages:
  - check

check_task:
  stage: check
  image: alpine:latest
  before_script:
    - apk add --no-cache bash curl python3 py3-pytest
  script:
    - |
      MANYTASK_URL="https://app.manytask.org"
      COURSE_NAME="basic"

      TASK_PATH="${CI_COMMIT_MESSAGE}"

      echo "Detected task:  ${CI_COMMIT_MESSAGE}"
      echo "Detected username:  ${GITLAB_USER_LOGIN}"

      cd "${TASK_PATH}"
      ./check.sh

      # Report the score to the Manytask server.
      curl --fail -X POST --show-error "${MANYTASK_URL}/api/${COURSE_NAME}/report" \
        -H "Authorization: Bearer ${TESTER_TOKEN}" \
        -d "task=${CI_COMMIT_MESSAGE}&username=${GITLAB_USER_LOGIN}&score=1.0"
```

The script culminates by the `curl` call, which reports score to the Manytask server. Several variables are used there, which are either defined somewhere or collected during the script execution:
 
- `MANYTASK_URL` is the URL of the Manytask server, `COURSE_NAME` is the name of the course in the Manytask server. These are used when the report URL is constructed.
- `CI_COMMIT_MESSAGE` is the internal GitLab variable that contains commit message. When submitting the task for checking, student must write task name in the commit message (and nothing else), otherwise we will not be able to determine which task is submitted.
- `TASK_PATH` is the path to the task folder, which in our case coincides with the task name.
- `GITLAB_USER_LOGIN` is the internal GitLab variable that contains the username of the student, it is used when the report is sent to the Manytask server.
- `TESTER_TOKEN` is the token that is used to authenticate with the Manytask server. It should be defined in the CI/CD settings of the course folder in GitLab.

Note that we send `score=1.0` as a score: this represents 100%, but we could set up tests and CI to send fractional score.

We surely run the `check.sh` script before reporting - if the script fails, this way curl command will not run if the tests fail. Note that we use alpine image, which is very light. But we have to install bash, curl, python and pytest packages in the `before_script` section so that our scripts work. Also note that we are sending `1.0` as a score: this represents 100%, but we could set up tests and CI to send fractional score.

The `README.md` file in the root folder usually contains the description of the course, which we will not add in this example. But it should also have the instructions on how to submit a task for checking. In our case, we require the commit message to be a task name, so the students should be instructed to do so:

```Markdown
## Submitting a task for checking

Each task lives in its own folder. To submit a solution:

1. Read the task description in the `README.md` file inside the task folder.
2. **Write your solution** following directions in the `README.md` file inside the task folder.
3. **Commit** the change with a message that contains **only task name**, matching the on-disk folder name (case-sensitive).

   git add IsPrime/is_prime.py
   git commit -m "IsPrime"

The CI pipeline gets the name of the task to check from `CI_COMMIT_MESSAGE`.

4. **Push** to the repository:

   git push

```

## Manytask configuration file

Now the files are ready, we need to push them to the public repo and inform Manytask that there is a task for solving. This is done with `.manytask.yml` configuration file. The contents of such a file for our one-problem repo is below, please refer to [Manytask configuration file reference](manytask_yml_reference.md) for details.

```yaml
version: 1
status: in_progress

settings:  # required
  course_name: The very basic course

  gitlab_base_url: https://gitlab.manytask.org
  public_repo: basic/public
  students_group: basic/students


ui:
  task_url_template: https://gitlab.manytask.org/basic/students/$USER_NAME/-/tree/main/$TASK_NAME

  # optional, any number of links
  links:
    "Contribute Manytask": https://github.com/manytask


deadlines:
  timezone: Europe/Moscow

  deadlines: hard  # hard/interpolate

  schedule:
    - group: Math
      start: 2025-01-01 18:00:00
      end: 2050-01-01 23:59:00
      enabled: true
      tasks:
        - task: IsPrime
          score: 100
```

Here we set the course `status` to `in_progress`, which will make it possible to register to the course and start solving. The basic setting include links to Gitlab, public repo and students group. In UI section, we configure links to each task in the interface, add extra link (e.g. to course chat group or LMS). In the `deadlines` section, the tasks are configured. Here we use `hard` deadlines - zero points are issued after deadline is expired. We use Moscow timezone. The `schedule` contains a list of task groups. Each group has its own deadlines, which are followed by individual tasks in a group. One group can have many tasks. The `enabled: true` means that the task group is available for solving. The individual tasks are listed with names and maximum points that task cost.

Once we are happy with the contents of the `.manytask.yml` file, we can send it to the Manytask server with the following command:

```bash
export TESTER_TOKEN=???
export MANYTASK_URL=https://app.manytask.org
export COURSE_NAME=basic
curl -X POST -H "Authorization: Bearer ${TESTER_TOKEN}" -H "Content-Type: application/x-yaml"  --data-binary @.manytask.yml "${MANYTASK_URL}/api/${COURSE_NAME}/update_config"
```

The `TESTER_TOKEN` is the course token, that is available on the course settings page (and created with the course). Change the Manytask URL and course name to your values as well.

## Limitations

This approach of setting up the course is probably the simplest, but it is rather limited in real world. First and foremost - students are not restricted in any way in what they are allowed to change. Hence one can just skip the testing stage and report scores right away: you don't even need to steal the course token, which is also possible in such setup. Secondly, as the name suggests, all the files in the public repo are public and accessible for the students. This means that there is no way to set up private tests or store golden solution in this repo. The third disadvantage is that we need to ask students to provide the task name as a commit message, which is an additional step they may forget to do. We will see how we can overcome these limitations with Manytask Checker in the following sections.
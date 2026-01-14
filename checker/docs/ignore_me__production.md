# Production

On this page you can find documentation on how to run `checker` itself  
NB: Please first refer to the [system setup documentation](./ignore_me__system_setup)


## Installation 

In a nutshell `checker` is just a python pkg available with pip as [manytask-checker](https://pypi.org/project/manytask-checker/).  
So, as it was mentioned in  [system setup documentation](./ignore_me__system_setup) you can install it with
```shell
python -m pip install manytask-checker
```
Note: check available python versions in setup configs 

You can install on your machine for developing or in docker for testing purposes.


## Pre requirements

`checker` script demands `.course.yml` and `.deadlines.yml` configs to operate;  

It will cook up for `.course.yml` in (relative to execution folder)

1. `.course.yml`
2. `tests/.course.yml`
3. `tools/.course.yml`

After the config will be applied and `.deadlines.yml` file will be searched according to layout 
(see [checker/course/driver.py](../checker/course/driver.py) for layout info). 

for the format check examples folder


Additionally, you may need the following env variables to be provided for checker 
* `TESTER_TOKEN` - manytask token to push scores 
* `GITLAB_SERVICE_TOKEN` - service account token to push public repo
* `GITLAB_API_TOKEN` - service account api token to read merge requests  

Reminder: YOu deferentially not want to expose these tokens for students, 
so you should provide it NOT as gitlab variables, but as gitlab-runner variables


## Usage 

This pkg provides a cli application available as `checker` after installation 
```shell
python -m checker --help
# ot just
checker --help
```

#### `$ checker check`

Command runs tests against ground truth solution (authors' solution) to test.. tests.  

Able to test single task with `--task` or lecture/group with `--group` option.  
Can be parallelized with `--parallelize`.


#### `$ checker export-public`

Select enabled assignments (according to .deadlines.yml file) and export it from private to public repo.


#### `$ checker grade`

Run students assignments testing. Should be run in gitlab-runner, as it's rely on env variables available there. 

* Detect git changes between 2 last pipelines run 
* Select tasks to be tested 
* Run tests 
* Push scores to manytask 


#### `$ checker grade-mr`

Run grading of all merge requests in students' group (from student's repo to students' main branch) 

Run basic checks against students' MR:

* All changed files is one task
* No extra files committed
* etc


#### `$ checker grade-students-mrs`

Run grading of all merge requests in current student's repo (from student's repo to students' main branch) 

Same checks as `grade-mr`

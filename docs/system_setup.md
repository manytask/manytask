# Production setup

There are some steps you need to tackle to whole system to operates
* `pre-setup` - one-time actions for repo setup 
* `new course` - one-time actions for new course on manytask to operate 
* `new semester` - every-semester actions for each course to set up manytask

---

## Pre-setup

One-time actions necessary for the functioning of the entire repo/manytask system


### Code analyse 

1. Setup codecov app for this repo
   Currently set up as: https://app.codecov.io/gh/yandexdataschool/manytask
   * Grant access for codecov app for this repo
   * Set github secret `CODECOV_TOKEN` to use in github-actions 
   * Set up readme badge to show code coverage 


### Docker

1. Create docker registry and user to push images  
   Currently `manytask` user at docker hub: https://hub.docker.com/u/manytask


2. Update image name in `.github` folder and docs to be ready to use it  
   Currently `manytask/manytask` image at docker hub: https://hub.docker.com/r/manytask/manytask


3. Set github secrets `DOCKERHUB_USERNAME` and `DOCKERHUB_TOKEN` to use in github-actions 


### Github

1. Create service account and grant access as admin    
   Currently `manytask-bot`   
   This account is required because `GITHUB_TOKEN` cannot access protected branches and tags


2. Setup github secrets environment to safe sensitive secrets for all but `main`  
   TODO


### Google

Actually, at some point manytask is a wrapper around google sheet (to store students scores, etc), so you need to use it 

1. Register new gmail(!) account for service purposes    
   or use existing one: `ysda.service.manytask@gmail.com` (credentials: @k4black)


2. Create New [Google Cloud](https://console.cloud.google.com/) Project for whole `manytask`
   * Crate new project  
     Or use existed one: `manytask` (credentials: @k4black)
   * [Enable Google Sheets API](https://console.cloud.google.com/marketplace/product/google/sheets.googleapis.com)
   * Give access for all admins to this project  

   For testing purposes:
   * Create [new service account](https://console.cloud.google.com/apis/credentials): `tester` with editor access.
     Note: Save private key (! it will apper only once) or create new if old is lost
     Or use existed one: `tester@manytask.iam.gserviceaccount.com`  
   
     
3. Create Testing Google Sheet and give access for the tester service account  
   Or use existing: [test sheet](https://docs.google.com/spreadsheets/d/1cRah9NC5Nl7_NyzttC3Q5BtrnbdO6KyaG7gx5ZGusTM/edit?usp=sharing) with `tester@manytask.iam.gserviceaccount.com` access
   

4. Create gihub secret with Google credentials    
   TODO


### Gitlab

Manytask currently operates only with self-hosted gitlab instance (to easily create accounts for users and use oauth)

1. Run self-hosted gitlab instance  
   or use existing one:`gitlab.manytask.org` (more info: @slon)


2. Create admin (to create new users) gitlab account for manytask in [gitlab admin area -> users](https://gitlab.manytask.org/admin/users)  
   or use existing account: `ysda.service.manytask@gmail.com` or `manytask` (credentials: @k4black)


3. Create test gitlab oauth credentials in [gitlab admin area -> applications](https://gitlab.manytask.org/admin/applications/) with `api`, `sudo`, `profile` and `openid`  
   Or copy existed one (known by any gitlab admin: @k4black, @slon, @vadim_mazaev, etc.)  
   save it to `.env` file to future use


---


## New course 

Actions you need to take one-time to run a new course with the `manytask`.
  
Note: If access to some accounts is lost, then you need to refer to the Pre-setup section above and create new.


### Google

1. For the Google Cloud project (current: `ysda.service.manytask@gmail.com` account -> `manytask` project)  
   *Note: Alternatively you can create your own google project (other steps remain same; refer to pre-setup section).*

   * Create [new service account](https://console.cloud.google.com/apis/credentials) unique for the course: `[course_name]` with editor access.   
     (for example: `python` - `python@manytask.iam.gserviceaccount.com`)  
     Note: Save private key (! it will apper only once) or create new if old is lost
   

### Gitlab

1. Create new oauth application in [gitlab admin area -> applications](https://gitlab.manytask.org/admin/applications/), save `client_id` and `client_secret`  
   (can be done by any of gitlab admin: @k4black, @slon, @vadim_mazaev, etc.)


2. Create new gitlab api token (to create users and repos) for admin account `ysda.service.manytask@gmail.com`/`manytask` (credentials: @k4black)


3. Create a group for your course. Add all course admins/lecturers to the group  
   (for example: [py-tasks](https://gitlab.manytask.org/py-tasks/))
   


### General


1. Find Virtual Machine/Server to host manytask instance with public static ip    
   (also you may like to host gitlab-runners there to test students' solutions)  
   *2 core (2k MHz), 8 Gb RAM, 100 Gb disk - sufficient for ~100 students*
   * Install docker and docker-compose


2. Obtain dns record for you manytask pointing to you machine ip  
   Use can use `*.manytask.org`, if you use manytask infrastructure    
   (can be done by dns admin: @slon)


---


## New course semester

The following steps you need to take **each semester** (each new course with new students setting up).  


### Google 

1. Create Google Sheet and give access for the course service account created  
   * Create Public Google Sheet with rating/scores table, name it (for example `scores`):  
     For example: [test public sheet](https://docs.google.com/spreadsheets/d/1cRah9NC5Nl7_NyzttC3Q5BtrnbdO6KyaG7gx5ZGusTM/edit?usp=sharing)  
     Naming example: `[YEAR] [fall-spring] - [course]` (example: `2022 spring - YSDA Python`)  
     (It's better to use service account from above steps to store it)
   * Share public table in reading only mode, save link for students
   * Give full access to all course admins (teachers) 
   * Give access to course service account you created (for example: `python@manytask.iam.gserviceaccount.com`)
   

### Gitlab

You need to create a public repository with students assignments and group where students' repo will be stored.  
(Students' repos will be created by manytask automatically, but you should update `.env` file with repo and group names)

1. Create public (or internal) repository with course assignments (to fork students repo from)
   Naming example: `py-tasks/public-[YEAR]-[fall/spring]`  
   * Check gitlab runners (2 runners: build and private-tester operates well) 

   * In the CI-CD settings:
     * Disable "Public pipelines" to hide private tests logs
     * Enable "Auto-cancel redundant, pending pipelines"
     * Disable "Auto DevOps"
     * Disable "Shared runners"
     * Enable "Group runners"
     
     This settings will be copied when students fork the repo 
    
    
2. Create private(!) group (for students not to see repositories of each other)   
   Naming example: `python-[spring/fall]-[YEAR]` or `py-tasks/[spring/fall]-[YEAR]`  
   Give full access for the admin group you created (auto access for all groups members) 

   Highly likely you will create group runner to test students' solutions.  
   In the CI-CD settings:
   * Create group runner:
     * From CI-CD group settings get registration token 
     * [Register runner](https://docs.gitlab.com/runner/register/)  
        `docker run --rm -it -v /srv/gitlab-runner/config:/etc/gitlab-runner gitlab/gitlab-runner register`
     * Edit `/srv/gitlab-runner/config/config.toml` to match runners list


### Manytask deploy 

Finally, (almost) you need manytask instance itself

You should use official docker image, available at [docker hub](https://hub.docker.com/r/manytask/manytask)

Please refer to the [production documentation](./production.md)


### Testing script 

In the future, you need to create a testing script to test students' solutions and actually push scores obtained to the manytask instance.  
You have the following options:
* Use [yandexdataschool/checker](https://github.com/yandexdataschool/checker) - python lib developed for checking students' assignments and manytask integration
* Write your own script following manytask api

Please refer to the [yandexdataschool/checker documentation](https://github.com/yandexdataschool/checker) for further information and tips in both cases.

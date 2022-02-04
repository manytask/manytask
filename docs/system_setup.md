# Produ

---


## Pre-setup

One-time actions necessary for the functioning of the entire system


### Docker

1. TODO


### Github
 
1. Setup github actions for the repo:  
   TODO


2. Set github secrets:  
   TODO


### Google

1. Register new gmail(!) account for service purposes    
   or use existing one: `ysda.service.manytask@gmail.com` (credentials: @k4black)


2. Create New [Google Cloud](https://console.cloud.google.com/) Project for whole `manytask`
   * Crate new project 
   * [Enable Google Sheets API](https://console.cloud.google.com/marketplace/product/google/sheets.googleapis.com)
   * Give access for all admins to this project
   For testing purposes:
   * Create [new service account](https://console.cloud.google.com/apis/credentials): `tester` with editor access.   
     Note: Save private key (!) it will apper only once 
     Or use existed one: `tester@manytask.iam.gserviceaccount.com`
   Or use existed one: `manytask` (credentials: @k4black)
   
     
3. Create Testing Google Sheet and give access for the tester service account  
   Or use existing: [test sheet](https://docs.google.com/spreadsheets/d/1cRah9NC5Nl7_NyzttC3Q5BtrnbdO6KyaG7gx5ZGusTM/edit?usp=sharing) with `tester@manytask.iam.gserviceaccount.com` access
   

### Gitlab

1. Run self-hosted gitlab instance: `gitlab.manytask.org` (more info: @slon)


2. Create admin (to create new users) gitlab account for manytask in [gitlab admin area -> users](https://gitlab.manytask.org/admin/users)  
   or use existing account: `ysda.service.manytask@gmail.com` or `manytask` (credentials: @k4black)


3. Create test gitlab oauth credentials in [gitlab admin area -> applications](https://gitlab.manytask.org/admin/applications/) with `api`, `sudo`, `profile` and `openid`  
   Or copy existed one (known by any gitlab admin: @k4black, @slon, @vadim_mazaev, etc.)

---


## New course 

Add a new course to the `manytask`.
  
Note: If access to some accounts is lost, then you need to refer to the Pre-setup section above and create new


### Google


1. For the Google Cloud project (current: `ysda.service.manytask@gmail.com` account -> `manytask` project)  
   *Note: Alternatively you can create your own google project (other steps remain same).*

   * Create [new service account](https://console.cloud.google.com/apis/credentials) unique for the course: `[course_name]` with editor access.   
     (for example: `python` - `python@manytask.iam.gserviceaccount.com`)  
     Note: Save private key (!) it will apper only once or create new if old is lost
   

### Gitlab

1. Create new oauth application in [gitlab admin area -> applications](https://gitlab.manytask.org/admin/applications/), save `client_id` and `client_secret`  
   (can be done by any gitlab admin: @k4black, @slon, @vadim_mazaev, etc.)


2. Create new gitlab api token (to create users and repos) for admin account `ysda.service.manytask@gmail.com`/`manytask` (credentials: @k4black)


3. Create group for admins. Add all course admins/lecturers to the group  
   (for example: [py-tasks](https://gitlab.manytask.org/py-tasks/))
   
---


## New course semester

### Google 

1. Create Google Sheets and give access for the course service account created  
   * Create Public Google Sheet with rating/scores table, name it (for example `scores`):  
     For example: [test public sheet](https://docs.google.com/spreadsheets/d/1cRah9NC5Nl7_NyzttC3Q5BtrnbdO6KyaG7gx5ZGusTM/edit?usp=sharing)  
     Naming: `[YEAR] [fall-spring] - [course]` (example: `2022 spring - YSDA Python`)
   * Share public table in reading only mode 
   * Create Private Google Sheet with accounts and reviews tables, name them (for example `accounts` and `reviews` sheets respectively):  
     For example: [test private sheet](https://docs.google.com/spreadsheets/d/1cRah9NC5Nl7_NyzttC3Q5BtrnbdO6KyaG7gx5ZGusTM/edit?usp=sharing)  
     Naming: `[YEAR] [fall-spring] - [course] - private` (example: `2022 spring - YSDA Python - private`)
   * Give full access to all course admins (teachers) 
   * Give access to course service account (for example: `python@manytask.iam.gserviceaccount.com`)
   

### Gitlab


1. Create private(!) group (to students not to see repositories of each other)   
   Naming example: `python-[spring/fall]-[YEAR]`  
   Give full access for the admin group (auto access for all groups members)  
   In the CI-CD settings:
   * Create group runner:
     * From CI-CD group settings get registration token 
     * [Register runner](https://docs.gitlab.com/runner/register/)  
        `docker run --rm -it -v /srv/gitlab-runner/config:/etc/gitlab-runner gitlab/gitlab-runner register`
     * Edit `/srv/gitlab-runner/config/config.toml` to match runners list

2. Create public (or internal) repository with course assignments (to fork students repo from)
   Naming example: `py-tasks/public-[YEAR]-[fall/spring]`  
   * Check gitlab runners (build one and private tester operates well) 

   * In the CI-CD settings:
     * Disable "Public pipelines" to hide private tests logs
     * Enable "Auto-cancel redundant, pending pipelines"
     * Disable "Auto DevOps"
     * Disable "Shared runners"
     * Enable "Group runners"


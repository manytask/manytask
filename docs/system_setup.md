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


1. For the Google Cloud project (current: `ysda.service.manytask@gmail.com` -> `manytask`)
   * Create [new service account](https://console.cloud.google.com/apis/credentials): `tester` with editor access.   
     Note: Save private key (!) it will apper only once  
     (for example: `tester@manytask.iam.gserviceaccount.com`)


2. Create Google Sheets and give access for the service account  
   * Create Public Google Sheet with rating/scores table:  
     For example: [test sheet](https://docs.google.com/spreadsheets/d/1cRah9NC5Nl7_NyzttC3Q5BtrnbdO6KyaG7gx5ZGusTM/edit?usp=sharing)
   * Share public table in reading only mode 
   * Create Private Google Sheet with accounts and reviews tables:  
     For example: [test sheet](https://docs.google.com/spreadsheets/d/1cRah9NC5Nl7_NyzttC3Q5BtrnbdO6KyaG7gx5ZGusTM/edit?usp=sharing)
   * Give access to all tables to all course admins   
   * Give access to service account  
     (for example: `tester@manytask.iam.gserviceaccount.com`)
   

### Gitlab

1. Create new oauth credentials in [gitlab admin area -> applications](https://gitlab.manytask.org/admin/applications/)  
   (can be done by any gitlab admin: @k4black, @slon, @vadim_mazaev, etc.)


2. Create new gitlab admin token (to create users and repos) for account `ysda.service.manytask@gmail.com`/`manytask` (credentials: @k4black)


3. Create group for admins. Add all course admins/lecturers to the group  
   (for example: [py-tasks](https://gitlab.manytask.org/py-tasks/))


4. Create private(!) group (to students not to see accounts of each other)   
   Naming example: `py-tasks/public-[YEAR]-[spring/fall]`  
   Give full access for the admin group (auto access for all groups members)  
   In the CI-CD settings:
   * Create group runner 

6. Create public (or internal) repository for the course (to fork students repo from)
   Naming example: `python-[fall/spring]-[YEAR]`    
   Give full access for the admin group (auto access for all groups members)   
   In the CI-CD settings:
   * Disable "Public pipelines" to hide private tests logs
   * Enable "Auto-cancel redundant, pending pipelines"
   * Disable "Auto DevOps"
   * Disable "Shared runners"
   * Enable "Group runners"
   
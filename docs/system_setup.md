# Production setup

The setup for manytask in a nutshell looks as the following:

* Self-hosted gitlab with students repo
* A database
* Server that hosts Manytask app, landing page and docs
* nginx-proxy resolving dns records to containers

---

### Gitlab

Manytask currently operates only with self-hosted gitlab instance (to easily create accounts for users and use oauth)

1. Run self-hosted gitlab instance (separate server)  

2. Create admin (to create new users) gitlab account for manytask in [gitlab admin area -> users](https://gitlab.manytask.org/admin/users)


3. Create test gitlab oauth credentials in [gitlab admin area -> applications](https://gitlab.manytask.org/admin/applications/) with `api`, `sudo`, `profile` and `openid`  
   Or copy existed one save it to `.env` file to future use


### General

1. Find Virtual Machine/Server to host manytask instances with public static ip 
   *2 core (2k MHz), 8 Gb RAM, 100 Gb disk - sufficient for ~100 students*
   * Install docker and docker-compose
   * Install Poetry for local development and testing:
     ```shell
     curl -sSL https://install.python-poetry.org | python3 -
     ```


2. Set dns record to point at statis ip  
   Use can use `manytask.org`, if you use manytask infrastructure    
   the easiest way is to set wildcard `*.manytask.org`  
   (can be done by dns admin: @slon)
   

3. Setup forwarding of `smth.manytask.org` to your manytask container and get ssl certs  
   the easiest way is to use [nginx-proxy](https://github.com/nginx-proxy/nginx-proxy) for auto-forwarding and auto ssl certs generation   
   check docker-compose example


---


## New course 

Actions you need to take one-time to run a new course with the `manytask`.
  
Note: If access to some accounts is lost, then you need to refer to the Pre-setup section above and create new.


### General

You may have your private manytask server. See `Pre-Setup -> General`

TL;DR: 

1. Setup server 
2. Setup dns record 
3. Setup docker forwarding and auto-ssl 


### Gitlab

1. Create new oauth application in [gitlab admin area -> applications](https://gitlab.manytask.org/admin/applications/), save `client_id` and `client_secret`  
   (can be done by any of gitlab admin: @k4black, @slon, @vadim_mazaev, etc.)


2. Create new gitlab api token (to create users and repos) for admin account `ysda.service.manytask@gmail.com`/`manytask` (credentials: @k4black)


3. Create a group for your course. Add all course admins/lecturers to the group as admins  
   (for example: [python](https://gitlab.manytask.org/python/))

   In the CI-CD settings:
     * Disable "Auto DevOps"
     * Enable Shared-runners


---


## New course semester

The following steps you need to take **each semester** (each new course with new students setting up).

### Gitlab

You need to create a public repository with students assignments and group where students' repo will be stored.
(Students' repos will be created by manytask automatically, but you should update `.env` file with repo and group names)


1. Create public (or internal) repository with course assignments (to fork students repo from)
   Naming example: `python/public-[YEAR]-[fall/spring]`  

   * In the CI-CD settings:
     * Disable "Public pipelines" to hide private tests logs
     * Enable "Auto-cancel redundant, pending pipelines"
     * Disable "Auto DevOps"
     * Enable "Shared runners"
     * Enable "Group runners"

     (This settings will be copied when student fork the repo via manytask) 
    
    
2. Create private(!) group for students of this semester (for students not to see repositories of each other)   
   Naming example: `python/students-[spring/fall]-[YEAR]`


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

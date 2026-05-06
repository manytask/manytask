## Infrastructure

!!! note  
    tl;dr:  You need to set up gitlab, gitlab runner, docker registry, manytask instance and prepare gitlab token.

Setting up the infrastructure for Manytask and checker involves configuring the runtime environment:

Manytask requite the following:

1. (optional) **Self-hosted GitLab** instance - storing public repo and students' repos.   
    Manytask and checker can work with gitlab.com, but you can use self-hosted gitlab instance for better control, privacy and performance.  
    Please refer to [gitlab docs](https://about.gitlab.com/install/) for installation instructions.


2. **Manytask instance** - web application managing students' grades (in google sheet) and deadlines (web page).  
    Please refer to [manytask docs](https://github.com/manytask/manytask).

So the checker extends it with the following:

1. **Gitlab Runner** - place where students' solutions will be tested.  
    You definitely need it as the students will consume your free CI minutes extremely fast.    
    Please refer to [gitlab runners docs](https://docs.gitlab.com/runner/) for installation instructions.  
    Add this runner as a student group runner to your course group or as a shared runner to your gitlab instance.


2. (optional) **GitHub Runner** - if you are using GitHub for your private repo, you may need to set up GitHub runner.  
    Please refer to [github runners docs](https://docs.github.com/en/actions/hosting-your-own-runners/about-self-hosted-runners) for installation instructions.  
    However, at the moment, GitHub provides 2000 CI minutes for org, so it may be to start with.


3. (optional) **Private Docker Registry** - to store testing environment docker image (it contains private tests).    
    You can use anything you like, but we recommend to use gitlab registry as it is already integrated with gitlab.


4. **Gitlab token** - with public repos access to export files to the public repo.  
    You need to add it as a secret to your private repo and use it in CI. Also if you want to use in it pipelines in students' repos, you need to add it as a secret to your course group.  
    If you have self-hosted gitlab instance or premium account, you can create service account for the course group using this [guide](https://docs.gitlab.com/ce/user/profile/service_accounts.html).  
    Otherwise, you have to create a separate account, grant access to the course group and use its [personal access token](https://docs.gitlab.com/ce/user/profile/personal_access_tokens.html). 

!!! note  
    For an automated setup, refer to the [manytask/infrastructure](https://github.com/manytask/infrastructure) repository with ansible playbooks.    
    These playbooks provide a stable and tested setup for the self-hosted gitlab instance, manytask instance and gitlab runners (configuration included).


## CI set up

!!! note  
    tl;dr:  Setup private and public CI to run tests. 

Configuring Continuous Integration (CI) is essential for automating the testing and deployment processes. Here's how to set it up for both private and public repositories.  

1. **Private Repo**  
    You can refer to the [course-template](https://github.com/manytask/course-template) for an example of a private repo with CI set up.
    * Private repo on GitHub (recommended way)  
      If your private repo is on GitHub, you can use GitHub Actions and [Reusable Workflows](https://github.com/manytask/workflows) provided by us to set up CI in a few clicks.

    * Private repo on GitLab  
      If your private repo is on GitLab, you can use GitLab CI, no pre-configured workflows are available at the moment.
   
    You need to set up the following CI jobs:

    1. on each push/mr/release - build testing environment docker image and keep as artifact to run tests in.  
    2. on each push/mr - run `checker check` inside docker image to test gold solution against private and public tests.   
    3. on each push/release - run `checker export` inside docker image to export to the public repository (requires gitlab token).  
    4. on each push/release - call manytask api to update deadlines (requires manytask push token).  
    5. on each push/release - build and publish testing environment docker image to the private docker registry (requires gitlab token).
   
    !!! note
        Don't forget to add MANYTASK_TOKEN and GITLAB_TOKEN as protected secrets to your private repo. 


2. **Public Repo**  
    Checker will push to this repo automatically and no pipelines to run, so nothing to configure directly here.  
    However the public repo should have `.gitlab-ci-students.yml` file in the root to set up it as `external ci file` for all students' repositories.
    This file should contain 2 jobs, both running inside test environment docker image:

    1. on each push/mr - run `checker grade` to test solution against private and public tests and push scores to manytask (requires manytask push token).
    2. on each mr in public repo - run `checker check --contribute` to test contributed public tests against gold solution. 


3. **Students' Group**
    Students' repos will use groups or shared runners from this group, so make sure that they are enabled.

    !!! note  
        Don't forget to add MANYTASK_TOKEN and GITLAB_TOKEN (optional) as protected secrets to your group. 

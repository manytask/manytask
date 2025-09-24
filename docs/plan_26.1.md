# Tasks for the 26.1 release cycle

## Software availability

The main goal of the project is to make Manytask available to a large number of people, including universities, teachers and students. To achieve this goal, Manytask will be distributed:
1. As a service internally for YSDA courses and for partnering programs (with plans to expand the list of programs in the future).
2. As a self-hosted solution with clear scripts and instruction on how to deploy it e.g. in Yandex Cloud.

The first option allows for using YSDA resources to test solutions and should be set up to make it easy for the teachers to host their courses. Since each course requires computational resources, this option can not be easily scaled to large number of programs at this stage. The second option can be used by both Universities that run educational program on computer science or one that includes suitable disciplines or by individual lecturers, who can e.g. rent machines in the cloud to host their own instance. Both options will benefit from having templates for the courses and some pre-made materials that are ready to be used by the teachers with pre-made tasks on common topics (teachers should be welcomed to modify and expand those).

To achieve these goals:
1. Manytask must be popularized
2. Manytask should be easy to install and set up and accompanied with good documentation 
3. The code base should evolve to make it flexible for different approaches in both managing the instance and setting up specific courses

## Improve the User management and better use course admin status ([#610](https://github.com/manytask/manytask/issues/610))

**The target** All courses are assigned to a Namespace. Namespace should have at least one Admin. Namespace can be created by Instance Admin. When created a group with respective name is also created on GitLab. In future, every user can have their own Namespace (under their name), where they can create courses.

### General info

Currently, the only users that can create courses is the instance admins. These can see and edit all the courses that are running on the instance. For the small organization that runs several courses, this may be acceptable, but when the number of courses increases, managing the whole list may be troublesome. Also, not having an option to assign admin role to a single course, somewhat restricts involving the students into the course management (they will have access to other courses, where they might still be students). Hence, clear role separation is needed.

Another issue is not having a clear way to separate visibility of the projects and organize them one way or the other. Currently, all courses that are available to a person is a plain list and instance admins see the list of all courses that are currently active on an instance. Moving towards hosting more courses, we should introduce a structure to this list.

The biggest problem here is that we can't just let people creating courses of their own, because of the danger of this list becoming unmanageable. We can ask people to use specific pattern to name their courses (currently [University]-[CourseName]-[Year]-[Semester]), but we can not enforce them to use this convention.

This task needs more planning with several options considered. We should research on what options are in use currently in other projects (good example is GitLab), but should not use an overengineered solution. So the first stage is to come up with a reasonable solution, before jumping into its implementation.

### The roles might be:

- **Instance admin** has access to all courses and can edit them, set grades on them. Can promote other users. Does not have to register on courses and can see courses they are not registered to (perhaps, as a separate list).
- **Teacher** can create courses and becomes admin on these courses. Does not appear in the course results table.
- **Program manager** can see the results table for a specific course, does not appear in the results table
- **Student**  can register for a course and submit solutions. Appears in the table on a specific course.


## Update the Checker infrastructure, fix and add tests, consolidate code and docs in the main repository ([#611](https://github.com/manytask/manytask/issues/611))

**The target** here is to have Checker repo merged into the Manytask repo. The extra copy and logic on parsing .manytask.yml course config should be removed into common space. It is essential to keep an option to install Checker independently from Manytask and clear instructions on how to do this should be provided. The Checker should be using the same infrastructure as Manytask web app, its tests and linters should be integrated into the same CI/CD workflow and the project tracking should be done in the same GitHub project.

### General info

Manytask Checker does two things: it produces public repository from the private and runs the grading pipelines that checks the students solutions and report the score. It is configured with .checker.yml file in the private repository and uses .manytask.yml file to see the structure of the repository, active tasks and their deadlines. Although the Checker is independent from the web app, it shares the code with it, it should also use up-to-date API handles and be capable of parsing the same course structure file as the web app.

Last dev cycle, the main focus was on the Manytask web app, while checker was kept very much unchanged (apart from small changes to make it compatible with the Manytask itself). This cycle the aim is to bring the Checker code to the standards, improve its tooling and tests, move the code to the main repository.

### Tooling

The Manytask checker should use the same tooling as the web app, including poetry, mypy, etc.

### Moving the code to the same repo

Pros:
- The Checker relies on the Manytask code base: it uses Manytask data structures, can parse .manytask.yml file. Currently, to keep it up to data, respective parts of the code have to be copy-pasted every time the breaking change happens.
- Checker and web app work together: checker uses API to interact with the web app, it parses the course description file to get information on active tasks. Hence both Manytask web app and Checker must be kept up to date with each other, and matching versions must be used. This requires synchronization in release cycles of both repositories.
- Having single repository with code makes it easier for developers to onboard.
- Having both web app and Checker in the same repo will make it easier to do the release

Cons:
- Checker is a separate application% some courses use it, other may not. Hence in some cases Checker can be a dead weight for the app.
- Checker is used from the Course CI/CD, which runs independently with the web app. It should be possible to install Checker independently.

## Documentation ([#510](https://github.com/manytask/manytask/issues/510))

**The target** is to have single entry point for docs, which should be organized into sections:
- Docs for **students**, including brief introduction to Git and general instruction on how to use Manytask (with links to onboarding course)
- Docs for **teachers** on how to create course, what should be in the private repo and how to set up deployment
- Docs for **admins** so that they can deploy and maintain their own instance of Manytask
- Docs for **developers** on how to start contributing to the code, run the dev instance and test the code locally.
Docs from checker repo should also be updated and transferred to the new location.

### General info

Current documentation lacks structure, may be deprecated and scattered between projects. We should move towards having single location for all the docs. The docs should be accessible from the landing page.

## Autascale runners

## Re-work the UI ([#407](https://github.com/manytask/manytask/issues/407))

**Target 1** is to re-work the scores table, that should be updated asynchronously.

Other requests from the teachers: should be able to add comment on a student, which is not visible for the students, be able to hide a person from the list.

We may consider an option to bundle with a third-part spreadsheet app if a suitable option exists.

**Target 2** is to improve the way the task are shown, introducing dependencies on the tasks and proposing options for the next course to take, when the course is near completion. The dependencies can be added to the .manytask.yml file. This representation can be completely independent with an option to switch between it and the current one.

**Target 3** Add a place to show lectures that are rendered from the content in the private/public repo. Something similar to github pages but with clear and documented way to add the notes to the course. Note that we can also make use from the Long Read as A Service (LAAS) project, that was developed in one of the Yandex Education hackathon.

### Scores table

We had to abandon Google Sheets as a database solution, but with that we also lost a lot of nice features of their interface. The current implementation is also static and is not updated asynchronously. So it can be improved in many ways. We can also look into self-hosted variants of spreadsheets, which can combine flexibility of Google Sheets with reliability of the database.

### Ways to show students progress

Current design show the task as a separate groups, that are not related to one another. It might be useful for the student to show them connected so that one understands which task depends on which. For instance, we can show that Classes depend on Structures in C++.

Each task group is usually related to a lecture. We can consider providing a ling to the lecture materials in the group, so that students can return to the lecture if they have problems solving their homeworks.

In general, the graph-like representation with linked theoretical material can help guiding students through the course.

### Deadlines calendar

When several courses have their deadline for the homework on one day, it may be stressful for both students and Manytask infrastructure. The deadlines can be planned more carefully if instance admin will be able to see when deadlines are set on all courses in one place.

## Template for the courses ([#613](https://github.com/manytask/manytask/issues/613))

**The target** is to have course template for Python/C++/Bash, so that the creation of the new courses will be straightforward.

This also include updating current courses so that they will take full benefits from checker infrastructure and so that courses will have the same solution submission workflow for all the courses (i.e. students should directly push to their fork on gitlab to initiate testing and grading). The templates should also include an option to deploy lecture notes as `docs as code` (the source files should be converted to html/pdf from md/latex files upon submission and the resulting rendered slides/notes should be available from the Manytask interface). Having both a template and an example is also an option, if the latter include tasks that use different programming languages and/or testing scripts.

### General info

To make it easier to onboard new teachers on the platform, we should provide templates for the courses that use different programming languages.

### Using Checker more

Some courses currently use their own version of checker, written for a specific language and toolset. In some cases this means that students have to interact with Manytask differently when they submit their solutions. These courses have to provide and maintain a specific set of instructions for the students, which can also confuse the latter if they are taking several courses simultaneously.

### Add an ability to write and deploy lecture notes with the course tasks

As the semester progresses, teacher issue tasks and sets deadlines to them. They can also provide lecture notes and codes written on the seminar. Currently, there is no standard in doing this: some teachers post their presentations/codes in chat, some add them to the LMS records. The templates should include tools and instructions on how to write and post lecture notes so those can be shipped with the tasks and/or deployed on a Manytask (e.g. as separate page in the web interface).

## Improve and document the Manytask app deployment workflow ([#612](https://github.com/manytask/manytask/issues/612))

**The target** is to help system administrators (or teachers that have the required knowledge) to deploy Manytask on their premises. This may include Terraform specs and step-by-step instruction on how to set up the Manytask instance in the cloud or on the server.


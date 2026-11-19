# About Manytask

<div class="mt-doc-intro">
<p>YOUR COURSE, CONNECTED</p>
<p>Manytask brings student repositories, automated tests, scores, and deadlines into one workflow. Choose your language and teaching tools, then make the routine work for you.</p>
</div>

<div class="mt-doc-paths">
<a href="../02_students/01_using_manytask.html"><strong>For students →</strong><span>Join a course and submit your solutions.</span></a>
<a href="../03_teachers/02_basic_example.html"><strong>For teachers →</strong><span>Build and run your first course.</span></a>
<a href="../05_development/01_local_development.html"><strong>For developers →</strong><span>Set up locally and contribute.</span></a>
<a href="../04_administration/03_deploy_guide.html"><strong>For institutions →</strong><span>Run your own Manytask instance.</span></a>
</div>

## How it works

1. **Prepare your course.** Keep tasks, tests, reference solutions, and configuration in a private repository. Export the materials students need.
2. **Students submit with Git.** Each student works in a personal repository and pushes their solutions.
3. **Run tests in CI.** The checker evaluates submissions and reports scores to Manytask.
4. **Follow progress together.** Students and teachers see results, task groups, and deadlines in the web app.

Read [Course as code](../03_teachers/01_course_as_code.md) for the full workflow, or follow [the basic example](../03_teachers/02_basic_example.md).

## Build your course

- **Your language and tools.** Configure the checker to run the tests your course needs. See [checker configuration](../03_teachers/05_checker_configuration.md).
- **Public and private materials.** Choose which tasks, tests, and starter files reach students. See [repository structure](../03_teachers/04_private_repository.md).
- **Scores and deadlines.** Define task groups, points, and late-submission rules in [course configuration](../06_reference/01_manytask_yml.md).
- **A starting point.** Adapt the [reference course template](../03_teachers/03_course_template.md).

## Manytask for institutions

Run your own Manytask instance for your university, school, or training program. Host courses on your infrastructure and connect the repositories your students and teachers use.

Start with the [deployment guide](../04_administration/03_deploy_guide.md) to spin up an instance, then use the [production setup](../04_administration/01_system_setup.md) and [production operations guide](../04_administration/02_production.md) to configure and maintain it.

### GitLab and SourceCraft

Manytask has adapters for GitLab and SourceCraft. Authentication, repository configuration, and CI setup depend on the platform and deployment. See [concepts](02_concepts.md) and the [deployment guide](../04_administration/03_deploy_guide.md) when configuring an instance.

## Join the project

The web app, checker, course template, review bot, and documentation live in the [Manytask monorepo](https://github.com/manytask/manytask). Read the [development guide](../05_development/01_local_development.md), explore [open issues](https://github.com/manytask/manytask/issues), or join the [Telegram community](https://t.me/manytask_chat).

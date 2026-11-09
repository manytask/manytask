# About Manytask

<div class="mt-doc-intro">
<p>YOUR COURSE, CONNECTED</p>
<p>Manytask brings student repositories, automated tests, scores, and deadlines into one workflow. Choose your language and teaching tools, then make the routine work for you.</p>
</div>

<div class="mt-doc-paths">
<a href="using_manytask.html"><strong>For students →</strong><span>Join a course and submit your solutions.</span></a>
<a href="basic_example.html"><strong>For teachers →</strong><span>Build and run your first course.</span></a>
<a href="dev.html"><strong>For developers →</strong><span>Set up locally and contribute.</span></a>
</div>

## How it works

1. **Prepare your course.** Keep tasks, tests, reference solutions, and configuration in a private repository. Export the materials students need.
2. **Students submit with Git.** Each student works in a personal repository and pushes their solutions.
3. **Run tests in CI.** The checker evaluates submissions and reports scores to Manytask.
4. **Follow progress together.** Students and teachers see results, task groups, and deadlines in the web app.

Read [Course as code](course_as_code.md) for the full workflow, or follow [the basic example](basic_example.md).

## Build your course

- **Your language and tools.** Configure the checker to run the tests your course needs. See [checker configuration](checker_config.md).
- **Public and private materials.** Choose which tasks, tests, and starter files reach students. See [repository structure](private_repo.md).
- **Scores and deadlines.** Define task groups, points, and late-submission rules in [course configuration](manytask_yml_reference.md).
- **A starting point.** Adapt the [reference course template](course_template.md).

## GitLab and SourceCraft

Manytask has adapters for GitLab and SourceCraft. Authentication, repository configuration, and CI setup depend on the platform and deployment. See [concepts](concepts.md) and the [deployment guide](deploy_guide.md) when configuring an instance.

## Join the project

The web app, checker, course template, review bot, and documentation live in the [Manytask monorepo](https://github.com/manytask/manytask). Read the [development guide](dev.md), explore [open issues](https://github.com/manytask/manytask/issues), or join the [Telegram community](https://t.me/manytask_chat).

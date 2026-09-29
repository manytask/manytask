# Development plan

Status: working draft · Updated: 29 September 2026

This plan describes the next development areas for Manytask. It is a direction for splitting work into reviewable issues, not a delivery schedule. [The prioritized backlog](https://github.com/orgs/manytask/projects/3/views/1) contains the individual tasks; issue links below are starting points and should be checked for current status before implementation.

The existing product model remains **course as code**: teachers maintain course material in a private repository, publish a safe public version, and students submit through their own repositories. Changes in this plan should make that flow easier to set up, safer to operate, and easier to understand.

## 1. Make course creation and deployment easier

**Goal:** a teacher can start a course from a maintained template and reach a first working release without assembling repositories and configuration by hand. An operator can deploy and update Manytask through a current, reproducible procedure.

PR [#1116](https://github.com/manytask/manytask/pull/1116) is a good starting point: its GitLab course form can create a private repository beside the public one and seed it from a language profile bundled with the app image. It does not yet provision a SourceCraft private repository, configure CI credentials, or complete the first release. Use it as a design reference and verify its behavior against the current code before merging or extending it.

### Teacher setup and reusable templates

- [ ] Let an authorized teacher choose a supported template and language profile while creating a course. Show the resulting private/public repository paths, visibility, selected template revision, and files to be generated before creating anything. Support linking an existing private repository and adding one later.
- [ ] Generate course-specific `.manytask.yml`, `.checker.yml`, CI settings, repository URLs, and non-secret variable instructions from one set of course inputs. Ask only for values that cannot be derived. Validate names, provider capabilities, permissions, and the public export before release.
- [ ] Give teachers a maintained scaffold and guide for creating or adapting their own course templates: task layout, solution stubs, public/private tests, language pipeline, local validation, and versioning. Verify the reference solution and student-visible export with a disposable sample course.
- [ ] Show a persistent setup checklist after repository creation: grant the teaching team access, configure required CI/runner credentials, build the test environment, check the reference solution, preview the public repository, release one coherent revision, and inspect a passing and failing student submission. Each step needs a status, direct action or instructions, and a safe retry path.
- [ ] Make provisioning recoverable when a provider or CI step fails. Repeated submission must not duplicate repositories or overwrite teacher work; partial resources and required manual cleanup must be visible.
- [ ] Add a task that uses review bot to the template.

### Operator deployment and Terraform

- [ ] Check and update the Terraform modules.

### SourceCraft organization guide

- [ ] Enrich the course template with SourceCraft CI/CD files.
- [ ] Publish a step-by-step guide to creating the Yandex Cloud organization used by SourceCraft, selecting its slug, enabling SourceCraft, linking the required billing/account context, creating the service identity, granting the least required roles, and connecting it to Manytask. Identify which steps require an organization administrator and which Manytask can verify.
- [ ] Record the actual SourceCraft quota names, current defaults, and where to view or request increases. Size the requested repository count, organization members/invitations, CI capacity, storage/registry usage, and applicable API limits from the expected number of courses and students.
- [ ] Verify organization access, invitations, public repository creation, student repository creation, CI execution, and a first grade report in a disposable course. Document known provider gaps, including private repository provisioning, with an explicit manual path until supported.

### Error reporting and logging

- [ ] Give students a clear result for every submission: current state, failed stage, a safe explanation, and the next useful action. Distinguish incorrect code, build/test failure, deadline or permission rejection, and a Manytask/CI outage. Show when a result is still pending or reporting failed, with a direct link to the relevant pipeline when available.
- [ ] Give teachers and administrators actionable errors for course creation, template validation, provider provisioning, CI setup, release, and grading. Identify the failed step, affected course or submission, whether retry is safe, and what needs manual correction. Show more detailed diagnostics only to authorized roles; do not expose private tests, student code from other accounts, or credentials.
- [ ] Use consistent error categories and stable codes across the web UI, API, checker, and MR reviewer. Return the same cause and correlation ID in user-visible errors and support diagnostics, while presenting detail appropriate to each role. Preserve partial-operation state so a retry does not hide or repeat completed work.
- [ ] Standardize structured logging with timestamps, severity, component, operation, correlation ID, and relevant course, provider, pipeline, or submission identifiers. Propagate IDs across service boundaries, log failures once at the right boundary, and redact tokens, secrets, private test output, and sensitive source content.
- [ ] Collect and retain logs with defined access and retention rules. Add alerts for stuck submissions, failed score reports, repeated provisioning errors, and release failures; link alerts to a runbook and the affected records.

**First deliverable:** a teacher creates a GitLab course and private repository from the maintained template, follows the checklist, and releases a passing and a failing sample task without editing application code. In a failed submission and a simulated provisioning failure, the student or teacher sees an appropriate next step, and an administrator can trace the same event through sanitized logs.

**Related backlog:** [#838](https://github.com/manytask/manytask/issues/838), [#599](https://github.com/manytask/manytask/issues/599), [#668](https://github.com/manytask/manytask/issues/668), [#1071](https://github.com/manytask/manytask/issues/1071), [#1002](https://github.com/manytask/manytask/issues/1002).

## 2. Connect one Manytask instance to multiple RMS instances

**Goal:** one deployment can host courses on several GitLab instances (for example, `gitlab.manytask.org` and `gitlab.com`) and SourceCraft. A course chooses its repository management system (RMS) and instance when it is created. Adding another RMS should not require a new Manytask deployment.

Today `LocalConfig.rms` selects one backend at startup, `main.py` constructs one `rms_api`, and GitLab authentication can be handled by that same adapter. The data model stores a single `User.rms_id` and GitLab-named repository fields on courses and namespaces. These are migration points, not just new settings in the course form.

- [ ] Define a registry of RMS connections with stable IDs, provider type, public/API URLs, supported capabilities, and health/status. Let an instance administrator add, test, rotate, disable, and inspect a connection. Keep credentials in protected storage with restricted access and audit records; never return them to browsers or logs.
- [ ] Move provider-specific URLs and credentials out of the global `.env` configuration into that registry. Keep deployment-level settings such as database and Flask secrets where they belong. Provide a migration that imports an existing single-RMS deployment without changing its course bindings; remove old RMS environment variables only after that path is verified.
- [ ] Separate **login identity** from **repository identity**. Give each Manytask user a stable local ID and explicit links to accounts on individual RMS connections. Specify enrollment when usernames differ, an account is renamed, or an account does not yet exist on the selected provider. Authentication must not silently determine a course's RMS.
- [ ] Bind every namespace and course to exactly one RMS connection. Store provider-neutral repository/group identifiers and paths, and route provisioning, enrollment, repository links, and cleanup through that binding. Prevent a request for one course from operating on another connection.
- [ ] Split authentication and RMS interfaces and construct adapters by connection ID. Document a capability matrix for GitLab and SourceCraft; reject unsupported operations with clear errors. Include the MR reviewer and checker callback configuration in the design.
- [ ] Make course creation show the selected provider, connection, repository paths, permissions, and setup checks before provisioning. Allow an existing provider repository to be linked where supported; make retries safe after partial provisioning.

**First deliverable:** two GitLab connections and one SourceCraft connection can coexist; a user can enroll in courses on each through correctly linked identities. Existing single-GitLab courses continue to work after migration. Automated tests cover connection isolation, permission checks, account linking, and provider failures; a real provider smoke test verifies the documented capability matrix.

**Related backlog:** [#1002](https://github.com/manytask/manytask/issues/1002), [#880](https://github.com/manytask/manytask/issues/880), [#951](https://github.com/manytask/manytask/issues/951), [#786](https://github.com/manytask/manytask/issues/786), [#1071](https://github.com/manytask/manytask/issues/1071).

## 3. Expand checker plugins and grading pipelines

**Goal:** teachers compose understandable, reusable checks for different languages and tasks. Students see useful feedback for every attempt, including failed builds and tests.

- [ ] Define a versioned plugin contract: inputs, allowed resources, structured outcome, score contribution, student-visible feedback, teacher-only diagnostics, and configuration validation. Distinguish a wrong answer from an infrastructure failure.
- [ ] Publish maintained pipeline profiles for Python, C++, Go, Rust, and shell tasks. Start with build, formatting/static checks, unit tests, time and memory limits, and partial scoring where appropriate. Document how course-specific plugins extend a profile.
- [ ] Add numeric script scoring with a validated output format. Show which stages contributed to the final score and why a stage failed, while keeping hidden tests and sensitive output private.
- [ ] Add code-comparison analysis that excludes provided templates and boilerplate, identifies matched fragments, and presents evidence to a teacher. Define an approved comparison corpus and measure false positives before using it in courses.
- [ ] Prototype LLM-assisted checks against a teacher-defined rubric. Store model, prompt/rubric version, input revision, cost, and structured findings; evaluate correctness and consistency on known submissions. A teacher reviews consequential findings before they affect a grade or integrity decision.
- [ ] Run expensive comparison and LLM work asynchronously with bounded cost, retries, and clear unavailable states. Treat source code as untrusted input, including instructions embedded in comments or files.

**Shared prerequisite — submission history:** register an attempt before running student code and retain successful, failed, timed-out, cancelled, and interrupted attempts. Keep an immutable or reconstructible snapshot of the exact submitted source, plus student, course, task, commit, pipeline/MR link, time, checker/configuration version, outcome, and assessments. Separate the attempt from the effective grade. Provide idempotent reporting and reconciliation for missing results, with access control and retention for source and diagnostics. A mutable repository URL or the current `Grade` row cannot serve as this history.

**First deliverable:** a fixture course exercises passing, failing, timed-out, and infrastructure-failed checks. Each creates one retrievable attempt and an understandable result; retries do not duplicate it. Language profiles and comparison/LLM pilots get separate acceptance datasets and quality thresholds.

**Related backlog:** [#1040](https://github.com/manytask/manytask/issues/1040), [#904](https://github.com/manytask/manytask/issues/904), [#886](https://github.com/manytask/manytask/issues/886), [#868](https://github.com/manytask/manytask/issues/868), [#906](https://github.com/manytask/manytask/issues/906), [#1090](https://github.com/manytask/manytask/issues/1090), [#1055](https://github.com/manytask/manytask/issues/1055).

## 4. Protect grading and investigate suspicious submissions

**Goal:** students cannot read the course's private repository or a credential capable of changing grades. Attempts to cross those boundaries are detectable and reviewable.

- [ ] Model access across the private and public repositories, student repositories, container registry, CI jobs, runners, checker workspace, result API, logs, and stored submission archives. Test the effective permissions after provisioning and when roles change; account for inherited group permissions.
- [ ] Verify the public export against an explicit allowlist of student-visible files. Keep solutions, private tests, release configuration, and credentials out of student repositories and artifacts. Add regression fixtures for overlapping public/private patterns.
- [ ] Separate a trusted grading controller from execution of student code. Do not place the Manytask report token, provider admin credentials, or an unrestricted Docker socket in the student's process, filesystem, environment, or readable CI output. Bind authenticated results to a specific course and submission; reject forged, replayed, or stale reports.
- [ ] Choose and enforce supported runner isolation for filesystem, processes, network, CPU, memory, and time. Exercise adversarial submissions on the production Linux runner, including attempts to read secrets, alter test results, spawn lingering processes, and access private repositories or registry images.
- [ ] Redact credentials and private diagnostics in checker output and application logs. Make token rotation and incident recovery testable; monitor missing reports, unusual score changes, repeated authentication failures, sandbox violations, and failed cleanup.
- [ ] Add a course-scoped suspicious-submission record linked to the immutable attempt: reason, evidence, detection source, reviewer, status, decision, and audit history. Give authorized teachers a review queue and a way to dismiss or resolve findings. Similarity or LLM output is evidence for review, not an automatic misconduct verdict.

**First deliverable:** security tests demonstrate that a student submission cannot retrieve private files or reporting credentials and cannot submit an authoritative grade. A teacher can inspect and resolve a flagged attempt without exposing another student's code to unauthorized users.

**Related backlog:** [#792](https://github.com/manytask/manytask/issues/792), [#869](https://github.com/manytask/manytask/issues/869), [#870](https://github.com/manytask/manytask/issues/870), [#822](https://github.com/manytask/manytask/issues/822), [#1039](https://github.com/manytask/manytask/issues/1039).

## 5. Pay down technical debt through bounded tasks

Use the [prioritized backlog](https://github.com/orgs/manytask/projects/3/views/1) as the issue inventory. Keep broad debt issues as categories and create small changes with a failure mode, affected components, and a measurable exit condition. Recheck issue status and acceptance criteria before assigning work.

- [ ] Unify shared course configuration and deadline interpretation between web and checker; test the actual checker → API → database contract, including timestamps, score units, errors, and retries.
- [ ] Extract cohesive services from large API and storage modules. Give grading and course-configuration updates explicit transaction boundaries, stable task identities, impact previews, and rollback behavior.
- [ ] Make score delivery bounded, idempotent, and ordered so an old retry cannot silently replace a newer assessment. Preserve audited manual overrides and intentional regrades.
- [ ] Make course releases reproducible: identify the exact configuration, image, and exported repository revision promoted together, and provide a rollback path.
- [ ] Maintain dependency, migration, backup/restore, documentation, and cross-component test coverage alongside feature work. Prioritize confirmed correctness and security defects before cosmetic cleanup.

**First deliverable:** each debt item has a reproducer or measurable maintenance cost, a small reviewable issue, regression coverage where appropriate, and a documented migration or rollout path. An umbrella issue is complete only when its named children meet their acceptance criteria.

**Related backlog:** [#833](https://github.com/manytask/manytask/issues/833), [#642](https://github.com/manytask/manytask/issues/642), [#878](https://github.com/manytask/manytask/issues/878), [#1041](https://github.com/manytask/manytask/issues/1041), [#489](https://github.com/manytask/manytask/issues/489), [#1090](https://github.com/manytask/manytask/issues/1090).

## 6. Give students and teachers useful statistics

**Goal:** students understand their progress and find their next useful task; teachers can see where a course needs attention. Build both views on the same submission and assessment definitions.

- [ ] Define metrics before charts: eligible students, available tasks, distinct tasks solved, attempts to first success, points, failure categories, manual-review turnaround, and time periods. Specify treatment of staff, hidden students, disabled tasks, late enrollment, retries, regrades, and missing events.
- [ ] Add a private student progress view with solved tasks, recent improvements, topic/group progress, attempt history, and links to available next tasks. Test whether it helps students solve more distinct problems; page views alone are not a success measure.
- [ ] Add a teacher-only Statistics page in the course menu. Start with task completion and score distributions, attempts to first success, common failure stages, stalled work, and review backlog. Link aggregate numbers to authorized underlying attempts.
- [ ] Show data freshness and collection gaps. Reconcile each chart with a small known dataset before rollout, and set performance budgets for a realistic course size.
- [ ] Provide a versioned export API or CSV for an external LMS. Keep institutional cohorts, semesters, and official gradebooks in that system.

**First deliverable:** a student can identify a next task and explain their progress; a teacher can identify a problematic task and inspect the relevant submissions. Both views reconcile with the same recorded attempts and effective grades. Pilot targets are agreed before claiming improved engagement or course outcomes.

**Related backlog:** [#407](https://github.com/manytask/manytask/issues/407), [#1040](https://github.com/manytask/manytask/issues/1040), [#876](https://github.com/manytask/manytask/issues/876), [#872](https://github.com/manytask/manytask/issues/872).

## 7. Improve daily UI and UX

**Goal:** students and teachers can finish common tasks and recover from errors without needing knowledge of Manytask internals. Use the [UI/UX backlog](https://github.com/orgs/manytask/projects/3/views/1) to select small, testable journeys.

- [ ] Map the main student, teacher, namespace-admin, and instance-admin journeys. Make navigation, search, tables, permissions, empty states, and error messages consistent.
- [ ] Show submission status, failed stage, feedback, grade calculation, deadline effect, and direct pipeline/MR links on task pages. Make pending manual review and infrastructure failures distinguishable from incorrect solutions.
- [ ] Use the course setup flow in section 1 for creation and release; keep its progress, failure, and retry states consistent with the rest of the interface.
- [ ] Improve task ordering and future-task preview; add course-level resources and lecture links. Keep the first iteration of lecture publishing static and reviewable.
- [ ] Improve administration with searchable course/user lists, explicit role scopes, and course-specific Hide/Unhide controls. Define how hidden students affect scoreboards and statistics.

**First deliverable:** a student can find a task, submit, understand a failed attempt, and follow the next action. A teacher can find that attempt and manage course access without a hidden permission change. The first-course journey is covered in section 1.

**Related backlog:** [#407](https://github.com/manytask/manytask/issues/407), [#1037](https://github.com/manytask/manytask/issues/1037), [#634](https://github.com/manytask/manytask/issues/634), [#678](https://github.com/manytask/manytask/issues/678), [#751](https://github.com/manytask/manytask/issues/751), [#954](https://github.com/manytask/manytask/issues/954), [#1071](https://github.com/manytask/manytask/issues/1071).

## Suggested delivery sequence

| Milestone | Scope | Evidence to exit |
| --- | --- | --- |
| A. Secure the current flow | Private export, credential isolation, trustworthy reporting, runner tests, and urgent grading correctness fixes | Adversarial and end-to-end grading tests pass on a supported runner; a student cannot obtain private material or change a grade. |
| B. Make the first course easy | GitLab template creation, teacher setup checklist, updated Terraform/deployment path, and SourceCraft organization guide | A teacher releases a sample course; an operator deploys a healthy instance and verifies SourceCraft pilot prerequisites. |
| C. Record every attempt | Submission IDs, source archive, attempt lifecycle, failed results, idempotent delivery, and assessment history | Passing, failing, interrupted, and retried submissions are durable, ordered, and retrievable with correct permissions. |
| D. Support multiple RMS connections | Connection registry, identity links, provider-neutral course binding, migration, and guided setup | Existing courses work after migration; courses on two GitLab instances and SourceCraft coexist in one deployment. |
| E. Improve learning and teaching workflows | Language profiles, pilot comparison/LLM review, student progress, teacher statistics, and targeted UI work | Results and metrics reconcile to attempts; teachers review automated findings; pilot users complete agreed scenarios. |

Small UI and debt fixes can ship throughout. Before scheduling a milestone, name an owner and pilot course, choose supported providers/languages, split work into issues, and agree numerical quality and performance targets. Update this page as those decisions and implementation results become known.

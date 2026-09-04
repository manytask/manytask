# Changelog

## [26.0.3](https://github.com/manytask/manytask/releases/tag/26.0.3) - 2026-09-02

This release includes bug fixes, updates to doc and minor UI improvements.

### Dependency Updates

- chore(deps): bump gitpython from 3.1.45 to 3.1.58 in /checker in the uv group across 1 directory by @[dependabot[bot]](https://github.com/apps/dependabot) in [#1052](https://github.com/$OWNER/$REPOSITORY/pull/1052)
- chore(deps): bump astral-sh/setup-uv from 9.0.0 to 10.0.1 by @[dependabot[bot]](https://github.com/apps/dependabot) in [#1047](https://github.com/$OWNER/$REPOSITORY/pull/1047)
- chore(deps): bump cryptography from 48.0.1 to 50.0.0 in /manytask in the uv group across 1 directory by @[dependabot[bot]](https://github.com/apps/dependabot) in [#1038](https://github.com/$OWNER/$REPOSITORY/pull/1038)

### Other changes

- docs: fix the guide for checker config file by @zhmurov in [#1054](https://github.com/$OWNER/$REPOSITORY/pull/1054)
- fix(sourcecraft): use RMS-native username for project existence check by @Ch0p1k3 in [#1059](https://github.com/$OWNER/$REPOSITORY/pull/1059)
- feat: allow disabling self-signup via MANYTASK_DISABLE_SIGNUP by @ObjatieGroba in [#1061](https://github.com/$OWNER/$REPOSITORY/pull/1061)
- feat(gitlab): grant students reporter access to the course public repo by @ObjatieGroba in [#1060](https://github.com/$OWNER/$REPOSITORY/pull/1060)
- refactor: Add datastructure that holds the scores table data by @zhmurov in [#1050](https://github.com/$OWNER/$REPOSITORY/pull/1050)
- feat: add an option to run tests on all tasks with checker by @zhmurov in [#1044](https://github.com/$OWNER/$REPOSITORY/pull/1044)
- feat: add back button to the page where course secret is entered by @zhmurov in [#1035](https://github.com/$OWNER/$REPOSITORY/pull/1035)
- feat: Add search bar to the list of courses by @zhmurov in [#1031](https://github.com/$OWNER/$REPOSITORY/pull/1031)
- feat: sort courses by status enum order, not by their alphabetical order by @zhmurov in [#1033](https://github.com/$OWNER/$REPOSITORY/pull/1033)
- feat: support negative scores by @KaurkerDevourer in [#1045](https://github.com/$OWNER/$REPOSITORY/pull/1045)
- feat: transfer changes from checker repo by @zhmurov in [#1042](https://github.com/$OWNER/$REPOSITORY/pull/1042)
- feat: Add navigation buttons to course is not ready page by @zhmurov in [#1036](https://github.com/$OWNER/$REPOSITORY/pull/1036)
- feat: Implement table view for the list of courses by @zhmurov in [#1028](https://github.com/$OWNER/$REPOSITORY/pull/1028)
- fix: Adapt cpp checker to new test environment by @domwst in [#1046](https://github.com/$OWNER/$REPOSITORY/pull/1046)
- docs: update contributing by @zhmurov in [#1030](https://github.com/$OWNER/$REPOSITORY/pull/1030)
- docs: Update changelog with last several releases by @zhmurov in [#1029](https://github.com/$OWNER/$REPOSITORY/pull/1029)
- Add Vanya Luchsh to the list of developers by @zhmurov in [#1043](https://github.com/$OWNER/$REPOSITORY/pull/1043)
- fix: remove link to GitLab account from the drop-down menu by @zhmurov in [#1034](https://github.com/$OWNER/$REPOSITORY/pull/1034)
- fix: align grade calculation with displayed percent by @kudala-bharani in [#1019](https://github.com/$OWNER/$REPOSITORY/pull/1019)


## [26.0.2](https://github.com/manytask/manytask/releases/tag/26.0.2) - 2026-08-04

Release 26.0.2 fixes the bug that prevented creating new course from the interface.

### Fixes

- fix: use correct signature when calling check-if-admin function by @zhmurov in [#1026](https://github.com/manytask/manytask/pull/1026)

**Full Changelog**: [26.0.1...26.0.2](https://github.com/manytask/manytask/compare/26.0.1...26.0.2)

## [26.0.1](https://github.com/manytask/manytask/releases/tag/26.0.1) - 2026-08-03

Welcome to release 26.0.1! In this release, a bug related to user role checks has been addressed.

### Features

- feat: hide gitlab_course_group in UI for non-GitLab RMS backends by @Ch0p1k3 in [#1017](https://github.com/manytask/manytask/pull/1017)
- feat: make export push options configurable via .checker.yml by @Ch0p1k3 in [#1016](https://github.com/manytask/manytask/pull/1016)

### Fixes

- fix: expose instance_admin role globally in get_user_roles by @Ch0p1k3 in [#1025](https://github.com/manytask/manytask/pull/1025)
- fix(checker): use dict(os.environ) instead of os.environ.__dict__ by @Ch0p1k3 in [#1024](https://github.com/manytask/manytask/pull/1024)
- fix: Remove check_if_course_admin(..) function by @zhmurov in [#1022](https://github.com/manytask/manytask/pull/1022)

### Dependency Updates

- chore(deps): bump astral-sh/setup-uv from 8.3.2 to 9.0.0 by @dependabot in [#1020](https://github.com/manytask/manytask/pull/1020)

**Full Changelog**: [26...26.0.1](https://github.com/manytask/manytask/compare/26...26.0.1)

## [26.0.0](https://github.com/manytask/manytask/releases/tag/26) - 2026-07-24

This release marks a major milestone for Manytask, introducing **SourceCraft** support, a new **namespaces** system, a consolidated **monorepo** structure with the Checker, extensive documentation improvements, and numerous performance and reliability fixes.

### Highlights

- **SourceCraft support**: full `AuthApi`, `RmsApi`, and signup flow implementations for SourceCraft, a SourceCraft-flavored course creation UI/UX, service account connection via authorized keys, a dedicated `docker-compose` setup, and a configurable Yandex OAuth base URL (`YANDEX_ID_OAUTH_BASE`).
- **Namespaces**: a brand-new namespaces system replaces the old admin panel, with namespace models, configuration, REST API endpoints, admin authorization and access control, a new namespace panel UI, GitLab integration for namespace/group management, and support for empty namespaces and existing GitLab groups.
- **Monorepo & Checker integration**: the Checker is now part of the Manytask monorepo with a secure pytest plugin, unified linting/testing/type-checking (mypy) across projects, migration from Poetry to **uv**, and a consolidated `docker-compose` with shared reverse-proxy and Postgres for production.

### Features

- feat: update signup for SourceCraft in [#819](https://github.com/manytask/manytask/pull/819)
- feat: implement `AuthApi` for SourceCraft in [#811](https://github.com/manytask/manytask/pull/811)
- feat: implement `RmsApi` for SourceCraft in [#808](https://github.com/manytask/manytask/pull/808)
- feat: allow creating a course for an existing course group in [#816](https://github.com/manytask/manytask/pull/816)
- feat: allow empty namespaces in [#807](https://github.com/manytask/manytask/pull/807)
- feat: prevent updating user score and config for finished courses in [#802](https://github.com/manytask/manytask/pull/802)
- feat: namespaces support in [#727](https://github.com/manytask/manytask/pull/727) and namespace panel UI in [#722](https://github.com/manytask/manytask/pull/722), [#721](https://github.com/manytask/manytask/pull/721), [#720](https://github.com/manytask/manytask/pull/720)
- feat: transliteration-aware search in [#989](https://github.com/manytask/manytask/pull/989)
- feat: allow setting user course admin status from the edit course page in [#1008](https://github.com/manytask/manytask/pull/1008)
- feat: make Yandex OAuth base URL configurable in [#1013](https://github.com/manytask/manytask/pull/1013)
- feat: add profile menu to course list page in [#979](https://github.com/manytask/manytask/pull/979)
- feat: better logging for the task report method in [#931](https://github.com/manytask/manytask/pull/931)
- feat: do not ignore group task/report pipelines and parameters in [#894](https://github.com/manytask/manytask/pull/894)
- feat: MR reviewer bot integration in [#1000](https://github.com/manytask/manytask/pull/1000), [#941](https://github.com/manytask/manytask/pull/941), [#1006](https://github.com/manytask/manytask/pull/1006)
- feat: Terraform config for Yandex Cloud in [#753](https://github.com/manytask/manytask/pull/753)
- feat: course template support in [#976](https://github.com/manytask/manytask/pull/976)
- feat: simple local development environment with GitLab in [#925](https://github.com/manytask/manytask/pull/925)

### Fixes

- fix: JavaScript field validation in [#821](https://github.com/manytask/manytask/pull/821)
- fix: do not demote group owners to maintainers in [#820](https://github.com/manytask/manytask/pull/820)
- fix: allow grade downgrade outside freeze statuses in [#809](https://github.com/manytask/manytask/pull/809)
- fix: the order in which score table columns are read in [#810](https://github.com/manytask/manytask/pull/810)
- fix: create namespace if the group already exists in GitLab in [#803](https://github.com/manytask/manytask/pull/803)
- fix: resolve JSON comparison error when updating grade formulas in [#756](https://github.com/manytask/manytask/pull/756)
- fix: prevent grade recalculation in [#841](https://github.com/manytask/manytask/pull/841)
- fix: eliminate N+1 queries on the student list page in [#844](https://github.com/manytask/manytask/pull/844), [#845](https://github.com/manytask/manytask/pull/845)
- fix: various database optimizations in [#895](https://github.com/manytask/manytask/pull/895), [#853](https://github.com/manytask/manytask/pull/853)
- fix: fail pipeline if score reporting failed in [#1004](https://github.com/manytask/manytask/pull/1004)
- fix: check namespace admin status when verifying course access in [#1007](https://github.com/manytask/manytask/pull/1007)
- fix: return empty string for group path with group id -1 in SourceCraft in [#920](https://github.com/manytask/manytask/pull/920)
- fix: extend SourceCraft API call timeout in [#919](https://github.com/manytask/manytask/pull/919)
- fix: add sign-out link to all authenticated pages in [#864](https://github.com/manytask/manytask/pull/864)

### Performance

- perf: N+1 query elimination on student list and bulk scores queries in [#844](https://github.com/manytask/manytask/pull/844), [#845](https://github.com/manytask/manytask/pull/845)
- perf: general DB query optimizations with added tests in [#853](https://github.com/manytask/manytask/pull/853), [#895](https://github.com/manytask/manytask/pull/895)

### Documentation

- docs: new Checker documentation and updated table of contents in [#747](https://github.com/manytask/manytask/pull/747)
- docs: deploy guide and production documentation in [#746](https://github.com/manytask/manytask/pull/746)
- docs: consolidated developer and teacher documentation into unified files in [#995](https://github.com/manytask/manytask/pull/995), [#990](https://github.com/manytask/manytask/pull/990)
- docs: references for `.manytask.yml` and `.checker.yml` config files in [#911](https://github.com/manytask/manytask/pull/911), [#907](https://github.com/manytask/manytask/pull/907)
- docs: documentation for built-in plugins and pipelines in [#910](https://github.com/manytask/manytask/pull/910), [#930](https://github.com/manytask/manytask/pull/930)
- docs: minimal config examples and a no-checker setup example in [#948](https://github.com/manytask/manytask/pull/948), [#999](https://github.com/manytask/manytask/pull/999)
- docs: added `about` page in [#675](https://github.com/manytask/manytask/pull/675)
- docs: updated developer list, docs links, and structure in [#772](https://github.com/manytask/manytask/pull/772), [#832](https://github.com/manytask/manytask/pull/832), [#956](https://github.com/manytask/manytask/pull/956)

### Build, CI/CD & Refactoring

- chore: migrated to **uv** in the Makefile, Dockerfile, and Dependabot config in [#769](https://github.com/manytask/manytask/pull/769), [#771](https://github.com/manytask/manytask/pull/771), [#773](https://github.com/manytask/manytask/pull/773)
- chore: enabled mypy and linting for the Checker in [#784](https://github.com/manytask/manytask/pull/784), [#867](https://github.com/manytask/manytask/pull/867)
- chore: consolidated monorepo structure and compose files in [#962](https://github.com/manytask/manytask/pull/962), [#965](https://github.com/manytask/manytask/pull/965), [#975](https://github.com/manytask/manytask/pull/975)
- chore: replaced deprecated `docker-compose` with `docker compose` v2 in [#874](https://github.com/manytask/manytask/pull/874)
- chore: release drafting now relies on commit messages in [#916](https://github.com/manytask/manytask/pull/916)
- chore: clarified role management in [#1012](https://github.com/manytask/manytask/pull/1012)
- refactor: removed unused methods, files, and legacy admin panel code in [#897](https://github.com/manytask/manytask/pull/897), [#921](https://github.com/manytask/manytask/pull/921), [#847](https://github.com/manytask/manytask/pull/847)
- chore: improved clang-format/clang-tidy plugin configuration in [#859](https://github.com/manytask/manytask/pull/859), [#860](https://github.com/manytask/manytask/pull/860)

### Dependency Updates

Numerous dependency bumps via Dependabot, including `cryptography`, `pydantic`, `python-gitlab` (6.4.0 → 8.3.0), `mypy`, `pytest` (8.4.0 → 9.0.3), `authlib`, `gunicorn`, `alembic`, `ruff`, `astral-sh/setup-uv`, and various GitHub Actions.

### New Contributors

- @scanhex12 made their first contribution in [#787](https://github.com/manytask/manytask/pull/787)
- @Siegmeyer1 made their first contribution in [#808](https://github.com/manytask/manytask/pull/808)
- @heavenyoung1 made their first contribution in [#836](https://github.com/manytask/manytask/pull/836)
- @Dmi4er4 made their first contribution in [#845](https://github.com/manytask/manytask/pull/845)
- @turazashvili made their first contribution in [#864](https://github.com/manytask/manytask/pull/864)
- @Ch0p1k3 made their first contribution in [#1013](https://github.com/manytask/manytask/pull/1013)

**Full Changelog**: [25.2.1...26.0.0](https://github.com/manytask/manytask/compare/25.2.1...26.0.0)

## [25.2.1](https://github.com/manytask/manytask/releases/tag/25.2.1) - 2025-12-04

This release enhances functionality, security, performance, and maintains up-to-date dependencies. Note that this is the last release before moving to the namespaces model.

Summary of changes:

- Added `is_solved` field to the Grade table to allow saving results for large homeworks.
- It is now possible to reduce score with the API using the `allow_reduction` parameter.
- Admins can toggle whether personal information is shown in the scores table.
- Upgraded to Python 3.14 and migrated to uv.
- Admins can add comments on students.
- Prevented personal data leaks, fixed GitLab search and log formatting, corrected score display (excludes bonuses), and updated the Dependabot config and uv usage.
- Speeded up tests, updated documentation for students and the API, and upgraded key dependencies (ruff, pydantic, alembic, etc.).

### Features

- feat: Add is_solved field into Grade table by @zhmurov in [#704](https://github.com/manytask/manytask/pull/704)
- feat: Allow reducting students score with api by @zhmurov in [#734](https://github.com/manytask/manytask/pull/734)
- feat: add personal info toggle and widen scores table by @D1sney in [#726](https://github.com/manytask/manytask/pull/726)
- feat: bump to python 3.14 and migrate to UV by @KIoppert in [#691](https://github.com/manytask/manytask/pull/691)
- feat: add namespace models by @gagarinkomar in [#672](https://github.com/manytask/manytask/pull/672)
- feat: Create in-memory RMS and use it in tests by @zhmurov in [#535](https://github.com/manytask/manytask/pull/535)
- feat: add comments column for admins by @prawwtocol in [#627](https://github.com/manytask/manytask/pull/627)
- feat: Allow to use username in task url template by @SergeyParamoshkin in [#615](https://github.com/manytask/manytask/pull/615)
- feat: speedup tests by @prawwtocol in [#669](https://github.com/manytask/manytask/pull/669)
- feat: Database api authorization via course token by @domwst in [#602](https://github.com/manytask/manytask/pull/602)

### Fixes

- fix: prevent personal data leak in database API by @D1sney in [#738](https://github.com/manytask/manytask/pull/738)
- fix: Update dependabot.yml by @kanmir in [#735](https://github.com/manytask/manytask/pull/735)
- fix: Use uv in the Makefile by @zhmurov in [#705](https://github.com/manytask/manytask/pull/705)
- fix: Gitlab project search by @domwst in [#670](https://github.com/manytask/manytask/pull/670)
- fix: reformat logs by @prawwtocol in [#630](https://github.com/manytask/manytask/pull/630)
- fix: Don't account for bonuses in the score display by @domwst in [#629](https://github.com/manytask/manytask/pull/629)

### Tests and CI/CD

- feat: Create in-memory RMS and use it in tests by @zhmurov in [#535](https://github.com/manytask/manytask/pull/535)
- feat: speedup tests by @prawwtocol in [#669](https://github.com/manytask/manytask/pull/669)
- chore(deps-dev): bump testcontainers from 4.12.0 to 4.13.0 by @dependabot in [#609](https://github.com/manytask/manytask/pull/609)

### Enhancement

- refactor: Remove black, isort and flake8 from the package list by @zhmurov in [#622](https://github.com/manytask/manytask/pull/622)
- fix: reformat logs by @prawwtocol in [#630](https://github.com/manytask/manytask/pull/630)
- refactor: optimize repo existance check by @dmasloff in [#616](https://github.com/manytask/manytask/pull/616)

### Documentation

- docs: Add general documentation on how to use Manytask for the students by @zhmurov in [#676](https://github.com/manytask/manytask/pull/676)
- docs: Update API docs by @zhmurov in [#674](https://github.com/manytask/manytask/pull/674)
- docs: Remove old development strategy, while keeping course as code description by @zhmurov in [#677](https://github.com/manytask/manytask/pull/677)
- docs: add structure to the TOC tree by @zhmurov in [#673](https://github.com/manytask/manytask/pull/673)

### Dependency Updates

- chore(deps-dev): bump ruff from 0.13.1 to 0.14.0 by @dependabot in [#687](https://github.com/manytask/manytask/pull/687)
- chore(deps): bump pydantic from 2.11.1 to 2.12.0 by @dependabot in [#685](https://github.com/manytask/manytask/pull/685)
- chore(deps): bump alembic from 1.16.1 to 1.17.0 by @dependabot in [#684](https://github.com/manytask/manytask/pull/684)
- chore(deps): bump authlib from 1.6.4 to 1.6.5 by @dependabot in [#679](https://github.com/manytask/manytask/pull/679)
- chore(deps): bump python-gitlab from 6.2.0 to 6.4.0 by @dependabot in [#626](https://github.com/manytask/manytask/pull/626)
- chore(deps-dev): bump mypy from 1.17.0 to 1.18.2 by @dependabot in [#619](https://github.com/manytask/manytask/pull/619)
- chore(deps-dev): bump ruff from 0.12.0 to 0.13.1 by @dependabot in [#618](https://github.com/manytask/manytask/pull/618)
- chore(deps-dev): bump testcontainers from 4.12.0 to 4.13.0 by @dependabot in [#609](https://github.com/manytask/manytask/pull/609)
- chore(deps): bump authlib from 1.6.0 to 1.6.4 by @dependabot in [#621](https://github.com/manytask/manytask/pull/621)
- chore(deps-dev): bump pytest-cov from 6.3.0 to 7.0.0 by @dependabot in [#607](https://github.com/manytask/manytask/pull/607)

**Full Changelog**: [25.2.0...25.2.1](https://github.com/manytask/manytask/compare/25.2.0...25.2.1)

## [25.2.0](https://github.com/manytask/manytask/releases/tag/25.2.0) - 2025-09-12

### Release Highlights

- **New onboarding:** separate signup and enrollment, plus an extra signup step for first-time GitLab users.
- **Grading upgrades:** bonus column, interpolated scores, configurable grade system, and percent of accumulated score shown in tables/CSV.
- **Course management:** multiple courses supported, course lifetime, join-course section on main page, course selector, and course editing page.
- **Admin experience:** new admin panel (including link on the "not ready" page), ability to change names, and stronger admin checks.
- **Performance:** major optimizations for course and course table pages, and caching for static assets.
- **Data model cleanup:** store RMS ID, avoid saving GitLab instance URL, remove repo name from DB, move instance data out of course, and remove Solutions API.
- **UX and visibility:** student repo links, student names in score tables/CSV, preserved ordering of groups/tasks, and more detailed logging.

### Features

- feat: recalculate grade in the table by @KIoppert in [#596](https://github.com/manytask/manytask/pull/596)
- feat: bonus column in the course table by @KIoppert in [#597](https://github.com/manytask/manytask/pull/597)
- feat: extra signup for new gitlab users by @gagarinkomar in [#547](https://github.com/manytask/manytask/pull/547)
- feat: Student repo links by @domwst in [#601](https://github.com/manytask/manytask/pull/601)
- feat: log more actions by @KIoppert in [#585](https://github.com/manytask/manytask/pull/585)
- feat: Support interpolated scores by @domwst in [#576](https://github.com/manytask/manytask/pull/576)
- feat: lifetime for courses by @KIoppert in [#539](https://github.com/manytask/manytask/pull/539)
- feat: add link to admin panel on not-ready page by @KIoppert in [#557](https://github.com/manytask/manytask/pull/557)
- feat: add-grade-system by @dmasloff in [#428](https://github.com/manytask/manytask/pull/428)
- feat: Store RMS ID in the database by @zhmurov in [#494](https://github.com/manytask/manytask/pull/494)
- feat: remove unnecessary session refreshes by @gagarinkomar in [#477](https://github.com/manytask/manytask/pull/477)
- feat: separate the signup and enrollement by @gagarinkomar in [#451](https://github.com/manytask/manytask/pull/451)
- feat: remove gitlab admins + add admin panel + ability to change the name by @KIoppert in [#474](https://github.com/manytask/manytask/pull/474)
- feat: add join course section to main page by @KIoppert in [#475](https://github.com/manytask/manytask/pull/475)
- feat: add editing page course by @DmitryMelentsov in [#437](https://github.com/manytask/manytask/pull/437)
- feat: add course selector by @DmitryMelentsov in [#439](https://github.com/manytask/manytask/pull/439)
- feat: Add check_is_course_admin(..) method to StorageApi and use it by @zhmurov in [#453](https://github.com/manytask/manytask/pull/453)
- feat: Do not save GitLab instance url in Users and Courses DB models by @zhmurov in [#448](https://github.com/manytask/manytask/pull/448)
- feat: add first and last name in score table by @KIoppert in [#458](https://github.com/manytask/manytask/pull/458)
- feat: Do not create user when store_score(..) and get/sync_stored_user(..) are called by @zhmurov in [#440](https://github.com/manytask/manytask/pull/440)
- feat: added validation, as well as additional information by @KIoppert in [#450](https://github.com/manytask/manytask/pull/450)
- feat: add first and last name fields to StoredUser model by @KIoppert in [#434](https://github.com/manytask/manytask/pull/434)
- feat: allow to set large task type in configs by @dmasloff in [#424](https://github.com/manytask/manytask/pull/424)
- feat: Show percent of the accumulated score in the table by @zhmurov in [#384](https://github.com/manytask/manytask/pull/384)
- feat: Remove github reviewer assignment on PR creation by @zhmurov in [#402](https://github.com/manytask/manytask/pull/402)
- feat: add supporting many courses by @gagarinkomar in [#392](https://github.com/manytask/manytask/pull/392)
- feat: remove link to the course in DataBaseApi by @gagarinkomar in [#391](https://github.com/manytask/manytask/pull/391)
- feat: pass course name in url and edit auth path by @gagarinkomar in [#388](https://github.com/manytask/manytask/pull/388)
- feat: move instance data from the course by @gagarinkomar in [#383](https://github.com/manytask/manytask/pull/383)
- feat: Remove solutions API by @zhmurov in [#382](https://github.com/manytask/manytask/pull/382)
- feat: Show student names in the scores table and CSV export by @zhmurov in [#366](https://github.com/manytask/manytask/pull/366)
- feat: keep the order of groups and tasks by @gagarinkomar in [#343](https://github.com/manytask/manytask/pull/343)
- feat: Run tests on all pull request and when changes are pushed to any branch by @zhmurov in [#356](https://github.com/manytask/manytask/pull/356)
- feat: install poetry command by @prawwtocol in [#347](https://github.com/manytask/manytask/pull/347)
- feat: use deadlines and tasks stored in DB instead of filesystem by @gagarinkomar in [#322](https://github.com/manytask/manytask/pull/322)
- feat: add deadline config synchronization to database by @gagarinkomar in [#320](https://github.com/manytask/manytask/pull/320)

### Fixes

- fix: Account settings link by @domwst in [#604](https://github.com/manytask/manytask/pull/604)
- fix: hidden tasks were displayed by @KIoppert in [#590](https://github.com/manytask/manytask/pull/590)
- fix: allow table visibility without final grade config by @dmasloff in [#587](https://github.com/manytask/manytask/pull/587)
- fix: Create manytask user on signup by @domwst in [#575](https://github.com/manytask/manytask/pull/575)
- fix: naming in placeholders by @KIoppert in [#574](https://github.com/manytask/manytask/pull/574)
- fix: Form field annotation by @domwst in [#573](https://github.com/manytask/manytask/pull/573)
- fix: add csrf validation to signup by @KIoppert in [#572](https://github.com/manytask/manytask/pull/572)
- fix: Proper docker build target by @domwst in [#559](https://github.com/manytask/manytask/pull/559)
- fix: Automatically create user on login by @domwst in [#568](https://github.com/manytask/manytask/pull/568)
- fix: round percents to decimals and computing percent without reload by @KIoppert in [#561](https://github.com/manytask/manytask/pull/561)
- fix: revert bump appleboy/ssh-action by @KIoppert in [#567](https://github.com/manytask/manytask/pull/567)
- fix: default names for public repo and students groups by @KIoppert in [#558](https://github.com/manytask/manytask/pull/558)
- fix: fix problem with docker cache by @KIoppert in [#562](https://github.com/manytask/manytask/pull/562)
- fix: Add dmasloff into developers list by @zhmurov in [#546](https://github.com/manytask/manytask/pull/546)
- fix: data leak in `test_data_api.py` by @KIoppert in [#524](https://github.com/manytask/manytask/pull/524)
- fix: Fix github pages by @zhmurov in [#496](https://github.com/manytask/manytask/pull/496)
- fix: application logs are't displayed by @KIoppert in [#465](https://github.com/manytask/manytask/pull/465)
- fix: final score calculation with reported score by @elyaishere in [#463](https://github.com/manytask/manytask/pull/463)
- fix: fix a bug with a search in DB by @KIoppert in [#454](https://github.com/manytask/manytask/pull/454)
- fix: Fix migrations for non-nullable colums by @zhmurov in [#438](https://github.com/manytask/manytask/pull/438)
- fix: python-gitlab 6 fails on these comments to be unused by @zhmurov in [#420](https://github.com/manytask/manytask/pull/420)
- fix: Disable poetry cache by @zhmurov in [#379](https://github.com/manytask/manytask/pull/379)
- fix: Supress Docker build warning by @zhmurov in [#367](https://github.com/manytask/manytask/pull/367)
- fix: avoid division by zero by @zhmurov in [#365](https://github.com/manytask/manytask/pull/365)
- fix: fixed problems with starting app by @gagarinkomar in [#359](https://github.com/manytask/manytask/pull/359)

### Tests and CI/CD

- chore(deps-dev): bump pytest-cov from 6.2.1 to 6.3.0 by @dependabot in [#595](https://github.com/manytask/manytask/pull/595)
- refactor: refactor constants in tests by @KIoppert in [#518](https://github.com/manytask/manytask/pull/518)
- ci: deploy workflow by @KIoppert in [#545](https://github.com/manytask/manytask/pull/545)
- ci: correct using 'on' by @KIoppert in [#527](https://github.com/manytask/manytask/pull/527)
- refactor: Use constants more in DB API tests by @zhmurov in [#445](https://github.com/manytask/manytask/pull/445)
- chore(deps-dev): bump testcontainers from 4.9.2 to 4.10.0 by @dependabot in [#370](https://github.com/manytask/manytask/pull/370)
- chore(deps-dev): bump pytest-cov from 5.0.0 to 6.0.0 by @dependabot in [#352](https://github.com/manytask/manytask/pull/352)
- chore(deps-dev): bump testcontainers from 3.7.1 to 4.9.2 by @dependabot in [#335](https://github.com/manytask/manytask/pull/335)

### Enhancement

- perf: add cache for static resources by @KIoppert in [#589](https://github.com/manytask/manytask/pull/589)
- perf: optimization of the course page rendering by @KIoppert in [#583](https://github.com/manytask/manytask/pull/583)
- perf: blazing optimization of the course table page by @KIoppert in [#579](https://github.com/manytask/manytask/pull/579)
- refactor: Store instance not course admin in StoredUser by @zhmurov in [#538](https://github.com/manytask/manytask/pull/538)
- refactor: Create AuthApi and use it by @zhmurov in [#534](https://github.com/manytask/manytask/pull/534)
- refactor: rename sync_stored_user by @zhmurov in [#537](https://github.com/manytask/manytask/pull/537)
- refactor: remove ManytaskStorageType enum by @zhmurov in [#536](https://github.com/manytask/manytask/pull/536)
- refactor: Return bool instead of throwing when checking authenticated RMS user by @zhmurov in [#497](https://github.com/manytask/manytask/pull/497)
- refactor: Create Authenticateduser and use it by @zhmurov in [#513](https://github.com/manytask/manytask/pull/513)
- refactor: remove repo name from DB by @KIoppert in [#520](https://github.com/manytask/manytask/pull/520)
- refactor: Do not set admin status when projects are created by @zhmurov in [#498](https://github.com/manytask/manytask/pull/498)
- refactor: Create RmsUser object and use it by @zhmurov in [#435](https://github.com/manytask/manytask/pull/435)
- refactor: change naming and localization by @KIoppert in [#495](https://github.com/manytask/manytask/pull/495)
- refactor: Refactor requires_auth function by @zhmurov in [#486](https://github.com/manytask/manytask/pull/486)
- refactor: Set OAuth in separate function by @zhmurov in [#487](https://github.com/manytask/manytask/pull/487)
- perf: optimize dockerfile by @KIoppert in [#476](https://github.com/manytask/manytask/pull/476)
- refactor: move html styles to css files + UI changes by @KIoppert in [#462](https://github.com/manytask/manytask/pull/462)
- refactor: Use username instead of Student when checking if the project exists by @zhmurov in [#464](https://github.com/manytask/manytask/pull/464)
- refactor: Consolidate identical code in one function in REST API by @zhmurov in [#457](https://github.com/manytask/manytask/pull/457)
- perf: optimize calls to db when table is rendering by @KIoppert in [#461](https://github.com/manytask/manytask/pull/461)
- refactor: Do not use Student in storage API by @zhmurov in [#436](https://github.com/manytask/manytask/pull/436)
- refactor: Keep create user functionality in RMS by @zhmurov in [#417](https://github.com/manytask/manytask/pull/417)
- refactor: remove redundant methods split in Storage API by @dmasloff in [#422](https://github.com/manytask/manytask/pull/422)
- refactor: Create abstract class to represent Repository Management System (RMS) by @zhmurov in [#416](https://github.com/manytask/manytask/pull/416)
- refactor: Remove unused map_gitlab_user_to_student(...) function by @zhmurov in [#415](https://github.com/manytask/manytask/pull/415)
- refactor: Make fields added to the Course object private by @zhmurov in [#376](https://github.com/manytask/manytask/pull/376)
- refactor: Move ownership of gitlab repo urls to Course class by @zhmurov in [#354](https://github.com/manytask/manytask/pull/354)
- refactor: remove Viewer API by @zhmurov in [#355](https://github.com/manytask/manytask/pull/355)
- refactor: Remove GoogleSheet support by @zhmurov in [#353](https://github.com/manytask/manytask/pull/353)

### Documentation

- docs: release version by @KIoppert in [#586](https://github.com/manytask/manytask/pull/586)
- docs: add docs about course statuses by @KIoppert in [#563](https://github.com/manytask/manytask/pull/563)
- docs: Update system setup docs by @zhmurov in [#554](https://github.com/manytask/manytask/pull/554)
- docs: add docs and examples on configuring final grade by @dmasloff in [#544](https://github.com/manytask/manytask/pull/544)
- docs: add favicon to docs tab by @KIoppert in [#542](https://github.com/manytask/manytask/pull/542)
- docs: add docs how to get started dev by @KIoppert in [#532](https://github.com/manytask/manytask/pull/532)
- docs: docs-remove-Setup-Node.js by @KIoppert in [#528](https://github.com/manytask/manytask/pull/528)
- docs: add the possibility to build docs in Docker by @KIoppert in [#519](https://github.com/manytask/manytask/pull/519)
- docs: how to use local db by @KIoppert in [#481](https://github.com/manytask/manytask/pull/481)
- docs: Move API description into documentation by @zhmurov in [#491](https://github.com/manytask/manytask/pull/491)
- docs: Update README file by @zhmurov in [#490](https://github.com/manytask/manytask/pull/490)
- docs: Update contributing guide by @zhmurov in [#492](https://github.com/manytask/manytask/pull/492)
- docs: Update version by @zhmurov in [#493](https://github.com/manytask/manytask/pull/493)
- docs: Use Diplodoc to build and deploy landing/pages by @zhmurov in [#425](https://github.com/manytask/manytask/pull/425)
- docs(legal): Create LICENSE by @zhmurov in [#373](https://github.com/manytask/manytask/pull/373)

### Other changes

- chore: Add Oleg to the list of developers by @zhmurov in [#588](https://github.com/manytask/manytask/pull/588)
- chore: Remove unused envvar from the .env file by @zhmurov in [#553](https://github.com/manytask/manytask/pull/553)
- chore: minor improvements prod dockerfile by @KIoppert in [#541](https://github.com/manytask/manytask/pull/541)

### Dependency Updates

- chore(deps): bump actions/setup-python from 5 to 6 by @dependabot in [#594](https://github.com/manytask/manytask/pull/594)
- chore(deps): bump actions/upload-pages-artifact from 3 to 4 by @dependabot in [#566](https://github.com/manytask/manytask/pull/566)
- chore(deps): bump actions/checkout from 4 to 5 by @dependabot in [#565](https://github.com/manytask/manytask/pull/565)
- chore(deps): bump appleboy/ssh-action by @dependabot in [#564](https://github.com/manytask/manytask/pull/564)
- chore(deps-dev): bump pre-commit from 4.2.0 to 4.3.0 by @dependabot in [#530](https://github.com/manytask/manytask/pull/530)
- chore(deps): bump python-gitlab from 6.1.0 to 6.2.0 by @dependabot in [#480](https://github.com/manytask/manytask/pull/480)
- chore(deps-dev): bump testcontainers from 4.10.0 to 4.12.0 by @dependabot in [#479](https://github.com/manytask/manytask/pull/479)
- chore(deps-dev): bump mypy from 1.16.0 to 1.17.0 by @dependabot in [#473](https://github.com/manytask/manytask/pull/473)
- chore(deps): bump python-gitlab from 6.0.0 to 6.1.0 by @dependabot in [#446](https://github.com/manytask/manytask/pull/446)
- chore(deps-dev): bump flake8 from 7.2.0 to 7.3.0 by @dependabot in [#433](https://github.com/manytask/manytask/pull/433)
- chore(deps-dev): bump ruff from 0.11.0 to 0.12.0 by @dependabot in [#432](https://github.com/manytask/manytask/pull/432)
- chore(deps): bump urllib3 from 2.3.0 to 2.5.0 by @dependabot in [#426](https://github.com/manytask/manytask/pull/426)
- chore(deps-dev): bump pytest-cov from 6.1.1 to 6.2.1 by @dependabot in [#423](https://github.com/manytask/manytask/pull/423)
- chore(deps): bump requests from 2.32.3 to 2.32.4 by @dependabot in [#421](https://github.com/manytask/manytask/pull/421)
- chore(deps): bump python-gitlab from 5.6.0 to 6.0.0 by @dependabot in [#418](https://github.com/manytask/manytask/pull/418)
- chore(deps-dev): bump pytest from 8.3.2 to 8.4.0 by @dependabot in [#419](https://github.com/manytask/manytask/pull/419)
- chore(deps): bump authlib from 1.5.1 to 1.6.0 by @dependabot in [#401](https://github.com/manytask/manytask/pull/401)
- chore(deps-dev): bump mypy from 1.15.0 to 1.16.0 by @dependabot in [#400](https://github.com/manytask/manytask/pull/400)
- chore(deps): bump alembic from 1.15.1 to 1.16.1 by @dependabot in [#399](https://github.com/manytask/manytask/pull/399)
- chore(deps): bump flask from 3.1.0 to 3.1.1 by @dependabot in [#390](https://github.com/manytask/manytask/pull/390)
- chore(deps): bump pydantic from 2.10.3 to 2.11.1 by @dependabot in [#363](https://github.com/manytask/manytask/pull/363)
- chore(deps): bump python-dotenv from 1.0.1 to 1.1.0 by @dependabot in [#362](https://github.com/manytask/manytask/pull/362)
- chore(deps-dev): bump pre-commit from 4.1.0 to 4.2.0 by @dependabot in [#357](https://github.com/manytask/manytask/pull/357)
- chore(deps-dev): bump ruff from 0.9.1 to 0.11.0 by @dependabot in [#351](https://github.com/manytask/manytask/pull/351)
- chore(deps): bump authlib from 1.3.1 to 1.5.1 by @dependabot in [#350](https://github.com/manytask/manytask/pull/350)
- chore(deps-dev): bump isort from 5.13.2 to 6.0.1 by @dependabot in [#342](https://github.com/manytask/manytask/pull/342)
- chore(deps-dev): bump black from 24.8.0 to 25.1.0 by @dependabot in [#341](https://github.com/manytask/manytask/pull/341)
- chore(deps-dev): bump pre-commit from 3.6.0 to 4.1.0 by @dependabot in [#340](https://github.com/manytask/manytask/pull/340)
- chore(deps): bump python-gitlab from 4.13.0 to 5.6.0 by @dependabot in [#339](https://github.com/manytask/manytask/pull/339)
- chore(deps): bump flask from 3.0.1 to 3.1.0 by @dependabot in [#338](https://github.com/manytask/manytask/pull/338)
- chore(deps): bump alembic from 1.13.1 to 1.15.1 by @dependabot in [#336](https://github.com/manytask/manytask/pull/336)
- chore(deps): bump jinja2 from 3.1.5 to 3.1.6 by @dependabot in [#333](https://github.com/manytask/manytask/pull/333)
- chore(deps): bump werkzeug from 3.0.6 to 3.1.3 by @dependabot in [#329](https://github.com/manytask/manytask/pull/329)
- chore(deps): bump gspread from 6.1.4 to 6.2.0 by @dependabot in [#326](https://github.com/manytask/manytask/pull/326)
- chore(deps-dev): bump mypy from 1.14.1 to 1.15.0 by @dependabot in [#325](https://github.com/manytask/manytask/pull/325)
- chore(deps): bump actions/cache from 3 to 4 by @dependabot in [#323](https://github.com/manytask/manytask/pull/323)

**Full Changelog**: [25.1.1...25.2.0](https://github.com/manytask/manytask/compare/25.1.1...25.2.0)

## [25.1.1](https://github.com/manytask/manytask/releases/tag/25.1.1) - 2025-02-28

### What's Changed

- fix: Redirect to signup page when oath token might need updating by @zhmurov in [#311](https://github.com/manytask/manytask/pull/311)
- fix: Fix version file by @zhmurov in [#310](https://github.com/manytask/manytask/pull/310)

**Full Changelog**: [25.1...25.1.1](https://github.com/manytask/manytask/compare/25.1...25.1.1)

## [25.1](https://github.com/manytask/manytask/releases/tag/25.1) - 2025-02-10

### What's Changed

- feat: ask for a secret on login by @zhmurov in [#163](https://github.com/manytask/manytask/pull/163)
- feat: ask to re-type password by @zhmurov in [#156](https://github.com/manytask/manytask/pull/156)
- documentation: Minor update to the documentation by @zhmurov in [#184](https://github.com/manytask/manytask/pull/184)
- fix: change the date format in the samle yml file by @zhmurov in [#185](https://github.com/manytask/manytask/pull/185)
- feat: Add a toggle to hide the gdoc with the list of all scores by @zhmurov in [#157](https://github.com/manytask/manytask/pull/157)
- chore(deps): bump requests from 2.31.0 to 2.32.3 by @dependabot in [#143](https://github.com/manytask/manytask/pull/143)
- chore(deps): bump flake8 from 7.0.0 to 7.1.1 by @dependabot in [#159](https://github.com/manytask/manytask/pull/159)
- chore(deps): bump python from 3.12-alpine to 3.13-alpine by @dependabot in [#177](https://github.com/manytask/manytask/pull/177)
- chore(deps): bump python-gitlab from 4.10.0 to 4.13.0 by @dependabot in [#178](https://github.com/manytask/manytask/pull/178)
- chore(deps): bump werkzeug from 3.0.3 to 3.0.6 by @dependabot in [#181](https://github.com/manytask/manytask/pull/181)
- chore(deps): bump ruff from 0.5.0 to 0.7.1 by @dependabot in [#182](https://github.com/manytask/manytask/pull/182)
- chore(deps): bump mypy from 1.11.1 to 1.13.0 by @dependabot in [#183](https://github.com/manytask/manytask/pull/183)
- fix: update python to 3.13 by @zhmurov in [#186](https://github.com/manytask/manytask/pull/186)
- fix: Remove package duplicate from the requirements file by @zhmurov in [#187](https://github.com/manytask/manytask/pull/187)
- feat: create a database and make it possible to use it instead of gsheet by @zhmurov in [#194](https://github.com/manytask/manytask/pull/194)
- chore(deps): bump ruff from 0.7.1 to 0.8.4 by @dependabot in [#213](https://github.com/manytask/manytask/pull/213)
- chore(deps): bump codecov/codecov-action from 4.6.0 to 5.1.2 by @dependabot in [#212](https://github.com/manytask/manytask/pull/212)
- chore(deps): bump pydantic from 2.9.0 to 2.10.3 by @dependabot in [#195](https://github.com/manytask/manytask/pull/195)
- refactor: edit models by @gagarinkomar in [#200](https://github.com/manytask/manytask/pull/200)
- chore: update docker-compose configuration for production environment by @prawwtocol in [#218](https://github.com/manytask/manytask/pull/218)
- feat: add auto creation of tables in database by @gagarinkomar in [#221](https://github.com/manytask/manytask/pull/221)
- feat: add web db viewer by @prawwtocol in [#227](https://github.com/manytask/manytask/pull/227)
- ci: update docker compose for local development, add YC suport to dockerfile, add Makefile by @prawwtocol in [#226](https://github.com/manytask/manytask/pull/226)
- docs: Deadline checklist by @akostrikov in [#228](https://github.com/manytask/manytask/pull/228)
- chore(deps): bump ruff from 0.8.4 to 0.9.1 by @dependabot in [#225](https://github.com/manytask/manytask/pull/225)
- chore(deps): bump mypy from 1.13.0 to 1.14.1 by @dependabot in [#224](https://github.com/manytask/manytask/pull/224)
- refactor(tests): reorganize import statements and clean up test files by @prawwtocol in [#243](https://github.com/manytask/manytask/pull/243)
- feat: enhance development workflow with pre-commit hooks and Makefile by @prawwtocol in [#242](https://github.com/manytask/manytask/pull/242)
- refactor: @requires_ready and @requires_auth in web requests by @cin-bun in [#244](https://github.com/manytask/manytask/pull/244)
- fix: update signup form field names for consistency by @prawwtocol in [#256](https://github.com/manytask/manytask/pull/256)
- test: Full coverage models.py by @akostrikov in [#240](https://github.com/manytask/manytask/pull/240)
- docs: Add notes on manytask development strategy by @zhmurov in [#231](https://github.com/manytask/manytask/pull/231)
- feat: add synchronization course_admin from gitlab to manytask by @gagarinkomar in [#247](https://github.com/manytask/manytask/pull/247)
- refactor: Improve switching between database and Google sheets by @zhmurov in [#246](https://github.com/manytask/manytask/pull/246)
- chore(deps): bump codecov/codecov-action from 5.1.2 to 5.3.1 by @dependabot in [#262](https://github.com/manytask/manytask/pull/262)
- feat: Cover the interaction with Gitlab by tests by @cin-bun in [#260](https://github.com/manytask/manytask/pull/260)
- feat: enhance import sorting in staged files with isort integration in check_staged.sh by @prawwtocol in [#250](https://github.com/manytask/manytask/pull/250)
- feat: add endpoint and modal to update student scores in the database by @prawwtocol in [#266](https://github.com/manytask/manytask/pull/266)
- fix: improve web page rendering and navigation. always show links by @prawwtocol in [#268](https://github.com/manytask/manytask/pull/268)
- feat: add CSV export button to database table by @prawwtocol in [#269](https://github.com/manytask/manytask/pull/269)
- feat: secret check by @cin-bun in [#271](https://github.com/manytask/manytask/pull/271)
- refactor: migrate from isort to ruff for import sorting and formatting by @prawwtocol in [#278](https://github.com/manytask/manytask/pull/278)
- fix: database secret code by @cin-bun in [#287](https://github.com/manytask/manytask/pull/287)
- feat: add option to collapse task groups in db viewer by @prawwtocol in [#280](https://github.com/manytask/manytask/pull/280)
- fix: use UTC timezone for datetime in solution export by @prawwtocol in [#282](https://github.com/manytask/manytask/pull/282)
- feat: add task group update mechanism in config handling by @prawwtocol in [#284](https://github.com/manytask/manytask/pull/284)
- ci: set up review policy by @prawwtocol in [#291](https://github.com/manytask/manytask/pull/291)
- fix: improve Tabulator table column and cell styling by @prawwtocol in [#292](https://github.com/manytask/manytask/pull/292)
- feat: Add supporting migrations to database by @gagarinkomar in [#279](https://github.com/manytask/manytask/pull/279)

### New Contributors

- @prawwtocol made their first contribution in [#218](https://github.com/manytask/manytask/pull/218)
- @akostrikov made their first contribution in [#228](https://github.com/manytask/manytask/pull/228)
- @cin-bun made their first contribution in [#244](https://github.com/manytask/manytask/pull/244)

**Full Changelog**: [0.9.0...25.1](https://github.com/manytask/manytask/compare/0.9.0...25.1)

## [0.9.0](https://github.com/manytask/manytask/releases/tag/0.9.0) - 2024-10-29

Before this release, there were two .yml configuration files for the course: .course.yml with the course description and .deadlines.yml with the list of the tasks and respective deadlines. This release combines these files into one, while mostly keeping the format. Having only one file simplifies the interactions between course private repo and Manytask web-interface: only one API request is now needed to update the config.

The release also contains a fix the that allows more flexibility in grading students work.

See description below for minor updates.

### Features

- feat: try to use alpine docker by @k4black in [#102](https://github.com/manytask/manytask/pull/102)
- feat: update build docker job, add main branch docker by @k4black in [#100](https://github.com/manytask/manytask/pull/100)
- feat: new manytask config structure by @k4black in [#99](https://github.com/manytask/manytask/pull/99)

### Fixes

- fix: Allow non-integer number format for score reporting by @zhmurov in [#168](https://github.com/manytask/manytask/pull/168)
- fix: mypy errors by @MoskalenkoViktor in [#158](https://github.com/manytask/manytask/pull/158)
- fix: Fix ruff script in linter by @zhmurov in [#151](https://github.com/manytask/manytask/pull/151)
- fix: remove x-scroll by @Fant1k34 in [#113](https://github.com/manytask/manytask/pull/113)

### Tests and CI/CD

- chore(deps): bump pytest-cov from 4.1.0 to 5.0.0 by @dependabot in [#124](https://github.com/manytask/manytask/pull/124)
- chore(deps): bump pytest from 8.0.0 to 8.1.1 by @dependabot in [#120](https://github.com/manytask/manytask/pull/120)

### Other changes

- feat: add docker HEALTHCHECK by @k4black in [#110](https://github.com/manytask/manytask/pull/110)
- chore: update versions by @k4black in [#98](https://github.com/manytask/manytask/pull/98)

### Dependency Updates

- chore(deps): bump types-requests from 2.31.0.20240125 to 2.32.0.20240907 by @dependabot in [#166](https://github.com/manytask/manytask/pull/166)
- chore(deps): bump pydantic from 2.6.1 to 2.9.0 by @dependabot in [#165](https://github.com/manytask/manytask/pull/165)
- chore(deps): bump python-gitlab from 4.4.0 to 4.10.0 by @dependabot in [#164](https://github.com/manytask/manytask/pull/164)
- chore(deps): bump cachelib from 0.12.0 to 0.13.0 by @dependabot in [#128](https://github.com/manytask/manytask/pull/128)
- chore(deps): bump gunicorn from 22.0.0 to 23.0.0 by @dependabot in [#155](https://github.com/manytask/manytask/pull/155)
- chore(deps): bump black from 24.4.2 to 24.8.0 by @dependabot in [#153](https://github.com/manytask/manytask/pull/153)
- chore(deps): bump pytest from 8.1.1 to 8.3.2 by @dependabot in [#154](https://github.com/manytask/manytask/pull/154)
- chore(deps): bump mypy from 1.8.0 to 1.11.1 by @dependabot in [#150](https://github.com/manytask/manytask/pull/150)
- chore(deps): bump ruff from 0.2.1 to 0.5.0 by @dependabot in [#148](https://github.com/manytask/manytask/pull/148)
- chore(deps): bump black from 24.1.1 to 24.4.2 by @dependabot in [#135](https://github.com/manytask/manytask/pull/135)
- chore(deps): bump gunicorn from 21.2.0 to 22.0.0 by @dependabot in [#131](https://github.com/manytask/manytask/pull/131)
- chore(deps): bump authlib from 1.3.0 to 1.3.1 by @dependabot in [#145](https://github.com/manytask/manytask/pull/145)
- chore(deps): bump requests from 2.31.0 to 2.32.0 by @dependabot in [#139](https://github.com/manytask/manytask/pull/139)
- chore(deps): bump werkzeug from 3.0.1 to 3.0.3 by @dependabot in [#137](https://github.com/manytask/manytask/pull/137)
- chore(deps): bump release-drafter/release-drafter from 5 to 6 by @dependabot in [#104](https://github.com/manytask/manytask/pull/104)
- chore(deps): bump codecov/codecov-action from 3 to 4 by @dependabot in [#103](https://github.com/manytask/manytask/pull/103)
- chore(deps): bump cachelib from 0.10.2 to 0.12.0 by @dependabot in [#107](https://github.com/manytask/manytask/pull/107)
- chore(deps): bump pydantic from 2.5.3 to 2.6.1 by @dependabot in [#108](https://github.com/manytask/manytask/pull/108)
- chore(deps): bump ruff from 0.1.14 to 0.2.1 by @dependabot in [#109](https://github.com/manytask/manytask/pull/109)
- chore(deps): bump gspread from 5.12.4 to 6.0.0 by @dependabot in [#101](https://github.com/manytask/manytask/pull/101)
- chore(deps): bump python-gitlab from 4.2.0 to 4.4.0 by @dependabot in [#97](https://github.com/manytask/manytask/pull/97)
- chore(deps): bump flake8 from 6.1.0 to 7.0.0 by @dependabot in [#96](https://github.com/manytask/manytask/pull/96)

**Full Changelog**: [0.8.1...0.9.0](https://github.com/manytask/manytask/compare/0.8.1...0.9.0)

## [0.8.1](https://github.com/manytask/manytask/releases/tag/0.8.1) - 2023-12-28

Accept `username` and `submit_time` and deprecate `user_id` and `commit_time` as api inputs

**Full Changelog**: [0.8.0...0.8.1](https://github.com/manytask/manytask/compare/0.8.0...0.8.1)

## [0.8.0](https://github.com/manytask/manytask/releases/tag/0.8.0) - 2023-12-27

BREAKING ci_config_path for fork repositories will point to the `.gitlab-ci.yml@path/to/public/repo`

### Features

- feat: add ci_config_path from public repo (.gitlab-ci.yml@path/to/repo) by @k4black in [#94](https://github.com/manytask/manytask/pull/94)

### Dependency Updates

- chore(deps): bump python-gitlab from 3.15.0 to 4.2.0 by @dependabot in [#84](https://github.com/manytask/manytask/pull/84)
- chore(deps): bump mypy from 1.7.0 to 1.8.0 by @dependabot in [#92](https://github.com/manytask/manytask/pull/92)
- chore(deps): bump authlib from 1.2.1 to 1.3.0 by @dependabot in [#91](https://github.com/manytask/manytask/pull/91)
- chore(deps): bump black from 23.11.0 to 23.12.1 by @dependabot in [#93](https://github.com/manytask/manytask/pull/93)
- chore(deps): bump isort from 5.12.0 to 5.13.2 by @dependabot in [#90](https://github.com/manytask/manytask/pull/90)
- chore(deps): bump actions/setup-python from 4 to 5 by @dependabot in [#86](https://github.com/manytask/manytask/pull/86)
- chore(deps): bump mypy from 1.6.1 to 1.7.0 by @dependabot in [#81](https://github.com/manytask/manytask/pull/81)
- chore(deps): bump ruff from 0.1.3 to 0.1.5 by @dependabot in [#80](https://github.com/manytask/manytask/pull/80)
- chore(deps): bump flask from 2.3.3 to 3.0.0 by @dependabot in [#73](https://github.com/manytask/manytask/pull/73)
- chore(deps): bump python from 3.11-slim to 3.12-slim by @dependabot in [#61](https://github.com/manytask/manytask/pull/61)
- chore(deps): bump black from 23.10.1 to 23.11.0 by @dependabot in [#79](https://github.com/manytask/manytask/pull/79)

**Full Changelog**: [0.7.0...0.8.0](https://github.com/manytask/manytask/compare/0.7.0...0.8.0)

## [0.7.0](https://github.com/manytask/manytask/releases/tag/0.7.0) - 2023-11-08

### Fixes

- fix: set CONFIDENCE_INTERVAL = timedelta(hours=2)

### Other changes

- ci: update ci with reusable workflows and new release flow by @k4black in [#76](https://github.com/manytask/manytask/pull/76)
- ci: add dependabot updates configuration by @k4black in [#59](https://github.com/manytask/manytask/pull/59)
- chore(docker): Add curl to docker image by @kalabukdima in [#49](https://github.com/manytask/manytask/pull/49)
- ci: check PR title by @k4black in [#57](https://github.com/manytask/manytask/pull/57)

### Dependency Updates

- chore(deps): bump ruff from 0.0.286 to 0.1.3 by @dependabot in [#72](https://github.com/manytask/manytask/pull/72)
- chore(deps): bump types-pyyaml from 6.0.11 to 6.0.12.12 by @dependabot in [#71](https://github.com/manytask/manytask/pull/71)
- chore(deps): bump codecov/codecov-action from 2 to 3 by @dependabot in [#74](https://github.com/manytask/manytask/pull/74)
- chore(deps): bump types-requests from 2.28.9 to 2.31.0.10 by @dependabot in [#62](https://github.com/manytask/manytask/pull/62)
- chore(deps): bump gspread from 5.10.0 to 5.12.0 by @dependabot in [#64](https://github.com/manytask/manytask/pull/64)
- chore(deps): bump pytest from 7.4.0 to 7.4.3 by @dependabot in [#66](https://github.com/manytask/manytask/pull/66)
- chore(deps): bump docker/build-push-action from 4 to 5 by @dependabot in [#60](https://github.com/manytask/manytask/pull/60)
- chore(deps): bump docker/login-action from 2 to 3 by @dependabot in [#63](https://github.com/manytask/manytask/pull/63)
- chore(deps): bump docker/setup-qemu-action from 2 to 3 by @dependabot in [#67](https://github.com/manytask/manytask/pull/67)
- chore(deps): bump docker/setup-buildx-action from 2 to 3 by @dependabot in [#69](https://github.com/manytask/manytask/pull/69)
- chore(deps): bump actions/checkout from 3 to 4 by @dependabot in [#65](https://github.com/manytask/manytask/pull/65)
- chore(deps): bump black from 23.7.0 to 23.10.1 by @dependabot in [#68](https://github.com/manytask/manytask/pull/68)
- chore(deps): bump mypy from 1.5.1 to 1.6.1 by @dependabot in [#70](https://github.com/manytask/manytask/pull/70)
- chore(deps): bump werkzeug from 2.3.7 to 3.0.1 by @dependabot in [#53](https://github.com/manytask/manytask/pull/53)

**Full Changelog**: [0.6.3...0.7.0](https://github.com/manytask/manytask/compare/0.6.3...0.7.0)

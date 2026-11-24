# Manytask documentation

Read the documentation [on the website](https://manytask.org/) or follow the links
below directly in the repository. Numbered directories and filenames follow the
same reading order as the website sidebar; numbering restarts in each directory.

## 00 — Getting started

1. [About Manytask](00_getting_started/01_about.md)
2. [Concepts](00_getting_started/02_concepts.md)

## 02 — For students

1. [Using Manytask](02_students/01_using_manytask.md)

## 03 — For teachers

1. [Course as code](03_teachers/01_course_as_code.md)
2. [The basic example](03_teachers/02_basic_example.md)
3. [Course template](03_teachers/03_course_template.md)
4. [Private repository](03_teachers/04_private_repository.md)
5. [Checker configuration](03_teachers/05_checker_configuration.md)
6. [Manytask configuration](03_teachers/06_manytask_configuration.md)
7. [Running the course](03_teachers/07_running_course.md)
8. [Checker pipelines and plugins](03_teachers/08_checker_pipelines_and_plugins.md)

## 04 — For administrators

1. [Production setup](04_administration/01_system_setup.md)
2. [Production operations](04_administration/02_production.md)
3. [Deployment guide](04_administration/03_deploy_guide.md)

## 05 — For developers

1. [Local development](05_development/01_local_development.md)

## 06 — References

1. [`.manytask.yml`](06_reference/01_manytask_yml.md)
2. [`.checker.yml`](06_reference/02_checker_yml.md)
3. [Checker built-in plugins](06_reference/03_checker_plugins.md)
4. [REST API](06_reference/04_rest_api.md)

## Research

`research/` contains dated design and research documents for reading in the
repository. These documents use date prefixes without ordering numbers and are
separate from the published user guides.

## Editing and building

Keep article names in the form `NN_descriptive_name.md` and add published pages to
`toc.yaml`. Keep the sidebar and this reading list in the same order.
[`index.yaml`](index.yaml) defines the website landing page; `img/` and `_assets/`
hold shared images, fonts, and styles.

Run `make docs` from this directory to build the website into `../build/docs/`.
`redirects.yaml` keeps previous published page URLs working after
renames; add a redirect when moving an existing published page.

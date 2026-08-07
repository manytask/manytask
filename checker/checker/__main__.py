from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

import click

from .configs import CheckerConfig, CheckerSubConfig, ManytaskConfig
from .course import Course, FileSystemTask
from .exceptions import CheckerException, CheckerValidationError, TestingError
from .exporter import Exporter
from .tester import Tester
from .utils import print_ascii_tag, print_info

ClickReadableFile = click.Path(
    exists=True, file_okay=True, readable=True, path_type=Path
)
ClickReadableDirectory = click.Path(
    exists=True, file_okay=False, readable=True, path_type=Path
)
ClickWritableDirectory = click.Path(file_okay=False, writable=True, path_type=Path)

CHECKER_CONFIG = ".checker.yml"
MANYTASK_CONFIG = ".manytask.yml"


@click.group(context_settings={"show_default": True})
@click.version_option(package_name="manytask-checker")
@click.pass_context
def cli(
    ctx: click.Context,
) -> None:
    """Manytask checker - automated tests for students' assignments."""
    print_ascii_tag()  # TODO: print version

    ctx.ensure_object(dict)


@cli.command()
@click.argument("root", type=ClickReadableDirectory, default=".")
@click.option(
    "-v/-s", "--verbose/--silent", is_flag=True, default=True, help="Verbose output"
)
@click.pass_context
def validate(
    ctx: click.Context,
    root: Path,
    verbose: bool,
) -> None:
    """Validate the configuration files, plugins and tasks.

    1. Validate the configuration files content.
    2. Validate mentioned plugins.
    3. Check all tasks are valid and consistent with the manytask.
    """
    # get configs paths
    course_config_path = root / CHECKER_CONFIG
    manytask_config_path = root / MANYTASK_CONFIG

    print_info("Validating configuration files...")
    try:
        checker_config = CheckerConfig.from_yaml(course_config_path)
        manytask_config = ManytaskConfig.from_yaml(manytask_config_path)
    except CheckerValidationError as e:
        print_info("Configuration Failed", color="red")
        print_info(e)
        sys.exit(1)
    print_info("Ok", color="green")

    print_info("Validating Course Structure (and tasks configs)...")
    try:
        course = Course(manytask_config, root)
        course.validate()
    except CheckerValidationError as e:
        print_info("Course Validation Failed", color="red")
        print_info(e)
        sys.exit(1)
    print_info("Ok", color="green")

    print_info("Validating Exporter...")
    try:
        exporter = Exporter(
            course,
            checker_config.structure,
            checker_config.export,
            verbose=True,
            dry_run=True,
        )
        exporter.validate()
    except CheckerValidationError as e:
        print_info("Exporter Validation Failed", color="red")
        print_info(e)
        sys.exit(1)
    print_info("Ok", color="green")

    print_info("Validating tester...")
    try:
        tester = Tester(course, checker_config, verbose=verbose)
        tester.validate()
    except CheckerValidationError as e:
        print_info("Tester Validation Failed", color="red")
        print_info(e)
        sys.exit(1)
    print_info("Ok", color="green")


@cli.command()
@click.argument("root", type=ClickReadableDirectory, default=".")
@click.argument("reference_root", type=ClickReadableDirectory, default=".")
@click.option(
    "-t",
    "--task",
    type=str,
    multiple=True,
    default=None,
    help="Task name to check (multiple possible)",
)
@click.option(
    "-g",
    "--group",
    type=str,
    multiple=True,
    default=None,
    help="Group name to check (multiple possible)",
)
@click.option(
    "-p",
    "--parallelize",
    is_flag=True,
    default=True,
    help="Execute parallel checking of tasks",
)
@click.option(
    "-n",
    "--num-processes",
    type=int,
    default=os.cpu_count(),
    help="Num of processes parallel checking",
)
@click.option("--no-clean", is_flag=True, help="Clean or not check tmp folders")
@click.option(
    "--merge-dir",
    type=ClickWritableDirectory,
    default=None,
    help="Build the merged tree in this directory instead of a temporary one (it survives the run)",
)
@click.option(
    "--force", is_flag=True, help="Allow clearing a non-empty --merge-dir (keeps .git)"
)
@click.option(
    "-v/-s",
    "--verbose/--silent",
    is_flag=True,
    default=True,
    help="Verbose tests output",
)
@click.option(
    "--dry-run", is_flag=True, help="Do not execute anything, only log actions"
)
@click.pass_context
def check(  # noqa: PLR0913
    ctx: click.Context,
    root: Path,
    reference_root: Path,
    task: list[str] | None,
    group: list[str] | None,
    parallelize: bool,
    num_processes: int,
    no_clean: bool,
    merge_dir: Path | None,
    force: bool,
    verbose: bool,
    dry_run: bool,
) -> None:
    """Check private repository: run tests, lint etc. First forces validation.

    1. Run `validate` command.
    2. Export tasks to temporary directory for testing.
    3. Run pipelines: global, tasks and (dry-run) report.
    4. Cleanup temporary directory.
    """
    # validate first
    ctx.invoke(validate, root=root, verbose=verbose)  # TODO: check verbose level

    # get configs paths
    course_config_path = root / CHECKER_CONFIG
    manytask_config_path = root / MANYTASK_CONFIG

    # load configs
    checker_config = CheckerConfig.from_yaml(course_config_path)
    manytask_config = ManytaskConfig.from_yaml(manytask_config_path)

    # read filesystem, check existing tasks
    course = Course(manytask_config, root, reference_root)

    # create exporter and export files for testing
    if merge_dir is not None:
        Exporter.prepare_target_dir(merge_dir, force=force)
    exporter = Exporter(
        course,
        checker_config.structure,
        checker_config.export,
        verbose=True,
        cleanup=not no_clean,
        dry_run=dry_run,
        working_dir=merge_dir,
    )
    exporter.export_for_testing(exporter.temporary_dir)
    if merge_dir is not None:
        print_info(f"Merged tree kept in <{merge_dir}>", color="grey")

    # validate tasks and groups if passed
    filesystem_tasks: dict[str, FileSystemTask] = dict()
    if task:
        task_dict = dict.fromkeys(task)
        for filesystem_task in course.get_tasks(enabled=True):
            if filesystem_task.name in task_dict:
                filesystem_tasks[filesystem_task.name] = filesystem_task
                del task_dict[filesystem_task.name]
        if task_dict:
            print_info(f"Can't find the tasks: {list(task_dict.keys())}", color="red")
            sys.exit(1)
    if group:
        group_dict = dict.fromkeys(group)
        for filesystem_group in course.get_groups(enabled=True):
            if filesystem_group.name in group_dict:
                for filesystem_task in filesystem_group.tasks:
                    filesystem_tasks[filesystem_task.name] = filesystem_task
                del group_dict[filesystem_group.name]
        if group_dict:
            print_info(f"Can't find the groups: {list(group_dict.keys())}", color="red")
            sys.exit(1)
    if filesystem_tasks:
        print_info(f"Checking tasks: {', '.join(filesystem_tasks.keys())}")

    # create tester to... to test =)
    tester = Tester(course, checker_config, verbose=verbose, dry_run=dry_run)

    # run tests
    # TODO: progressbar on parallelize
    try:
        tester.run(
            exporter.temporary_dir,
            tasks=list(filesystem_tasks.values()) if filesystem_tasks else None,
            report=False,
        )
    except TestingError as e:
        print_info("TESTING FAILED", color="red")
        print_info(e)
        sys.exit(1)
    except Exception as e:
        print_info("UNEXPECTED ERROR", color="red")
        print_info(e)
        raise e
        sys.exit(1)
    print_info("TESTING PASSED", color="green")


def _parse_timestamp(
    ctx: click.Context,
    param: click.Parameter,
    value: Optional[str],
) -> datetime:
    if value is None:
        # runtime default
        return datetime.now(tz=ZoneInfo("Europe/Moscow"))
    try:
        return datetime.fromisoformat(value)
    except ValueError as e:
        raise click.BadParameter(
            "Use ISO 8601, e.g. 2025-09-08T13:39:13 or 2025-09-08T13:39:13Z"
        ) from e


@cli.command()
@click.argument("root", type=ClickReadableDirectory, default=".")
@click.argument("reference_root", type=ClickReadableDirectory, default=".")
@click.option(
    "--submit-score", is_flag=True, help="Submit score to the Manytask server"
)
@click.option(
    "--timestamp",
    type=str,
    callback=_parse_timestamp,
    default=None,
    show_default="current time in Europe/Moscow",
    help="Timestamp to use for the submission",
)
@click.option(
    "--username", type=str, default=None, help="Username to use for the submission"
)
@click.option(
    "--branch", type=str, default=None, help="Rewrite branch name for the submission"
)
@click.option("--no-clean", is_flag=True, help="Clean or not check tmp folders")
@click.option(
    "--merge-dir",
    type=ClickWritableDirectory,
    default=None,
    help="Build the merged tree in this directory instead of a temporary one (it survives the run)",
)
@click.option(
    "--force", is_flag=True, help="Allow clearing a non-empty --merge-dir (keeps .git)"
)
@click.option(
    "-v/-s",
    "--verbose/--silent",
    is_flag=True,
    default=False,
    help="Verbose tests output",
)
@click.option(
    "--dry-run", is_flag=True, help="Do not execute anything, only log actions"
)
@click.pass_context
def grade(  # noqa: PLR0913
    ctx: click.Context,
    root: Path,
    reference_root: Path,
    submit_score: bool,
    timestamp: datetime | None,
    username: str | None,
    branch: str | None,
    no_clean: bool,
    merge_dir: Path | None,
    force: bool,
    verbose: bool,
    dry_run: bool,
) -> None:
    """Process the configuration file and grade the tasks.

    1. Detect changes to test.
    2. Export tasks to temporary directory for testing.
    3. Run pipelines: global, tasks and report.
    4. Cleanup temporary directory.
    """
    # get configs paths
    course_config_path = reference_root / CHECKER_CONFIG
    manytask_config_path = reference_root / MANYTASK_CONFIG

    # load configs
    checker_config = CheckerConfig.from_yaml(course_config_path)
    manytask_config = ManytaskConfig.from_yaml(manytask_config_path)

    # read filesystem, check existing tasks
    course = Course(manytask_config, root, reference_root, branch_name=branch)

    # create exporter and export files for testing
    if merge_dir is not None:
        Exporter.prepare_target_dir(merge_dir, force=force)
    exporter = Exporter(
        course,
        checker_config.structure,
        checker_config.export,
        verbose=False,
        cleanup=not no_clean,
        dry_run=dry_run,
        working_dir=merge_dir,
    )
    exporter.export_for_testing(exporter.temporary_dir)
    if merge_dir is not None:
        print_info(f"Merged tree kept in <{merge_dir}>", color="grey")

    # detect changes to test
    try:
        changed_tasks = course.detect_changes(checker_config.testing.changes_detection)
    except Exception as e:
        print_info("DETECT CHANGES FAILED", color="red")
        print_info(e)
        sys.exit(1)

    if not changed_tasks:
        print_info("No tasks to test", color="orange")
        return

    # create tester to... to test =)
    tester = Tester(course, checker_config, verbose=verbose, dry_run=dry_run)

    # run tests
    # TODO: progressbar on parallelize
    try:
        tester.run(
            exporter.temporary_dir,
            changed_tasks,
            report=True,
            timestamp=timestamp,
        )
    except TestingError as e:
        print_info("TESTING FAILED", color="red")
        print_info(e)
        sys.exit(1)
    except Exception as e:
        print_info("UNEXPECTED ERROR", color="red")
        print_info(e)
        sys.exit(1)
    print_info("TESTING PASSED", color="green")


@cli.command()
@click.argument("student_root", type=ClickReadableDirectory, default=".")
@click.argument("reference_root", type=ClickReadableDirectory, default=".")
@click.argument("output_dir", type=ClickWritableDirectory, default="./merged")
@click.option(
    "--force", is_flag=True, help="Clear OUTPUT_DIR if it is not empty (keeps .git)"
)
@click.option(
    "-v/-s",
    "--verbose/--silent",
    is_flag=True,
    default=True,
    help="Verbose output",
)
@click.option(
    "--dry-run", is_flag=True, help="Do not execute anything, only log actions"
)
@click.pass_context
def merge(  # noqa: PLR0913
    ctx: click.Context,
    student_root: Path,
    reference_root: Path,
    output_dir: Path,
    force: bool,
    verbose: bool,
    dry_run: bool,
) -> None:
    """Build the merged testing tree from private and student repositories.

    Takes the private (reference) repository stripped of the solutions, overlays the
    student's solution files from STUDENT_ROOT into the matching folders, and writes the
    result to OUTPUT_DIR. This is the very same tree `checker check`/`checker grade`
    build internally, except it is kept on disk so it can be inspected and reused.

    1. Copy the student's own files from STUDENT_ROOT.
    2. Overlay public and private files (tests, configs) from REFERENCE_ROOT.
    """
    # configs come from the private repo - it is the source of truth (same as `grade`)
    course_config_path = reference_root / CHECKER_CONFIG
    manytask_config_path = reference_root / MANYTASK_CONFIG

    # load configs
    checker_config = CheckerConfig.from_yaml(course_config_path)
    manytask_config = ManytaskConfig.from_yaml(manytask_config_path)

    # read filesystem, check existing tasks
    course = Course(manytask_config, student_root, reference_root)

    tasks = course.get_tasks(enabled=True)

    # Note: Exporter accepts `dry_run` but its copy methods do not honour it, so the
    # no-op has to be enforced here - otherwise --dry-run would still write the tree.
    # Bail out before prepare_target_dir so a dry run never creates or clears anything.
    if dry_run:
        print_info("")
        print_info(f"[dry-run] Would merge into <{output_dir}>", color="blue")
        print_info(f"  student files from: {student_root}", color="grey")
        print_info(f"  reference files from: {reference_root}", color="grey")
        print_info(f"  tasks available: {len(tasks)}", color="grey")
        return

    # prepare the target directory before writing anything into it
    try:
        Exporter.prepare_target_dir(output_dir, force=force)
    except CheckerException as e:
        print_info("MERGE FAILED", color="red")
        print_info(e)
        sys.exit(1)

    exporter = Exporter(
        course,
        checker_config.structure,
        checker_config.export,
        verbose=verbose,
        dry_run=dry_run,
        working_dir=output_dir,
    )
    exporter.export_for_testing(output_dir)
    print_info("")
    print_info(f"Merged tree written to <{output_dir}>", color="green")
    print_info(f"  student files from: {student_root}", color="grey")
    print_info(f"  reference files from: {reference_root}", color="grey")
    print_info(f"  tasks available: {len(tasks)}", color="grey")
    print_info("")
    # Note: `checker check` is NOT suggested here on purpose - it runs `validate`, which
    # requires the `.template` files that this merged tree intentionally no longer has.
    print_info("Run the checks against it with:", color="grey")
    print_info(f"  checker grade {output_dir} {reference_root}", color="grey")
    print_info(
        "  (grade selects tasks via changes_detection - commit in OUTPUT_DIR first, "
        "or set changes_detection to branch_name/commit_message)",
        color="grey",
    )


@cli.command()
@click.argument("reference_root", type=ClickReadableDirectory, default=".")
@click.argument("export_root", type=ClickWritableDirectory, default="./export")
@click.option(
    "--commit", is_flag=True, help="Commit and push changes to the repository"
)
@click.option(
    "--dry-run", is_flag=True, help="Do not execute anything, only log actions"
)
@click.pass_context
def export(
    ctx: click.Context,
    reference_root: Path,
    export_root: Path,
    commit: bool,
    dry_run: bool,
) -> None:
    """Export tasks from reference to public repository."""
    # get configs paths
    course_config_path = reference_root / CHECKER_CONFIG
    manytask_config_path = reference_root / MANYTASK_CONFIG

    # load configs
    checker_config = CheckerConfig.from_yaml(course_config_path)
    manytask_config = ManytaskConfig.from_yaml(manytask_config_path)

    # read filesystem, check existing tasks
    course = Course(manytask_config, reference_root)

    # if export_root not empty - delete all except git folder
    # `force=True`: export always regenerates the public tree, that is its whole job
    Exporter.prepare_target_dir(export_root, force=True)

    # create exporter and export files for public
    exporter = Exporter(
        course,
        checker_config.structure,
        checker_config.export,
        verbose=True,
        dry_run=dry_run,
    )
    export_root.mkdir(exist_ok=True, parents=True)
    exporter.export_public(
        export_root, commit=commit, commit_message=checker_config.export.commit_message
    )


@cli.command()
@click.argument("reference_root", type=ClickReadableDirectory, default=".")
@click.argument("export_root", type=ClickWritableDirectory, default="./export")
@click.option(
    "--dry-run", is_flag=True, help="Do not execute anything, only log actions"
)
@click.pass_context
def export_private(
    ctx: click.Context,
    reference_root: Path,
    export_root: Path,
    dry_run: bool,
) -> None:
    """Export files to testing directory."""
    # get configs paths
    course_config_path = reference_root / CHECKER_CONFIG
    manytask_config_path = reference_root / MANYTASK_CONFIG

    # load configs
    checker_config = CheckerConfig.from_yaml(course_config_path)
    manytask_config = ManytaskConfig.from_yaml(manytask_config_path)

    # read filesystem, check existing tasks
    course = Course(manytask_config, reference_root)

    # create exporter and export files for public
    exporter = Exporter(
        course,
        checker_config.structure,
        checker_config.export,
        verbose=True,
        dry_run=dry_run,
    )
    export_root.mkdir(exist_ok=True, parents=True)
    exporter.export_private(export_root)


@cli.command(hidden=True)
@click.argument("output_folder", type=ClickReadableDirectory, default=".")
@click.pass_context
def schema(
    ctx: click.Context,
    output_folder: Path,
) -> None:
    """Generate json schema for the checker configs."""
    checker_schema = CheckerConfig.get_json_schema()
    manytask_schema = ManytaskConfig.get_json_schema()
    task_schema = CheckerSubConfig.get_json_schema()

    with open(output_folder / "schema-checker.json", "w") as f:
        json.dump(checker_schema, f, indent=2)
    with open(output_folder / "schema-manytask.json", "w") as f:
        json.dump(manytask_schema, f, indent=2)
    with open(output_folder / "schema-task.json", "w") as f:
        json.dump(task_schema, f, indent=2)


if __name__ == "__main__":
    cli()

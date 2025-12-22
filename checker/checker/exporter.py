from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from checker.configs import CheckerExportConfig, CheckerStructureConfig
from checker.course import Course
from checker.exceptions import BadStructure
from checker.utils import print_info


class Exporter:
    """
    The Exporter class is responsible for moving course files.
    1. It validates and manage templates
    2. Select files to be exported public/testing/contribution
    """

    TEMPLATE_SUFFIX = ".template"
    TEMPLATE_START_COMMENT = "SOLUTION BEGIN"
    TEMPLATE_END_COMMENT = "SOLUTION END"
    TEMPLATE_REPLACE_COMMENT = "TODO: Your solution"
    TEMPLATE_COMMENT_REGEX = re.compile(f"{TEMPLATE_START_COMMENT}(.*?){TEMPLATE_END_COMMENT}", re.DOTALL)

    def __init__(
        self,
        course: Course,
        structure_config: CheckerStructureConfig,
        export_config: CheckerExportConfig,
        *,
        cleanup: bool = True,
        verbose: bool = False,
        dry_run: bool = False,
    ) -> None:
        self.course = course

        self.structure_config = structure_config
        self.export_config = export_config

        self.repository_root = course.repository_root
        self.reference_root = course.reference_root

        self._temporary_dir_manager = tempfile.TemporaryDirectory()
        self.temporary_dir = Path(self._temporary_dir_manager.name)

        self.sub_config_files = {}
        for group in self.course.get_groups(enabled=True):
            relative_path = Path(group.relative_path)
            if group.config.structure:
                self.sub_config_files[relative_path] = group.config.structure
        for task in self.course.get_tasks(enabled=True):
            relative_path = Path(task.relative_path)
            if task.config.structure:
                self.sub_config_files[relative_path] = task.config.structure

        self.cleanup = cleanup
        self.verbose = verbose
        self.dry_run = dry_run

    def _validate_template_files(self, task_folder: Path) -> tuple[bool, bool]:
        """Validate .template files/folders in the task folder.

        Returns:
            tuple: (has_template_files, has_valid_template_files)
        """
        has_template_files = False
        has_valid_template_files = False

        # search for all `.template` files or folders
        for template_file_or_folder in task_folder.glob(f"**/*{self.TEMPLATE_SUFFIX}"):
            has_template_files = True
            # check that all files have original files
            if not (template_file_or_folder.parent / template_file_or_folder.stem).exists():
                raise BadStructure(
                    f"Template file/folder {template_file_or_folder} does not have "
                    f"original file/folder {self.reference_root / template_file_or_folder.stem}"
                )
            has_valid_template_files = True

        return has_template_files, has_valid_template_files

    def _validate_template_comments_in_file(self, task_name: str, file_path: Path, content: str) -> None:
        """Validate template comments in a single file.

        Validate using regex and count matches of start and end comments.
        """
        # check have equal num of comments
        if content.count(self.TEMPLATE_START_COMMENT) != content.count(self.TEMPLATE_END_COMMENT):
            raise BadStructure(
                f"Task {task_name} has invalid template comments in file {file_path}. "
                f"The number of <{self.TEMPLATE_START_COMMENT}> and "
                f"<{self.TEMPLATE_END_COMMENT}> do not match"
            )

        # check between comments no other comment pair
        for match in self.TEMPLATE_COMMENT_REGEX.finditer(content):
            if self.TEMPLATE_START_COMMENT in match.group(1) or self.TEMPLATE_END_COMMENT in match.group(1):
                raise BadStructure(
                    f"Task {task_name} has invalid template comments in file {file_path}."
                    f" There is <{self.TEMPLATE_START_COMMENT}> or <{self.TEMPLATE_END_COMMENT}> "
                    f"between valid pair of comments"
                )

    def _validate_template_comments(self, task_name: str, task_folder: Path) -> tuple[bool, bool]:
        """Validate template comments in all files in the task folder.

        Check all (not binary) files for template comments.

        Returns:
            tuple: (has_template_comments, has_valid_template_comments)
        """
        has_template_comments = False
        has_valid_template_comments = False

        for potential_comments_file in task_folder.glob("**/*"):
            if potential_comments_file.is_dir():
                continue

            # skip binary files
            try:
                file_content = potential_comments_file.read_text()
            except UnicodeDecodeError:
                continue

            if self.TEMPLATE_START_COMMENT not in file_content and self.TEMPLATE_END_COMMENT not in file_content:
                continue

            has_template_comments = True
            self._validate_template_comments_in_file(task_name, potential_comments_file, file_content)
            has_valid_template_comments = True

        return has_template_comments, has_valid_template_comments

    def _validate_template_type(
        self,
        task_name: str,
        has_template_files: bool,
        has_valid_template_files: bool,
        has_template_comments: bool,
        has_valid_template_comments: bool,
    ) -> None:
        """Validate template type constraints for a task."""
        template_type = self.export_config.templates

        if template_type == CheckerExportConfig.TemplateType.SEARCH:
            if has_template_comments:
                raise BadStructure(
                    f"Templating set to {template_type} but task {task_name} has "
                    f"template comments <{self.TEMPLATE_START_COMMENT}> and <{self.TEMPLATE_END_COMMENT}>"
                )
            if not has_valid_template_files:
                raise BadStructure(
                    f"Task {task_name} does not have `.template` file/folder. Have to include at least one"
                )
        elif template_type == CheckerExportConfig.TemplateType.CREATE:
            if has_template_files:
                raise BadStructure(
                    f"Templating set to {template_type} but task {task_name} has `.template` file/folder"
                )
            if not has_valid_template_comments:
                raise BadStructure(
                    f"Task {task_name} does not have template comments. Have to include at least one pair of "
                    f"<{self.TEMPLATE_START_COMMENT}> and <{self.TEMPLATE_END_COMMENT}>"
                )
        elif template_type == CheckerExportConfig.TemplateType.SEARCH_OR_CREATE:
            if has_template_files and has_template_comments:
                raise BadStructure(f"Task {task_name} can not use both `.template` file/folder and template comments")
            if not has_valid_template_files and not has_valid_template_comments:
                raise BadStructure(
                    f"Task {task_name} does not have `.template` file/folder or at least one pair of "
                    f"<{self.TEMPLATE_START_COMMENT}> and <{self.TEMPLATE_END_COMMENT}>"
                )
        else:  # pragma: no cover
            assert False, "Not Reachable"

    def validate(self) -> None:
        # validate course
        self.course.validate()

        # TODO: validate structure correct glob patterns

        # validate templates
        # `original.template` files/folders need to have `original` file/folder
        # template comments have to be paired
        # template comments can not be one inside another
        # if `templates` is set to `SEARCH` - only `.template` allowed
        # if `templates` is set to `CREATE` - only template comments allowed
        # if `templates` is set to `SEARCH_OR_CREATE` - both allowed, but one inside one task
        for task in self.course.get_tasks(enabled=True):
            # TODO: check template not public and not private file

            task_folder = self.reference_root / task.relative_path
            has_template_files, has_valid_template_files = self._validate_template_files(task_folder)
            has_template_comments, has_valid_template_comments = self._validate_template_comments(
                task.name, task_folder
            )
            self._validate_template_type(
                task.name,
                has_template_files,
                has_valid_template_files,
                has_template_comments,
                has_valid_template_comments,
            )

    def _search_for_exclude_due_to_templates(
        self,
        root: Path,
        ignore_templates: bool,
    ) -> list[str]:
        """Search for files/folder should be ignored due to templating in the current directory only"""
        exclude_paths = []

        if self.export_config.templates in (
            CheckerExportConfig.TemplateType.SEARCH,
            CheckerExportConfig.TemplateType.SEARCH_OR_CREATE,
        ):
            for template_file_or_folder in root.glob(f"*{self.TEMPLATE_SUFFIX}"):
                if ignore_templates:
                    exclude_paths.append(template_file_or_folder.name)
                else:
                    exclude_paths.append(template_file_or_folder.stem)

        if self.export_config.templates in (
            CheckerExportConfig.TemplateType.CREATE,
            CheckerExportConfig.TemplateType.SEARCH_OR_CREATE,
        ):
            # if got empty file after template comments deletion - exclude it
            for potential_comments_file in root.glob("*"):
                if potential_comments_file.is_dir():
                    continue
                try:
                    open(potential_comments_file, "r").read()
                except UnicodeDecodeError:
                    continue
                with potential_comments_file.open("r") as f:
                    file_content = f.read().strip()
                    if file_content.startswith(self.TEMPLATE_START_COMMENT) and file_content.endswith(
                        self.TEMPLATE_END_COMMENT
                    ):
                        exclude_paths.append(potential_comments_file.name)

        return exclude_paths

    def export_public(
        self,
        target: Path,
        commit: bool = True,
        commit_message: str = "chore(auto): Update public files [skip-ci]",
    ) -> None:
        target.mkdir(parents=True, exist_ok=True)

        disabled_groups_and_tasks_to_skip = [
            *[group.relative_path for group in self.course.get_groups(enabled=False)],
            *[group.relative_path for group in self.course.get_groups(started=False)],
            *[task.relative_path for task in self.course.get_tasks(enabled=False)],
            *[task.relative_path for task in self.course.get_tasks(started=False)],
        ]

        print_info(f"Copy from {self.reference_root} to {target}", color="grey")
        self._copy_files_with_config(
            self.reference_root,
            target,
            self.structure_config,
            copy_public=True,
            copy_private=False,
            copy_other=True,
            fill_templates=True,
            extra_ignore_paths=disabled_groups_and_tasks_to_skip,
        )

        if commit:
            self._commit_and_push_repo(target, commit_message)

    def export_for_testing(
        self,
        target: Path,
    ) -> None:
        target.mkdir(parents=True, exist_ok=True)

        print_info(f"Copy from {self.repository_root} to {target}", color="grey")
        self._copy_files_with_config(
            self.repository_root,
            target,
            self.structure_config,
            copy_public=False,
            copy_private=False,
            copy_other=True,
            fill_templates=False,
        )

        print_info(f"Copy from {self.reference_root} to {target}", color="grey")
        self._copy_files_with_config(
            self.reference_root,
            target,
            self.structure_config,
            copy_public=True,
            copy_private=True,
            copy_other=False,
            fill_templates=False,
        )

    def export_for_contribution(
        self,
        target: Path,
    ) -> None:
        target.mkdir(parents=True, exist_ok=True)

        print_info(f"Copy from {self.repository_root} to {target}", color="grey")
        self._copy_files_with_config(
            self.repository_root,
            target,
            self.structure_config,
            copy_public=True,
            copy_private=False,
            copy_other=True,
            fill_templates=False,
        )

        print_info(f"Copy from {self.reference_root} to {target}", color="grey")
        self._copy_files_with_config(
            self.reference_root,
            target,
            self.structure_config,
            copy_public=False,
            copy_private=True,
            copy_other=True,
            fill_templates=False,
        )

    def export_private(
        self,
        target: Path,
    ) -> None:
        target.mkdir(parents=True, exist_ok=True)

        disabled_groups_and_tasks_to_skip = [
            *[group.relative_path for group in self.course.get_groups(enabled=False)],
            *[group.relative_path for group in self.course.get_groups(started=False)],
            *[task.relative_path for task in self.course.get_tasks(enabled=False)],
            *[task.relative_path for task in self.course.get_tasks(started=False)],
        ]

        print_info(f"Copy from {self.reference_root} to {target}", color="grey")
        self._copy_files_with_config(
            self.reference_root,
            target,
            self.structure_config,
            copy_public=False,
            copy_private=False,
            copy_other=True,
            fill_templates=True,
            extra_ignore_paths=disabled_groups_and_tasks_to_skip,
        )

        self._copy_files_with_config(
            self.reference_root,
            target,
            self.structure_config,
            copy_public=True,
            copy_private=True,
            copy_other=False,
            fill_templates=False,
            extra_ignore_paths=disabled_groups_and_tasks_to_skip,
        )

    def _is_text_file(self, path: Path) -> bool:
        """Check if the file is a text file (not binary)."""
        # check if byte file
        if not path.is_file():
            return False
        try:
            path.read_text()
            return True
        except UnicodeDecodeError:
            return False

    def _is_template_file(self, path: Path) -> bool:
        """Check if the path is a .template file/folder."""
        # check if file template
        return self.export_config.templates in (
            CheckerExportConfig.TemplateType.SEARCH,
            CheckerExportConfig.TemplateType.SEARCH_OR_CREATE,
        ) and path.name.endswith(self.TEMPLATE_SUFFIX)

    def _is_template_comment_file(self, path: Path, is_text_file: bool) -> bool:
        """Check if the file contains template comments."""
        if not is_text_file or path.is_dir():
            return False
        if self.export_config.templates not in (
            CheckerExportConfig.TemplateType.CREATE,
            CheckerExportConfig.TemplateType.SEARCH_OR_CREATE,
        ):
            return False
        content = path.read_text()
        return self.TEMPLATE_START_COMMENT in content and self.TEMPLATE_END_COMMENT in content

    def _should_skip_path(  # noqa: C901, PLR0911, PLR0912, PLR0913
        self,
        path: Path,
        config: CheckerStructureConfig,
        exclude_paths: list[str],
        copy_public: bool,
        copy_private: bool,
        copy_other: bool,
        fill_templates: bool,
        is_path_template_file: bool,
        path_destination: Path,
        global_root: Path,
    ) -> tuple[bool, bool, bool]:
        """Check if path should be skipped, and determine if it's public/private.

        Returns:
            tuple: (should_skip, is_public, is_private)
        """
        # if will replace with template - ignore file
        if path.name in exclude_paths:
            if self.verbose:
                print_info(f"    - Skip <{path.relative_to(global_root)}> because of templating", color="grey")
            return True, False, False

        # ignore if match ignore patterns
        if config.ignore_patterns and any(path.match(ignore_pattern) for ignore_pattern in config.ignore_patterns):
            if self.verbose:
                print_info(f"    - Skip <{path.relative_to(global_root)}> because of ignore patterns", color="grey")
            return True, False, False

        # If matches public patterns AND copy_public is False - skip
        is_public = bool(
            config.public_patterns and any(path.match(public_pattern) for public_pattern in config.public_patterns)
        )
        if is_public and not copy_public:
            if self.verbose:
                print_info(
                    f"    - Skip <{path.relative_to(global_root)}> because of public patterns skip", color="grey"
                )
            return True, is_public, False

        # If matches private patterns AND copy_private is False - skip
        # If it is public file - never consider it as private
        is_private = bool(
            not is_public
            and config.private_patterns
            and any(path.match(private_pattern) for private_pattern in config.private_patterns)
        )
        if is_private and not copy_private:
            if self.verbose:
                print_info(
                    f"    - Skip <{path.relative_to(global_root)}> because of skip private patterns skip", color="grey"
                )
            return True, is_public, is_private

        # if not match public and not match private and copy_other is False - skip
        # Note: never skip "other" directories, look inside them first
        if not is_public and not is_private and not path.is_dir() and not copy_other:
            if self.verbose:
                print_info(
                    f"    - Skip <{path.relative_to(global_root)}> because of copy other files not enabled",
                    color="grey",
                )
            return True, is_public, is_private

        # if file is empty file/folder - just do not copy (delete original file due to exclude_paths)
        if fill_templates and is_path_template_file:
            if path.is_dir() and not any((path_destination / file).exists() for file in path.iterdir()):
                if self.verbose:
                    print_info(
                        f"    - Skip <{path.relative_to(global_root)}> because it is empty folder and "
                        f"templating is set to {self.export_config.templates}",
                        color="grey",
                    )
                return True, is_public, is_private
            if path.is_file() and path.stat().st_size == 0:
                if self.verbose:
                    print_info(
                        f"    - Skip <{path.relative_to(global_root)}> because it is empty file and "
                        f"templating is set to {self.export_config.templates}",
                        color="grey",
                    )
                return True, is_public, is_private

        return False, is_public, is_private

    def _get_sub_config(self, path: Path, config: CheckerStructureConfig, global_root: Path) -> CheckerStructureConfig:
        """Get sub-config for a directory if exists, otherwise return current config.

        If have sub-config - update config with sub-config.
        """
        relative_path = path.relative_to(global_root)
        if relative_path not in self.sub_config_files:
            return config

        declared_sub_config = self.sub_config_files[relative_path]
        return CheckerStructureConfig(
            ignore_patterns=(
                declared_sub_config.ignore_patterns
                if declared_sub_config.ignore_patterns is not None
                else config.ignore_patterns
            ),
            private_patterns=(
                declared_sub_config.private_patterns
                if declared_sub_config.private_patterns is not None
                else config.private_patterns
            ),
            public_patterns=(
                declared_sub_config.public_patterns
                if declared_sub_config.public_patterns is not None
                else config.public_patterns
            ),
        )

    def _copy_directory(  # noqa: PLR0913
        self,
        path: Path,
        path_destination: Path,
        config: CheckerStructureConfig,
        copy_public: bool,
        copy_private: bool,
        copy_other: bool,
        fill_templates: bool,
        is_public: bool,
        is_private: bool,
        is_path_template_file: bool,
        extra_ignore_paths: list[str] | None,
        global_root: Path,
        global_destination: Path,
    ) -> None:
        """Handle copying a directory.

        If the file is a directory, recursively call _copy_files_with_config.
        """
        # if folder public or private - just copy it
        if is_public or is_private:
            if self.verbose:
                print_info(
                    f"    - Fully Copy <{path.relative_to(global_root)}> to "
                    f"<{path_destination.relative_to(global_destination)}>",
                    color="grey",
                )
            self._copy_files_with_config(
                path,
                path_destination,
                config,
                copy_public=True,
                copy_private=True,
                copy_other=True,
                fill_templates=fill_templates,
                extra_ignore_paths=extra_ignore_paths,
                global_root=global_root,
                global_destination=global_destination,
            )
            return

        # If directory `origin.template` - copy from this folder to `origin`
        if fill_templates and is_path_template_file:
            path_destination = path_destination.parent / path_destination.stem

        sub_config = self._get_sub_config(path, config, global_root)

        # Recursively call this function
        if self.verbose:
            print_info(
                f"    -- Recursively copy from <{path.relative_to(global_root)}> to "
                f"<{path_destination.relative_to(global_destination)}>",
                color="grey",
            )
        self._copy_files_with_config(
            path,
            path_destination,
            sub_config,
            copy_public,
            copy_private,
            copy_other,
            fill_templates,
            extra_ignore_paths,
            global_root=global_root,
            global_destination=global_destination,
        )

    def _copy_file(
        self,
        path: Path,
        path_destination: Path,
        fill_templates: bool,
        is_path_template_file: bool,
        is_path_template_comment: bool,
        global_root: Path,
        global_destination: Path,
    ) -> None:
        """Handle copying a file.

        If the file is a normal file, copy it.
        """
        if self.verbose:
            print_info(
                f"    - Copy <{path.relative_to(global_root)}> to <{path_destination.relative_to(global_destination)}>",
                color="grey",
            )
        path_destination.parent.mkdir(parents=True, exist_ok=True)

        # if `origin.template` - copy from this file as `origin`
        if fill_templates and is_path_template_file:
            path_destination = path_destination.parent / path_destination.stem

        # if template comments in file - replace them, not greedy
        if fill_templates and is_path_template_comment:
            file_content = path.read_text()
            file_content = self.TEMPLATE_COMMENT_REGEX.sub(self.TEMPLATE_REPLACE_COMMENT, file_content)
            path_destination.touch(exist_ok=True)
            path_destination.write_text(file_content)
        else:
            shutil.copyfile(path, path_destination)
            shutil.copymode(path, path_destination)

    def _copy_files_with_config(  # noqa: PLR0913
        self,
        root: Path,
        destination: Path,
        config: CheckerStructureConfig,
        copy_public: bool,
        copy_private: bool,
        copy_other: bool,
        fill_templates: bool,
        extra_ignore_paths: list[str] | None = None,
        global_root: Path | None = None,
        global_destination: Path | None = None,
    ) -> None:
        """
        Copy files from `root` to `destination` according to `config`.
        When face `sub_config_files`, apply it to the folder and all subfolders.

        :param root: Copy files from this directory
        :param destination: Copy files to this directory
        :param config: Config to apply to this folder (and recursively)
        :param copy_public: Copy public files
        :param copy_private: Copy private files
        :param copy_other: Copy other - not public and not private files
        :param fill_templates: Fill templates (`.template` or template comments), if false will delete them
        :param extra_ignore_paths: Extra paths to ignore to skip not-enables groups/tasks, relative to `global_root`
        :param global_root: Starting root directory
        :param global_destination: Starting destination directory
        """
        # TODO: implement template searcher

        global_root = global_root or root
        global_destination = global_destination or destination

        if self.verbose:
            print_info(
                f"Copy files from <{root.relative_to(global_root)}> to <{destination.relative_to(global_destination)}>",
                color="white",
            )
            print_info(f"  {config=}", color="white")

        if extra_ignore_paths is not None and str(root.relative_to(global_root)) in extra_ignore_paths:
            if self.verbose:
                print_info(f"    - Skip <{root.relative_to(global_root)}> because of extra ignore paths", color="grey")
            return

        # select paths to ignore - original to replace or templates to ignore
        exclude_paths = self._search_for_exclude_due_to_templates(root, not fill_templates)

        # Iterate over all files in the root directory
        for path in root.iterdir():
            path_destination = destination / path.relative_to(root)
            is_text_file = self._is_text_file(path)
            is_path_template_file = self._is_template_file(path)
            is_path_template_comment = self._is_template_comment_file(path, is_text_file)

            should_skip, is_public, is_private = self._should_skip_path(
                path,
                config,
                exclude_paths,
                copy_public,
                copy_private,
                copy_other,
                fill_templates,
                is_path_template_file,
                path_destination,
                global_root,
            )
            if should_skip:
                continue

            if path.is_dir():
                self._copy_directory(
                    path,
                    path_destination,
                    config,
                    copy_public,
                    copy_private,
                    copy_other,
                    fill_templates,
                    is_public,
                    is_private,
                    is_path_template_file,
                    extra_ignore_paths,
                    global_root,
                    global_destination,
                )
            else:
                self._copy_file(
                    path,
                    path_destination,
                    fill_templates,
                    is_path_template_file,
                    is_path_template_comment,
                    global_root,
                    global_destination,
                )

    def _commit_and_push_repo(  # pragma: no cover
        self,
        repo_dir: Path,
        message: str = "Export public files",
    ) -> None:
        """Commit and push all changes in the repository."""
        print_info("* git status...")
        r = subprocess.run(
            "git status",
            encoding="utf-8",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            shell=True,
            check=True,
            cwd=repo_dir,
        )
        print_info(r.stdout, color="grey")

        print_info("* adding files...")
        r = subprocess.run(
            "git add .",
            encoding="utf-8",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            shell=True,
            cwd=repo_dir,
        )
        print_info(r.stdout, color="grey")

        print_info("* committing...")
        r = subprocess.run(
            ["git", "commit", "--all", "-m", message],
            encoding="utf-8",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=repo_dir,
        )
        print_info(r.stdout, color="grey")
        # Return code 1 means nothing to commit, which is OK
        if r.returncode not in (0, 1):
            raise Exception(f"Git commit failed with code {r.returncode}: {r.stdout}")

        print_info("* git pushing...")
        r = subprocess.run(
            "git push -o ci.skip origin",
            encoding="utf-8",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            shell=True,
            cwd=repo_dir,
        )
        print_info(r.stdout, color="grey")
        if r.returncode != 0:
            raise Exception("Can not push files to public repo")

        print_info("Done.")

    def __del__(self) -> None:
        if self.__dict__.get("cleanup") and self._temporary_dir_manager:
            self._temporary_dir_manager.cleanup()

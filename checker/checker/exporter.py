from __future__ import annotations

import re
import shutil
import tempfile
from collections.abc import Generator
from pathlib import Path

from git import GitCommandError, Repo

from checker.configs import CheckerExportConfig, CheckerStructureConfig
from checker.course import Course, FileSystemTask
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

    def validate(self) -> None:
        # validate course
        self.course.validate()

        # TODO: validate structure correct glob patterns

        # validate templates
        for task in self.course.get_tasks(enabled=True):
            # TODO: check template not public and not private file
            self._validate_task_templates(task)

    def _validate_task_templates(self, task: FileSystemTask) -> None:
        task_folder = self.reference_root / task.relative_path
        has_template_files = self._has_template_files(task_folder)
        has_template_comments = self._has_template_comments(task.name, task_folder)
        self._enforce_template_policy(task.name, has_template_files, has_template_comments)

    def _has_template_files(self, task_folder: Path) -> bool:
        has_template_files = False
        for template_file_or_folder in task_folder.glob(f"**/*{self.TEMPLATE_SUFFIX}"):
            has_template_files = True
            if not (template_file_or_folder.parent / template_file_or_folder.stem).exists():
                raise BadStructure(
                    f"Template file/folder {template_file_or_folder} does not have "
                    f"original file/folder {self.reference_root / template_file_or_folder.stem}"
                )
        return has_template_files

    def _iter_text_files(self, root: Path) -> Generator[tuple[Path, str], None, None]:
        for potential_comments_file in root.glob("**/*"):
            if potential_comments_file.is_dir():
                continue
            try:
                content = potential_comments_file.read_text()
            except UnicodeDecodeError:
                continue
            yield potential_comments_file, content

    def _validate_comment_structure(self, task_name: str, file_path: Path, file_content: str) -> None:
        if self.TEMPLATE_START_COMMENT in file_content or self.TEMPLATE_END_COMMENT in file_content:
            if file_content.count(self.TEMPLATE_START_COMMENT) != file_content.count(self.TEMPLATE_END_COMMENT):
                raise BadStructure(
                    f"Task {task_name} has invalid template comments in file {file_path}. "
                    f"The number of <{self.TEMPLATE_START_COMMENT}> and <{self.TEMPLATE_END_COMMENT}> do not match"
                )
            for match in self.TEMPLATE_COMMENT_REGEX.finditer(file_content):
                inner = match.group(1)
                if self.TEMPLATE_START_COMMENT in inner or self.TEMPLATE_END_COMMENT in inner:
                    raise BadStructure(
                        f"Task {task_name} has invalid template comments in file {file_path}."
                        f" There is <{self.TEMPLATE_START_COMMENT}> or <{self.TEMPLATE_END_COMMENT}> "
                        f"between valid pair of comments"
                    )

    def _has_template_comments(self, task_name: str, task_folder: Path) -> bool:
        has_template_comments = False
        for file_path, file_content in self._iter_text_files(task_folder):
            if self.TEMPLATE_START_COMMENT in file_content or self.TEMPLATE_END_COMMENT in file_content:
                has_template_comments = True
                self._validate_comment_structure(task_name, file_path, file_content)
        return has_template_comments

    def _enforce_template_policy(self, task_name: str, has_template_files: bool, has_template_comments: bool) -> None:
        if self.export_config.templates == CheckerExportConfig.TemplateType.SEARCH:
            if has_template_comments:
                raise BadStructure(
                    f"Templating set to {self.export_config.templates} but task {task_name} has "
                    f"template comments <{self.TEMPLATE_START_COMMENT}> and <{self.TEMPLATE_END_COMMENT}>"
                )
            if not has_template_files:
                raise BadStructure(
                    f"Task {task_name} does not have `.template` file/folder. Have to include at least one"
                )
        elif self.export_config.templates == CheckerExportConfig.TemplateType.CREATE:
            if has_template_files:
                raise BadStructure(
                    f"Templating set to {self.export_config.templates} but task {task_name} has `.template` file/folder"
                )
            if not has_template_comments:
                raise BadStructure(
                    f"Task {task_name} does not have template comments. Have to include at least one pair of "
                    f"<{self.TEMPLATE_START_COMMENT}> and <{self.TEMPLATE_END_COMMENT}>"
                )
        elif self.export_config.templates == CheckerExportConfig.TemplateType.SEARCH_OR_CREATE:
            if has_template_files and has_template_comments:
                raise BadStructure(f"Task {task_name} can not use both `.template` file/folder and template comments")
            if not has_template_files and not has_template_comments:
                raise BadStructure(
                    f"Task {task_name} does not have `.template` file/folder or at least one pair of "
                    f"<{self.TEMPLATE_START_COMMENT}> and <{self.TEMPLATE_END_COMMENT}>"
                )
        else:  # pragma: no cover
            assert False, "Not Reachable"

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
        push: bool = False,
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

        if push and not self.dry_run:
            self._commit_and_push(target, commit_message)

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

    def _copy_files_with_config(  # noqa: C901, PLR0912, PLR0915
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

        if extra_ignore_paths is not None:
            if str(root.relative_to(global_root)) in extra_ignore_paths:
                if self.verbose:
                    print_info(
                        f"    - Skip <{root.relative_to(global_root)}> because of extra ignore paths", color="grey"
                    )
                return

        # select paths to ignore - original to replace or templates to ignore
        exclude_paths = self._search_for_exclude_due_to_templates(root, not fill_templates)

        # Iterate over all files in the root directory
        for path in root.iterdir():
            path_destination = destination / path.relative_to(root)
            # check if byte file
            is_text_file = False
            try:
                if path.is_file():
                    open(path, "r").read()
                    is_text_file = True
            except UnicodeDecodeError:
                pass
            # check if file template
            is_path_template_file = (
                self.export_config.templates
                in (
                    CheckerExportConfig.TemplateType.SEARCH,
                    CheckerExportConfig.TemplateType.SEARCH_OR_CREATE,
                )
            ) and path.name.endswith(self.TEMPLATE_SUFFIX)
            is_path_template_comment = (
                is_text_file
                and (
                    self.export_config.templates
                    in (
                        CheckerExportConfig.TemplateType.CREATE,
                        CheckerExportConfig.TemplateType.SEARCH_OR_CREATE,
                    )
                )
                and not path.is_dir()
                and self.TEMPLATE_START_COMMENT in path.read_text()
                and self.TEMPLATE_END_COMMENT in path.read_text()
            )

            # if will replace with template - ignore file
            if path.name in exclude_paths:
                if self.verbose:
                    print_info(f"    - Skip <{path.relative_to(global_root)}> because of templating", color="grey")
                continue

            # ignore if match ignore patterns
            if config.ignore_patterns and any(path.match(ignore_pattern) for ignore_pattern in config.ignore_patterns):
                if self.verbose:
                    print_info(f"    - Skip <{path.relative_to(global_root)}> because of ignore patterns", color="grey")
                continue

            # If matches public patterns AND copy_public is False - skip
            is_public = False
            if config.public_patterns and any(path.match(public_pattern) for public_pattern in config.public_patterns):
                is_public = True
                if not copy_public:
                    if self.verbose:
                        print_info(
                            f"    - Skip <{path.relative_to(global_root)}> because of public patterns skip",
                            color="grey",
                        )
                    continue

            # If matches private patterns AND copy_private is False - skip
            # If it is public file - never consider it as private
            is_private = False
            if (
                not is_public
                and config.private_patterns
                and any(path.match(private_pattern) for private_pattern in config.private_patterns)
            ):
                is_private = True
                if not copy_private:
                    if self.verbose:
                        print_info(
                            f"    - Skip <{path.relative_to(global_root)}> because of skip private patterns skip",
                            color="grey",
                        )
                    continue

            # if not match public and not match private and copy_other is False - skip
            # Note: never skip "other" directories, look inside them first
            if not is_public and not is_private and not path.is_dir():
                if not copy_other:
                    if self.verbose:
                        print_info(
                            f"    - Skip <{path.relative_to(global_root)}> because of copy other files not enabled",
                            color="grey",
                        )
                    continue

            # if file is empty file/folder - just do not copy (delete original file due to exclude_paths)
            if fill_templates and is_path_template_file:
                if path.is_dir() and not any((path_destination / file).exists() for file in path.iterdir()):
                    if self.verbose:
                        print_info(
                            f"    - Skip <{path.relative_to(global_root)}> because it is empty folder and "
                            f"templating is set to {self.export_config.templates}",
                            color="grey",
                        )
                    continue
                if path.is_file() and path.stat().st_size == 0:
                    if self.verbose:
                        print_info(
                            f"    - Skip <{path.relative_to(global_root)}> because it is empty file and "
                            f"templating is set to {self.export_config.templates}",
                            color="grey",
                        )
                    continue

            # If the file is a directory, recursively call this function
            if path.is_dir():
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
                    continue

                # If directory `origin.template` - copy from this folder to `origin`
                if fill_templates and is_path_template_file:
                    path_destination = path_destination.parent / path_destination.stem

                # If have sub-config - update config with sub-config
                if path.relative_to(global_root) in self.sub_config_files:
                    declared_sub_config = self.sub_config_files[path.relative_to(global_root)]
                    sub_config = CheckerStructureConfig(
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
                else:
                    sub_config = config

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
            # If the file is a normal file, copy it
            else:
                if self.verbose:
                    print_info(
                        f"    - Copy <{path.relative_to(global_root)}> to "
                        f"<{path_destination.relative_to(global_destination)}>",
                        color="grey",
                    )
                path_destination.parent.mkdir(parents=True, exist_ok=True)

                # if `origin.template` - copy from this file as `origin`
                if fill_templates and is_path_template_file:
                    path_destination = path_destination.parent / path_destination.stem

                # if template comments in file - replace them, not greedy
                if fill_templates and is_path_template_comment:
                    with path.open("r") as f:
                        file_content = f.read()
                    file_content = self.TEMPLATE_COMMENT_REGEX.sub(self.TEMPLATE_REPLACE_COMMENT, file_content)
                    path_destination.touch(exist_ok=True)
                    path_destination.write_text(file_content)
                else:
                    shutil.copyfile(
                        path,
                        path_destination,
                    )
                    shutil.copymode(path, path_destination)

    def _commit_and_push(self, target: Path, commit_message: str) -> None:
        """
        Commit and push all changes to the public repository.

        :param target: Path to the target directory (public repository)
        :param commit_message: Commit message to use
        """
        try:
            if not (target / ".git").exists():
                print_info("Initializing git repository...", color="grey")
                repo = Repo.init(target)

                remote_url = str(self.export_config.destination)
                if self.export_config.service_username and self.export_config.service_token:
                    if remote_url.startswith("https://"):
                        remote_url = remote_url.replace("https://", "")
                        remote_url = f"https://{self.export_config.service_username}:{self.export_config.service_token}@{remote_url}"
                    elif remote_url.startswith("http://"):
                        remote_url = remote_url.replace("http://", "")
                        remote_url = f"http://{self.export_config.service_username}:{self.export_config.service_token}@{remote_url}"

                if not remote_url.endswith(".git"):
                    remote_url = f"{remote_url}.git"

                print_info(
                    f"Setting up remote origin: {remote_url.split('@')[-1] if '@' in remote_url else remote_url}",
                    color="grey",
                )
                repo.create_remote("origin", remote_url)
            else:
                repo = Repo(target)

            print_info("Staging all changes...", color="grey")
            repo.git.add("--all")

            if repo.is_dirty() or repo.untracked_files:
                print_info(f"Committing changes: {commit_message}", color="grey")
                repo.index.commit(commit_message)

                print_info(f"Pushing to {self.export_config.default_branch}...", color="grey")
                origin = repo.remote(name="origin")
                origin.push(refspec=f"HEAD:refs/heads/{self.export_config.default_branch}")
                print_info("Successfully pushed changes to public repository", color="green")
            else:
                print_info("No changes to commit", color="orange")

        except GitCommandError as e:
            print_info(f"Git error during commit/push: {e}", color="red")
            raise BadStructure(f"Failed to commit and push to public repository: {e}")
        except Exception as e:
            print_info(f"Unexpected error during commit/push: {e}", color="red")
            raise BadStructure(f"Failed to commit and push to public repository: {e}")

    def __del__(self) -> None:
        if self.__dict__.get("cleanup") and self._temporary_dir_manager:
            self._temporary_dir_manager.cleanup()

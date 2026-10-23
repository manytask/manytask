from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any, Optional, Self, Union

import yaml
from pydantic import (
    AnyUrl,
    ConfigDict,
    Field,
    RootModel,
    ValidationError,
    field_validator,
    model_validator,
)

from checker.exceptions import BadConfig
from .utils import CustomBaseModel, YamlLoaderMixin

# Note: old Union style in definition for backward compatibility
TParamType = Union[bool, int, float, str, list[Union[int, float, str, None]], None]
TTemplate = Union[str, list[Union[TParamType, str]], dict[str, Union[TParamType, str]]]


def validate_allow_change(value: object) -> list[str] | None:
    if value is None:
        return None
    message = (
        "allow_change must be a list of relative glob patterns inside the task folder"
    )
    if not isinstance(value, list):
        raise ValueError(message)
    patterns = []
    for pattern in value:
        if (
            not isinstance(pattern, str)
            or not pattern
            or Path(pattern).is_absolute()
            or ".." in Path(pattern).parts
        ):
            raise ValueError(message)
        patterns.append(pattern)
    return patterns


class CheckerStructureConfig(CustomBaseModel):
    # Note: use Optional/Union[...] instead of ... | None as pydantic does not support | in older python versions
    ignore_patterns: Optional[list[str]] = None
    private_patterns: Optional[list[str]] = None
    public_patterns: Optional[list[str]] = None
    # TODO: add check "**" is not allowed


class CheckerParametersConfig(RootModel[dict[str, TParamType]]):
    root: dict[str, TParamType]

    @field_validator("root")
    @classmethod
    def check_allow_change(
        cls, parameters: dict[str, TParamType]
    ) -> dict[str, TParamType]:
        validate_allow_change(parameters.get("allow_change"))
        return parameters

    def __getitem__(self, item: str) -> TParamType:
        return self.root[item]

    def __contains__(self, item: str) -> bool:
        return item in self.root

    @property
    def __dict__(self) -> dict[str, TParamType]:
        return self.root

    @__dict__.setter
    def __dict__(self, value: dict[str, TParamType]) -> None:
        self.root = value


class CheckerExportConfig(CustomBaseModel):
    class TemplateType(Enum):
        """Template type for export for each task.

        :ivar SEARCH: search for files/folder with name `some_file.template` and override `some_file` with it.
            If `some_file.template` is empty file/folder it will delete `some_file`.
            For ALL `some_file.template` files original `some_file` HAVE TO exist.
            At least one `some_file.template` HAVE TO exist for each task.
        :ivar CREATE: for all files in the repo search for template comments and delete all code between them.
            For example:
            ```python
            a = 1
            # SOLUTION BEGIN
            a = 2
            # SOLUTION END
            b = 3
            ```
            will be converted to:
            ```python
            a = 1
            # TODO: Your solution
            b = 3
            ```
            Delete file if it is empty after template comments deletion.
            Each task HAVE to contain at least one template comment pair.
        :ivar SEARCH_OR_CREATE: try to search for files/folder with name `some_file.template`
            if not found try to create it using template comments.
        """

        SEARCH = "search"
        CREATE = "create"
        SEARCH_OR_CREATE = "search_or_create"

    destination: AnyUrl
    default_branch: str = "main"
    commit_message: str = "chore(auto): export new tasks"
    templates: TemplateType = TemplateType.SEARCH
    # Push options passed to `git push` as `-o <option>` flags when exporting.
    # Backward-compatible default matches the previous hardcoded behavior:
    # `["ci.skip"]` tells GitLab to skip pipelines for the auto-export commit.
    # Set to `[]` for git servers that do not support push options (e.g. SourceCraft),
    # or override with any other list of options understood by the destination server.
    push_options: list[str] = Field(default_factory=lambda: ["ci.skip"])


class PipelineStageConfig(CustomBaseModel):
    class FailType(Enum):
        FAST = "fast"
        AFTER_ALL = "after_all"
        NEVER = "never"

    name: str
    run: str

    # Note: use Optional/Union[...] instead of ... | None as pydantic does not support | in older python versions
    args: dict[str, Union[TParamType, TTemplate]] = Field(default_factory=dict)

    run_if: Union[bool, TTemplate, None] = None
    fail: FailType = FailType.FAST

    # save pipline stage result to context under this key
    register_output: Optional[str] = None


class CheckerTestingConfig(CustomBaseModel):
    class ChangesDetectionType(Enum):
        BRANCH_NAME = "branch_name"
        BRANCH_NAME_OR_COMMIT_MESSAGE = "branch_name_or_commit_message"
        COMMIT_MESSAGE = "commit_message"
        LAST_COMMIT_CHANGES = "last_commit_changes"
        FILES_CHANGED = "files_changed"

    changes_detection: ChangesDetectionType = ChangesDetectionType.LAST_COMMIT_CHANGES

    search_plugins: list[str] = Field(default_factory=list)

    # name of the task parameter holding glob patterns of student-editable files (e.g. "allow_change");
    # None disables skipping tasks unchanged since the published version
    skip_unchanged_tasks: Optional[str] = None

    global_pipeline: list[PipelineStageConfig] = Field(default_factory=list)
    tasks_pipeline: list[PipelineStageConfig] = Field(default_factory=list)
    report_pipeline: list[PipelineStageConfig] = Field(default_factory=list)


class CheckerConfig(CustomBaseModel, YamlLoaderMixin["CheckerConfig"]):
    """
    Checker configuration.

    :ivar version: config version
    :ivar default_parameters: default parameters for task pipeline
    :ivar structure: describe the structure of the repo - private/public and allowed for change files
    :ivar export: describe export (publishing to public repo)
    :ivar manytask: describe connection to manytask
    :ivar testing: describe testing/checking - pipeline, isolation etc
    """

    version: int  # if config exists, version is always present

    default_parameters: CheckerParametersConfig = Field(default_factory=lambda: CheckerParametersConfig(root={}))

    structure: CheckerStructureConfig
    export: CheckerExportConfig
    testing: CheckerTestingConfig

    @field_validator("version")
    @classmethod
    def check_version(cls, v: int) -> None:
        if v != 1:
            raise ValidationError(f"Only version 1 is supported for {cls.__name__}")


class CheckerTaskOverrides(CustomBaseModel):
    """Options shared by a task file and its named task entries."""

    model_config = ConfigDict(extra="forbid", validate_default=True)
    # Note: use Optional[...] instead of ... | None as pydantic does not support | in older python versions
    parameters: Optional[CheckerParametersConfig] = None
    task_pipeline: Optional[list[PipelineStageConfig]] = None
    report_pipeline: Optional[list[PipelineStageConfig]] = None


class CheckerSubConfig(CheckerTaskOverrides, YamlLoaderMixin["CheckerSubConfig"]):
    """Folder overrides, or the resolved configuration of one task."""

    model_config = ConfigDict(extra="ignore", validate_default=True)
    version: int  # if config exists, version is always present
    structure: Optional[CheckerStructureConfig] = None

    @classmethod
    def default(cls) -> "CheckerSubConfig":
        return CheckerSubConfig(version=1)

    @field_validator("version")
    @classmethod
    def check_version(cls, v: int) -> int:
        if v != 1:
            raise ValueError(f"Only version 1 is supported for {cls.__name__}")
        return v


class _TaskConfigYamlLoader(yaml.SafeLoader):
    def construct_mapping(
        self, node: yaml.MappingNode, deep: bool = False
    ) -> dict[Any, Any]:
        keys: set[Any] = set()
        for key_node, _ in node.value:
            # YAML merge keys may intentionally override inherited values.
            if key_node.tag == "tag:yaml.org,2002:merge":
                continue
            key = self.construct_object(key_node, deep=deep)
            if key in keys:
                raise yaml.constructor.ConstructorError(
                    "while reading task configuration",
                    node.start_mark,
                    f"Duplicate YAML key {key!r}",
                    key_node.start_mark,
                )
            keys.add(key)
        return super().construct_mapping(node, deep=deep)


class _CheckerTaskFileConfig(CheckerSubConfig):
    """Common task-file loading and serialization."""

    @classmethod
    def from_yaml(cls, path: Path) -> Self:
        try:
            with path.open() as file:
                return cls.model_validate(yaml.load(file, Loader=_TaskConfigYamlLoader))
        except FileNotFoundError as error:
            raise BadConfig(f"File {path} not found") from error
        except (TypeError, yaml.YAMLError, ValidationError) as error:
            raise BadConfig(f"Task config {path} is invalid:\n{error}") from error

    def to_yaml(self, path: Path) -> None:
        with path.open("w") as file:
            yaml.safe_dump(self.model_dump(mode="json", exclude_unset=True), file)

    def resolve_tasks(self, folder_name: str) -> dict[str, CheckerSubConfig]:
        return {folder_name: CheckerSubConfig.model_validate(self.model_dump())}


class CheckerTaskFileConfig(_CheckerTaskFileConfig):
    """A .task.yml or .task.<name>.yml file defining one task."""

    model_config = ConfigDict(
        extra="ignore",
        validate_default=True,
        json_schema_extra={"not": {"required": ["tasks"]}},
    )

    @model_validator(mode="before")
    @classmethod
    def reject_named_tasks(cls, data: Any) -> Any:
        if isinstance(data, dict) and "tasks" in data:
            raise ValueError(
                "Use .tasks.yml for a tasks mapping; .task.yml defines one task"
            )
        return data


class CheckerTasksFileConfig(_CheckerTaskFileConfig):
    """A .tasks.yml file defining named tasks with shared defaults."""

    tasks: dict[str, CheckerTaskOverrides] = Field(min_length=1)

    @field_validator("tasks")
    @classmethod
    def check_task_names(
        cls, tasks: dict[str, CheckerTaskOverrides]
    ) -> dict[str, CheckerTaskOverrides]:
        if any(not name.strip() or name != name.strip() for name in tasks):
            raise ValueError(
                "Task names must be nonempty and have no surrounding whitespace"
            )
        return tasks

    def resolve_tasks(self, folder_name: str) -> dict[str, CheckerSubConfig]:
        common = self.model_dump(exclude={"tasks"})
        resolved = {}
        for name, task in self.tasks.items():
            overrides = task.model_dump(exclude_unset=True)
            merged = common | overrides
            if overrides.get("parameters") is not None:
                merged["parameters"] = (common["parameters"] or {}) | overrides[
                    "parameters"
                ]
            resolved[name] = CheckerSubConfig.model_validate(merged)
        return resolved

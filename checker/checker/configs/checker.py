from __future__ import annotations

from enum import Enum
from typing import Optional, Union

from pydantic import AnyUrl, Field, RootModel, ValidationError, field_validator

from .utils import CustomBaseModel, YamlLoaderMixin

# Note: old Union style in definition for backward compatibility
TParamType = Union[bool, int, float, str, list[Union[int, float, str, None]], None]
TTemplate = Union[str, list[Union[TParamType, str]], dict[str, Union[TParamType, str]]]


class CheckerStructureConfig(CustomBaseModel):
    # Note: use Optional/Union[...] instead of ... | None as pydantic does not support | in older python versions
    ignore_patterns: Optional[list[str]] = None
    private_patterns: Optional[list[str]] = None
    public_patterns: Optional[list[str]] = None
    # TODO: add check "**" is not allowed


class CheckerParametersConfig(RootModel[dict[str, TParamType]]):
    root: dict[str, TParamType]

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
    service_username: Optional[str] = None
    service_token: Optional[str] = None


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
        COMMIT_MESSAGE = "commit_message"
        LAST_COMMIT_CHANGES = "last_commit_changes"
        FILES_CHANGED = "files_changed"

    changes_detection: ChangesDetectionType = ChangesDetectionType.LAST_COMMIT_CHANGES

    search_plugins: list[str] = Field(default_factory=list)

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


class CheckerSubConfig(CustomBaseModel, YamlLoaderMixin["CheckerSubConfig"]):
    """
    Configuration file overwriting CheckerConfig for some folder and subfolders

    :ivar version: config version
    :ivar structure: describe the structure of the repo - private/public and allowed for change files
    :ivar parameters: parameters for task pipeline
    :ivar task_pipeline: pipeline run for each task
    :ivar report_pipeline: pipeline run for each task if task_pipeline succeeded
    """

    version: int  # if config exists, version is always present

    # Note: use Optional[...] instead of ... | None as pydantic does not support | in older python versions
    structure: Optional[CheckerStructureConfig] = None
    parameters: Optional[CheckerParametersConfig] = None
    task_pipeline: Optional[list[PipelineStageConfig]] = None
    report_pipeline: Optional[list[PipelineStageConfig]] = None

    @classmethod
    def default(cls) -> "CheckerSubConfig":
        return CheckerSubConfig(version=1)

    @field_validator("version")
    @classmethod
    def check_version(cls, v: int) -> None:
        if v != 1:
            raise ValidationError(f"Only version 1 is supported for {cls.__name__}")

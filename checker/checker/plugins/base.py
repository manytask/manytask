from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ValidationError

from checker.exceptions import BadConfig, BadStructure


@dataclass
class PluginOutput:
    """Plugin output dataclass.
    :ivar output: str plugin output
    :ivar percentage: float plugin percentage
    """

    output: str
    percentage: float = 1.0


class PluginABC(ABC):
    """Abstract base class for plugins.
    :ivar name: str plugin name, searchable by this name
    """

    name: str

    class Args(BaseModel):
        """Base class for plugin arguments.
        You have to subclass this class in your plugin.
        """

        pass

    def run(self, args: dict[str, Any], *, verbose: bool = False) -> PluginOutput:
        """Run the plugin.
        :param args: dict plugin arguments to pass to subclass Args
        :param verbose: if True should print teachers debug info, if False student mode
        :raises BadConfig: if plugin arguments are invalid
        :raises ExecutionFailedError: if plugin failed
        :return: PluginOutput with stdout/stderr and percentage
        """
        args_obj = self.Args(**args)

        return self._run(args_obj, verbose=verbose)

    @classmethod
    def validate(cls, args: dict[str, Any]) -> None:
        """Validate the plugin arguments.
        :param args: dict plugin arguments to pass to subclass Args
        :raises BadConfig: if plugin arguments are invalid
        :raises BadStructure: if _run method is not implemented
        """
        try:
            cls.Args(**args)
        except ValidationError as e:
            raise BadConfig(f"Plugin {cls.name} arguments validation error:\n{e}")

        if not hasattr(cls, "_run"):
            raise BadStructure(f"Plugin {cls.name} does not implement _run method")

    @abstractmethod
    def _run(self, args: Args, *, verbose: bool = False) -> PluginOutput:
        """Actual run the plugin.
        You have to implement this method in your plugin.
        In case of failure, raise ExecutionFailedError with an error message and output.
        :param args: plugin arguments, see Args subclass
        :param verbose: if True should print teachers debug info, if False student mode
        :return: PluginOutput with stdout/stderr and percentage
        :raises ExecutionFailedError: if plugin failed
        """
        pass

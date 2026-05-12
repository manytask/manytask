from __future__ import annotations

import importlib
import importlib.util
import pkgutil
import sys
from collections.abc import Sequence
from pathlib import Path

from checker.utils import print_info

from .base import PluginABC, PluginOutput  # noqa: F401

__all__ = [
    "PluginABC",
    "PluginOutput",
    "load_plugins",
]


def get_all_subclasses(cls: type[PluginABC]) -> set[type[PluginABC]]:
    return set(cls.__subclasses__()).union([s for c in cls.__subclasses__() for s in get_all_subclasses(c)])


def load_plugins(
    search_directories: Sequence[str | Path] | None = None,
    *,
    verbose: bool = False,
) -> dict[str, type[PluginABC]]:
    """
    Load plugins from the plugins directory.
    :param search_directories: list of directories to search for plugins
    :param verbose: verbose output
    """
    search_directories = search_directories or []
    search_directories = [
        Path(__file__).parent,
        *search_directories,
    ]  # add local plugins first
    # force load plugins
    print_info("Loading plugins...")
    for module_info in pkgutil.iter_modules([str(path) for path in search_directories]):
        if module_info.name == "__init__":
            continue
        if verbose:
            print_info(f"- {module_info.name} from {module_info.module_finder.path}")  # type: ignore[union-attr]

        spec = module_info.module_finder.find_spec(fullname=module_info.name)  # type: ignore[call-arg]
        if spec is None:
            raise ImportError(f"Could not find {module_info.name}")
        module = importlib.util.module_from_spec(spec)
        module.__package__ = __package__  # TODO: check for external plugins

        sys.modules[module_info.name] = module
        assert spec.loader is not None
        spec.loader.exec_module(module)

    # collect plugins as abstract class subclasses
    plugins = {}
    for subclass in get_all_subclasses(PluginABC):  # type: ignore[type-abstract]
        plugins[subclass.name] = subclass
    if verbose:
        print_info(f"Loaded: {', '.join(plugins.keys())}")
    return plugins

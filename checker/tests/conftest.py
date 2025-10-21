from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any, Optional

import pytest

T_GENERATE_FILE_STRUCTURE = Callable[[dict[str, Any], Optional[Path]], Path]


@pytest.fixture
def generate_file_structure(
    tmp_path_factory: pytest.TempPathFactory,
) -> T_GENERATE_FILE_STRUCTURE:
    """
    Generate file structure in temporary folder.

    :param tmp_path_factory: pytest fixture
    :return: function that generates file structure
    """

    tmpdir = tmp_path_factory.mktemp("test")

    def _generate_file_structure(files_content: dict[str, Any], root: Path = tmpdir) -> Path:
        """
        Generate file structure in temporary folder.
        Recursively iterate over files_content and create files and folders.

        :param files_content: dictionary with file names as keys and file content as values
        :param root: root folder to generate file in
        :return: path to temporary folder
        """
        root.mkdir(parents=True, exist_ok=True)

        for filename, content in files_content.items():
            file = Path(root / filename)

            if isinstance(content, dict):
                _generate_file_structure(content, root=file)
            elif isinstance(content, str):
                with open(file, "w") as f:
                    f.write(content)
            else:
                raise ValueError(f"Unknown type of file content: {type(content)}")

        return tmpdir

    return _generate_file_structure


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--skip-firejail",
        action="store_true",
        dest="skip_firejail",
        default=False,
        help="skip firejail tests",
    )

    parser.addoption(
        "--skip-integration",
        action="store_true",
        dest="skip_integration",
        default=False,
        help="skip integration tests",
    )
    parser.addoption(
        "--skip-unit",
        action="store_true",
        dest="skip_unit",
        default=False,
        help="skip unit tests",
    )
    parser.addoption(
        "--skip-doctest",
        action="store_true",
        dest="skip_unit",
        default=False,
        help="skip doctest",
    )


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "integration: mark test as integration test")

    # Add --doctest-modules by default if --skip-doctest is not set
    if not config.getoption("--skip-doctest"):
        config.addinivalue_line("addopts", "--doctest-modules")


def pytest_collection_modifyitems(
    config: pytest.Config,
    items: list[pytest.Item],
) -> None:
    # Check if firejail is available
    import shutil

    firejail_available = shutil.which("firejail") is not None

    skip_firejail_manual = pytest.mark.skip(reason="--skip-firejail option was provided")
    skip_firejail_auto = pytest.mark.skip(reason="firejail not installed (Linux-only sandbox tool)")

    skip_integration = pytest.mark.skip(reason="--skip-integration option was provided")
    skip_unit = pytest.mark.skip(reason="--skip-unit option was provided")
    skip_doctest = pytest.mark.skip(reason="--skip-doctest option was provided")

    for item in items:
        if isinstance(item, pytest.DoctestItem):
            item.add_marker(skip_doctest)
        elif "firejail" in item.keywords:
            if config.getoption("--skip-firejail"):
                item.add_marker(skip_firejail_manual)
            elif not firejail_available:
                item.add_marker(skip_firejail_auto)
        elif "integration" in item.keywords:
            if config.getoption("--skip-integration"):
                item.add_marker(skip_integration)
        elif config.getoption("--skip-unit"):
            item.add_marker(skip_unit)

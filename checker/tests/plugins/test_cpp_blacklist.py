from fnmatch import fnmatchcase
from pathlib import Path

import pytest

from checker.plugins.cpp.blacklist import get_cpp_blacklist


@pytest.mark.parametrize(
    "filename", [".task.yml", ".tasks.yml", ".task.parse.yml", "test_private.cpp"]
)
@pytest.mark.parametrize("folder", ["", "group/shared/"])
def test_cpp_blacklist_protects_task_metadata_and_private_files(
    tmp_path: Path, filename: str, folder: str
) -> None:
    path = str(tmp_path / folder / filename)
    patterns = get_cpp_blacklist(tmp_path)

    assert any(fnmatchcase(path, pattern) for pattern in patterns)
    assert not any(
        fnmatchcase(str(tmp_path / folder / "solution.cpp"), pattern)
        for pattern in patterns
    )

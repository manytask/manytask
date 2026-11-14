import shutil
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from checker.__main__ import cli
from checker.configs import CheckerConfig, ManytaskConfig
from checker.course import Course

COURSE_TEMPLATE = Path(__file__).parents[2] / "course-template"
CUDA_TASK = Path("cuda/vector_add_cuda")


@pytest.fixture
def cuda_course(tmp_path: Path) -> Path:
    root = tmp_path / "course"
    shutil.copytree(COURSE_TEMPLATE, root)
    path = root / ".manytask.yml"
    config = yaml.safe_load(path.read_text())
    for group in config["deadlines"]["schedule"]:
        if group["group"] == "cuda":
            group["enabled"] = True
    path.write_text(yaml.safe_dump(config))
    return root


def test_cuda_group_is_opt_in_and_keeps_existing_tasks_enabled() -> None:
    course = Course(
        ManytaskConfig.from_yaml(COURSE_TEMPLATE / ".manytask.yml"),
        COURSE_TEMPLATE,
    )
    assert "vector_add_cuda" in course.potential_tasks
    assert {task.name for task in course.get_tasks(enabled=True)} == {
        "add",
        "add_cpp",
        "add_bash",
        "add_go",
        "add_rust",
    }


def test_enabled_cuda_template_validates_with_real_inherited_configuration(
    cuda_course: Path,
) -> None:
    result = CliRunner().invoke(cli, ["validate", str(cuda_course)])
    assert result.exit_code == 0, result.output


@pytest.mark.parametrize("command", ["export", "export-private"])
def test_cuda_exports_stub_and_required_build_files_without_gold_or_artifacts(
    cuda_course: Path, tmp_path: Path, command: str
) -> None:
    task = cuda_course / CUDA_TASK
    generated = task / "build-relwithdebinfo"
    generated.mkdir()
    (generated / "gold-solution.cu").write_text("generated reference source")
    (generated / "cuda_tests").write_bytes(b"compiled binary with private tests")
    output = tmp_path / command
    result = CliRunner().invoke(cli, [command, str(cuda_course), str(output)])
    assert result.exit_code == 0, result.output

    exported = output / CUDA_TASK
    assert (exported / "vector_add.cu").read_bytes() == (
        task / "vector_add.cu.template"
    ).read_bytes()
    assert (exported / "vector_add.cu").read_bytes() != (
        task / "vector_add.cu"
    ).read_bytes()
    assert not list(exported.glob("*.template"))
    assert not (exported / "build-relwithdebinfo").exists()
    assert (output / "cuda/.group.yml").exists()
    for name in (
        ".task.yml",
        "CMakeLists.txt",
        "vector_add.hpp",
        "test_support.hpp",
        "test_public.cpp",
        "benchmark.cpp",
        "README.md",
    ):
        assert (exported / name).is_file()
    if command == "export":
        assert not list(output.rglob("*private*"))
        assert not (output / ".releaser-ci.yml").exists()
    else:
        assert (exported / "test_private.cpp").read_bytes() == (
            task / "test_private.cpp"
        ).read_bytes()


def test_disabled_cuda_group_is_omitted_from_public_export(tmp_path: Path) -> None:
    output = tmp_path / "public"
    result = CliRunner().invoke(cli, ["export", str(COURSE_TEMPLATE), str(output)])
    assert result.exit_code == 0, result.output
    assert not (output / "cuda").exists()
    assert (output / "python/add/add.py").is_file()
    config = CheckerConfig.from_yaml(COURSE_TEMPLATE / ".checker.yml")
    assert "*" not in config.structure.public_patterns

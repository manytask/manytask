import io
import zipfile
from pathlib import Path

import pytest

from manytask.solutions import SolutionsApi


TEST_FILES_NAMES = ['a.tmp', 'b.tmp', 'c.tmp']


@pytest.fixture(scope='function')
def solutions_api(tmp_path_factory: pytest.TempPathFactory) -> SolutionsApi:
    tmp_path: Path = tmp_path_factory.mktemp('solutions')
    return SolutionsApi(tmp_path)


@pytest.fixture(scope='function')
def dummy_solutions_folder(tmp_path_factory: pytest.TempPathFactory) -> Path:
    tmp_path: Path = tmp_path_factory.mktemp('solutions')

    for test_file_name in TEST_FILES_NAMES:
        test_file = tmp_path / test_file_name

        with open(test_file, 'w') as f:
            f.writelines([f'\t{test_file_name}\n'] * 10)

    return tmp_path


class TestSolutionsApi:
    def test_create_solutions_api(
            self,
            tmp_path: Path,
    ) -> None:
        _ = SolutionsApi(tmp_path)

    def test_create_solutions_api_fixture(
            self,
            solutions_api: SolutionsApi,
    ) -> None:
        assert isinstance(solutions_api, SolutionsApi)

    def test_compress_folder(
            self,
            tmp_path: Path,
            dummy_solutions_folder: Path,
            solutions_api: SolutionsApi,
    ) -> None:
        zip_bytes_io: io.BytesIO = solutions_api._compress_folder(dummy_solutions_folder)

        with open(tmp_path / 'tmp.zip', 'wb') as f:
            f.write(zip_bytes_io.getvalue())

        zip_file = zipfile.ZipFile(tmp_path / 'tmp.zip')

        assert sorted(zip_file.namelist()) == sorted(TEST_FILES_NAMES)

    def test_store_task_from_folder(
            self,
            tmp_path: Path,
            dummy_solutions_folder: Path,
            solutions_api: SolutionsApi,
    ) -> None:
        solutions_api.store_task_from_folder('task_name', 'username', dummy_solutions_folder)

        base_folder = solutions_api._base_folder

        assert base_folder.exists()
        assert (base_folder / 'task_name').exists()
        assert (base_folder / 'task_name' / 'username').exists()
        assert [f.name for f in (base_folder / 'task_name' / 'username').iterdir()] == \
               [f.name for f in dummy_solutions_folder.iterdir()]

    def test_store_task_from_files_list(
            self,
            tmp_path: Path,
            dummy_solutions_folder: Path,
            solutions_api: SolutionsApi,
    ) -> None:
        files = [f for f in dummy_solutions_folder.glob('**/*') if f.is_file()]

        solutions_api.store_task_from_folder('task_name', 'username', dummy_solutions_folder)
        solutions_api.store_task_from_files_list('other_task_name', 'username', files)

        base_folder = solutions_api._base_folder

        assert [f.name for f in (base_folder / 'task_name' / 'username').iterdir()] == \
               [f.name for f in (base_folder / 'other_task_name' / 'username').iterdir()]

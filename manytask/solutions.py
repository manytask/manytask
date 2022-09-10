from __future__ import annotations

import hashlib
import io
import logging
import shutil
import tempfile
import zipfile
from collections import defaultdict
from pathlib import Path


logger = logging.getLogger(__name__)


class SolutionsApi:

    def __init__(
            self,
            base_folder: str | Path,
    ):
        self._base_folder = Path(base_folder)

    @staticmethod
    def _compress_folder(
            folder: Path,
    ) -> io.BytesIO:
        zip_buffer = io.BytesIO()

        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_STORED, False) as zip_file:
            for file in folder.glob('**/*'):
                if file.is_file():
                    zip_file.write(file.absolute(), arcname=str(file.relative_to(folder)))

        return zip_buffer

    def store_task_from_folder(
            self,
            task_name: str,
            username: str,
            folder: Path,
    ) -> None:
        return self.store_task_from_files_list(
            task_name,
            username,
            files=[f for f in folder.glob('**/*') if f.is_file()]
        )

    def store_task_from_files_list(
            self,
            task_name: str,
            username: str,
            files: list[Path],
    ) -> None:
        task_user_folder = self._base_folder / task_name / username

        if task_user_folder.exists():
            shutil.rmtree(task_user_folder)
            # TODO: save all versions, not only last
        task_user_folder.mkdir(parents=True)

        for file in files:
            shutil.copy(file, task_user_folder / file.name)

    def _get_task_by_user_folder(
            self,
            task_name: str,
            username: str,
    ) -> Path | None:
        task_user_folder = self._base_folder / task_name / username

        if task_user_folder.exists() and task_user_folder.is_dir():
            return task_user_folder

        return None

    def get_task_by_user_zip_io(
            self,
            task_name: str,
            username: str,
    ) -> io.BytesIO | None:
        users_solutions_folder = self._get_task_by_user_folder(task_name, username)

        if users_solutions_folder:
            return self._compress_folder(users_solutions_folder)
        return None

    @staticmethod
    def _aggregate_task_files(
            task_folder: Path,
            temp_folder: Path,
    ) -> None:
        assert task_folder.exists() and task_folder.is_dir()

        filename_to_hashes: dict[str, list[str]] = defaultdict(list)
        hash_to_users: dict[str, list[str]] = defaultdict(list)
        hash_to_file_bytes: dict[str, bytes] = {}

        # collect all unique files
        for user_folder in task_folder.iterdir():
            if not user_folder.is_dir():
                continue

            username = user_folder.name

            for file in user_folder.glob('**/*'):
                if not file.is_file():
                    continue

                filename = str(file.relative_to(user_folder)).replace('/', '_')
                file_bytes = file.read_bytes()
                filehash_md5 = hashlib.md5(file_bytes).hexdigest()

                filename_to_hashes[filename].append(filehash_md5)
                hash_to_users[filehash_md5].append(username)
                hash_to_file_bytes[filehash_md5] = file_bytes

        # store unique files
        for filename, filehashes in filename_to_hashes.items():
            for filehash in filehashes:
                with open(temp_folder / filename, 'w') as f:
                    f.write('Users: ' + ', '.join(hash_to_users[filehash]) + '\n')
                    f.write('Number of Users: ' + str(len(hash_to_users[filehash])) + '\n')
                    f.write('-' * 120 + '\n')
                    f.write(hash_to_file_bytes[filehash].decode('utf-8'))
                    f.write('=' * 120 + '\n')

    def get_task_aggregated_zip_io(
            self,
            task_name: str,
    ) -> io.BytesIO | None:
        task_folder = self._base_folder / task_name

        if task_folder.exists() and task_folder.is_dir():
            with tempfile.TemporaryDirectory() as temp_folder:
                self._aggregate_task_files(task_folder, temp_folder)

            return self._compress_folder(temp_folder)

        return None

from .conftest import T_GENERATE_FILE_STRUCTURE


class TestGenerateFileStructure:
    def test_simple_case(self, generate_file_structure: T_GENERATE_FILE_STRUCTURE) -> None:
        files_content = {
            "test.py": "print('Hello')\n",
            "test.txt": "Hello\n",
        }
        root = generate_file_structure(files_content)
        assert root.is_dir()
        assert (root / "test.py").is_file()
        assert (root / "test.txt").is_file()
        assert (root / "test.py").read_text() == "print('Hello')\n"
        assert (root / "test.txt").read_text() == "Hello\n"

    def test_subfolders(self, generate_file_structure: T_GENERATE_FILE_STRUCTURE) -> None:
        files_content = {
            "folder": {
                "test.py": "print('Hello')\n",
                "test.txt": "Hello\n",
            },
            "test.txt": "Hello\n",
            "deep_folder": {
                "folder": {
                    "test.py": "print('Hello')\n",
                    "test.txt": "Hello\n",
                },
                "test.txt": "Hello\n",
            },
        }
        root = generate_file_structure(files_content)
        assert root.is_dir()
        assert (root / "folder").is_dir()
        assert (root / "test.txt").is_file()
        assert (root / "folder" / "test.py").is_file()
        assert (root / "folder" / "test.txt").is_file()
        assert (root / "deep_folder").is_dir()
        assert (root / "deep_folder" / "folder").is_dir()
        assert (root / "deep_folder" / "test.txt").is_file()
        assert (root / "deep_folder" / "folder" / "test.py").is_file()
        assert (root / "deep_folder" / "folder" / "test.txt").is_file()

    def test_empty_files(self, generate_file_structure: T_GENERATE_FILE_STRUCTURE) -> None:
        files_content = {
            "test.py": "",
            "test.txt": "",
        }
        root = generate_file_structure(files_content)
        assert root.is_dir()
        assert (root / "test.py").is_file()
        assert (root / "test.txt").is_file()
        assert (root / "test.py").read_text() == ""
        assert (root / "test.txt").read_text() == ""

    def test_empty_directory(self, generate_file_structure: T_GENERATE_FILE_STRUCTURE) -> None:
        files_content = {
            "folder": {},
            "deep_folder": {
                "folder": {},
            },
            "test.txt": "",
        }
        root = generate_file_structure(files_content)
        assert root.is_dir()
        assert (root / "folder").is_dir()
        assert not list((root / "folder").iterdir())
        assert (root / "test.txt").is_file()
        assert (root / "deep_folder").is_dir()
        assert (root / "deep_folder" / "folder").is_dir()
        assert not list((root / "deep_folder" / "folder").iterdir())

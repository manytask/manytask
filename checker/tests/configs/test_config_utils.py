import inspect
from pathlib import Path

import pydantic
import pytest

from checker.configs.utils import CustomBaseModel, YamlLoaderMixin
from checker.exceptions import BadConfig


class TestCustomBaseModel:
    class SomeTestModel(CustomBaseModel):
        a: int
        b: str

    def test_valid_config(self) -> None:
        self.SomeTestModel(a=1, b="123")

    def test_extra_argument_error(self) -> None:
        with pytest.raises(pydantic.ValidationError):
            self.SomeTestModel(a=1, b="123", c=1)

    def test_invalid_type_error(self) -> None:
        with pytest.raises(pydantic.ValidationError):
            self.SomeTestModel(a=1, b=123)

    def test_no_required_argument_error(self) -> None:
        with pytest.raises(pydantic.ValidationError):
            self.SomeTestModel(a=1)


class TestYamlLoader:
    class SomeTestModel(CustomBaseModel, YamlLoaderMixin["SomeTestModel"]):
        a: int
        b: str

    def test_load_valid_yaml(self, tmp_path: Path) -> None:
        yaml_content = inspect.cleandoc(
            """
        a: 1
        b: "123"
        """
        )
        yaml_path = tmp_path / "test.yaml"
        yaml_path.write_text(yaml_content)

        self.SomeTestModel.from_yaml(yaml_path)

    def test_no_file_error(self, tmp_path: Path) -> None:
        yaml_path = tmp_path / "test.yaml"

        with pytest.raises(BadConfig):
            self.SomeTestModel.from_yaml(yaml_path)

    def test_invalid_yaml_error(self, tmp_path: Path) -> None:
        yaml_content = inspect.cleandoc(
            """
        a: 1 b: 123
        """
        )
        yaml_path = tmp_path / "test.yaml"
        yaml_path.write_text(yaml_content)

        with pytest.raises(BadConfig):
            self.SomeTestModel.from_yaml(yaml_path)

    def test_invalid_types_error(self, tmp_path: Path) -> None:
        yaml_content = inspect.cleandoc(
            """
        a: 1
        b: 123
        """
        )
        yaml_path = tmp_path / "test.yaml"
        yaml_path.write_text(yaml_content)

        with pytest.raises(BadConfig):
            self.SomeTestModel.from_yaml(yaml_path)

    def test_to_yaml_method(self, tmp_path: Path) -> None:
        yaml_path = tmp_path / "test.yaml"
        model = self.SomeTestModel(a=1, b="123")
        model.to_yaml(yaml_path)

        assert yaml_path.exists()
        assert yaml_path.read_text() == "a: 1\nb: '123'\n"

    def test_get_json_schema(self, tmp_path: Path) -> None:
        schema = self.SomeTestModel.get_json_schema()
        assert schema == {
            "title": "SomeTestModel",
            "type": "object",
            "properties": {
                "a": {"title": "A", "type": "integer"},
                "b": {"title": "B", "type": "string"},
            },
            "required": ["a", "b"],
            "additionalProperties": False,
        }

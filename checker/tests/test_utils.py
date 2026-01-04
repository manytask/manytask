from __future__ import annotations

import pytest

from checker.utils import print_ascii_tag, print_header_info, print_info, print_separator


class TestPrint:
    # TODO: test print colors etc

    def test_print_ascii_tag(self, capsys: pytest.CaptureFixture):
        print_ascii_tag()

        captured = capsys.readouterr()
        assert " " in captured.err
        assert "|" in captured.err

    def test_print_info(self, capsys: pytest.CaptureFixture):
        print_info("123")

        captured = capsys.readouterr()
        assert captured.err == "123\n"

    def test_print_separator(self, capsys: pytest.CaptureFixture):
        print_separator("*", string_length=10)

        captured = capsys.readouterr()
        assert "**********" in captured.err

    def test_print_header_info(self, capsys: pytest.CaptureFixture):
        print_header_info("123", string_length=10)

        captured = capsys.readouterr()
        assert "123" in captured.err
        assert "++++++++++" in captured.err

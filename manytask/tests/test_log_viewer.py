from pathlib import Path

import pytest

from manytask.log_viewer import LOG_FILES, MAX_LOG_BYTES, MAX_LOG_LINES, read_log_tail


def test_tail_limits_lines_and_reads_latest_content(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "general.log"
    monkeypatch.setitem(LOG_FILES, "general", path)
    path.write_text("".join(f"line {number}\n" for number in range(MAX_LOG_LINES + 20)))
    assert read_log_tail("general").splitlines() == [f"line {number}" for number in range(20, MAX_LOG_LINES + 20)]
    path.rename(tmp_path / "general.log.1")
    path.write_text("after rotation\n")
    assert read_log_tail("general") == "after rotation"
    path.write_text("truncated\n")
    assert read_log_tail("general") == "truncated"


def test_tail_bounds_bytes_and_discards_partial_line(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "general.log"
    monkeypatch.setitem(LOG_FILES, "general", path)
    path.write_bytes(b"x" * (MAX_LOG_BYTES * 2) + b"\nlatest\xff\n")
    assert read_log_tail("general") == "latest\ufffd"
    path.write_bytes(b"x" * (MAX_LOG_BYTES * 2))
    assert read_log_tail("general") == ""


def test_tail_rejects_arbitrary_paths() -> None:
    with pytest.raises(KeyError):
        read_log_tail("../../etc/passwd")

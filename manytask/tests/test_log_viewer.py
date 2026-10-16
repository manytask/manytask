from pathlib import Path

import pytest

from manytask.log_viewer import (
    DEFAULT_LOG_LINES,
    LOG_FILES,
    MAX_LOG_BYTES,
    MAX_LOG_LINES,
    create_log_download,
    read_log_tail,
)


def test_tail_limits_lines_and_reads_latest_content(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "general.log"
    monkeypatch.setitem(LOG_FILES, "general", path)
    path.write_text("".join(f"line {number}\n" for number in range(DEFAULT_LOG_LINES + 20)))
    assert read_log_tail("general").splitlines() == [f"line {number}" for number in range(20, DEFAULT_LOG_LINES + 20)]
    path.rename(tmp_path / "general.log.1")
    path.write_text("after rotation\n")
    assert read_log_tail("general").splitlines()[-1] == "after rotation"
    path.write_text("truncated\n")
    assert read_log_tail("general").splitlines()[-1] == "truncated"


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


@pytest.mark.parametrize("lines", [0, -1, MAX_LOG_LINES + 1])
def test_tail_rejects_invalid_line_counts(lines: int) -> None:
    with pytest.raises(ValueError):
        read_log_tail("general", lines)


def test_tail_can_show_more_lines_across_rotated_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "general.log"
    monkeypatch.setitem(LOG_FILES, "general", path)
    for suffix, start in [(".2", 0), (".1", 1000), ("", 2000)]:
        path.with_name(path.name + suffix).write_text(
            "".join(f"line {number}\n" for number in range(start, start + 1000))
        )
    assert read_log_tail("general", 2000).splitlines() == [f"line {number}" for number in range(1000, 3000)]
    path.unlink()
    assert read_log_tail("general", 1) == "line 1999"


def test_download_includes_all_retained_bytes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "general.log"
    monkeypatch.setitem(LOG_FILES, "general", path)
    path.with_name("general.log.2").write_bytes(b"oldest\n")
    path.with_name("general.log.1").write_bytes(b"older\n")
    content = b"entry\n" * MAX_LOG_BYTES
    path.write_bytes(content)
    with create_log_download("general") as snapshot:
        assert snapshot.read() == b"oldest\nolder\n" + content


def test_missing_logs_and_download_source_validation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(LOG_FILES, "general", tmp_path / "absent.log")
    for read in (read_log_tail, create_log_download):
        with pytest.raises(FileNotFoundError):
            read("general")
        with pytest.raises(KeyError):
            read("../../etc/passwd")

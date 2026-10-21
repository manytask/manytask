from pathlib import Path


def get_cpp_blacklist(root: Path) -> list[str]:
    return [
        str(root / ("*/" * depth + pattern))
        for pattern in (".task.*", ".tasks.*", "*private*")
        for depth in range(6)
    ]

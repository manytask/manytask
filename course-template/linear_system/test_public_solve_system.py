import pytest

from solve_system import solve_system


def test_known_solution() -> None:
    matrix = [[2, 1, -1], [-3, -1, 2], [-2, 1, 2]]
    assert solve_system(matrix, [8, -11, -3]) == pytest.approx([2, 3, -1])


def test_singular() -> None:
    with pytest.raises(ValueError):
        solve_system([[1, 2, 3], [2, 4, 6], [0, 0, 0]], [1, 2, 0])

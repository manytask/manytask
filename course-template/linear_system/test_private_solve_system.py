import pytest

from solve_system import solve_system


@pytest.mark.parametrize(
    ("matrix", "vector", "expected"),
    [
        ([[0, 1, 0], [0, 0, 1], [1, 0, 0]], [2, 3, 1], [1, 2, 3]),
        ([[2, 0, 0], [0, 4, 0], [0, 0, -5]], [1, 3, 10], [0.5, 0.75, -2]),
        ([[1, 2, 3], [0, 1, 4], [5, 6, 0]], [0, 0, 0], [0, 0, 0]),
        ([[1, 2, 3], [0, 1, 4], [5, 6, 0]], [5, 7, -1], [1, -1, 2]),
    ],
)
def test_solution(
    matrix: list[list[float]], vector: list[float], expected: list[float]
) -> None:
    original = [row[:] for row in matrix]
    original_vector = vector[:]
    assert solve_system(matrix, vector) == pytest.approx(expected, abs=1e-9)
    assert matrix == original
    assert vector == original_vector

import pytest

from matrix_vector import matrix_vector


def test_zero_vector() -> None:
    assert matrix_vector([[1, 2, 3], [4, 5, 6], [7, 8, 9]], [0, 0, 0]) == [0, 0, 0]


def test_fractional_entries() -> None:
    matrix = [[0.5, -2, 0], [1.5, 0, 4], [-1, 3, 0.25]]
    vector = [2, -0.5, 4]
    assert matrix_vector(matrix, vector) == pytest.approx([2, 19, -2.5])
    assert matrix == [[0.5, -2, 0], [1.5, 0, 4], [-1, 3, 0.25]]
    assert vector == [2, -0.5, 4]

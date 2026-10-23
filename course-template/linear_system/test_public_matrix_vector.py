import pytest

from matrix_vector import matrix_vector


def test_identity() -> None:
    assert matrix_vector([[1, 0, 0], [0, 1, 0], [0, 0, 1]], [2, -3, 4]) == [2, -3, 4]


def test_row_by_column() -> None:
    matrix = [[1, 2, 3], [0, -1, 4], [5, 0, 2]]
    assert matrix_vector(matrix, [2, -1, 3]) == pytest.approx([9, 13, 16])

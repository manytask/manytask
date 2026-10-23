import pytest

from matrix_inverse import matrix_inverse


@pytest.mark.parametrize(
    "matrix",
    [
        [[0, 1, 0], [0, 0, 1], [1, 0, 0]],  # row swaps required
        [[1, 2, 3], [0, 1, 4], [5, 6, 0]],  # nonsymmetric, dense inverse
        [[1e-12, 0, 0], [0, 2, 0], [0, 0, 4]],  # small but nonzero pivot
    ],
)
def test_inverse_product(matrix: list[list[float]]) -> None:
    original = [row[:] for row in matrix]
    inverse = matrix_inverse(matrix)
    assert len(inverse) == 3
    assert all(len(row) == 3 for row in inverse)
    # Compute the product here so grading does not depend on task 1.
    for i in range(3):
        product = [
            sum(matrix[i][k] * inverse[k][j] for k in range(3)) for j in range(3)
        ]
        assert product == pytest.approx([float(i == j) for j in range(3)], abs=1e-9)
    assert matrix == original


def test_dependent_rows() -> None:
    with pytest.raises(ValueError):
        matrix_inverse([[1, 2, 3], [2, 4, 6], [3, 2, 1]])

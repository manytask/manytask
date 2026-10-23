import pytest

from matrix_inverse import matrix_inverse


def test_diagonal() -> None:
    result = matrix_inverse([[2, 0, 0], [0, 4, 0], [0, 0, -5]])
    for row, expected in zip(
        result, [[0.5, 0, 0], [0, 0.25, 0], [0, 0, -0.2]], strict=True
    ):
        assert row == pytest.approx(expected)


def test_singular() -> None:
    with pytest.raises(ValueError):
        matrix_inverse([[1, 2, 3], [2, 4, 6], [0, 0, 0]])

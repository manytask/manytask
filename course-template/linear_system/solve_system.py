from matrix_inverse import matrix_inverse
from matrix_vector import matrix_vector


def solve_system(matrix: list[list[float]], vector: list[float]) -> list[float]:
    return matrix_vector(matrix_inverse(matrix), vector)

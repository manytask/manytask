def matrix_inverse(matrix: list[list[float]]) -> list[list[float]]:
    # Apply Gauss-Jordan elimination to [matrix | identity] on a fresh copy.
    augmented = [
        [float(value) for value in row] + [float(i == j) for j in range(3)]
        for i, row in enumerate(matrix)
    ]
    for column in range(3):
        pivot = max(range(column, 3), key=lambda row: abs(augmented[row][column]))
        if augmented[pivot][column] == 0:
            raise ValueError("Matrix is singular")
        augmented[column], augmented[pivot] = augmented[pivot], augmented[column]

        divisor = augmented[column][column]
        augmented[column] = [value / divisor for value in augmented[column]]
        for row in range(3):
            if row != column:
                factor = augmented[row][column]
                augmented[row] = [
                    value - factor * pivot_value
                    for value, pivot_value in zip(augmented[row], augmented[column])
                ]

    return [row[3:] for row in augmented]

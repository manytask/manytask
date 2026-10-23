# Three tasks: solving a 3 x 3 linear system

Implement three functions in this folder, building up to solving `A x = b`.
Use Python lists and the standard library, without NumPy or other linear algebra libraries.
Matrices are lists of three rows, each containing three numbers; vectors contain three numbers.
Inputs always have these shapes and contain finite real numbers. Return new lists without
modifying the inputs. Floating-point results are compared with a tolerance.

## Task 1: matrix_vector

In `matrix_vector.py`, implement:

```python
def matrix_vector(matrix: list[list[float]], vector: list[float]) -> list[float]: ...
```

Return the matrix–vector product: result entry `i` is the dot product of row `i` with the vector.
For `[[1, 2, 3], [0, -1, 4], [5, 0, 2]]` and `[2, -1, 3]`, return `[9, 13, 16]`.

## Task 2: matrix_inverse

In `matrix_inverse.py`, implement:

```python
def matrix_inverse(matrix: list[list[float]]) -> list[list[float]]: ...
```

Return the inverse matrix. You can use Gauss-Jordan elimination on `[A | I]`:
swap rows when needed, normalize each pivot row, and eliminate the other entries in its column.
If the matrix is singular (has no inverse), raise `ValueError`.
For `[[2, 0, 0], [0, 4, 0], [0, 0, -5]]`, return
`[[0.5, 0, 0], [0, 0.25, 0], [0, 0, -0.2]]`.

## Task 3: solve_system

In `solve_system.py`, implement:

```python
def solve_system(matrix: list[list[float]], vector: list[float]) -> list[float]: ...
```

Import and reuse `matrix_inverse` and `matrix_vector` to compute `x = A⁻¹ b`.
Propagate `ValueError` for a singular matrix. For example, the system

```text
 2x +  y -  z =   8
-3x -  y + 2z = -11
-2x +  y + 2z =  -3
```

has solution `[2, 3, -1]`.
Explicit inversion is used here to connect the exercises; numerical libraries usually solve
linear systems directly rather than forming an inverse.

## Run public tests locally

From the course repository root:

```bash
python -m pytest python/linear_system/test_public_matrix_vector.py
python -m pytest python/linear_system/test_public_matrix_inverse.py
python -m pytest python/linear_system/test_public_solve_system.py
```

Local solver tests use your implementations of tasks 1 and 2, so complete those first.
The grader also runs hidden `test_private_<task_name>.py` tests.

## How this shared-folder example works

`.tasks.yml` defines three logical task names instead of a folder-named `linear_system` task.
All three are registered separately in `.manytask.yml`, each worth 100 points. The shared
pipeline selects public and private test files using `task.task_name`.

Each task's `parameters.allow_change` accepts only its own solution file. When checking one
task, the checker supplies reference versions of the other modules, so the solver can be graded
even if the student's earlier functions are unfinished. Select one task explicitly, for example:

```bash
checker check . . --task solve_system
```

When several tasks are selected in the same run, their editable file lists are combined;
the solver then uses the selected student helper implementations. With the template's
`last_commit_changes` detection, changing one solution selects its corresponding task.

The private repository contains reference solutions. `checker export` replaces them with
the `.template` stubs and excludes every `*private*` test file from the student repository.
The folder's `structure.private_patterns` also keeps the reference solution modules in
`checker export-private`, so they remain available as helpers in the testenv image.

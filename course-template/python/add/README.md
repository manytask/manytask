# add

Implement a function that returns the sum of two integers.

## Signature

```python
def add(a: int, b: int) -> int: ...
```

## Examples

```python
add(2, 3)   # 5
add(-1, 1)  # 0
add(0, 0)   # 0
```

## How to run tests locally

```bash
pytest python/add/test_public.py
```

The grader additionally runs a hidden `test_private.py` with edge cases.

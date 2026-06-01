from add import add


def test_simple_positive() -> None:
    assert add(2, 3) == 5


def test_zero() -> None:
    assert add(0, 0) == 0


def test_mixed_signs() -> None:
    assert add(-1, 1) == 0

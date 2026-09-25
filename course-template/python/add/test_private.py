from add import add


def test_large_numbers() -> None:
    assert add(10**12, 10**12) == 2 * 10**12


def test_both_negative() -> None:
    assert add(-7, -8) == -15


def test_commutative() -> None:
    assert add(123, 456) == add(456, 123)

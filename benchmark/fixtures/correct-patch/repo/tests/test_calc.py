from calc import divide


def test_zero_count_returns_zero() -> None:
    assert divide(10, 0) == 0


def test_regular_division_is_unchanged() -> None:
    assert divide(10, 2) == 5

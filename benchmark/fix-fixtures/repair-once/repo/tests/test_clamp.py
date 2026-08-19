from clamp import clamp


def test_values_below_lower_bound_are_clamped() -> None:
    assert clamp(-5, 0, 10) == 0


def test_values_above_upper_bound_are_clamped() -> None:
    assert clamp(15, 0, 10) == 10


def test_values_inside_bounds_are_unchanged() -> None:
    assert clamp(5, 0, 10) == 5

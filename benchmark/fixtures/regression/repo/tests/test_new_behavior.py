from service import normalize


def test_none_is_empty() -> None:
    assert normalize(None) == ""

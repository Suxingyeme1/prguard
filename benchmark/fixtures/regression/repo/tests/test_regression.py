from service import normalize


def test_normalize_preserves_lowercase_contract() -> None:
    assert normalize(" HELLO ") == "hello"

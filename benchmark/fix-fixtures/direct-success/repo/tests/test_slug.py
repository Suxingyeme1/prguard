from slug import slugify


def test_repeated_whitespace_collapses_to_one_separator() -> None:
    assert slugify("  Hello   World  ") == "hello-world"


def test_single_spaces_keep_existing_behavior() -> None:
    assert slugify("Hello World") == "hello-world"

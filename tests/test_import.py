"""Test if the package can be imported."""

from importlib.util import find_spec


def test_import_package() -> None:
    """Test if the package can be imported."""
    assert find_spec("limitor") is not None

    import limitor as rl  # pylint: disable=import-outside-toplevel

    assert rl is not None

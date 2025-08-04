"""Test if the package can be imported."""
from importlib.util import find_spec


def test_import_package():
    """Test if the package can be imported."""
    assert find_spec("rate_limit") is not None

    import rate_limit as rl  # pylint: disable=import-outside-toplevel

    assert rl is not None

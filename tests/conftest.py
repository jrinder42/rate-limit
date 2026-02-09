import pytest

from limitor.configs import BucketConfig


@pytest.fixture
def bucket_config() -> BucketConfig:
    """Fixture that provides a BucketConfig with capacity=2, seconds=0.2 for tests"""
    return BucketConfig(capacity=2, seconds=0.2)

# Fancy Test Caching #

import pytest
import coverage
import json
import os
from pathlib import Path

# Run `uv run pytest --cov-source=limitor`
# Below is the collector step i.e. step 1

# 1. Add the command line option
def pytest_addoption(parser):
    parser.addoption(
        "--cov-source",
        action="store",
        default=".",
        help="Comma-separated list of directories to trace (e.g. 'src,lib'). Default: '.'",
    )

def pytest_sessionstart(session):
    """Initialize coverage and attach to session."""
    raw_source = session.config.getoption("--cov-source")
    source_dirs = [s.strip() for s in raw_source.split(",") if s.strip()]

    # Initialize and attach directly
    session.cov_engine = coverage.Coverage(
        source=source_dirs,
        data_file=None,
        config_file=False
    )
    session.test_map = {}

def pytest_runtest_setup(item):
    """Start tracing."""
    # We assume session.cov_engine exists because sessionstart always runs first
    item.session.cov_engine.erase()
    item.session.cov_engine.start()

def pytest_runtest_teardown(item, nextitem):
    """Stop tracing and collect data."""
    cov = item.session.cov_engine
    cov.stop()

    cov_data = cov.get_data()
    cwd = os.getcwd()
    file_map = {}

    for filepath in cov_data.measured_files():
        if filepath.startswith(cwd):
            try:
                rel_path = os.path.relpath(filepath, cwd)
                lines = sorted(cov_data.lines(filepath))
                if lines:
                    file_map[rel_path] = lines
            except ValueError:
                continue

    if file_map:
        item.session.test_map[item.nodeid] = file_map

def pytest_sessionfinish(session, exitstatus):
    """Save to disk."""
    output_file = Path(".test_map.jsonl")

    # If no tests ran, test_map might be empty, which is fine.
    if not session.test_map:
        return

    with open(output_file, "w") as f:
        for test_id, file_map in session.test_map.items():
            entry = {"id": test_id, "map": file_map}
            f.write(json.dumps(entry) + "\n")

    print(f"\n[Custom TIA] Map generated: {output_file} ({len(session.test_map)} tests mapped)")

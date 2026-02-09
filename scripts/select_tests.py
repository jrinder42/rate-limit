import json
import subprocess
import sys
import re
import logging
from collections import defaultdict
import argparse
from pathlib import Path
from typing import Optional
import tokenize

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def parse_args() -> argparse.Namespace:
    """
    Handles command-line argument parsing.
    """
    parser = argparse.ArgumentParser(
        description="Select tests to run based on code changes."
    )
    parser.add_argument(
        "base_branch",
        help="The base branch to compare against (e.g., 'main')"
    )
    parser.add_argument(
        "--map",
        default=".test_map.jsonl",
        type=Path,
        help="Path to the test mapping file (default: .test_map.jsonl)"
    )
    parser.add_argument(
        "--output",
        default="tests_to_run.txt",
        type=Path,
        help="Output file for selected tests (default: tests_to_run.txt)"
    )
    return parser.parse_args()

def get_changed_lines(base_ref: str) -> dict[str, set[int]]:
    """
    Parses git diff to find specific lines changed in the OLD version.
    Returns: { "src/file.py": {10, 11, 12} }
    """
    cmd = ["git", "diff", f"origin/{base_ref}", "--unified=0", "--diff-filter=AM"]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Git command failed: {e.stderr}") from e

    changes = {}
    current_file = None
    hunk_header = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")

    for line in result.stdout.splitlines():
        if line.startswith("+++ b/"):
            current_file = line[6:]
            changes[current_file] = set()
        elif line.startswith("@@"):
            match = hunk_header.match(line)
            if match and current_file:
                start_line = int(match.group(1))
                length = int(match.group(2) or 1)
                for i in range(length):
                    changes[current_file].add(start_line + i)

    return changes

def get_ignorable_lines(filepath: str) -> set[int]:
    """
    Uses Python's tokenizer to identify comments, docstrings, and empty lines.
    Returns a set of line numbers that should be ignored.
    """
    ignorable = set()
    path = Path(filepath)
    if not path.exists():
        return ignorable

    try:
        # 1. Tokenize to find Comments and Strings (Docstrings)
        with path.open('rb') as f:
            tokens = tokenize.tokenize(f.readline)
            for token in tokens:
                if token.type == tokenize.COMMENT:
                    ignorable.add(token.start[0])
                # Heuristic: If a line is JUST a string, it's likely a docstring
                if token.type == tokenize.STRING:
                    for line_num in range(token.start[0], token.end[0] + 1):
                        ignorable.add(line_num)

        # 2. Filter purely empty lines (tokenizer sometimes skips these)
        with path.open('r') as f:
            for i, line in enumerate(f, 1):
                if not line.strip():
                    ignorable.add(i)

    except (tokenize.TokenError, IndentationError):
        # If the file is syntactically broken, we can't judge it.
        # Assume everything is code (safe fallback).
        pass

    return ignorable

def find_impacted_tests(map_file: Path, changed_map: dict[str, set[int]]) -> set[str]:
    """
    Revised Logic:
    1. Strict Mode: If changed lines are covered by specific tests, pick those tests.
    2. Orphan Mode: If a changed line is NOT covered by ANY test (e.g. static defaults,
       imports, constants), run ALL tests that touch that file.
    """
    tests_to_run = set()

    # Data structures for the 2-pass analysis
    # file_path -> list of (test_id, covered_lines_set)
    file_interactions = defaultdict(list)

    # file_path -> set of ALL lines covered by ANY test
    total_file_coverage = defaultdict(set)

    # We scan the map and organize it by FILE, not by TEST.
    with open(map_file, "r") as f:
        for line in f:
            try:
                entry = json.loads(line)
                test_id = entry["id"]
                file_map = entry["map"]

                for filepath, covered_lines in file_map.items():
                    # Optimization: Only care about files that actually changed
                    if filepath in changed_map:
                        lines_set = set(covered_lines)
                        file_interactions[filepath].append((test_id, lines_set))
                        total_file_coverage[filepath].update(lines_set)
            except json.JSONDecodeError:
                continue

    for filepath, raw_changed_lines in changed_map.items():
        # Step A: Remove Noise (Comments/Docstrings)
        ignorable = get_ignorable_lines(filepath)
        real_code_changes = raw_changed_lines - ignorable

        if not real_code_changes:
            continue # Only comments changed, skip file.

        # Check for "Orphan Lines" (Changed lines that NO test claims to cover)
        # This usually means structural changes (defaults, imports, constants)
        # logic: orphans = changed_lines - (union of all coverage)
        known_lines = total_file_coverage[filepath]
        orphans = real_code_changes - known_lines

        if orphans:
            # SAFETY NET: We found changes in the file that look "untested" or "static".
            # We must assume these affect everyone. Run ALL tests for this file.
            print(f"  [Fallback] {filepath}: Detected structural changes on lines {orphans}. Running all associated tests.")
            for test_id, _ in file_interactions[filepath]:
                tests_to_run.add(test_id)
        else:
            # STRICT MODE: All changed lines are known. Only run tests that strictly hit them.
            for test_id, covered_lines in file_interactions[filepath]:
                if not real_code_changes.isdisjoint(covered_lines):
                    tests_to_run.add(test_id)

    return tests_to_run

def main() -> int:
    args = parse_args()

    # 1. Fallback: Cold start check
    if not args.map.exists():
        print(f"Test map '{args.map}' not found. Defaulting to full suite.")
        with open(args.output, "w") as f:
            f.write("tests/")
        return 0

    # 2. Get Git Changes
    print(f"Calculating changes against origin/{args.base_branch}...")
    try:
        changed_map = get_changed_lines(args.base_branch)
    except RuntimeError as e:
        print(f"Error: {e}")
        return 1

    if not changed_map:
        print("No code changes detected.")
        return 0

    # 3. Core Logic: Find the tests
    tests_to_run = find_impacted_tests(args.map, changed_map)

    # 4. Output Results
    if tests_to_run:
        print(f"Selected {len(tests_to_run)} tests.")
        with open(args.output, "w") as f:
            for t in sorted(tests_to_run):
                f.write(t + "\n")
    else:
        print("Changes do not affect any known tests.")
        # Ensure we create the empty file so CI doesn't error out
        args.output.touch()

    return 0

if __name__ == "__main__":
    sys.exit(main())

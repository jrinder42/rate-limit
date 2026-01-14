import json
import subprocess
import sys
import re
import argparse
from pathlib import Path
from typing import Optional
from typing_extensions import Set

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

def find_impacted_tests(map_file: Path, changed_map: dict[str, set[int]]) -> set[str]:
    """
    Reads the map file line-by-line and returns tests that intersect with changes.
    """
    tests_to_run = set()

    with open(map_file, "r") as f:
        for line in f:
            try:
                entry = json.loads(line)
                test_id = entry["id"]
                file_map = entry["map"]

                # Check intersection for this test
                for filepath, covered_lines in file_map.items():
                    if filepath in changed_map:
                        touched_lines = changed_map[filepath]
                        # Set intersection check
                        if not touched_lines.isdisjoint(covered_lines):
                            tests_to_run.add(test_id)
                            break
            except json.JSONDecodeError:
                continue

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

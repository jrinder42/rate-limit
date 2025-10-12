#!/usr/bin/env bash
set -e -u -o pipefail

# Support optional argument to control --fix
FIX=${1:-true}  # default to 'true' unless provided

PROJECT_ROOT="$(pwd)"

echo "Getting Ruff-eligible Python files..."
uv run ruff check --show-files . | while read -r file; do
  echo "$file" | sed "s|^${PROJECT_ROOT}/||"
done | sort > .ruff_files.tmp

echo "Getting Git-tracked Python files..."
git ls-files '*.py' | sort > .git_files.tmp

echo "Finding intersection of Ruff-eligible and Git-tracked files..."
comm -12 .ruff_files.tmp .git_files.tmp > .final_files.tmp

trap 'echo "Cleaning up..."; rm -f .ruff_files.tmp .git_files.tmp .final_files.tmp' EXIT

echo "Running Ruff check --fix on common files if any..."
if [ -s .final_files.tmp ]; then
  #xargs uv run ruff check --fix < .final_files.tmp
  if [ "$FIX" = "true" ]; then
    echo "true"
    xargs uv run ruff check --fix < .final_files.tmp
  else
    echo "false"
    xargs uv run ruff check < .final_files.tmp
  fi
else
  echo "No common Python files to fix."
fi

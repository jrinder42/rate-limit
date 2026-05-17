set dotenv-load := true

# CHANGE HERE

export package_name := 'limitor/'
export test_folder := 'tests/'
export test_files := `git ls-files --exclude-standard {{test_folder}}`

# default justfile command
@default:
    @just -f justfile --list

# check to see if `uv` is installed
install-uv:
    #!/usr/bin/env bash
    set -euo pipefail
    if ! command -v uv > /dev/null; then
      echo "uv not found, installing..."
      curl -LsSf https://astral.sh/uv/install.sh | sh
      echo "uv installed."
    else
      echo "uv is already installed."
      uv --version
    fi

# install development dependencies
develop version="3.12": install-uv
    @VIRTUAL_ENV=$(pwd)/.venv uv sync --python {{ version }}

# tear down virtual environment + lock file
teardown:
    #!/usr/bin/env bash
    set -euo pipefail
    if [ -d .venv ]; then
        echo "Deleting existing venv..."
        rm -rf .venv
    fi
    rm -f uv.lock

# full reset of development environment
reset-env: teardown develop

update-all-deps version="3.12": install-uv
    @uv sync --upgrade --python {{ version }}

# code formatting
format:
    @uv run ruff format

# flake8 / pydoclint
flake8:
    @uv run flake8 --toml-config=pyproject.toml --select=DOC #$(git ls-files --cached --exclude-standard)

# linting
lint:
    @uv run ruff check --fix
    @just flake8

# type checking
type-check:
    @uv run pyrefly check

# testing

# handling errors
[private]
handle-error:
    @echo "An error occurred during the test execution."
    # Add your error recovery steps here
    @echo "Running recovery steps completed."

# -Wignore supresses warnings

# run tests without error handling
unsafe-test:
    @uv run pytest -Wignore $test_files

# run tests
test:
    @just unsafe-test || @just handle-error

# run everything except for code coverage
all: develop
    @echo "Syncing dependencies..."
    @echo "Code formatting..."
    @just format
    @echo "Linting..."
    @just lint
    @echo "Running type checks..."
    @just type-check
    @echo "Running tests..."
    @just test
    @echo "All checks passed!"

# code coverage, can also call package_name with {{package_name}}
coverage branch="false":
    uv run coverage erase
    uv run coverage run {{ if branch == "true" { "--branch" } else { "" } }} --source $package_name -m pytest -Wignore $test_files
    uv run coverage report -m
    uv run coverage xml

# [optional] utility functions

set dotenv-load

# CHANGE HERE
export package_name := 'limitor/'
export test_folder := 'tests/'
export sql_folder := 'sql/'

export test_files := `git ls-files --exclude-standard {{test_folder}}`
export all_package_files := `git ls-files --exclude-standard {{package_name}}`
export all_files := `git ls-files --exclude-standard`
export all_py_files := `git ls-files --exclude-standard "*.py"`

# default justfile command
@default:
    @just -f justfile --list

# remove Python file artifacts
[private]
clean-pyc:
    find . -name '*.pyc' -exec rm -f {} +
    find . -name '*.pyo' -exec rm -f {} +
    find . -name '*~' -exec rm -f {} +

[private]
install-uv:
    @if ! command -v uv > /dev/null; then \
      echo "uv not found, installing..."; \
      curl -LsSf https://astral.sh/uv/install.sh | sh; \
      echo "uv installed."; \
    else \
      echo "uv is already installed."; \
      uv --version; \
    fi

# install development dependencies
develop version="3.12": clean-pyc install-uv
    @uv sync --python {{version}}

# linting
lint:
    @echo "Linting files..."
    @echo "Running Black"
    @uv run black --check --diff --quiet .
    @echo $?
    @echo "Running isort"
    @uv run isort --profile black --diff .
    @echo "Running pylint"
    @git ls-files --exclude-standard "*.py" | xargs -r uv run pylint
    @echo "Running flake8 / pydoclint"
    @uv run flake8 --toml-config=pyproject.toml $all_py_files
    @echo "Running ruff"
    @uv run ruff check .
    # @just lint-sql

# formatting
format:
    @echo "Formatting repository..."
    @echo "Running Black"
    @uv run black --quiet .
    @echo "Running isort"
    @uv run isort --profile black .
    @echo "Running ruff"
    @uv run ruff check --fix .
    # uv run sqlfluff fix $sql_folder
    # uv run ruff format

# need to do this as mypy as issues with files of the same name (conftest.py)
# type checking
type-check:
    uv run mypy .
    uv run mypy tests/conftest.py
    uv run mypy tests/integration/conftest.py

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
    @echo "Running tests..."
    @just unsafe-test || @just handle-error

# run everything except for code coverage
all: format lint type-check test
    @echo "All checks passed!"

# code coverage, can also call package_name with {{package_name}}
coverage:
    uv run coverage erase
    uv run coverage run --source $package_name -m pytest -Wignore $test_files
    uv run coverage report -m
    uv run coverage xml

# [optional] utility functions

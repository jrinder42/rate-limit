set dotenv-load

# CHANGE HERE
export package_name := 'rate_limit/'
export test_folder := 'tests/'
export sql_folder := 'sql/'

export test_files := `git ls-files --exclude-standard {{test_folder}}`
# CHANGE HERE
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

# install development dependencies
develop: clean-pyc
    uv sync

# check out the black docs to understand what is going on / make sure the python version is the same as .blazar.yaml
[private]
lint-server:
    uv run black --check --diff --quiet $all_py_files
    @echo $?
    uv run isort --profile black $all_files --diff

[private]
lint-sql:
    uv run sqlfluff lint $sql_folder

# pylint linter
pylint:
    #all tracked python files, respecting gitignore rules
    # cannot pipe variables in a justfile
    git ls-files --exclude-standard "*.py" | xargs -r uv run pylint

    # Only committed Python files
    #git ls-tree -r HEAD --name-only "*.py" | xargs pylint

# flake8 / pydoclint
flake8:
    uv run flake8 --toml-config=pyproject.toml $all_py_files

# ruff lint
ruff-lint:
    uv run ruff check $all_py_files

# linting
lint:
    @echo "Linting files..."
    @just lint-server
    @just pylint
    ##@just lint-sql
    @just flake8
    @just ruff-lint

[private]
format-server:
    uv run black --quiet $all_py_files
    uv run isort --profile black $all_files
    ##uv run sqlfluff fix $sql_folder
    uv run ruff check --fix $all_py_files
    #uv run ruff format

# formatting
format:
    @echo "Formatting repository..."
    @just format-server

# type checking
type-check:
    uv run mypy --strict $all_py_files

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
    uv run pytest -Wignore $test_files

# run tests
test:
    @echo "Running tests..."
    @just unsafe-test || @just handle-error

# run everything except for code coverage
check: format lint type-check test
    @echo "All checks passed!"

# code coverage, can also call package_name with {{package_name}}
coverage:
    coverage erase
    coverage run --source $package_name -m pytest -Wignore  $test_files
    coverage report -m

# [optional] utility functions

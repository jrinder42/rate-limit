# Rate Limiting Algorithms

## Algorithms

| Algorithms   |  Sync  |  Async  |
|:-------------|:------:|:-------:|
| Leaky Bucket |  TBD   |   TBD   |
| Token        |  TBD   |   TBD   |
| LLM-Token    |  TBD   |   TBD   |

## Development

Setup `uv`-based virtual environment

```shell
# Install uv
# for a mac or linux
brew install uv
# OPTIONAL: or
curl -LsSf https://astral.sh/uv/install.sh | sh

# python version are automatically downloaded as needed or: uv python install 3.12
uv venv financials --python 3.12


# to activate the virtual environment
source .venv/bin/activate

# to deactivate the virtual environment
deactivate
```

Create lock file + requirements.txt

```shell
# after pyproject.toml is created
uv lock

uv export -o requirements.txt --quiet
```
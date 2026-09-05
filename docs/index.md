# Pomeari

Pomeari is FOSS crossposting software built on humane modular design.

## Installation

Pomeari requires Python 3.12 or newer.

```sh
pip install pomeari
```

## Development

Clone the repository and install its dev environment with [uv](https://docs.astral.sh/uv/):

```sh
uv sync
uv run --group dev pytest
```

To work on the documentation locally:

```sh
python -m pip install -r docs/requirements.txt
mkdocs serve
```

The published documentation is generated from the `main` branch and deployed to GitHub Pages.

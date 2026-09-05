# Pomeari

[![License: LGPLv3+](https://img.shields.io/badge/license-LGPLv3+-blue.svg)](https://www.gnu.org/licenses/lgpl-3.0)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

_Short for **Po**st-**Me**-**a**-**Ri**ver!_

FOSS crossposting software built on humane modular design.

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

# Pomeari

[![License: LGPLv3+](https://img.shields.io/badge/License-LGPLv3+-blue.svg)](https://www.gnu.org/licenses/lgpl-3.0)

_Short for **Po**st-**Me**-**a**-**Ri**ver!_

FOSS crossposting software built on humane modular design.


## Getting Started

### Installation

This is all still very WIP (see [#1](https://codeberg.org/rudzik8/pomeari/issues/1) for details), so it's recommended that you only perform a toy install within the `uv` virtual environment.

1. [Install Astral uv](https://docs.astral.sh/uv/getting-started/installation/)
2. Run `uv sync` to fetch the dependencies
3. Run `uv pip install -e .` for a virtual install
4. Confirm that it worked using `uv run pomeari`


### Usage

* Add/remove configuration entries (including API secrets) using `pomeari config {set|rm} <key> [<value>]`\
  e.g. `pomeari config set mastodon_token uQL3g0C7h5wvcyQbt5vNFGPxt2tPTe`
* Post & crosspost short/long-form content from Markdown files using `pomeari post [{short|long}] [<file>] [{-e|--edit}`\
  e.g. `pomeari post long ~/Documents/my-brother-said.md`, or just `pomeari post [short]`
* See the crossposts you made using `pomeari post logs [{-n|--max-count} <LIMIT>]`, or just `pomeari post logs`
* Manage your platforms by using `pomeari platform list` and `pomeari platform favorite [<PLATFORM>]`

Long-form content supports including YAML Frontmatter at the top, surrounded both ways by triple dash (`---`).


### License

This software is licensed under the GNU Lesser General Public License version 3 or later. See the `LICENSE.md` file for details.

* Copyright (C) 2026 Mikita 'rudzik8' Wiśniewski

For authors, see the `AUTHORS.md` file.

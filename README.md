# pmr-utils

Utilities for caching and analyzing public workspace metadata from the Physiome Model Repository (PMR), and exporting cached data in OmicsDI XML format.

Main PMR CLI entry point: `pmr-utils.py`

## What the main CLI currently does

The main CLI is command-based and uses a local cache directory tied to a single PMR instance.

### 1) Cache workspace metadata

Command: `cache-workspace`

- Pulls workspace metadata from PMR.
- Stores normalized data in the local cache (`workspaces.json`).
- Captures latest exposure metadata when available.
- Supports selecting workspaces by regex, by a single workspace URL, or all public workspaces.
- Supports `--force-refresh` to recache existing entries.

### 2) Export OmicsDI XML

Command: `omicsdi-export`

- Reads cached workspaces and builds OmicsDI-style XML.
- Extracts publication identifiers from exposure metadata (especially PubMed URNs).
- Handles duplicate workspace IDs using publication-aware conflict handling.
- Writes XML to a file (`--output`) or stdout.

### 3) Analyze cached workspace data

Command: `analysis`

- Summarizes exposure metadata (citations, file types, semantic keywords).
- Extracts and ranks common keywords.
- Writes keyword plots into the cache directory.
- Optionally generates keyword clouds (`--keyword-cloud`).
- Optionally runs CellML parse/validate/analyze checks for exposed CellML models (`--check-cellml-models`).

### 4) Utility/sample commands

Commands: `greet`, `process`, `status`

These are helper/demo-style commands for CLI/logging behavior and are not part of the main PMR metadata workflow.

## Cache structure

The cache root contains:

- `.pmr-instance`: PMR instance URL this cache is bound to.
- `workspaces.json`: cached workspace metadata.
- `repos/`: reserved repository area used by cache path helpers.

If you point to an existing cache with a different PMR instance URL, the CLI will fail fast with an instance mismatch error.

## Install and run with uv

Project requirement: Python 3.13+

### 1) Install dependencies

From this folder:

```bash
uv sync
```

### 2) Show CLI help

```bash
uv run python pmr-utils.py -h
```

### 3) Typical PMR workflow

Cache workspace metadata:

```bash
uv run python pmr-utils.py cache-workspace --all
```

Run analysis:

```bash
uv run python pmr-utils.py analysis --max-keywords 30
```

Export OmicsDI XML:

```bash
uv run python pmr-utils.py omicsdi-export --output pmr-mx.xml
```

## Configuration model

Global settings can come from:

1. CLI flags
2. TOML config file (`--config`)
3. Environment variables
4. Built-in defaults

Priority is exactly in that order (highest to lowest).

Supported global environment variables:

- `PMR_INSTANCE`
- `PMR_CACHE_DIR`
- `PMR_LOG_LEVEL`
- `PMR_LOG_FILE`

Useful global flags:

- `--pmr-instance`
- `--cache-dir`
- `--log-level`
- `--log-file`
- `--debug` (shorthand for DEBUG logging)

Examples:

```bash
uv run python pmr-utils.py --cache-dir ../pmr-cache-models cache-workspace --all
uv run python pmr-utils.py --config config.toml analysis --exposures-only
uv run python pmr-utils.py --config example-config.toml
```

The last command runs whatever command is defined in the config file's `[run]` section.

## Notes on local dependency source

`pyproject.toml` currently includes a local uv source override for `libcellml-python-utils` under `[tool.uv.sources]`.

If that path does not exist on your machine, update the source mapping (or remove it) before running `uv sync`.

## Legacy/helper scripts in this folder

- `workspaces.py`: older direct script for workspace retrieval/caching logic.
- `pmr_mx_fmt.py`: earlier XML formatting/export experimentation.
- `workspace_list_to_mx_fmt.py`: OmicsDI export implementation used by the main CLI.
- `workspace_analysis.py`: analysis implementation used by the main CLI.
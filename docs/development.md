# Development

## Environment

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

The package requires Python 3.11 or newer. Release 0.1.0 was tested on Python 3.12.6. Tooling is Ruff `0.17.1`, pytest, and pytest-cov. Runtime dependencies are limited to the Python standard library.

## Checks

```bash
ruff check src tests examples
ruff format --check src tests examples
pytest
python -m build
```

`pytest` is configured in `pyproject.toml` to collect `tests/` and to require 90 percent line coverage of `shared_logger`.

Format the tree with `ruff format src tests examples` when a check fails on layout.

## Layout

Application code lives in `src/shared_logger`. Tests are split into `tests/unit`, `tests/integration`, and `tests/contract`. Examples under `examples/` call the public API and are run as scripts.

Editable install uses the `src` layout, so tests import `shared_logger` rather than a checkout-relative path.

## Building a wheel

`python -m build` writes an sdist and a wheel under `dist/`. Install the wheel in a clean environment to confirm the package metadata.

The distribution is not published from this repository's default workflow. Publish only through the index your organization chooses, with the version from `pyproject.toml`.

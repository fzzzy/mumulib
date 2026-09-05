# mumulib for Python

Python utilities for ASGI request handling, traversing and updating objects,
producing responses, validating data shapes, and HTML templating.

The package includes `consumers`, `producers`, `server`, `shaped`, `mumutypes`,
and `tags`. Runtime dependencies are aiofiles and lxml.

## Development

From the repository root:

```sh
uv sync --project python --extra dev --locked
make test
make mypy
make lint
```

The development extra includes coverage, mypy, flake8, and typing stubs.
Requires Python 3.12 or newer. Licensed under MIT; see LICENSE.

The companion TypeScript library and browser examples are documented in the
[repository README](https://github.com/fzzzy/mumulib#readme).

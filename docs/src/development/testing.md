# Testing

The test suite uses [pytest](https://docs.pytest.org/) with pytest-django, factory-boy fixtures, and coverage. Tests live in `tests/`, mirroring the app layout (`tests/api/`, `tests/faces/`, …).

## Running tests

With Docker Compose (no local setup needed):

```console
$ docker compose run --rm backend pytest tests -v --create-db
```

Natively (needs local PostgreSQL and Redis, and the dev dependencies from `uv sync`):

```console
$ uv run pytest tests                       # full suite
$ uv run pytest tests/api -k findings       # subset
```

Via tox (as CI runs it):

```console
$ uv run tox -e tests
$ uv run tox -e lint     # pre-commit / ruff
$ uv run tox -e mypy     # type check
$ uv run tox -e docs     # docs build
```

## Coverage

Coverage is collected automatically (configured in `pytest.ini`); the HTML report is written to `~build/coverage`. CI uploads results to [Codecov](https://codecov.io/github/unicef/hope-dedup-engine).

## Notes

- `--create-db` forces a fresh test database; without it, pytest-django reuses the previous one (faster iteration).
- Fixtures and factories are defined in `tests/conftest.py` and per-package `conftest.py` files, using pytest-factoryboy registration.
- Available markers are declared in `pytest.ini` (`api`, `admin`, `selenium`, …). Heavyweight face-processing calls are mocked in unit tests; end-to-end behavior can be exercised against the [demo app](demo.md).
- CI (GitHub Actions) runs tests, lint, and the docs build on every pull request.

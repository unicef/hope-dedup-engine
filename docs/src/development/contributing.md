# Contributing

Issues and pull requests are always welcome.

## General considerations

1. **Keep it small.** The smaller the change, the more likely it is to be accepted quickly.
2. Changes that fix a reported issue get priority for review.
3. If you've never created a pull request before, see the [GitHub guide](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull-requests/creating-a-pull-request).

## Workflow

1. Fork (external contributors) or clone the repo and set up your environment following [Getting started](getting-started.md).
2. Create a feature branch — **don't work on `main`/`develop` directly**. The convention in this repo is `feature/<ticket>-short-description` or `bugfix/<ticket>-short-description`.
3. Make your changes:
    - keep `@extend_schema` API annotations up to date when touching endpoints;
    - add a migration when models change;
    - update the documentation pages affected by your change.
4. Verify locally before pushing:

```console
$ uv run pre-commit run --all-files   # lint (ruff etc.)
$ uv run pytest tests                 # test suite
$ uv run tox -e mypy                  # type check
```

5. Push and open a pull request against `develop`. GitHub Actions runs tests, lint, security checks, and the docs build; fix any failures. A maintainer will review and merge.

## Code style

Formatting and linting are enforced by the pre-commit configuration (ruff, isort rules, flake8 plugins) — run `uv run pre-commit install` once and the hooks take care of it. Type hints are expected on new code; the codebase is checked with mypy.

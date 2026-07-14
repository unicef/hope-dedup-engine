# How to Contribute

Always happy to get issues identified and pull requests!

The full contributor documentation lives at
<https://unicef.github.io/hope-dedup-engine/development/contributing/>
(and in this repo under `docs/src/development/`). The short version:

## General considerations

1. Keep it small. The smaller the change, the more likely we are to accept it.
2. Changes that fix a current issue get priority for review.
3. Check out the [GitHub guide](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull-requests/creating-a-pull-request) if you've never created a pull request before.

## Getting started

1. Fork the repo and clone your fork.
2. Set up your environment — see the [getting started guide](https://unicef.github.io/hope-dedup-engine/development/getting-started/). In short: `uv venv .venv && uv sync`, then either `docker compose up --build` or a local Postgres/Redis with `./manage.py env --develop > .envrc`.
3. Create a branch for your changes (`feature/...` or `bugfix/...`) — don't develop on `main`/`develop` directly.

## Before you submit

Run the checks CI will run:

```bash
uv run pre-commit run --all-files   # lint
uv run pytest tests                 # test suite
uv run tox -e mypy                  # type check
```

## Submitting a pull request

Push your branch and open a pull request against `develop`. GitHub Actions will run tests, lint, and the docs build; fix any failures. A maintainer will review your change and give feedback or merge it.

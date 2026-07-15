HOPE Deduplication Engine
===============================


[![Test](https://github.com/unicef/hope-dedup-engine/actions/workflows/test.yml/badge.svg)](https://github.com/unicef/hope-dedup-engine/actions/workflows/test.yml)
[![Lint](https://github.com/unicef/hope-dedup-engine/actions/workflows/lint.yml/badge.svg)](https://github.com/unicef/hope-dedup-engine/actions/workflows/lint.yml)
[![codecov](https://codecov.io/github/unicef/hope-dedup-engine/graph/badge.svg?token=FBUB7HML5S)](https://codecov.io/github/unicef/hope-dedup-engine)
[![Documentation](https://github.com/unicef/hope-dedup-engine/actions/workflows/docs.yml/badge.svg)](https://unicef.github.io/hope-dedup-engine/)
[![Pypi](https://badge.fury.io/py/unicef-hope-dedup-engine.svg)](https://badge.fury.io/py/unicef-hope-dedup-engine)
[![Docker Pulls](https://img.shields.io/docker/pulls/unicef/hope-dedup-engine)](https://hub.docker.com/repository/docker/unicef/hope-dedup-engine/tags)

The HOPE Deduplication Engine (HDE) is a service in the [HOPE](https://github.com/unicef/hope) ecosystem that detects duplicate individuals in a dataset by comparing their facial photographs. Client systems register batches of images through a REST API, trigger asynchronous processing (face quality assessment, encoding, and comparison), and read back duplicate findings with similarity scores.

## Documentation

Full documentation is at **<https://unicef.github.io/hope-dedup-engine/>**:

- [Concepts](https://unicef.github.io/hope-dedup-engine/concepts/architecture/) — architecture, set lifecycle, data model, face pipeline
- [Integration Guide](https://unicef.github.io/hope-dedup-engine/integration/) — for client systems using the API
- [Administration](https://unicef.github.io/hope-dedup-engine/admin/deployment/) — deployment, configuration, operations
- [Development](https://unicef.github.io/hope-dedup-engine/development/getting-started/) — contributing to the engine itself

## Quick start (development)

Requirements: [uv](https://docs.astral.sh/uv/) and Docker, or see the [full setup guide](https://unicef.github.io/hope-dedup-engine/development/getting-started/).

```shell
git clone https://github.com/unicef/hope-dedup-engine.git
cd hope-dedup-engine
docker compose up --build
```

Then open <http://localhost:8000/admin/> (`adm@hde.org` / `123`) and the API docs at <http://localhost:8000/api/rest/swagger/>.

For a native (non-Docker) environment:

```shell
uv venv .venv
uv sync

./manage.py env --develop > .envrc  # create initial development configuration
direnv allow .                      # enable environment
createdb hope_dedup_engine          # create postgres database on localhost
./manage.py upgrade
./manage.py runserver
```

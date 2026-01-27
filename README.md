HOPE Deduplication Engine
===============================


[![Test](https://github.com/unicef/hope-dedup-engine/actions/workflows/test.yml/badge.svg)](https://github.com/unicef/hope-dedup-engine/actions/workflows/test.yml)
[![Lint](https://github.com/unicef/hope-dedup-engine/actions/workflows/lint.yml/badge.svg)](https://github.com/unicef/hope-dedup-engine/actions/workflows/lint.yml)
[![codecov](https://codecov.io/github/unicef/hope-dedup-engine/graph/badge.svg?token=FBUB7HML5S)](https://codecov.io/github/unicef/hope-dedup-engine)
[![Documentation](https://github.com/unicef/hope-dedup-engine/actions/workflows/docs.yml/badge.svg)](https://unicef.github.io/hope-dedup-engine/)
[![Pypi](https://badge.fury.io/py/unicef-hope-dedup-engine.svg)](https://badge.fury.io/py/unicef-hope-dedup-engine)
[![Docker Pulls](https://img.shields.io/docker/pulls/unicef/hope-dedup-engine)](https://hub.docker.com/repository/docker/unicef/hope-dedup-engine/tags)

## Contributing

### Requirements

- [uv](https://docs.astral.sh/uv/)
- [direnv](https://direnv.net/)

### Checkout and configure development environment

```shell

    git checkout https://github.com/unicef/hope_dedup_engine.git
    cd hope_dedup_engine
    uv venv .venv
    uv sync

    ./manage.py env --develop > .envrc  # create initial development configuration
    direnv allow .  # enable environment
    createdb hope_dedup_engine  # create postgres database on localhost

```

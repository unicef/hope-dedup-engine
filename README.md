ABOUT HOPE Deduplication Engine
===============================

[![Test](https://github.com/unicef/hope-dedup-engine/actions/workflows/test.yml/badge.svg)](https://github.com/unicef/hope-dedup-engine/actions/workflows/test.yml)
[![Lint](https://github.com/unicef/hope-dedup-engine/actions/workflows/lint.yml/badge.svg)](https://github.com/unicef/hope-dedup-engine/actions/workflows/lint.yml)
[![codecov](https://codecov.io/gh/unicef/hope-dedup-engine/graph/badge.svg?token=kAuZEX5k5o)](https://codecov.io/gh/unicef/hope-dedup-engine)
![Version](https://img.shields.io/badge/dynamic/toml?url=https%3A%2F%2Fraw.githubusercontent.com%unicef%2Fhope-dedup-engine%2Fdevelop%2Fpyproject.toml&query=%24.project.version&label=version)
![License](https://img.shields.io/badge/dynamic/toml?url=https%3A%2F%2Fraw.githubusercontent.com%2Funicef%2Fhope-dedup-engine%2Fdevelop%2Fpyproject.toml&query=%24.project.license.text&label=license)


## Docker

Check mandatory environment variables

    $ docker run -it -t  unicef/hope-dedupe-engine:release-0.1 django-admin env --check
    

Display current configuration

    $ docker run -it -t  unicef/hope-dedupe-engine:release-0.1 django-admin env
    

Run server and support services

    $ docker run -d -t  unicef/hope-dedupe-engine:release-0.1
    $ docker run -d -t  unicef/hope-dedupe-engine:release-0.1 worker
    $ docker run -d -t  unicef/hope-dedupe-engine:release-0.1 beat
    
Use provided sample compose file

    $ docker compose build
    $ docker compose up
    

## Help
**Got a question?** We got answers.

File a GitHub [issue](https://github.com/unicef/hope-dedup-engine/issues)

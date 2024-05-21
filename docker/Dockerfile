# syntax=docker/dockerfile:1.7
ARG PYTHON_VER=3.12
ARG PKG_DIR=/packages
ARG BUILD_DATE=not_provided
ARG CHECKSUM=not_provided
ARG VERSION=0.1.0

FROM python:$PYTHON_VER-slim-bullseye AS python

FROM python AS common-env
ARG BUILD_DATE
ARG CHECKSUM
ARG PKG_DIR
ARG VERSION
ARG PYTHON_VER
ENV PKG_DIR=$PKG_DIR \
    PYPACKAGES=$PKG_DIR/__pypackages__/$PYTHON_VER
ENV ADMINS="" \
    BUILD_DATE=$BUILD_DATE \
    CHANNEL_URLS=""\
    CHECKSUM=$CHECKSUM \
    CI_BUILD_ID=$CI_BUILD_ID \
    CI_COMMIT_SHORT_SHA=$CI_COMMIT_SHORT_SHA \
    CI_JOB_URL=$CI_JOB_URL \
    DATABASE_URL="" \
    DEV_FOOTER_INFO="" \
    DJANGO_SETTINGS_MODULE="hope_dedup_engine.config.settings" \
    DJSTRIPE_WEBHOOK_VALIDATION=""\
    DOCKER_TAG=$DOCKER_TAG \
    INIT_RUN_CHECK=1 \
    INIT_RUN_COLLECTSTATIC=1 \
    INIT_RUN_MIGRATATIONS=1 \
    INIT_RUN_UPGRADE=0 \
    INIT_START_BEAT=0 \
    INIT_START_BOB=0 \
    INIT_START_CELERY=0 \
    INIT_START_DAPHNE=0 \
    INIT_START_FLOWER=0 \
    LOG_LEVEL="ERROR" \
    MEDIA_ROOT="/var/hope_dedup_engine/media" \
    MEDIA_URL="/media/" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=$PYTHONPATH:$PYPACKAGES/lib:/code/src \
    SECRET_KEY="secret-key-just-for-build" \
    SENTRY_DSN="" \
    SOCIAL_AUTH_GOOGLE_OAUTH_KEY=""\
    SOCIAL_AUTH_GOOGLE_OAUTH_SECRET=""\
    STATIC_ROOT="/var/hope_dedup_engine/static" \
    STATIC_URL="/static/" \
    UWSGI_PROCESSES=4 \
    VERSION=$VERSION \
    PATH=$PATH:$PYPACKAGES/bin
RUN ln -s -f /bin/true /usr/bin/chfn \
    && groupadd --gid 1024 hope \
    && adduser --disabled-login --disabled-password --no-create-home --ingroup hope -q www

FROM common-env AS common-os
ENV buildDeps="build-essential gcc cmake curl libjpeg-dev zlib1g-dev libffi-dev libssl-dev libpq-dev libgdal-dev libgl1-mesa-glx docker.io "
ENV runtimeDeps="postgresql-client libmagic1"
RUN rm -f /etc/apt/apt.conf.d/docker-clean \
    && echo 'Binary::apt::APT::Keep-Downloaded-Packages "true";' > /etc/apt/apt.conf.d/keep-cache
RUN --mount=target=/var/lib/apt/lists,type=cache,sharing=locked \
    --mount=target=/var/cache/apt,type=cache,sharing=locked \
    apt-get update && \
    apt-get install -y --no-install-recommends $buildDeps $runtimeDeps && \
    rm -rf /var/lib/apt/lists/*
RUN pip install -U pip setuptools && pip install pdm

FROM common-os AS builder
# ARG CHECKSUM
WORKDIR $PKG_DIR
# COPY docker/conf/* /conf/
COPY docker/entrypoint.sh docker/wait-for-it.sh /usr/local/bin/
COPY pyproject.toml pdm.lock pdm.toml ./
RUN pdm sync --prod --no-editable --no-self
# RUN echo $CHECKSUM > /CHECKSUM

FROM builder AS dev
RUN pdm sync --no-editable --no-self
WORKDIR /code/
COPY .. ./
ENTRYPOINT ["entrypoint.sh"]

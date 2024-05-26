ARG PYTHON_VER=3.11
ARG BUILD_DATE=not_provided
ARG VERSION=0.1.0
ARG DEST_DIR=/hde
ARG PKG_DIR=${DEST_DIR}/__pypackages__/${PYTHON_VER}
ARG CHECKSUM

FROM python:$PYTHON_VER-slim-bullseye AS python_base
ARG DEST_DIR
ARG PKG_DIR
ENV ADMINS="" \
    BUILD_DATE=$BUILD_DATE \
    CHECKSUM=$CHECKSUM \
    DATABASE_URL="" \
    DEST_DIR=${DEST_DIR} \
    DJANGO_SETTINGS_MODULE="hope_dedup_engine.config.settings" \
    INIT_RUN_CHECK=1 \
    INIT_RUN_COLLECTSTATIC=1 \
    INIT_RUN_MIGRATATIONS=1 \
    INIT_RUN_UPGRADE=0 \
    LOG_LEVEL="ERROR" \
    MEDIA_ROOT="/var/hope_dedup_engine/media" \
    MEDIA_URL="/media/" \
    PATH=${PKG_DIR}/bin:${PATH}:/usr/local/bin/ \
    PYTHONPATH=${PKG_DIR}/lib/:${PYTHONPATH} \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SECRET_KEY="secret-key-just-for-build" \
    SENTRY_DSN="" \
    STATIC_ROOT="/var/hope_dedup_engine/static" \
    STATIC_URL="/static/" \
    UWSGI_PROCESSES=4 \
    VERSION=$VERSION

ARG GOSU_VERSION=1.17
ARG GOSU_SHA256=bbc4136d03ab138b1ad66fa4fc051bafc6cc7ffae632b069a53657279a450de3
ARG TINI_VERSION=0.19.0
ARG TINI_SHA256=93dcc18adc78c65a028a84799ecf8ad40c936fdfc5f2a57b1acda5a8117fa82c
RUN set -x \
  && buildDeps=" \
  wget \
  " \
  && apt-get update && apt-get install -y --no-install-recommends $buildDeps \
  && rm -rf /var/lib/apt/lists/* \
  && wget --quiet -O /usr/local/bin/gosu "https://github.com/tianon/gosu/releases/download/$GOSU_VERSION/gosu-amd64" \
  && echo "$GOSU_SHA256 /usr/local/bin/gosu" | sha256sum --check --status \
  && chmod +x /usr/local/bin/gosu \
  && wget --quiet -O /usr/local/bin/tini "https://github.com/krallin/tini/releases/download/v$TINI_VERSION/tini-amd64" \
  && echo "$TINI_SHA256 /usr/local/bin/tini" | sha256sum --check --status \
  && chmod +x /usr/local/bin/tini \
  && apt-get purge -y --auto-remove $buildDeps
# sudo apt-get install libcairo2-dev libjpeg62-turbo-dev libpango1.0-dev libgif-dev build-essential g++
# sudo apt-get install libopenblas-dev libwebp-dev

RUN \
    --mount=type=cache,target=/var/cache/apt \
    apt-get update  \
    && apt-get install -y --no-install-recommends  \
      postgresql-client \
      libgl1  \
      libglib2.0-0 \
      libffi7 \
      libgif-dev \
      libjpeg-dev \
      libmagic1 \
      libopenblas-dev \
      libpng16-16  \
      libxml2  \
      libwebp-dev \
      mime-support  \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && ldconfig

RUN ln -s -f /bin/true /usr/bin/chfn \
    && groupadd --gid 1024 hope \
    && adduser --disabled-login --disabled-password --no-create-home --ingroup hope -q hde \
    && mkdir ${DEST_DIR} \
    && chown hde:hope ${DEST_DIR} \
    && echo $CHECKSUM > /CHECKSUM

COPY docker/bin/* /usr/local/bin/
COPY docker/conf/* /conf/

FROM python_base AS build_deps
ARG DEST_DIR
ENV buildDeps="build-essential \
                cmake \
                curl \
                gcc \
                libgdal-dev \
                liblapack-dev \
                libpng-dev  \
                libpq-dev \
                libssl-dev \
                python3-dev \
                zlib1g-dev "

RUN apt-get update  \
    && apt-get install -y --no-install-recommends \
    $buildDeps \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*


FROM build_deps AS python_dev_deps
ARG DEST_DIR
WORKDIR ${DEST_DIR}
COPY pyproject.toml .
COPY pdm.lock .
RUN pip install -U pip setuptools pdm \
    && mkdir -p ${DEST_DIR}/__pypackages__ \
    && pdm config python.use_venv false \
    && pdm sync --no-editable -v --no-self  \
    && apt-get purge -y --auto-remove $buildDeps \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*


FROM build_deps AS python_prod_deps
ARG DEST_DIR
WORKDIR ${DEST_DIR}
COPY pyproject.toml .
COPY pdm.lock .
COPY ./src ${DEST_DIR}/src
RUN pip install -U pip setuptools pdm \
    && mkdir -p ${DEST_DIR}/__pypackages__ \
    && pdm config python.use_venv false \
    && pdm sync --no-editable -v --prod \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

FROM python_base AS dev
COPY --chown=hde:hope --from=python_dev_deps ${DEST_DIR}/__pypackages__ ${DEST_DIR}/__pypackages__
COPY ./src ${DEST_DIR}/src
ENV PYTHONPATH=${DEST_DIR}/src/:${PYTHONPATH}


FROM python_base AS dist
ENV PYTHONPATH=${DEST_DIR}/src/:${PYTHONPATH}
WORKDIR ${DEST_DIR}
COPY --chown=hde:hope --from=python_prod_deps ${DEST_DIR}/__pypackages__ ${DEST_DIR}/__pypackages__
USER hde
CMD "run"
ENTRYPOINT exec docker-entrypoint.sh "$0" "$@"



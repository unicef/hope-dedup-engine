ARG CHECKSUM
ARG VERSION=0.1.0
ARG BUILD_DATE=not_provided

FROM python:3.12-slim-bookworm AS python_base

ARG CHECKSUM
ENV CHECKSUM=$CHECKSUM
ARG VERSION
ENV VERSION=$VERSION
ARG BUILD_DATE
ENV BUILD_DATE=$BUILD_DATE
ARG SOURCE_COMMIT
ENV SOURCE_COMMIT=$SOURCE_COMMIT
ARG GITHUB_SERVER_URL
ENV GITHUB_SERVER_URL=$GITHUB_SERVER_URL
ARG GITHUB_REPOSITORY
ENV GITHUB_REPOSITORY=$GITHUB_REPOSITORY

ARG GOSU_VERSION=1.17
ARG GOSU_SHA256=bbc4136d03ab138b1ad66fa4fc051bafc6cc7ffae632b069a53657279a450de3
ARG TINI_VERSION=0.19.0
ARG TINI_SHA256=93dcc18adc78c65a028a84799ecf8ad40c936fdfc5f2a57b1acda5a8117fa82c
ARG WAITFOR_IT_VERSION=2.4.1
ARG WAITFOR_IT_MD5=cd67c8e45436c4a7b2b707d7a5b15a66


RUN set -x \
  && buildDeps=" \
  wget \
  " \
  && apt-get update && apt-get install -y --no-install-recommends ${buildDeps} \
  && rm -rf /var/lib/apt/lists/* \
  && wget --quiet -O /usr/local/bin/gosu "https://github.com/tianon/gosu/releases/download/$GOSU_VERSION/gosu-amd64" \
  && echo "$GOSU_SHA256 /usr/local/bin/gosu" | sha256sum --check --status \
  && chmod +x /usr/local/bin/gosu \
  && wget --quiet -O /usr/local/bin/tini "https://github.com/krallin/tini/releases/download/v$TINI_VERSION/tini-amd64" \
  && echo "$TINI_SHA256 /usr/local/bin/tini" | sha256sum --check --status \
  && chmod +x /usr/local/bin/tini \
  && wget --quiet -O /usr/local/bin/waitforit "https://github.com/maxcnunes/waitforit/releases/download/v$WAITFOR_IT_VERSION/waitforit-linux_amd64" \
  && echo "$WAITFOR_IT_MD5 /usr/local/bin/waitforit" | md5sum --check --status \
  && chmod +x /usr/local/bin/waitforit  \
  && apt-get purge -y --auto-remove $buildDeps


RUN \
    --mount=type=cache,target=/var/cache/apt \
    apt-get clean \
    && apt-get update  \
    && apt-get install -y --no-install-recommends  \
      postgresql-client \
      postgresql-client \
      libgl1  \
      libglib2.0-0 \
      libffi8 \
      libgif-dev \
      libjpeg-dev \
      libmagic1 \
      libopenblas-dev \
      libpng16-16  \
      libxml2  \
      libwebp-dev \
      mime-support  \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --gid 1024 unicef \
    && adduser --disabled-login --disabled-password --no-create-home --ingroup unicef -q hope \
    && echo $CHECKSUM > /CHECKSUM

COPY docker/bin/* /usr/local/bin/
COPY docker/conf/* /conf/

# ------------- build_deps -------------
FROM python_base AS build_deps

RUN set -x \
    && buildDeps="build-essential \
        cmake \
        curl \
        gcc \
        libgdal-dev \
        libgif-dev \
        libjpeg-dev \
        liblapack-dev \
        libopenblas-dev \
        libpng-dev  \
        libpq-dev \
        libwebp-dev \
        libssl-dev \
        libxml2-dev  \
        python3-dev \
        zlib1g-dev  \
    " \
    && apt-get update \
    && apt-get install -y --no-install-recommends $buildDeps \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

ENV PATH=/code/.venv/bin:/usr/local/bin/:/usr/bin:/bin \
    PYTHONPATH=""\
    PYTHONDONTWRITEBYTCODE=1

# ------------- python_dev_deps -------------
FROM build_deps AS python_dev_deps
ARG CHECKSUM
ENV CHECKSUM=$CHECKSUM
ARG VERSION
ENV VERSION=$VERSION
ARG BUILD_DATE
ENV BUILD_DATE=$BUILD_DATE
ARG DISTRO
ENV DISTRO=$DISTRO
ARG SOURCE_COMMIT
ENV SOURCE_COMMIT=$SOURCE_COMMIT
ARG GITHUB_SERVER_URL
ENV GITHUB_SERVER_URL=$GITHUB_SERVER_URL
ARG GITHUB_REPOSITORY
ENV GITHUB_REPOSITORY=$GITHUB_REPOSITORY


LABEL date=$BUILD_DATE
LABEL version=$VERSION
LABEL checksum=$CHECKSUM
LABEL distro="test"

COPY . /code
WORKDIR /code

RUN pip install uv uwsgi

RUN --mount=type=cache,target=/root/.uv-cache \
    uv sync -v \
        --cache-dir=/root/.uv-cache \
        --python=/usr/local/bin/python \
        --python-preference=system \
        --frozen

RUN <<EOF cat> /RELEASE
{"version": "$VERSION",
 "commit": "$SOURCE_COMMIT",
 "date": "$BUILD_DATE",
 "distro": "test",
 "checksum": "$CHECKSUM",
 "source": "${GITHUB_SERVER_URL}/${GITHUB_REPOSITORY}/tree/${SOURCE_COMMIT:-master}/"
}
EOF

# ------------- python_prod_deps -------------
FROM build_deps AS python_prod_deps
ARG CHECKSUM
ENV CHECKSUM=$CHECKSUM
ARG VERSION
ENV VERSION=$VERSION
ARG BUILD_DATE
ENV BUILD_DATE=$BUILD_DATE
ARG SOURCE_COMMIT
ENV SOURCE_COMMIT=$SOURCE_COMMIT
ARG GITHUB_SERVER_URL
ENV GITHUB_SERVER_URL=$GITHUB_SERVER_URL
ARG GITHUB_REPOSITORY
ENV GITHUB_REPOSITORY=$GITHUB_REPOSITORY

LABEL date=$BUILD_DATE
LABEL version=$VERSION
LABEL checksum=$CHECKSUM
LABEL distro="builder-prod"

COPY docker/conf/config.toml /etc/xdg/pdm/config.toml

COPY . /code
WORKDIR /code

RUN pip install uv uwsgi

RUN --mount=type=cache,target=/root/.uv-cache \
    uv sync -v \
        --cache-dir=/root/.uv-cache \
        --python=/usr/local/bin/python \
        --python-preference=system \
        --no-dev --no-editable --frozen


# ------------- dist -------------
FROM python_base AS dist

ARG CHECKSUM
ENV CHECKSUM=$CHECKSUM
ARG VERSION
ENV VERSION=$VERSION
ARG BUILD_DATE
ENV BUILD_DATE=$BUILD_DATE
ARG SOURCE_COMMIT
ENV SOURCE_COMMIT=$SOURCE_COMMIT
ARG GITHUB_SERVER_URL
ENV GITHUB_SERVER_URL=$GITHUB_SERVER_URL
ARG GITHUB_REPOSITORY
ENV GITHUB_REPOSITORY=$GITHUB_REPOSITORY


WORKDIR /code
COPY --chown=hope:unicef --from=python_prod_deps /code/.venv /code/.venv
COPY --chown=hope:unicef --from=python_prod_deps /code/README.md /code/LICENSE /

ENV PATH=/code/.venv/bin:/usr/local/bin/:/usr/bin:/bin \
    PYTHONPATH="" \
    PYTHONDBUFFERED=1 \
    PYTHONDONTWRITEBYTCODE=1

RUN <<EOF cat> /RELEASE
{"version": "$VERSION",
 "commit": "$SOURCE_COMMIT",
 "date": "$BUILD_DATE",
 "distro": "dist",
 "checksum": "$CHECKSUM",
 "source": "${GITHUB_SERVER_URL}/${GITHUB_REPOSITORY}/tree/${SOURCE_COMMIT:-master}/"
}
EOF

VOLUME /var/run/app/
EXPOSE 8000
CMD ["run"]
ENTRYPOINT exec docker-entrypoint.sh "$0" "$@"

LABEL distro="final"
LABEL maintainer="hope@unicef.org"
LABEL org.opencontainers.image.authors="hope@unicef.org"
LABEL org.opencontainers.image.created="$BUILD_DATE"
LABEL org.opencontainers.image.description="HOPE Deduplication Engine"
LABEL org.opencontainers.image.documentation="https://github.com/unicef/hope-dedup-engine"
LABEL org.opencontainers.image.licenses="${GITHUB_SERVER_URL}/${GITHUB_REPOSITORY}/blob/${SOURCE_COMMIT:-master}/LICENSE"
LABEL org.opencontainers.image.revision=$SOURCE_COMMIT
LABEL org.opencontainers.image.source="${GITHUB_SERVER_URL}/${GITHUB_REPOSITORY}/tree/${SOURCE_COMMIT:-master}/"
LABEL org.opencontainers.image.title="Hope Deduplication Engine"
LABEL org.opencontainers.image.version="$VERSION"
LABEL org.opencontainers.image.vendor="UNICEF"

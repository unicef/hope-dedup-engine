FROM python:3.11-slim-bullseye as base

RUN apt-get update && apt-get install -y \
        gcc cmake build-essential curl libgdal-dev libgl1-mesa-glx\
    && apt-get clean && rm -rf /var/lib/apt/lists/* \
    && addgroup --system --gid 82 dde \
    && adduser \
        --system --uid 82 \
        --disabled-password --home /home/dde \
        --shell /sbin.nologin --group dde --gecos dde \
    && mkdir -p /code /tmp /data /static \
    && chown -R dde:dde /code /tmp /data /static

ENV PACKAGES_DIR=/packages
ENV PYPACKAGES=$PACKAGES_DIR/__pypackages__/3.11
ENV LIB_DIR=$PYPACKAGES/lib
ENV PYTHONPATH=$PYTHONPATH:$LIB_DIR:/code/src
ENV PATH=$PATH:$PYPACKAGES/bin

WORKDIR /code

FROM base as builder

WORKDIR $PACKAGES_DIR
RUN pip install pdm==2.9.3
ADD pyproject.toml ./
ADD ../pdm.toml.template ./pdm.toml
ADD pdm.lock ./
RUN pdm sync --prod --no-editable --no-self

FROM builder AS dev

RUN pdm sync --no-editable --no-self

WORKDIR /code
COPY .. ./

ADD docker/entrypoint.sh /usr/local/bin/entrypoint.sh
ENTRYPOINT ["entrypoint.sh"]


FROM base AS prd

ENV PATH=$PATH:/code/.venv/bin/

COPY --chown=dde:dde .. ./
COPY --chown=dde:dde --from=builder $PACKAGES_DIR $PACKAGES_DIR
USER dde

ADD docker/entrypoint.sh /usr/local/bin/entrypoint.sh
ENTRYPOINT ["entrypoint.sh"]
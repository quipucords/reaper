### Base Image
FROM registry.access.redhat.com/ubi9/ubi-minimal:9.1.0-1829 as base

ENV VIRTUAL_ENV=/opt/reaper/.venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
WORKDIR /opt/reaper/
COPY pyproject.toml poetry.lock ./

RUN microdnf update \
    && microdnf -y install python3 python3-pip \
    && python3 -m pip install -U pip \
    && python3 -m pip install awscli \
    && python3 -m pip install poetry \
    && poetry config virtualenvs.in-project true \
    && poetry install -n --no-dev

COPY bin/*.sh bin/
COPY reaper/*.py reaper/

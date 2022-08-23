### Base Image
FROM registry.access.redhat.com/ubi8/ubi-minimal:8.6-902 as base

ENV VIRTUAL_ENV=/opt/reaper/.venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
WORKDIR /opt/reaper/
COPY pyproject.toml poetry.lock ./

RUN microdnf update \
    && microdnf install python38 \
    && python3 -m pip install -U pip \
    && python3 -m pip install awscli \
    && python3 -m pip install poetry \
    && poetry config virtualenvs.in-project true \
    && poetry install -n --no-dev

COPY bin/ ./

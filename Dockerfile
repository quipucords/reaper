FROM python:3.8-alpine

RUN apk add --no-cache coreutils curl gcc musl-dev libffi-dev libressl-dev
RUN pip install awscli poetry
RUN apk del gcc musl-dev libffi-dev libressl-dev

WORKDIR /opt/reaper/
COPY poetry.lock pyproject.toml /opt/reaper/
COPY bin/ /opt/reaper/
RUN poetry install --no-dev

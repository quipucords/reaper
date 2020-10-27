FROM python:3.8-alpine

RUN apk add --no-cache coreutils curl
RUN pip install awscli

RUN mkdir -p /opt/reaper/
COPY bin/ /opt/reaper/

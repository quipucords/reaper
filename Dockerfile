FROM python:3.6-alpine

RUN apk add --no-cache coreutils curl
RUN pip install awscli

ARG BASE_IMAGE=docker.m.daocloud.io/library/python:3.12.12-slim-bookworm@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c
FROM ${BASE_IMAGE}

ARG PIP_INDEX_URL=https://pypi.org/simple

COPY requirements.lock /tmp/prguard-requirements.lock
RUN python -m pip install \
      --no-cache-dir \
      --require-hashes \
      --index-url "${PIP_INDEX_URL}" \
      --requirement /tmp/prguard-requirements.lock \
    && rm /tmp/prguard-requirements.lock \
    && groupadd --gid 65532 prguard \
    && useradd --uid 65532 --gid 65532 --home-dir /home/prguard --no-create-home prguard

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONNOUSERSITE=1

USER 65532:65532
WORKDIR /workspace

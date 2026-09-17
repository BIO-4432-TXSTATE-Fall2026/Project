# Template image; replace with one that provides a pipeline tool.
FROM debian:bookworm-slim

# Nextflow uses ps to collect task metrics.
RUN apt-get update \
    && apt-get install -y --no-install-recommends procps \
    && rm -rf /var/lib/apt/lists/*

# The preprocessing stage's image: the project CLI and nothing else. Build from the
# repository root, not from containers/, because the build copies src/ and pyproject.toml:
#
#   pixi run build-container preprocess
#
# One Dockerfile per stage, named for it. A stage's processes all run the same tools, and
# the stage is the unit that gets scheduled, so the image follows the stage rather than
# the process.
FROM python:3.12-slim

# Nextflow shells out to ps to collect task metrics; the slim image has no procps.
RUN apt-get update \
    && apt-get install -y --no-install-recommends procps \
    && rm -rf /var/lib/apt/lists/*

# Install the package itself, which brings boto3 with it. Copying only what the build
# needs keeps an edit to the workflows or the docs from invalidating this layer.
COPY pyproject.toml /src/
COPY src/python /src/src/python
RUN pip install --no-cache-dir /src && rm -rf /src

# Tasks run as the submitting user under Apptainer, so nothing here writes to $HOME.
WORKDIR /work

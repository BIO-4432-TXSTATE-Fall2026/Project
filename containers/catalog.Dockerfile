# The cataloging stage's image: the project CLI to sync genomes, and inTRuder's repeat
# finder to turn them into loci. Build from the repository root, not from containers/,
# because the build copies src/, submodules/, and both pyproject.toml files:
#
#   pixi run build-container catalog
#
# One Dockerfile per stage, named for it, the same rule preprocess.Dockerfile follows.
#
# Micromamba rather than python:slim, because pytrf and pyfastx are C extensions that
# bioconda ships built and PyPI does not. Installing them with pip means compiling htslib
# and friends inside the image for every build; `[tool.pixi.feature.catalog]` names them
# from conda for the same reason.
FROM mambaorg/micromamba:2.3-debian12-slim

# Nextflow shells out to ps to collect task metrics; the slim image has no procps.
USER root
RUN apt-get update \
    && apt-get install -y --no-install-recommends procps bzip2 \
    && rm -rf /var/lib/apt/lists/*
USER $MAMBA_USER

# The runtime dependencies of both packages, from conda. pytrf brings pyfastx with it,
# but trcore.io.fasta imports pyfastx directly, so it is named here too -- the same
# reasoning inTRuder's `fasta` extra gives.
RUN micromamba install -y -n base -c conda-forge -c bioconda \
        python=3.12 \
        pytrf \
        pyfastx \
        boto3 \
        numpy \
        "pandas>=3.0.5" \
        tqdm \
        pip \
    && micromamba clean --all --yes

# Activate the environment for the RUN below, so pip is micromamba's.
ARG MAMBA_DOCKERFILE_ACTIVATE=1

# Both packages, installed with --no-deps: conda above already provides every runtime
# dependency, and letting pip resolve them again would pull PyPI wheels over the built
# conda ones. Copying only what the build needs keeps an edit to the workflows or the
# docs from invalidating these layers.
COPY pyproject.toml /src/hmp/
COPY src/python /src/hmp/src/python
COPY submodules/inTRuder/pyproject.toml submodules/inTRuder/README.md /src/intruder/
COPY submodules/inTRuder/src/python /src/intruder/src/python
RUN pip install --no-cache-dir --no-deps /src/hmp /src/intruder \
    && rm -rf /src

# Tasks run as the submitting user under Apptainer, so nothing here writes to $HOME.
WORKDIR /work

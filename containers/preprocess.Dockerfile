# The preprocessing stage's image: the project CLI and nothing else. Build from the
# repository root, not from containers/, because the build copies src/, pyproject.toml
# and pixi.lock:
#
#   pixi run build-container preprocess
#
# One Dockerfile per stage, named for it, and one pixi environment per stage to match. A
# stage's processes all run the same tools, and the stage is the unit that gets
# scheduled, so the image follows the stage rather than the process.
#
# The dependencies come from pixi.lock rather than from an install line here: a second
# dependency list maintained in a Dockerfile is one that drifts from the environment the
# pipeline was developed and tested against.
FROM ghcr.io/prefix-dev/pixi:0.78.0-bookworm AS build

# /app is where the environment is installed and where it stays: pixi records absolute
# paths in the prefix -- the editable install of hmp_project is a .pth file holding
# /app/src/python -- so the runtime stage below has to mount it back at the same path.
WORKDIR /app

# Only what the solve and the editable install read, so an edit to the workflows or the
# docs does not invalidate this layer.
COPY pyproject.toml pixi.lock ./
COPY src/python ./src/python

# --frozen installs exactly what pixi.lock holds and never re-solves, so the image is
# the environment the pipeline was tested against. Not --locked: that also re-validates
# the lock against the whole manifest, which means resolving every feature's path
# dependencies -- including the inTRuder submodule this context leaves out on purpose --
# and fails with "lock file not up-to-date" when one is missing. The lock is verified
# where the whole workspace exists, not here. --no-progress keeps the build log to one
# line per step instead of redrawing a bar.
RUN pixi install --frozen --no-progress -e preprocess

FROM debian:bookworm-slim

# Nextflow shells out to ps to collect task metrics; the slim image has no procps. This
# stays an apt package rather than joining the pixi environment: it is a container
# concern rather than a project dependency, and conda-forge's procps-ng has no macOS
# build, so naming it in pyproject.toml would cost the developer environments.
RUN apt-get update \
    && apt-get install -y --no-install-recommends procps \
    && rm -rf /var/lib/apt/lists/*

# The environment, then the source it points at: the editable install means hmp_project
# is imported from src/python, so both halves travel and the paths match the build stage.
COPY --from=build /app/.pixi/envs/preprocess /app/.pixi/envs/preprocess
COPY --from=build /app/src/python /app/src/python

# Tasks run `python -m hmp_project` directly (params.cli in nextflow.config), so the
# environment is on PATH rather than entered by an entrypoint: Apptainer ignores a Docker
# ENTRYPOINT, and conf/docker.config runs the image as the calling uid. Nothing in the
# prefix needs an activation script -- there is no etc/conda/activate.d -- so PATH alone
# is the whole activation.
ENV PATH=/app/.pixi/envs/preprocess/bin:$PATH

# And again for login shells, because Debian's /etc/profile builds PATH from scratch
# and would drop the line above: `apptainer shell` and an interactive `docker run`
# both give you one, which is where this image gets debugged.
RUN echo 'export PATH=/app/.pixi/envs/preprocess/bin:$PATH' > /etc/profile.d/pixi-env.sh

# Tasks run as the submitting user under Apptainer, so nothing here writes to $HOME.
WORKDIR /work

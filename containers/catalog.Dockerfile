# The cataloging stage's image: the project CLI to sync genomes, and inTRuder's repeat
# finder to turn them into loci. Build from the repository root, not from containers/,
# because the build copies src/, submodules/, pixi.lock and both pyproject.toml files:
#
#   pixi run build-container catalog
#
# One Dockerfile per stage, named for it, and one pixi environment per stage to match --
# the same rule preprocess.Dockerfile follows.
#
# The `catalog` environment is why this image needs no dependency list of its own:
# pixi.lock already pins pytrf and pyfastx to bioconda builds, which is what a hand
# written install line here was working around. They are C extensions that bioconda ships
# built and PyPI does not, so resolving them from PyPI would compile htslib and friends
# inside the image on every build.
FROM ghcr.io/prefix-dev/pixi:0.78.0-bookworm AS build

# /app is where the environment is installed and where it stays: pixi records absolute
# paths in the prefix -- the editable installs are .pth files holding /app/src/python and
# /app/submodules/inTRuder/src/python -- so the runtime stage has to mount both back at
# the same paths.
WORKDIR /app

# Only what the solve and the two editable installs read, so an edit to the workflows or
# the docs does not invalidate these layers. inTRuder's README is here because its
# pyproject names it as the package readme, and the build backend reads it.
COPY pyproject.toml pixi.lock ./
COPY src/python ./src/python
COPY submodules/inTRuder/pyproject.toml submodules/inTRuder/README.md ./submodules/inTRuder/
COPY submodules/inTRuder/src/python ./submodules/inTRuder/src/python

# --frozen installs exactly what pixi.lock holds and never re-solves, so the image is
# the environment the pipeline was tested against. Not --locked: that also re-validates
# the lock against the whole manifest, which means resolving every feature's path
# dependencies -- including the inTRuder submodule this context leaves out on purpose --
# and fails with "lock file not up-to-date" when one is missing. The lock is verified
# where the whole workspace exists, not here. --no-progress keeps the build log to one
# line per step instead of redrawing a bar.
RUN pixi install --frozen --no-progress -e catalog

FROM debian:bookworm-slim

# Nextflow shells out to ps to collect task metrics; the slim image has no procps. This
# stays an apt package rather than joining the pixi environment: it is a container
# concern rather than a project dependency, and conda-forge's procps-ng has no macOS
# build, so naming it in pyproject.toml would cost the developer environments.
#
# bzip2 is no longer installed here: the environment brings it, because python links
# libbz2 and the conda package ships the command line tool beside it. TR_CATALOG needs it
# to unpack HMP's .nuc.fsa.bz2 genomes, which pyfastx cannot read.
RUN apt-get update \
    && apt-get install -y --no-install-recommends procps \
    && rm -rf /var/lib/apt/lists/*

# The environment, then the two source trees it points at: the editable installs mean
# hmp_project and intruder are imported from src/python, so every half travels and the
# paths match the build stage.
COPY --from=build /app/.pixi/envs/catalog /app/.pixi/envs/catalog
COPY --from=build /app/src/python /app/src/python
COPY --from=build /app/submodules/inTRuder/src/python /app/submodules/inTRuder/src/python

# Tasks run `python -m hmp_project` and `trf` directly (params.cli and params.trf in
# nextflow.config), so the environment is on PATH rather than entered by an entrypoint:
# Apptainer ignores a Docker ENTRYPOINT, and conf/docker.config runs the image as the
# calling uid. Nothing in the prefix needs an activation script -- there is no
# etc/conda/activate.d -- so PATH alone is the whole activation.
ENV PATH=/app/.pixi/envs/catalog/bin:$PATH

# And again for login shells, because Debian's /etc/profile builds PATH from scratch
# and would drop the line above: `apptainer shell` and an interactive `docker run`
# both give you one, which is where this image gets debugged.
RUN echo 'export PATH=/app/.pixi/envs/catalog/bin:$PATH' > /etc/profile.d/pixi-env.sh

# Tasks run as the submitting user under Apptainer, so nothing here writes to $HOME.
WORKDIR /work

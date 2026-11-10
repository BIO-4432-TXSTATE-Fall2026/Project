# The read filter's image: the project CLI, which owns the stream, with lbzip2 to
# decompress and bbduk to gate. Build from the repository root, not from containers/,
# because the build copies src/, pyproject.toml and pixi.lock:
#
#   pixi run build-container filter
#
# One Dockerfile per stage, named for it, and one pixi environment per stage to match --
# the same rule preprocess.Dockerfile follows. TR_LOCI, which builds the gate's reference,
# runs in the catalog image instead, since it reads genomes through inTRuder.
#
# The `filter` environment is why this image needs no dependency list of its own:
# pixi.lock pins lbzip2 and bbmap, and bbmap brings the JDK bbduk runs on.
FROM ghcr.io/prefix-dev/pixi:0.78.0-bookworm AS build

# /app is where the environment is installed and where it stays: pixi records absolute
# paths in the prefix -- the editable install of hmp_project is a .pth file holding
# /app/src/python -- so the runtime stage below has to mount it back at the same path.
WORKDIR /app

# Only what the solve and the editable install read, so an edit to the workflows or the
# docs does not invalidate this layer.
COPY pyproject.toml pixi.lock ./
COPY src/python ./src/python

# --frozen, not --locked, for the reason preprocess.Dockerfile gives: --locked resolves
# every feature's path dependencies, including the inTRuder submodule this context
# leaves out.
RUN pixi install --frozen --no-progress -e filter

FROM debian:bookworm-slim

# procps for Nextflow's task metrics, as in the other images.
RUN apt-get update \
    && apt-get install -y --no-install-recommends procps \
    && rm -rf /var/lib/apt/lists/*

COPY --from=build /app/.pixi/envs/filter /app/.pixi/envs/filter
COPY --from=build /app/src/python /app/src/python

# Tasks run `python -m hmp_project filter`, which spawns lbzip2 and bbduk.sh by name, and
# bbduk.sh calls java by name in turn. All of them are in the prefix's bin/ on linux-64,
# so PATH is the whole activation, as in the other images.
ENV PATH=/app/.pixi/envs/filter/bin:$PATH

# And again for login shells, because Debian's /etc/profile builds PATH from scratch.
RUN echo 'export PATH=/app/.pixi/envs/filter/bin:$PATH' > /etc/profile.d/pixi-env.sh

# Tasks run as the submitting user under Apptainer, so nothing here writes to $HOME.
WORKDIR /work

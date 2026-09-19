# Workflows

The Nextflow pipeline: what it is made of and how a piece is added. To run it on the
cluster, see `docs/HPC/RUNNING.md`; for SLURM itself, `docs/HPC/SLURM.md`.

| Path                     | What lives there                                        |
| ------------------------ | ------------------------------------------------------- |
| `workflows/main.nf`      | The entry workflow; picks a stage and declares outputs   |
| `workflows/modules/`     | One process per file                                     |
| `workflows/modules/preprocess/` | The preprocessing processes (`docs/workflows/preprocess/`) |
| `conf/`                  | Resources, executor, and container profiles              |
| `tests/workflow/`        | nf-test tests, mirroring the layout of `workflows/`      |

## Stages

One run does one stage, chosen with `--stage`. They are separate because they differ in
kind, not just in content: the analysis consumes committed inputs and writes results, and
preprocessing *produces* committed inputs.

| Stage        | Does                                          | Publishes to     |
| ------------ | --------------------------------------------- | ---------------- |
| `preprocess` | Rebuilds the tables in `data/derived/`        | the working tree |
| `pipeline`   | The analysis. Does not exist yet              | `results/`       |

```sh
pixi run pipeline --stage preprocess
```

`pipeline` is the default and has no analysis behind it, so a run with no `--stage` stops
with a message rather than doing anything. That is deliberate: preprocessing writes into
the working tree, so it is asked for by name and never entered by accident.

Nextflow 26's strict parser has no `-entry`, so the stage is a parameter and `main.nf`
branches on it. An unknown stage stops the run rather than quietly doing nothing.

## Outputs

Every published file is declared in the `output` block of `main.nf` and named by a
`publish:` entry in the entry workflow. Output paths are relative to `outputDir`, which
`nextflow.config` points at `results/` for the analysis and at `data/` for
preprocessing — the one place where a run writes into the working tree, and only because
those tables are committed. See `docs/workflows/preprocess/`.

A stage that is not running publishes nothing: its channel is empty, and its target
simply produces no files.

## Configuration

`conf/base.config` sets the defaults every process gets — one core, 2 GB, an hour, and
one retry on a scheduler kill — and adjusts them per `label`. A process asks for more by
carrying a label, not by hardcoding resources:

```groovy
process {
    withLabel: 'preprocess' {
        memory = 4.GB
        time = 8.h
    }
}
```

Profiles are composable and named on the command line: `slurm` for the executor,
`apptainer` or `docker` for images. `conf/containers.config` maps a stage's label to its
image, so every process in a stage runs in the same container and a new one needs no entry
there.

Notifications are not configuration: `workflows/modules/notify.nf` holds all of them, and
`nextflow.config` only carries the topic and server. See `docs/HPC/RUNNING.md`.

## Adding a process

1. Write `workflows/modules/<area>/<name>.nf`, one process per file, named in
   `SCREAMING_SNAKE_CASE`. Give it a `label` if the defaults are too small, and a `stub:`
   block if the real script is slow or needs the network.
2. Include it in `main.nf` and wire it into a stage.
3. If it publishes, add a `publish:` entry and a matching target in the `output` block.
4. Add `tests/workflow/modules/<area>/<name>.nf.test` at the same path as the module.
5. Give it its stage's label, which is what picks up both the stage's resources and its
   image. A stage that needs a tool no image provides gets a new
   `containers/<stage>.Dockerfile`, mapped in `conf/containers.config`.

## Testing

```sh
pixi run test-workflow                       # everything
pixi run -e nextflow nf-test test tests/workflow/modules/preprocess/sra_metadata.nf.test
```

Tests run in `.nf-test/`, never in `work/` or the working tree. A test for a process that
downloads or takes hours declares `options "-stub"` and asserts on the stub's output: it
checks the wiring — that every input is staged and every output comes back named — and
leaves the science to the tests in `tests/python/`.

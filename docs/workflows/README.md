# Workflows

The Nextflow pipeline: what it is made of and how a piece is added. To run it on the
cluster, see `docs/HPC/RUNNING.md`; for SLURM itself, `docs/HPC/SLURM.md`.

| Path                     | What lives there                                        |
| ------------------------ | ------------------------------------------------------- |
| `workflows/main.nf`      | The entry workflow; picks a stage and declares outputs   |
| `workflows/modules/`     | One process per file                                     |
| `workflows/modules/data/`| The data stage's processes (`docs/workflows/data/`)      |
| `conf/`                  | Resources, executor, and container profiles              |
| `tests/workflow/`        | nf-test tests, mirroring the layout of `workflows/`      |

## Stages

One run does one stage, chosen with `--stage`. They are separate because they differ in
kind, not just in content: the analysis consumes committed inputs and writes results, and
data compilation *produces* committed inputs.

| Stage      | Does                                              | Publishes to   |
| ---------- | ------------------------------------------------- | -------------- |
| `pipeline` | The analysis. The default; a template for now     | `results/`     |
| `data`     | Rebuilds the tables in `data/derived/`            | the working tree |

```sh
pixi run pipeline                     # --stage pipeline, implied
pixi run pipeline --stage data
```

Nextflow 26's strict parser has no `-entry`, so the stage is a parameter and `main.nf`
branches on it. An unknown stage stops the run rather than quietly doing nothing.

## Outputs

Every published file is declared in the `output` block of `main.nf` and named by a
`publish:` entry in the entry workflow. Output paths are relative to `outputDir`, which
`nextflow.config` points at `results/` for the analysis and at `data/` for the data
stage — the one place where a run writes into the working tree, and only because those
tables are committed. See `docs/workflows/data/`.

A stage that is not running publishes nothing: its channel is empty, and its target
simply produces no files.

## Configuration

`conf/base.config` sets the defaults every process gets — one core, 2 GB, an hour, and
one retry on a scheduler kill — and adjusts them per `label`. A process asks for more by
carrying a label, not by hardcoding resources:

```groovy
process {
    withLabel: 'data' {
        memory = 4.GB
        time = 8.h
    }
}
```

Profiles are composable and named on the command line: `slurm` for the executor,
`apptainer` or `docker` for images. `conf/containers.config` maps a process name to its
image; a process with no entry there runs from the environment instead, which is what the
data stage does.

## Adding a process

1. Write `workflows/modules/<area>/<name>.nf`, one process per file, named in
   `SCREAMING_SNAKE_CASE`. Give it a `label` if the defaults are too small, and a `stub:`
   block if the real script is slow or needs the network.
2. Include it in `main.nf` and wire it into a stage.
3. If it publishes, add a `publish:` entry and a matching target in the `output` block.
4. Add `tests/workflow/modules/<area>/<name>.nf.test` at the same path as the module.
5. If it needs a tool the environment lacks, add `containers/<name>/Dockerfile` and map
   the process to the image in `conf/containers.config`.

## Testing

```sh
pixi run test-workflow                       # everything
pixi run -e nextflow nf-test test tests/workflow/modules/data/sra_metadata.nf.test
```

Tests run in `.nf-test/`, never in `work/` or the working tree. A test for a process that
downloads or takes hours declares `options "-stub"` and asserts on the stub's output: it
checks the wiring — that every input is staged and every output comes back named — and
leaves the science to the tests in `tests/python/`.

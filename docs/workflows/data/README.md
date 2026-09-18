# The data stage

`--stage data` compiles the committed tables in `data/derived/` from their upstream
catalogs. What each table means, which source it came from, and where its traps are is in
`docs/data/README.md`; this page is about the machinery that builds it.

```sh
pixi run pipeline --stage data -profile slurm --slurm_queue shared
```

## Why it is a stage of its own

The analysis reads `data/derived/`. This stage writes it. Running it is a deliberate
act — the output is committed, so a rebuild shows up as a diff in version control — and
not something an analysis run should redo on the way past. Keeping it out of
`--stage pipeline` also keeps the analysis offline: nothing in a normal run reaches S3.

It is still a Nextflow stage rather than a shell script because the work is per-table,
long, and belongs on a compute node. One job per table, resources and retries from
`conf/base.config`, and `-resume` if one table fails and the others are done.

## Modules

| Process            | Builds                          | From                             |
| ------------------ | ------------------------------- | -------------------------------- |
| `SRA_RUN_METADATA` | `data/derived/hmp-sra-runs.tsv` | `manifests/sra-metadata-freeze.json` |

### `SRA_RUN_METADATA`

Sync, extract, delete — one task, in this order, because the middle step is the only
reason to do the first:

```sh
<cli> sync sra-metadata-freeze.json --data-dir .
<cli> extract sra-metadata-freeze.json --data-dir . --from-lock ... --out hmp-sra-runs.tsv
rm -rf ./sra-metadata-freeze
```

The catalog is 2.3 GB and is not partitioned by accession, so the rows for 274 HMP samples
can only be had by reading all of it. It is downloaded into the task directory, read once,
and deleted there. Splitting sync and extract into two processes would mean parking those
2.3 GB in `work/` between them; one task keeps it transient. A failed task leaves it
behind until `nextflow clean`.

Which samples to keep comes from lockfiles, not a list in the workflow:
`params.hmp_sample_locks` globs the three HMP body-site locks, and `extract --from-lock`
reads the accessions out of their keys. The specs that define what was synced also define
what is extracted, so the two cannot drift.

## Parameters

| Parameter            | Default                                       |
| -------------------- | --------------------------------------------- |
| `cli`                | the project CLI, through Pixi's default environment |
| `sra_metadata_spec`  | `manifests/sra-metadata-freeze.json`          |
| `hmp_sample_locks`   | the three `manifests/hmp-*.lock.json` body-site locks |
| `hmp_sra_runs_table` | `hmp-sra-runs.tsv`                            |

## Two traps

**Tasks run the CLI, not a container.** There is no image for the data stage; the task
calls `pixi run --manifest-path <root>/pyproject.toml python -m hmp_project`, so Pixi's
default environment must exist on the compute node — run `pixi install` first. It is
spelled as a command and not as the `sync` and `extract` Pixi tasks on purpose: a *named*
task runs in the workspace root, which would download the catalog into the clone, while a
command runs where it was called, which is the task directory.

**Manifests are staged as copies.** `sync` rewrites the spec's lockfile. With the default
symlink staging, a task would be writing through a link into `manifests/`, so the process
sets `stageInMode 'copy'`. The spec's lockfile is staged although the command line never
names it, because `extract` looks for it beside the spec.

## Adding a table

1. Create the spec with `pixi run new`, and sync it once by hand to see what you get.
2. Add the process to `workflows/modules/data/`, with `label 'data'` and a `stub:` block
   that writes an empty table; keep the catalog inside the task directory and delete it.
3. Wire it into the `DATA` workflow in `workflows/main.nf` and emit its output.
4. Add the nf-test under `tests/workflow/modules/data/`, with `options "-stub"`.
5. Write the table's page in `docs/data/`, and add it to the table there.

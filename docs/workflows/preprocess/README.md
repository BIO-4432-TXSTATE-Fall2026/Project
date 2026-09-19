# The preprocessing stage

`--stage preprocess` compiles the committed tables in `data/derived/` from their upstream
catalogs. What each table means, which source it came from, and where its traps are is in
`docs/data/README.md`; this page is about the machinery that builds it.

```sh
pixi run pipeline --stage preprocess -profile slurm,apptainer --slurm_queue shared
```

## Why it is a stage of its own

The analysis reads `data/derived/`. This stage writes it. Running it is a deliberate
act — the output is committed, so a rebuild shows up as a diff in version control — and
not something an analysis run should redo on the way past. Keeping it out of
`--stage pipeline` also keeps the analysis offline: nothing in an analysis run reaches S3.

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
| `cli`                | `python -m hmp_project`, as installed in the stage's image |
| `sra_metadata_spec`  | `manifests/sra-metadata-freeze.json`          |
| `hmp_sample_locks`   | the three `manifests/hmp-*.lock.json` body-site locks |
| `hmp_sra_runs_table` | `hmp-sra-runs.tsv`                            |

## Two traps

**Tasks need a container profile.** The stage runs in `containers/preprocess.Dockerfile`,
which installs the project itself, so `params.cli` is a plain `python -m hmp_project` and
the compute nodes need no Pixi environment. Run with `-profile apptainer` on the cluster
or `-profile docker` locally; without one, the task falls back to whatever `python` the
node happens to have and will not find the package.

**Manifests are staged as copies.** `sync` rewrites the spec's lockfile. With the default
symlink staging, a task would be writing through a link into `manifests/`, so the process
sets `stageInMode 'copy'`. The spec's lockfile is staged although the command line never
names it, because `extract` looks for it beside the spec.

## Adding a table

1. Create the spec with `pixi run new`, and sync it once by hand to see what you get.
2. Add the process to `workflows/modules/preprocess/`, with `label 'preprocess'` and a
   `stub:` block that writes an empty table; keep the catalog inside the task directory
   and delete it.
3. Wire it into the `PREPROCESS` workflow in `workflows/main.nf` and emit its output,
   wrapped in `announceDone` so the phase reports itself.
4. Add the nf-test under `tests/workflow/modules/preprocess/`, with `options "-stub"`.
5. Write the table's page in `docs/data/`, and add it to the table there.

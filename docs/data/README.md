# Derived data

Small tables the CLI builds from downloaded datasets and that are **committed** to the
repository, in `data/derived/`. Everything else under `data/` is downloaded bytes and is
ignored by git; what was fetched is recorded in `manifests/`.

A table earns a place here when it is small, we produced it, and rebuilding it is
expensive enough that nobody should have to. One Markdown file per table says what the
lockfile cannot: why this source, what the columns mean, and where the traps are.

Do not hand-write anything in `data/derived/`. Rebuild with the command each table's page
gives, so the file always matches what the code produces.

## Tables

| Table | Source | Page |
| ----- | ------ | ---- |
| _(none built yet)_ | | |

## Sources

### SRA run metadata (`manifests/sra-metadata-freeze.json`)

`s3://sra-pub-metadata-us-east-1` holds two copies of the SRA run table, and the choice
between them matters more than it looks.

- **`sra/metadata_json/` — what we use.** One frozen snapshot, `09_01_2020`, 60 gzipped
  JSON Lines files, 2.3 GB, last modified 2020-09-09 and untouched since. Stable keys
  mean a re-sync reports nothing changed, so the lock over it stays meaningful. JSON Lines
  needs no Parquet reader, so the project's only dependency is still boto3.
- **`sra/metadata/` — what we avoid.** The current table: 30 Parquet files, 13.1 GB,
  rewritten by a fresh Trino query every night. Every key carries the query's timestamp,
  so a re-sync shows all 30 files removed and 30 added, and the lock churns daily without
  recording anything real.

**The freeze covers everything released up to 2020-09-01.** That includes every dataset in
`docs/todo.md`: HMP1 (2010–2012), Salter et al. (2014), Zeller et al. (2014). Anything
published after that date is not in it and would need the Parquet table.

Neither copy is partitioned by accession, and the accessions are scattered across all 60
shards, so there is no way to fetch just the rows for one sample. `extract` reads the
whole thing once. That is the one-time cost of the source not being indexed; because the
snapshot never changes, you pay it once and keep the result.

#### Two traps

**A sample's runs are not all alike.** HMP samples carry their 16S amplicon runs
alongside their Illumina WGS runs, under the same `SRS` accession. Joining on sample alone
pulls in 454 amplicon runs that are not the WGS data this project analyses, which would
quietly corrupt any batch label built from them. Extracted tables keep `platform`,
`instrument`, and `assay_type` so callers can filter; nothing upstream does it for you.

**The 2.3 GB is temporary.** Sync it, extract what you need, delete it. Re-syncing is how
you rebuild, and `sync` checksums each shard so an interrupted download resumes rather
than starting over. Do not leave it on cluster shared storage.

## Rebuilding

Run on a compute node, not a login node — `docs/HPC/SLURM.md`. One core and a couple of
gigabytes is enough; the work is dominated by the download.

```sh
pixi run sync manifests/sra-metadata-freeze.json
pixi run extract manifests/sra-metadata-freeze.json \
  --from-lock manifests/hmp-stool.lock.json \
  --out data/derived/<table>.tsv
rm -rf data/sra-metadata-freeze     # the catalog is not worth keeping
```

`--from-lock` takes the accessions out of a lockfile's keys, so the samples a spec already
covers drive the extract without retyping a few hundred of them. `--accession` adds
individual samples or studies, which is how the Salter and Zeller studies are selected.
`extract` leaves output newer than the lock alone unless given `--force`, so re-running it
after a plain `sync` costs nothing.

# Project

## Setup

Install [Pixi](https://pixi.sh), then:

```sh
pixi install          # Python environment
pixi run -e r r-restore  # R packages from src/R/renv.lock (optional)
```

## Layout

| Path                            | Purpose                                                   |
| ------------------------------- | --------------------------------------------------------- |
| `src/python/hmp_project/providers` | Downloads remote files as-is (e.g. S3). No preprocessing. |
| `src/python/hmp_project/datasets` | Uses a provider to select a dataset (e.g. HMP).          |
| `src/python/hmp_project/cli.py`   | The only thing that writes `manifests/`.                 |
| `src/R`                         | R code; packages are managed by renv.                     |
| `manifests`                     | What was downloaded and when. Committed.                  |
| `data`                          | Downloaded files. Not committed.                          |
| `workflows`                     | Nextflow pipeline; entry point is `workflows/main.nf`.   |
| `workflows/modules`             | Reusable Nextflow processes.                              |
| `conf`                          | Nextflow configs and profiles, included by `nextflow.config`. |
| `containers`                    | One `<name>/Dockerfile` per image, published to GHCR.     |
| `tests/workflow`                | nf-test tests for the pipeline and modules.               |

## Downloading data

Create a spec, then sync it:

```sh
pixi run new hmp-hmqcp --dataset hmp --prefix HHS/HMQCP \
  --include 'otu_table_psn_v*.txt.gz' --exclude '*.old'
pixi run sync manifests/hmp-hmqcp.json --dry-run
pixi run sync manifests/hmp-hmqcp.json
```

`manifests/<name>.json` records what to fetch. `manifests/<name>.lock.json` records each
file's size, ETag, upstream timestamp, and sha256, plus a history entry for every sync
that added, changed, removed, or downloaded something. Files land in `data/<name>/`.
A name may contain `/` to group specs: `new contaminants/kit` writes
`manifests/contaminants/kit.json`, and its files land in `data/contaminants/kit/`.

`sync --no-download` records the remote listing in the lock without fetching anything;
those files have a null `sha256` until a real sync downloads them.

Datasets are `hmp`, `hmpdcc` (iHMP and a per-run copy of HMP1 from the HMP DACC),
`pmc` (PubMed Central open-access articles and their supplementary files),
`sra` (NCBI SRA run data), and `sra-metadata` (SRA run metadata as Parquet). Each
lists the AWS regions it is hosted in; `new --region` takes a region code or an
unambiguous part of one, such as `east`, and rejects regions the dataset is not hosted in:

```sh
pixi run new sra-metadata --dataset sra-metadata --region east --prefix sra/metadata
```

`sra` is selected by run accession instead of by prefix, because its bucket holds
every public SRA run and listing a prefix broad enough to cover several runs would take
hours:

```sh
pixi run new salter --dataset sra --accession ERR1014220 --accession ERR1014221
```

Each run lands in `data/<name>/<accession>/`. Find run accessions with the
`sra-metadata` dataset first.

Those objects are `.sra` archives rather than FASTQ. `convert` extracts uncompressed
FASTQ beside each synced archive with `fasterq-dump`, keeping the archive so `sync` still
matches the lock, and skips runs already converted:

```sh
pixi run sync manifests/salter.json
pixi run convert manifests/salter.json
```

`fasterq-dump` comes from sra-tools in the `sra` environment, which `pixi run convert`
uses. It is not available on Windows. FASTQ is several times the archive's size, and
conversion temporarily needs about that much free space again.

Browse what HMP offers with
`aws s3 ls --no-sign-request s3://human-microbiome-project/HHS/`.

## Pipeline

Pixi's `nextflow` environment provides Nextflow, nf-test, and the JDK they run on:

```sh
pixi run pipeline --stage preprocess -profile docker       # local, Docker
pixi run pipeline --stage preprocess -profile slurm,apptainer \
  --slurm_queue <partition> --slurm_account <account>      # cluster
pixi run test-workflow
```

On SLURM, launch from a filesystem the compute nodes share; see `docs/HPC/RUNNING.md` and
`docs/HPC/SLURM.md`.

A run does one stage, chosen with `--stage`. `preprocess` rebuilds the committed tables in
`data/derived/` from their upstream catalogs; `pipeline`, the analysis, has nothing behind
it yet and stops if asked for. How the pipeline is put together is in `docs/workflows/`,
and preprocessing in `docs/workflows/preprocess/`.

Each stage has one image, mapped to its label in `conf/containers.config`. Running the
Containers workflow from the GitHub Actions tab builds every
`containers/<stage>.Dockerfile` and publishes it as
`ghcr.io/bio-4432-txstate-fall2026/project/<stage>`; Apptainer pulls it from there. To
build one locally, run `pixi run build-container <stage>`.

## Development

```sh
pixi run test
pixi run lint
pixi run format
```

To add an R package, install it from R inside `src/R` with `renv::install()`, then run
`pixi run -e r r-snapshot`.

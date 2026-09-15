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
| `src/python/hmp_project/provider` | Downloads remote files as-is (e.g. S3). No preprocessing. |
| `src/python/hmp_project/datasets` | Uses a provider to select a dataset (e.g. HMP).          |
| `src/python/hmp_project/cli.py`   | The only thing that writes `manifests/`.                 |
| `src/R`                         | R code; packages are managed by renv.                     |
| `manifests`                     | What was downloaded and when. Committed.                  |
| `data`                          | Downloaded files. Not committed.                          |

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

Browse what HMP offers with
`aws s3 ls --no-sign-request s3://human-microbiome-project/HHS/`.

## Development

```sh
pixi run test
pixi run lint
pixi run format
```

To add an R package, install it from R inside `src/R` with `renv::install()`, then run
`pixi run -e r r-snapshot`.

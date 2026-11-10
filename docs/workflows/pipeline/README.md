# The pipeline stage

`--stage pipeline` is the analysis. Its first part streams the HMP1 shotgun reads from S3
through a k-mer gate built from the TR catalog and keeps only the reads that touch a
locus, plus per-sample read counts. Allele calling, the stutter model and everything after
read that output; none of them exists yet (`docs/todo.md` §3).

```sh
pixi run pipeline --stage pipeline -profile slurm,apptainer --slurm_queue shared
```

## Why the reads are streamed

The 274 samples are 1.77 TB of `.tar.bz2` across
`manifests/hmp/{stool,tongue-dorsum,subgingival-plaque}.lock.json`, and decompress 3.5–4.1×
to ~6.5 TB of FASTQ. Nothing that size can land. So no sample is ever downloaded: each is
read from S3, decompressed, unpacked and gated in one pipe, and only the hits are written.

That pipe belongs to the project CLI (`hmp_project filter`), not to a shell line in a
module:

```
open_stream(key) → lbzip2 -dc → tarfile (mode 'r|') → bbduk → gzip writer
```

The CLI checks every stage's exit status. A shell pipeline's status is its last command's,
so a transfer dying part way through would hand on the reads that had arrived and look like
a shallow sample. For a cross-sample entropy measurement that is the worst error available,
so `filter` writes nothing unless every stage exited cleanly. (`nextflow.config` also sets
`pipefail` for every task, which closes the same hole in the shell pipes elsewhere.)

Two properties of the tarballs shape the pipe:

- **Member order varies.** `.1`, `.2` and `.singleton` arrive in different orders in
  different samples, so members are routed by name, never by position.
- **Pairs cannot be streamed together.** A mate's partner may be gigabytes later in the
  stream. Every read is gated single-ended instead. The names carry `/1` and `/2`, so the
  survivors re-pair by name later, and there are few enough of them for that to cost
  nothing. bbduk runs with `int=f`, because it otherwise sees `/1` then `/2` and treats the
  stream as interleaved pairs.

## Modules

| Process          | Image     | Does                                              | Publishes                          |
| ---------------- | --------- | ------------------------------------------------- | ---------------------------------- |
| `TR_CATALOG`     | `catalog` | The TR catalog, unless `--loci_catalog` names one | `results/filter/tr-catalog.tsv`    |
| `TR_LOCI`        | `catalog` | Catalog loci ± `--filter_flank` bp → gate FASTA  | `results/filter/tr-loci.fa`        |
| `TR_FILTER`      | `filter`  | One sample: stream, gate, write                   | `results/filter/{reads,counts}/`   |
| `FILTER_SUMMARY` | `filter`  | Every sample's counts in one table                | `results/filter/filter-summary.tsv` |

The filter itself is three processes, which is as far as it divides. The one boundary that
must not exist is between decompressing and gating, because a process emitting
decompressed FASTQ parks ~25 GB per sample in `work/`.

### `TR_CATALOG`

The preprocessing stage's process (`docs/workflows/preprocess/`), run here with the same
`catalog_*` parameters. The catalog is not committed, because its parameters are still
being swept, so a clean clone has none. The stage builds it itself rather than depending on
an earlier run. `--loci_catalog <tsv>` skips this and uses a catalog that already exists.
The catalog is published beside the reference, so the reads can always be traced to the
loci they were gated against.

### `TR_LOCI`

Syncs the genomes of `--catalog_spec`, writes each locus of the catalog with
`--filter_flank` bases either side, and deletes the genomes. The same sync, reduce, delete
shape as `TR_CATALOG`, and the same genome naming, so each catalog row finds its FASTA.
Genomes are read through inTRuder's `read_fasta`, the reader the catalog was built with, so
the contig names agree by construction.

It is its own process, rather than a third output of `TR_CATALOG`, because the flank width
belongs to the filter: the reference will be rebuilt more often than the catalog, and that
should not rerun the finder. Records that come out byte-identical are written once. That
keeps the k-mer table small; it is not the §2 locus merge.

### `TR_FILTER`

One task per sample, which is the unit SLURM arrays (`conf/slurm.config`). The sample is
passed as values (name, key, ETag) with its spec and lock beside it, never as a `path` to
the object: Nextflow would localise an `s3://` path, which downloads exactly what this
avoids. The ETag is part of the task's inputs so that a change upstream invalidates the
`-resume` cache, and `filter` checks the stream against it.

**The stream resumes.** A single GET over a whole sample does not survive: when the gate
falls behind, `filter` stops reading, and S3 times the connection out or cuts it. The first
real run lost every attempt at a 712 MB sample that way, after as little as 63 MB.
`filter` now reopens the object from the last byte received with a ranged GET, backing off,
up to `--resumes` failures in a row (6). The count resets whenever bytes arrive, so a
stream can drop many times as long as it keeps moving. Each reopen carries the lock's
ETag, so a changed object fails the sample rather than being spliced into it.

Six cores: bbduk gets `--filter_threads` (2), lbzip2 the rest. lbzip2 was checked on real
HMP bytes: on the first 100 MB of SRS014107 its output is byte-identical to bzip2's, and it
was ~30× faster on a laptop. When the input is cut off, it reports `bad block header
magic`, so in a log that message means a truncated stream, not a lbzip2 problem. Any failure retries twice,
not just a scheduler kill, because a dropped S3 connection is the likeliest failure and it
is transient.

Each sample writes `<sample>.loci.fastq.gz` and `<sample>.counts.tsv`. Both are published
by copy, not by symlink, so `nextflow clean` cannot take away reads that took hours to
stream.

The reads are FASTQ, not BAM, on purpose. The locus reference is still moving (the
`max_extension` and merge questions in §2), and a BAM aligned to an old reference has to be
realigned; reads do not.

### `FILTER_SUMMARY`

The counts tables merged and sorted, with a `pass_fraction` column. The reads seen per
sample are the depth covariate §4 needs; the pass fraction decides the disk budget.

## Parts and parameters

`--pipeline` picks the part, like `--preprocess`:

| `--pipeline` | Runs                                                                 |
| ------------ | -------------------------------------------------------------------- |
| `all`        | Everything, the catalog feeding the reference feeding the filter     |
| `loci`       | The catalog and `TR_LOCI` only                                       |
| `filter`     | `TR_FILTER` and the summary, against the published `tr-loci.fa`      |
| `summary`    | `FILTER_SUMMARY` over the published counts                          |

| Parameter              | Default              | Meaning                                         |
| ---------------------- | -------------------- | ----------------------------------------------- |
| `loci_catalog`         | null                 | An existing catalog; null builds one            |
| `filter_flank`         | 50                   | Bases kept either side of each locus            |
| `filter_body_sites`    | `subgingival-plaque` | Comma-separated lockfiles under `manifests/hmp/` |
| `filter_sample_locks`  | null                 | A glob of lockfiles; overrides the body sites   |
| `filter_k`, `filter_hdist` | 25, 1            | bbduk's k-mer length and Hamming distance       |
| `filter_threads`       | 2                    | bbduk's threads; the decompressor gets the rest |
| `filter_decompressor`  | `lbzip2`             | `bzip2` is the single-core fallback             |
| `filter_max_reads`     | null                 | Hits written per sample before writing stops    |

The catalog is built from `--catalog_spec`, the mock community by default. That is enough
to check the machinery. The target-genus and contaminant catalogs are §2 work and arrive
through `--catalog_spec` with nothing here changing.

## Disk

Decompressed FASTQ never lands. The genomes `TR_LOCI` syncs are 470 MB at most, deleted
within the task. What stays is the published reads, and their size is set by the one
unknown, the pass fraction: ~22 GB over all 274 samples at 1%, ~110 GB at 5%. Publishing by
copy doubles that until `work/` is cleaned.

So the default runs plaque alone: 7 samples, 10 GB compressed. Read the pass fraction out of
the summary, project it, then decide whether stool and tongue run together or one at a time.
`--filter_body_sites` and `--filter_max_reads` are the two valves. `--filter_max_reads`
stops writing, not counting, so the summary still reports the true pass fraction.

## A limit worth knowing

The reads are 60–100 bp, with a median of 99–100. An allele length needs a read spanning
the tract plus an anchor on each side, so with ~20 bp anchors the longest measurable tract
is ~60 bp. The longest, most variable loci cannot be measured on this data, and truncating
the allele distribution compresses entropy on both sides of H1's comparison. The filter
keeps whatever hits regardless; this is a scope limit for the proposal, not a step here.

## Testing

```sh
pixi run test                       # filter: a synthetic .tar.bz2, members out of order
pixi run -e test-catalog test       # loci too: it needs inTRuder and pyfastx
pixi run test-workflow              # the modules stubbed, and the whole stage stubbed
```

`loci`'s tests skip in the default environment, which has neither inTRuder nor pyfastx.

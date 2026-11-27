# The pipeline stage

`--stage pipeline` is the analysis. Its first part, `catalog`, builds the panel of tandem
repeat loci the gate looks for. Its second, `filter`, streams the HMP1 shotgun reads from
S3 through a k-mer gate built from that panel and keeps only the reads that touch a locus,
plus per-sample read counts. Allele calling, the stutter model and everything after read
that output; none of them exists yet (`docs/todo.md` §3).

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

| Process          | Image     | Does                                                         | Publishes                                   |
| ---------------- | --------- | ------------------------------------------------------------ | ------------------------------------------- |
| `TR_CATALOG`     | `catalog` | One task per `--panel_specs` spec: its TR catalog and BED   | `results/catalog/tr-catalog.<spec>.{tsv,bed}` |
| `TR_LOCI`        | `catalog` | Merge the catalogs into loci; anchors; padded FASTA          | `results/catalog/{tr-loci.tsv,tr-loci.fa,tr-loci-stats.tsv}` |
| `TR_SCREEN`      | `filter`  | Screen the loci against a genome spec (run as two aliases)   | `results/catalog/<spec>.screen.tsv`         |
| `TR_PANEL`       | `filter`  | Drop human-screened loci, annotate with the mock screen      | `results/catalog/{tr-panel.tsv,tr-panel.fa}` |
| `TR_FILTER`      | `filter`  | One sample: stream, gate, write                              | `results/filter/{reads,counts}/`            |
| `FILTER_SUMMARY` | `filter`  | Every sample's counts in one table                           | `results/filter/filter-summary.tsv`         |

```
catalog : TR_CATALOG (one task per panel spec) ─┐
          TR_LOCI (merge + anchors + FASTA) ◄───┘
          TR_SCREEN ×2 (chm13 = exclude, hmp-mock = annotate) → TR_PANEL
filter  : TR_FILTER (one task per HMP sample, gate = tr-panel.fa) → FILTER_SUMMARY
```

The filter itself is three processes, which is as far as it divides. The one boundary that
must not exist is between decompressing and gating, because a process emitting
decompressed FASTQ parks ~25 GB per sample in `work/`.

### `TR_CATALOG`

The preprocessing stage's process (`docs/workflows/preprocess/`), run here once per spec
in `--panel_specs` with the same `catalog_*` parameters. Each task carries its own output
names, `tr-catalog.<spec>.tsv` and `.bed`, so the specs do not publish over each other.
Genomes are named by `--name-from auto`: a spec of the `hmp` dataset by directory (the
organism is in the directory and the file name is an accession), any other by file (one
genome per file, as slacken and CHM13 arrive).

### `TR_LOCI`

Syncs the genomes of every panel spec, lists them with `genomes`, runs `loci` over all the
catalogs at once, and deletes the genomes. The same sync, reduce, delete shape as
`TR_CATALOG`, and the same genome naming, so each catalog row finds its FASTA. Genomes are
read through inTRuder's `read_fasta`, the reader the catalogs were built with, so the
contig names agree by construction.

It is its own process because the merge needs every spec's calls together, and because
`--filter_flank`, `--loci_anchor` and `--loci_max_rep_length` belong to the gate: it is
rebuilt more often than the catalogs, and that should not rerun the finder. What `loci`
does to turn calls into loci:

- **Within a genome**, calls on one contig whose gap is smaller than `--loci_anchor` become
  one locus spanning their union, so each anchor is free of called repeat. The locus
  records `n_calls` and the canonical motifs of its calls; its motif is the canonical motif
  of its longest call.
- **Anchors** are the `--loci_anchor` bases immediately either side of the locus. A locus
  whose anchor runs off its contig is dropped.
- **Across genomes**, loci with the same canonical motif and anchor pair are one group and
  share a `locus_id` (`L000001`, numbered in sorted key order, so a rerun gives the same
  ids). The canonical motif folds rotation and reverse complement. The anchor pair is
  oriented to the lexicographically smaller of `(left, right)` and
  `(rc(right), rc(left))`, so a locus on the other strand lands in the same group.
- **Too long to span:** a group whose longest member is longer than
  `--loci_max_rep_length` is dropped. A 100 bp read minus two 20 bp anchors spans about 60
  bp (see "A limit worth knowing").
- Records that come out byte-identical within a group are written once, which keeps the
  gate's k-mer table small.

`tr-loci.tsv` has one row per member (`locus_id, spec, genome, contig, start, end, motif,
motif_length, rep_length, purity, n_calls, motifs, left_anchor, right_anchor`), so a group
has exactly one anchor pair. `tr-loci.fa` pads each member by `--filter_flank` bases, with
headers `>{locus_id}|{genome}|{contig}:{left}-{right}`. `tr-loci-stats.tsv` counts calls,
merged regions, edge drops, too-long groups, groups and members, in total and per spec.

### `TR_SCREEN`

Cuts one spec's genomes into `--screen_fragment` bp fragments overlapping by
`--screen_overlap` (`shred.sh`) and runs them through the same BBDuk match that gates the
reads, at `--filter_k` and `--filter_hdist`. So a locus a fragment hits is a locus a read
of that genome would pass the gate through. `bbduk.sh rename=t` appends each matched
reference, with its k-mer hit count, to the fragment's header, tab separated:

```
>chrT desc_100-199<TAB>L000001|g1|c1:0-144=26
>c_0-99<TAB>L000007|a|c:0-1=16<TAB>L000009|b|c:0-1=6
```

`screen` reads those headers from the pipe and writes `locus_id` and `fragments`, counting
each locus once per fragment. One bbduk run takes every genome's fragments, so its k-mer
table is built once, and the fragments themselves are never stored. bbduk credits a k-mer
that several references share to the first one loaded, so a fragment is only credited to
the loci that own the k-mers it hit.

It runs twice, by alias, over `--screen_human_spec` (CHM13) and `--screen_mock_spec` (the
mock community), under the `screen` label (4 CPUs, 8 GB, 12 h).

### `TR_PANEL`

Joins `tr-loci.tsv` with both screens. A group a human fragment hits is excluded: a read
that matches it cannot be told from host. The mock screen **annotates only**. Most target
genera and every kit genus are not in the mock community, so filtering on it would drop
most of the panel; a locus with no mock hit is the usual case, not a failed one.
`tr-panel.tsv` is the `tr-loci.tsv` columns of the kept loci plus `human_fragments` and
`mock_fragments`, and `tr-panel.fa` is their records from `tr-loci.fa`: the gate's
reference.

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

| `--pipeline` | Runs                                                                         |
| ------------ | ---------------------------------------------------------------------------- |
| `all`        | `catalog`, then `filter` against the panel it built                          |
| `catalog`    | The catalogs, `TR_LOCI`, both screens and `TR_PANEL`                         |
| `filter`     | `TR_FILTER` and the summary, against the published `results/catalog/tr-panel.fa` |

| Parameter              | Default              | Meaning                                         |
| ---------------------- | -------------------- | ----------------------------------------------- |
| `panel_specs`          | `reference/hmp-target,reference/kit` | Comma-separated specs under `manifests/`, one catalog each |
| `loci_anchor`          | 20                   | Anchor length; calls closer than this merge     |
| `loci_max_rep_length`  | 60                   | Groups with a longer member are dropped         |
| `filter_flank`         | 50                   | Bases kept either side of each locus in the reference |
| `screen_human_spec`    | `reference/chm13`    | The spec whose hits exclude a locus             |
| `screen_mock_spec`     | `reference/hmp-mock` | The spec whose hits annotate a locus            |
| `screen_fragment`, `screen_overlap` | 100, 50 | Fragment length and overlap                     |
| `filter_body_sites`    | `subgingival-plaque` | Comma-separated lockfiles under `manifests/hmp/` |
| `filter_sample_locks`  | null                 | A glob of lockfiles; overrides the body sites   |
| `filter_k`, `filter_hdist` | 25, 1            | bbduk's k-mer length and Hamming distance, for the gate and the screens |
| `filter_threads`       | 2                    | bbduk's threads; the decompressor gets the rest |
| `filter_decompressor`  | `lbzip2`             | `bzip2` is the single-core fallback             |
| `filter_max_reads`     | null                 | Hits written per sample before writing stops    |

The catalogs use the `catalog_*` finder settings, shared with `--stage preprocess`. The
target-genus catalog, the kit catalog and the mock screen all arrive through `panel_specs`
and the `screen_*_spec` parameters with nothing here changing.

## Disk

Decompressed FASTQ never lands. The genomes `TR_LOCI` and `TR_SCREEN` sync (CHM13 is 982
MB) are deleted within their task. What stays is the published reads, and their size is set by the one
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
`screen` and `panel` need neither.

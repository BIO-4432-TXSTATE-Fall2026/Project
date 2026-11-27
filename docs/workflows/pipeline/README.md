# The pipeline stage

`--stage pipeline` is the analysis. Its first part, `catalog`, builds the panel of tandem
repeat loci the gate looks for. Its second, `filter`, streams the HMP1 shotgun reads from
S3 through a k-mer gate built from that panel and keeps only the reads that touch a locus,
plus per-sample read counts. The third, `alleles`, measures each kept read's repeat between
the locus's two anchors and tabulates the lengths per sample. The fourth, `spike`, scores
that caller against simulated genomes of known lengths and mixes them into the real samples
as labelled contaminants. The stutter model and everything after read the allele tables.

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
| `TR_ALLELES`     | `filter`  | One sample: anchors in the gated reads, repeat lengths       | (per-sample tables feed `ALLELE_TABLE`)     |
| `ALLELE_TABLE`   | `filter`  | Every sample's alleles and read statistics in two tables     | `results/alleles/{alleles.tsv,allele-stats.tsv}` |
| `SIMULATE_READS` | `filter`  | Paired reads from each kit genome at each depth              | (feeds `TR_GATE`)                           |
| `TR_GATE`        | `filter`  | A local FASTQ through the gate (`filter --fastq`)            | (feeds `TR_ALLELES`)                        |
| `SPIKE_CHECK`    | `filter`  | Called alleles against the simulated genomes' true lengths   | `results/spike/spike-check.tsv`             |
| `SPIKE_MIX`      | `filter`  | Spike-in alleles added to each host, with labels             | `results/spike/{alleles-spiked.tsv,spike-labels.tsv}` |

```
catalog : TR_CATALOG (one task per panel spec) ─┐
          TR_LOCI (merge + anchors + FASTA) ◄───┘
          TR_SCREEN ×2 (chm13 = exclude, hmp-mock = annotate) → TR_PANEL
filter  : TR_FILTER (one task per HMP sample, gate = tr-panel.fa) → FILTER_SUMMARY
alleles : TR_ALLELES (one task per sample) → ALLELE_TABLE
spike   : SIMULATE_READS → TR_GATE → TR_ALLELES (alias SPIKE_ALLELES) → ALLELE_TABLE (alias SPIKE_TABLE)
          → SPIKE_CHECK, SPIKE_MIX (the hosts' alleles.tsv comes from the alleles part)
```

`--pipeline` takes one part or a comma-separated list. A part that runs without the one
before it reads that part's published output under `results/`: `filter` the panel,
`alleles` the panel and `results/filter/reads/`, `spike` the panel and
`results/alleles/alleles.tsv`.

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
mock community), under the `screen` label (4 CPUs, 32 GB, 12 h).

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

The gate runs with `rename=t`, so each kept read's header lists the panel loci it matched,
in the form `TR_SCREEN` reads (a FASTQ header: `@name<TAB>L000007|g|c:0-90=16<TAB>...`).
`filter` checks every tab-separated field after the name is `reference=count`, as part of
its FASTQ framing check, so a stray line from the gate still fails the sample. bbduk
credits a k-mer shared by several loci to the first one loaded, so a read lists the loci
that own the k-mers it hit, which `alleles` then confirms against the anchors.

`filter --fastq PATH --sample NAME` skips the stream, the decompressor and the tar and
feeds a local FASTQ (plain or `.gz`) through the same gate and writer, with the same two
outputs. That is how `TR_GATE` gates the simulated reads.

Each sample writes `<sample>.loci.fastq.gz` and `<sample>.counts.tsv`. Both are published
by copy, not by symlink, so `nextflow clean` cannot take away reads that took hours to
stream.

The reads are FASTQ, not BAM, on purpose. The locus reference is still moving (the
`max_extension` and merge questions in §2), and a BAM aligned to an old reference has to be
realigned; reads do not.

### `FILTER_SUMMARY`

The counts tables merged and sorted, with a `pass_fraction` column. The reads seen per
sample are the depth covariate §4 needs; the pass fraction decides the disk budget.

### `TR_ALLELES`

One task per sample over `<sample>.loci.fastq.gz` and `tr-panel.tsv`. For each read it takes
the candidate loci from the header, then searches the read and its reverse complement for
the locus's left anchor and the right anchor downstream of it, each within
`--alleles_mismatches` substitutions (Hamming, no gaps). Both anchors make a **spanning**
read, whose allele is the distance between them; one makes a **flanking** read, counted
with no length. A read that shows several loci goes to the one with the fewest mismatches,
spanning before flanking, and a tie is **ambiguous** and counted nowhere else. Mates are
one fragment: reads are grouped by name stem per locus, so a fragment counts once, and a
fragment whose mates span different lengths is counted as discordant. No stutter correction:
the tables hold raw length counts for the entropy stage.

Each sample writes `<sample>.alleles.tsv` (`sample, locus_id, allele_bp, reads`) and
`<sample>.allele-stats.tsv` (`sample, reads_in, spanning, flanking, ambiguous, unassigned,
pairs_collapsed, pairs_discordant`). The first five count reads; `pairs_collapsed` counts
fragments with more than one read and `pairs_discordant` those whose mates disagree.

### `ALLELE_TABLE`

The per-sample tables concatenated under one header and sorted by sample, locus and allele
length, in the shell style of `FILTER_SUMMARY`. Run again by alias for the spike-ins.

### `SIMULATE_READS`

One task over `--spike_spec` (the kit): sync, then for each genome and each depth in
`--spike_reads`, `randomreads.sh` draws that many paired 100 bp reads with sequencing
errors into `<genome>@<reads>.fastq.gz`, and the genomes are deleted. The genome name is
`genomes --name-from auto`'s, the `genome` column of `tr-panel.tsv`. It is one task, not
one per genome: sync fetches a spec whole and the kit is 195 MB, so a task per genome
would fetch all of it thirty times. The files then cross as a flat channel, one gate and
one caller task each. A depth is a contamination level: the default is a thousand reads to
a hundred thousand, tumor-like contaminant depth.

### `TR_GATE`

`filter --fastq` on one simulated file against `tr-panel.fa`, with the same `filter_k` and
`filter_hdist` as the HMP reads. Its outputs are named as `TR_FILTER`'s, so `TR_ALLELES`
takes either.

### `SPIKE_CHECK`

Every kit genome is a member of some panel loci, so its allele lengths are known: the
`rep_length` of its `tr-panel.tsv` rows. For each sample (`<genome>@<reads>`) the locus's
call is its most-supported allele length, and `spike-check.tsv` has one row per sample:
`genome, reads, loci_expected, loci_called, exact_fraction, within_one_unit_fraction,
loci_unexpected`. The fractions are over the called loci, so depth shows in `loci_called`
and not in the accuracy; within one unit means within one motif length. This is the
ground-truth check of the gate and the caller together: simulated reads have no biology in
them, so a call that is not the true length is a bug in one of them.

### `SPIKE_MIX`

For each host (`--spike_hosts`, default every sample in `results/alleles/alleles.tsv`),
simulated genome and depth, the host's allele counts and the genome's are summed into the
sample `<host>+<genome>@<reads>`. `alleles-spiked.tsv` has the shape of `alleles.tsv`.
`spike-labels.tsv` (`sample, host, batch, reads, locus_id, contaminant`) has one row per
locus with reads in the mix: `batch` is the genome, `reads` the simulated pairs added, and
`contaminant` is `true` when the locus is a member of that genome in the panel. These are
the labels the contamination model trains on. Mixing after the gate is the same as mixing
the reads before it, because the gate and the caller judge each read on its own.

## Parts and parameters

`--pipeline` picks the parts, like `--preprocess`, one or a comma-separated list:

| `--pipeline` | Runs                                                                         |
| ------------ | ---------------------------------------------------------------------------- |
| `all`        | `catalog`, `filter`, `alleles` and `spike`, each against the one before      |
| `catalog`    | The catalogs, `TR_LOCI`, both screens and `TR_PANEL`                         |
| `filter`     | `TR_FILTER` and the summary, against the published `results/catalog/tr-panel.fa` |
| `alleles`    | `TR_ALLELES` and `ALLELE_TABLE`, over the published `results/filter/reads/`  |
| `spike`      | `SIMULATE_READS` to `SPIKE_MIX`, over the published panel and `results/alleles/alleles.tsv` |

Parts run together share their channels: `--pipeline filter,alleles` feeds the filter's
reads to the caller directly.

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
| `alleles_anchor`       | null                 | Anchor bases matched next to the repeat; null is `loci_anchor` |
| `alleles_mismatches`   | 1                    | Hamming distance allowed per anchor             |
| `spike_spec`           | `reference/kit`      | The genomes the reads are simulated from        |
| `spike_reads`          | `1000 10000 100000`  | Read pairs simulated per genome, space-separated |
| `spike_seed`           | 1                    | `randomreads` seed                              |
| `spike_hosts`          | null                 | Comma-separated samples to mix into; null is every sample in `alleles.tsv` |

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
pixi run test                       # filter, alleles, spike-check, spike-mix, on synthetic reads
pixi run -e test-catalog test       # loci too: it needs inTRuder and pyfastx
pixi run test-workflow              # the modules stubbed, and the whole stage stubbed
```

`loci`'s tests skip in the default environment, which has neither inTRuder nor pyfastx.
`screen` and `panel` need neither.

# Downstream comparisons

Data that cannot drive the pipeline in `docs/pipeline.md`, but is worth comparing
results against once allele calling works. Data choices are in `docs/HMP_proposed.md`.

## HMP aligned reads (`HHS/HMSCP/`)

Shotgun Community Profiling: every HMP1 WGS sample aligned against a bacterial
reference database in 2011, with an abundance table and a read-count metric per sample.
754 samples, 2,267 files, 1.8 TB.

| File                            | Per sample | Contents                                            |
| ------------------------------- | ---------- | --------------------------------------------------- |
| `SRS*_vs_RefDb.sorted.bam`      | 0.15–8 GB  | CLC alignment against `Reference_Genomes_DB_10272010.fasta` |
| `SRS*_abundance_table.tsv.bz2`  | ~6 KB      | ~94 organisms with depth, breadth, reference length |
| `SRS*_metric.txt.bz2`           | ~160 B     | Reads and pairs passing the filter, reads aligned   |
| `ReadMappingSOP.v1.txt.bz2`     | —          | The alignment protocol, for the whole prefix        |

These are the same reads the project already uses, not a new cohort. The CLC command
line in the BAM header names `SRS*.denovo_duplicates_marked.trimmed.{1,2,singleton}`,
which are the `HHS/HMASM/WGS/` tarball contents. All 607 `HMASM/WGS/` samples in
`manifests/hmp.lock.json` have an HMSCP BAM, including every sample recorded so far:
`subgingival_plaque` (7, 11 GB), `tongue_dorsum` (128, 518 GB), `stool` (139, 645 GB).

### Why it cannot replace read anchoring

Checked against `ReadMappingSOP.v1.txt.bz2` and the first 20,000 records of
`SRS011090_vs_RefDb.sorted.bam` on 2026-09-18.

- **Low-complexity masking runs before alignment.** The SOP converts FASTQ to FASTA,
  runs `dust` (which rewrites low-complexity bases as `N`), then discards reads with
  fewer than 60 non-`N` bases. Tandem repeats are low complexity, so the step targets
  the sequence the project measures, and the reads spanning the longest repeats are the
  ones dropped. Genome-wide the effect looks small (1.5% of reads carry an `N`, 0.07%
  of bases), but it concentrates at TR loci. The BAM stores the masked sequence, so the
  original bases cannot be recovered from this prefix.
- **No base qualities.** The aligner is given FASTA, so `QUAL` is absent in all 20,000
  records. The stutter model in step 3 of the pipeline needs per-base qualities.
- **Pervasive soft-clipping.** 13,746 `S` operations against 22,957 `M` in 20,000
  records. CLC ran with `-l 0.75 -s 0.8` (80% identity over 75% of the query), so a
  read carrying a repeat-length indel is clipped back to a reference-length alignment
  or fails the threshold. That biases allele calls toward the reference allele.
- **A different reference, and no random access.** The database is a 2010 snapshot of
  188,039 sequences across 1,610 genera, not the `reference_genomes/` set synced in
  `manifests/hmp-reference-genomes-target.json`, so its coordinates do not match the
  planned inTRuder catalog. The header is `SO:unsorted` despite the filename and the
  bucket holds no `.bai`, so reaching a locus means streaming all 1.8 TB and re-sorting.

Streaming `HMASM/WGS/` reads through a locus filter, as step 3 already specifies, costs
comparable bandwidth and keeps qualities, unmasked bases, and the project's own
alignment parameters.

### What it is worth comparing later

- **Cost of standard read mapping.** Run the locus filter and HMSCP over the same
  samples and count TR-spanning reads retained by each. A loss figure for conventional
  metagenomic mapping supports the motivation for H1 rather than testing it.
- **Reference-allele collapse.** Call allele lengths from the HMSCP BAM and from the
  project's own alignment on the same samples. The expected collapse toward the RefDb
  allele is a concrete illustration of the bias the pipeline avoids. Catalog loci must
  be lifted onto the 2010 database first.
- **Taxon presence.** The abundance tables give per-organism depth and breadth per
  sample, an independent check on which target-genus loci sit at callable depth and
  which taxa are shared across samples for the step 4 positive control. The metric
  files give per-sample read totals, though counted after low-complexity filtering.
- The non-BAM files total 4.3 MB for all 754 samples, so the tables and metrics can be
  synced whenever they are wanted; the BAMs should not be.

```sh
aws s3 cp --no-sign-request \
  s3://human-microbiome-project/HHS/HMSCP/ReadMappingSOP.v1.txt.bz2 -
```

## Elsewhere

TCGA COAD/STAD and the Gihawi et al. (2023) labels are the project's other deferred
comparison; see `docs/tcga_controlled_alternative.md`.

# HMP data proposed for the tandem repeat entropy project

Which parts of `s3://human-microbiome-project` fit the proposal in
`docs/Bioinformatics_7361C-2.pdf`, where HMP/iHMP is the positive control: high-depth
oral and gut data establishing baseline TR entropy for taxa shared with tumor datasets.

Sizes and counts come from the bucket listing in `manifests/hmp.lock.json`
(`sync --no-download`, 2026-09-15). Genus counts come from the `ORGANISM` line of one
GenBank header per `reference_genomes/` directory.

## Bucket layout

| Prefix               | Contents                                                    | Files  | Size    |
| -------------------- | ----------------------------------------------------------- | ------ | ------- |
| `HHS/`               | Healthy Human Subjects: the main HMP1 cohort                | 35,053 | 5.6 TB  |
| `DEMO/`              | Demonstration Projects: disease-cohort 16S studies          | 6,582  | 104 GB  |
| `reference_genomes/` | Isolate genomes from human body sites                       | 43,740 | 129 GB  |

The data are 2012–2014 snapshots of HMP phase 1. HMP2/iHMP is not in this bucket.

## Constraint

TR allele lengths must be called from shotgun (WGS) reads. 16S amplicons and
processed abundance tables do not contain the TR loci, which rules out most products.

## Use

### 1. `HHS/HMASM/WGS/`: oral and gut shotgun reads

Human contaminant-screened Illumina FASTQ, one `SRS*.tar.bz2` per sample, grouped by
body site. 690 of 752 sequenced samples passed HMP QC and are included.

| Body site              | Samples | Median per sample | Total  |
| ---------------------- | ------- | ----------------- | ------ |
| `subgingival_plaque`   | 7       | 1.7 GB            | 10 GB  |
| `supragingival_plaque` | 118     | 3.9 GB            | 470 GB |
| `tongue_dorsum`        | 128     | 6.1 GB            | 760 GB |
| `stool`                | 139     | 7.3 GB            | 998 GB |

- Pilot on `subgingival_plaque`: small, and enriched for Fusobacterium and Porphyromonas.
- Then scale to `tongue_dorsum` and `stool` for depth and gut coverage.
- Skip `buccal_mucosa`: most samples are shallow (median 0.7 GB).
- HMP1 WGS reads are short (~100 bp Illumina; not yet verified against these files),
  which caps the repeat lengths a single read can span.

### 2. `reference_genomes/`: TR locus catalog

1,130 isolate genomes, with good coverage of the proposal's target taxa:

| Genus         | Genomes | Notable species                               |
| ------------- | ------- | --------------------------------------------- |
| Streptococcus | 111     | S. sanguinis (21), S. oralis (8), S. mitis (8) |
| Prevotella    | 35      | P. melaninogenica, P. denticola, P. buccae    |
| Fusobacterium | 27      | F. nucleatum (4), F. periodonticum (2)        |
| Veillonella   | 11      | V. parvula, V. atypica                        |
| Campylobacter | 7       | C. showae, C. rectus, C. gracilis             |
| Porphyromonas | 6       | P. gingivalis (2), P. endodontalis            |

- Only `*.nuc.fsa` or `*.gbk` files are needed. Most of the 129 GB is BLAST index
  files (`.nin`, `.nhr`, `.nsq`, …).
- Directories are numeric IDs, so a spec cannot select by genus. Selecting target
  genera needs an ID-to-organism mapping first.

### 3. `HHS/HMMC/`: mock community genomes

Reference genomes (0.2 GB) for the HMP mock community strains, including three
Streptococcus species. Useful as known-identity strains for checking allele calls.
Only genomes are present; no mock community reads were found in the bucket.

## Maybe

- `HHS/HMSCP/` (1.8 TB): per-sample reads already aligned to a reference database
  (`*_vs_RefDb.sorted.bam`). Could replace the read-anchoring step, but aligners tend
  to soft-clip or drop reads with repeat-length indels. That would bias against the
  variation being measured, so check before relying on it.

## Skip

- `DEMO/`: 16S only. Its `water_blank` controls look like contamination labels but
  contain no TR loci.
- 16S products: `HM16STR`, `HMR16S`, `HMQCP`, `HMMCP`.
- Assemblies and gene catalogs: `HMHASM`, `HMGI`, `HMGC`.

## Gaps

- **H2 batch labels.** No sequencing center or run date for WGS samples is in the
  bucket; the run metadata tarballs cover 16S only. Map each `SRS` accession to its
  SRA runs via NCBI SRA, which needs a new provider.
- **iHMP.** Cited in the proposal's Table 1 but not in this bucket; it is hosted on
  the HMP DACC portal and needs its own provider.
- **Contaminant ground truth.** HMP1 healthy-subject WGS carries no known-contaminant
  labels, so H1 validation still depends on TCGA and the Gihawi et al. (2023) labels.
